
import fs from 'fs';
import * as rimraf from 'rimraf';
import { v1 as uuidv1 } from 'uuid';
import { pdalCLI, executeCommand, micromambaCLI } from '../scripts.js';
import logger from '../logger.js';
import {
    HIDE_GUI,
    SHOW_GUI,
    POINT_CLOUD_COUNT,
    POINT_CLOUD_PROJECTION,
    POINT_CLOUD_PROCESS_LAS,
    POINT_CLOUD_TILESET,
    POINT_CLOUD_TO_MESH,
    DATA,
    POINT_CLOUD_PREVIEW,
    POINT_CLOUD_SHOW_PREVIEW
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

const pdalStats = ({ file }) => {
    let out = [];
    logger({ message: 'Read point cloud statistic...' });
    return executeCommand(
        pdalCLI([
            'info',
            `static/data/${file.name}${file.extension}`,
            '--stats'
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
            logger({ message: 'Horizontal WKT:<br><br>' + JSON.stringify(response?.metadata?.srs?.horizontal || {}, null, 4), type: 'success' });
            logger({ message: 'Vertical WKT:<br><br>' + JSON.stringify(response?.metadata?.srs?.vertical || {}, null, 4), type: 'success' });
            return response;
        });
};

const previewLas = ({ file }) => {
    const previePath = 'data/_preview/';
    const previewDirectory = `static/${previePath}`;
    const outputPreview = `${previewDirectory}${file.name}.xyz`;
    const outputPath = `${previePath}${file.name}.xyz`;
    if (fs.existsSync(outputPreview)) {
        return Promise.resolve(outputPath);
    }
    return Promise.all([pdalStats({ file }), pdalMetadata({ file })])
        .then(([{ stats }, { metadata }]) => {
            const statistic = stats.statistic;
            const x = statistic.find(val => val.name === 'X');
            const y = statistic.find(val => val.name === 'Y');
            const z = statistic.find(val => val.name === 'Z');
            const red = statistic.find(val => val.name === 'Red');
            const size = [
                (x.maximum - x.minimum),
                (y.maximum - y.minimum),
                (z.maximum - z.minimum),
            ];
            const center = [
                x.minimum + (size[0] / 2),
                y.minimum + (size[1] / 2),
                z.minimum + (size[2] / 2),
            ];
            
            const tmpDirectory = './tmp/';
            const pipelineFilename = `${tmpDirectory}pipeline-${uuidv1()}.json`;
            const pipeline = [
                {
                    filename: `static/data/${file.name}${file.extension}`,
                    type: 'readers.las'
                },
                ...(metadata?.count > 500000 ? [{
                    type: 'filters.decimation',
                    step: Math.ceil(metadata?.count / 500000)
                }] : []),
                {
                    type: 'filters.transformation',
                    matrix: `1  0  0  ${-center[0]}  0  1  0  ${-center[1]}  0  0  1  ${-center[2]}  0  0  0  1`
                },
                {
                    type: 'writers.text',
                    format: 'csv',
                    order: red ? 'X,Y,Z,Red:0,Green:0,Blue:0' : 'X,Y,Z',
                    keep_unspecified: false,
                    filename: outputPreview
                }
            ];
            if (!fs.existsSync(tmpDirectory)) {
                fs.mkdirSync(tmpDirectory);
            }
            if (!fs.existsSync(previewDirectory)) {
                fs.mkdirSync(previewDirectory);
            }
            fs.writeFileSync(pipelineFilename, JSON.stringify(pipeline), 'utf-8');
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
                return outputPath;
            });
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

const lasToMesh = ({ file, config }) => {

    const tmpDirectory = './tmp/';
    const pipelineFilename = `${tmpDirectory}pipeline-${uuidv1()}.json`;
    const outputXYZ = `static/data/${file.name}.xyz`;
    const pipeline = [
        {
            filename: `static/data/${file.name}${file.extension}`,
            type: 'readers.las'
        },
        {
            type: 'writers.text',
            format: 'csv',
            order: 'X,Y,Z,Red,Green,Blue',
            keep_unspecified: false,
            filename: outputXYZ
        }
    ];

    if (!fs.existsSync(tmpDirectory)) {
        fs.mkdirSync(tmpDirectory);
    }
    if (fs.existsSync(outputXYZ)) {
        rimraf.sync(outputXYZ);
    }
    fs.writeFileSync(pipelineFilename, JSON.stringify(pipeline), 'utf-8');

    logger({ message: 'Init conversion from las to xyz...' });
    return executeCommand(
        pdalCLI([
            'pipeline',
            pipelineFilename
        ]),
        {
            onStdOut: (data) => {
                console.log(data.toString());
            },
            onStdErr: (data) => {
                console.log(data.toString());
            }
        }
    ).then(() => {
        rimraf.sync(pipelineFilename);
        const outputPly = `static/data/${file.name}_mesh.ply`;
        if (fs.existsSync(outputPly)) {
            rimraf.sync(outputPly);
        }
        logger({ message: 'Init conversion from xyz to mesh...' });
        return executeCommand(
            micromambaCLI('tools_env', [
                'python',
                'src/scripts/xyz_to_mesh.py',
                outputXYZ,
                outputPly,
                config.pointCloudPoissonDepth || 10,
                config.pointCloudPoissonScale || 1.1,
                config.removeVerticesThreshold || 0.1
            ]),
            {
                onStdOut: (data) => {
                    console.log(data.toString());
                },
                onStdErr: (data) => {
                    console.log(data.toString());
                }
            }
        ).then(() => {
            rimraf.sync(outputXYZ);
            logger({ message: 'Process completed!', type: 'success' });
            return true;
        });
    });
};

const initPointCloudWorkflow = ({
    socket,
    readDataFiles
}) => {
    socket.on(POINT_CLOUD_COUNT, ({ file }) => {
        socket.emit(HIDE_GUI);
        countLasPoint({ file })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on(POINT_CLOUD_PROJECTION, ({ file }) => {
        socket.emit(HIDE_GUI);
        getLasCRS({ file })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on(POINT_CLOUD_PROCESS_LAS, (config) => {
        socket.emit(HIDE_GUI);
        processLas(config)
            .then(() => {
                const updatedFiles = readDataFiles();
                socket.emit(DATA, { files: updatedFiles });
            })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on(POINT_CLOUD_TILESET, (config) => {
        socket.emit(HIDE_GUI);
        fromLasToTileset(config)
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on(POINT_CLOUD_TO_MESH, (config) => {
        socket.emit(HIDE_GUI);
        lasToMesh(config)
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on(POINT_CLOUD_PREVIEW, (config) => {
        socket.emit(HIDE_GUI);
        previewLas(config)
            .then((path) => {
                socket.emit(POINT_CLOUD_SHOW_PREVIEW, { path })
                return true;
            })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
}

export default initPointCloudWorkflow;
