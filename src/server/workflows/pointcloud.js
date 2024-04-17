
import fs from 'fs';
import * as rimraf from 'rimraf';
import { v1 as uuidv1 } from 'uuid';
import { pdalCLI, executeCommand, micromambaCLI } from '../scripts.js';
import logger from '../logger.js';
import {
    HIDE_GUI,
    SHOW_GUI
} from '../../constants.js';

const pdalMetadata = ({ file }) => {
    let out = [];
    logger({ message: 'Read point cloud metadata...' });
    return executeCommand(
        pdalCLI([
            'info',
            `static/data/${file.name}${file.extension}`,
            '--metadata'
        ]),
        {
            onStdOut: (data) => {
                out.push(data);
            },
            onStdErr: (data) => {
                logger({ message: data.toString(), type: 'error' });
            }
        }
    ).then(() => {
        let response;
        try {
            response = JSON.parse(out.reduce((acc, data) => acc + data.toString(), ''))
        } catch (e) {
            logger({ message: e?.message || e, type: 'error' });
            throw e;
        }
        return response;
    });
};

const countLasPoint = ({ file }) => {
    return pdalMetadata({ file })
        .then((response) => {
            logger({ message: `Point count: ${response?.metadata?.count}`, type: 'success' });
            return response;
        });
};

const getLasCRS = ({ file }) => {
    return pdalMetadata({ file })
        .then((response) => {
            logger({ message: 'Horizontal SRS:<br><br>' + JSON.stringify(response?.metadata?.srs?.horizontal || {}, null, 4), type: 'success' });
            logger({ message: 'Vertical SRS:<br><br>' + JSON.stringify(response?.metadata?.srs?.vertical || {}, null, 4), type: 'success' });
            return response;
        });
};

const processLas = ({ file, config }) => {
    const {
        rasterFile,
        outputName,
        crsIn,
        groundClassification,
        sampleRadius
    } = config || {};
    const outputFileName = `${outputName || file.name}${file.extension}`;
    const outputFile = `./static/data/${outputFileName}`;
    const crsOut = config?.crsOut || crsIn;
    // example of vertical datum shift
    // const vDatumFile = `./vdatum/egm08_25.gtx`;
    // {
    //     type: 'filters.reprojection',
    //     in_srs: `+init=EPSG:${crsIn} +geoidgrids=${vDatumFile}`,
    //     out_srs: `EPSG:${crsOut}+${geodeticCrs}`,
    //     error_on_failure: true
    // }
    if (fs.existsSync(outputFile)) {
        const error = `Please change output name. A file called "${outputFileName}" already exists in the static/data folder`;
        return Promise.reject(error);
    }

    const pipeline = [
        {
            filename: `static/data/${file.name}${file.extension}`,
            type: 'readers.las'
        },
        ...(rasterFile ? [
            {
                type: 'filters.colorization',
                raster: `static/data/${rasterFile}`
            }
        ]
        : []),
        ...(sampleRadius ? [
            {
                type: 'filters.sample',
                radius: sampleRadius
            }
        ]
        : []),
        ...(crsIn !== crsOut
            ? [
                {
                    type: 'filters.reprojection',
                    in_srs: crsIn,
                    out_srs: crsOut,
                    error_on_failure: true
                }
            ]
            : []),
        ...(groundClassification ? [
            {
                type: 'filters.assign',
                assignment: 'Classification[:]=0'
            },
            {
                type: 'filters.elm'
            },
            {
                type: 'filters.outlier'
            },
            {
                type: 'filters.smrf',
                ignore: 'Classification[7:7]'
            }
        ]
        : []),
        {
            type: 'writers.las',
            ...(crsOut && { a_srs: crsOut }),
            filename: outputFile,
            compression: true
        }
    ];

    console.log(pipeline);

    const tmpDirectory = './tmp/';
    const pipelineFilename = `${tmpDirectory}pipeline-${uuidv1()}.json`;
    if (!fs.existsSync(tmpDirectory)) {
        fs.mkdirSync(tmpDirectory);
    }

    fs.writeFileSync(pipelineFilename, JSON.stringify(pipeline), 'utf-8');
    logger({ message: 'Init point cloud processing...' });
    return executeCommand(
        pdalCLI([
            'pipeline',
            pipelineFilename
        ]),
        {
            onStdOut: (data) => {
                logger({ message: data.toString() });
            },
            onStdErr: (data) => {
                logger({ message: data.toString(), type: 'error' });
            }
        }
    ).then(() => {
        rimraf.sync(pipelineFilename);
        logger({ message: 'Process completed!', type: 'success' });
        return true;
    });
};

const scaleGeometricError = (leaf, scale = 1) => {
    return {
        ...leaf,
        geometricError: leaf.geometricError * scale,
        ...(leaf.children && { children: leaf.children.map((childLeaf) => scaleGeometricError(childLeaf, scale)) })
    }
}

const py3dtilesToTileset = ({ file, config }) => {
    logger({ message: 'Init tiling...' });
    let errors = [];
    return executeCommand(
        micromambaCLI('tools_env', [
            'py3dtiles',
            'convert',
            `static/data/${file.name}${file.extension}`,
            '--overwrite',
            '--classification',
            '--color_scale', 255, // see https://gitlab.com/py3dtiles/py3dtiles/-/issues/201
            '--out', `static/tilesets/${file.name}/`,
            '--srs_in', config.crsIn,
            '--srs_out', '4978'
        ]),
        {
            onStdOut: (data) => {
                logger({ message: data.toString() });
            },
            onStdErr: (data) => {
                const error = data.toString();
                logger({ message: error, type: 'error' });
                if (error.includes('CRSError')) {
                    logger({ message: error, type: 'error' });
                    errors.push(error);
                }
            }
        }
    ).then(() => {
        if (!errors.length) {

            const { geometricError, ...tileset } = JSON.parse(fs.readFileSync(`static/tilesets/${file.name}/tileset.json`, 'utf-8'));

            fs.writeFileSync(`static/tilesets/${file.name}/tileset.json`, JSON.stringify({
                ...tileset,
                properties: {
                    Classification: { minimum: 0, maximum: 255 }
                },
                root: config.geometricErrorScale ? scaleGeometricError(tileset?.root, config.geometricErrorScale) : tileset?.root
            }));

            logger({
                message: '', 
                type: 'success',
                options: { action: { link: `/preview/?${file.name}`, type: 'popup', label: 'Tileset preview' } }
            });
        }
        return true;
    });
};

const fromLasToTileset = (options) => {
    return py3dtilesToTileset(options);
};

const initPointCloudWorkflow = ({
    socket,
    readDataFiles
}) => {
    socket.on('point-cloud:count', ({ file }) => {
        socket.emit(HIDE_GUI);
        countLasPoint({ file })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on('point-cloud:projection', ({ file }) => {
        socket.emit(HIDE_GUI);
        getLasCRS({ file })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on('point-cloud:process-las', (config) => {
        socket.emit(HIDE_GUI);
        processLas(config)
            .then(() => {
                const updatedFiles = readDataFiles();
                socket.emit('data', { files: updatedFiles });
            })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on('point-cloud:tileset', (config) => {
        socket.emit(HIDE_GUI);
        fromLasToTileset(config)
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
}
export default initPointCloudWorkflow;
