
import child_process from 'child_process';
import fs from 'fs';
import * as rimraf from 'rimraf';
import { v1 as uuidv1 } from 'uuid';
import dbConfig from './postgis.js';
import { getInfo } from '../info.js';
import path from 'path';
import { collectionToPointInstances } from '../instances.js';
import { parseStringExpression, parseNumericExpression } from '../expression.js';

const executeCommand = (command, options) => {
    return new Promise((resolve, reject) => {
        const cmd = command.join(' ');
        console.log(cmd);
        const cp = child_process.exec(cmd);
        cp.stdout.on('data', (data) => {
            if (options.onStdOut) {
                options.onStdOut(data);
            }
        });
        cp.stderr.on('data', (data) => {
            if (options.onStdErr) {
                options.onStdErr(data);
            }
        });
        cp.on('error', (error) => {
            reject(error.message);
        });
        cp.on('exit', (data) => {
            resolve(data);
        });
    });
};

const micromambaCLI = (env, params = []) => {
    return [
        'micromamba',
        'run',
        '-n', env,
        ...params
    ];
};

const pdalCLI = (params = []) => {
    return micromambaCLI('pdal_env', ['pdal', ...params ]);
};

export const pdalMetadata = ({ file }, log = console.log) => {
    let out = [];
    log('Read point cloud metadata...');
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
                log(data.toString(), 'error');
            }
        }
    ).then(() => {
        let response;
        try {
            response = JSON.parse(out.reduce((acc, data) => acc + data.toString(), ''))
        } catch (e) {
            log(e?.message || e, 'error');
            throw e;
        }
        return response;
    });
};

export const countLasPoint = ({ file }, log = console.log) => {
    return pdalMetadata({ file }, log)
        .then((response) => {
            log(`Point count: ${response?.metadata?.count}`, 'success');
            return response;
        });
};

export const getLasCRS = ({ file }, log = console.log) => {
    return pdalMetadata({ file }, log)
        .then((response) => {
            log('Horizontal SRS:<br><br>' + JSON.stringify(response?.metadata?.srs?.horizontal || {}, null, 4), 'success');
            log('Vertical SRS:<br><br>' + JSON.stringify(response?.metadata?.srs?.vertical || {}, null, 4), 'success');
            return response;
        });
};

export const processLas = ({ file, config }, log = console.log) => {
    const {
        rasterFile, // TODO: implement raster file in the UI
        outputName,
        crsIn,
        geodeticCrs,
        groundClassification,
        sampleRadius
    } = config || {};
    const outputFileName = `${outputName || file.name}${file.extension}`;
    const outputFile = `./static/data/${outputFileName}`;
    const crsOut = config?.crsOut || crsIn;
    const vDatumFile = `./vdatum/egm08_25.gtx`;
    
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
                raster: `${rasterFile}`
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
        ...(geodeticCrs && crsIn
            ? [
                {
                    type: 'filters.reprojection',
                    in_srs: `+init=EPSG:${crsIn} +geoidgrids=${vDatumFile}`,
                    out_srs: `EPSG:${crsOut}+${geodeticCrs}`,
                    error_on_failure: true
                }
            ]
            : crsIn !== crsOut
                ? [
                    {
                        type: 'filters.reprojection',
                        in_srs: `EPSG:${crsIn}`,
                        out_srs: `EPSG:${crsOut}`,
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
            ...(crsOut && { a_srs: `EPSG:${crsOut}` }),
            filename: outputFile,
            compression: true
        }
    ];

    const tmpDirectory = './tmp/';
    const pipelineFilename = `${tmpDirectory}/pipeline-${uuidv1()}.json`;
    if (!fs.existsSync(tmpDirectory)) {
        fs.mkdirSync(tmpDirectory);
    }

    fs.writeFileSync(pipelineFilename, JSON.stringify(pipeline), 'utf-8');
    log('Init point cloud processing...');
    return executeCommand(
        pdalCLI([
            'pipeline',
            pipelineFilename
        ]),
        {
            onStdOut: (data) => {
                log(data.toString());
            },
            onStdErr: (data) => {
                log(data.toString(), 'error');
            }
        }
    ).then(() => {
        rimraf.sync(pipelineFilename);
        log('Process completed!', 'success');
        return true;
    });
};

export const fromLasToTileset = ({ file, config }, log = console.log) => {
    log('Init tiling...');
    let errors = [];
    return executeCommand(
        micromambaCLI('tools_env', [
            'py3dtiles',
            'convert',
            `static/data/${file.name}${file.extension}`,
            '--overwrite',
            '--classification',
            '--out', `static/tilesets/${file.name}/`,
            '--srs_in', config.crsIn,
            '--srs_out', '4978'
        ]),
        {
            onStdOut: (data) => {
                log(data.toString());
            },
            onStdErr: (data) => {
                const error = data.toString();
                if (error.includes('CRSError')) {
                    log(error, 'error');
                    errors.push(error);
                }
            }
        }
    ).then(() => {
        if (!errors.length) {
            log('', 'success', { action: { link: `/preview/?${file.name}`, type: 'popup', label: 'Tileset preview' } });
        }
        return true;
    });
};

export const fromPolyhedronToTileset = ({ collection, config }, log = console.log) => {
    const {
        tableName,
        output,
        geometryName,
        attributes,
        properties,
    } = getInfo(collection, config);
    log('Init tiling...');
    rimraf.sync(output);
    return executeCommand(
        [
            'pg2b3dm',
            '-h', dbConfig.host,
            '-p', dbConfig.port,
            '-d', dbConfig.database,
            '-U', dbConfig.user,
            '-o', output,
            '-c', geometryName,
            '-t', tableName,
            '-a', (attributes || []).map(entry => entry[0]).join(','),
            '-g', `${config.maxGeometricError || 250},${config.minGeometricError || 0}`,
            '--double_sided', !!config.doubleSided,
            '--use_implicit_tiling', false,
            '--max_features_per_tile', config?.maxFeaturesPerTile || 100
        ],
        {
            onStdOut: (data) => {
                log(data.toString());
            },
            onStdErr: (data) => {
                log(data.toString(), 'error');
            }
        }
    ).then(() => {
        try {
            const tilesetPath = path.join(output, 'tileset.json');
            const tileset = JSON.parse(fs.readFileSync(tilesetPath, 'utf8'));
            fs.writeFileSync(tilesetPath, JSON.stringify({
                ...tileset,
                properties
            }), 'utf8');
        } catch (e) {
            throw e;
        }
        log('', 'success', { action: { link: `/preview/?${tableName}`, type: 'popup', label: 'Tileset preview' } });
        return true;
    });
}

export const fromPointInstancesToTileset = ({ collection, config }, log = console.log) => {
    const {
        tableName,
        output,
        geometryName,
        properties,
    } = getInfo(collection, config);
    const { models } = collectionToPointInstances(collection, {
        computeOptions: (feature) => ({
            scale: parseNumericExpression(config?.scale, feature.properties),
            rotation: parseNumericExpression(config?.rotation, feature.properties),
            translateZ: parseNumericExpression(config?.translateZ, feature.properties),
            model: parseStringExpression(config?.model, feature.properties)
        })
    });
    rimraf.sync(output);
    log('Init tiling...');
    return executeCommand(
        [
            'i3dm.export',
            '-c', `"Host=${dbConfig.host};Username=${dbConfig.user};password=${dbConfig.password};Port=${dbConfig.port};Database=${dbConfig.database}"`,
            '-t', tableName,
            '-o', output,
            '-f', 'cesium',
            '-g', `${config.maxGeometricError || 5000}`,
            '--use_external_model', true,
            '--use_scale_non_uniform', false,
            '--geometrycolumn', geometryName,
            '--max_features_per_tile', config?.maxFeaturesPerTile || 1000,
            '--use_gpu_instancing', false,
            '--boundingvolume_heights', '0,10' // TODO: verify the usage of this parameter
        ],
        {
            onStdOut: (data) => {
                log(data.toString());
            },
            onStdErr: (data) => {
                log(data.toString(), 'error');
            }
        }
    ).then(() => {
        try {
            const tilesetPath = path.join(output, 'tileset.json');
            const tileset = JSON.parse(fs.readFileSync(tilesetPath, 'utf8'));
            fs.writeFileSync(tilesetPath, JSON.stringify({
                ...tileset,
                properties
            }), 'utf8');
            (models || []).forEach((model) => {
                fs.copyFileSync(path.join('static', 'glb', model), path.join(output, 'content', model));
            });
        } catch (e) {
            throw e;
        }
        log('', 'success', { action: { link: `/preview/?${tableName}`, type: 'popup', label: 'Tileset preview' } });
        return true;
    });
};
