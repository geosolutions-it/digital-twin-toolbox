
import fs from 'fs';
import * as rimraf from 'rimraf';
import dbConfig from '../postgis.js';
import { getInfo } from '../../info.js';
import path from 'path';
import {
    getPointInstancesTableQuery
} from '../table.js';
import { executeCommand } from '../scripts.js';
import { asyncQuery } from '../query.js';
import logger from '../logger.js';
import {
    HIDE_GUI,
    SHOW_GUI
} from '../../constants.js';
import { collectionToPointInstances } from '../../instances.js';
import { parseStringExpression, parseNumericExpression } from '../../expression.js';

const fromPointInstancesToTileset = ({ collection, config }) => {
    const {
        tableName,
        output,
        geometryName,
        properties,
    } = getInfo(collection, config);
    const { models } = collectionToPointInstances(collection, {
        computeOptions: (feature) => ({
            scale: parseNumericExpression(config?.scale, feature),
            rotation: parseNumericExpression(config?.rotation, feature),
            translateZ: parseNumericExpression(config?.translateZ, feature),
            model: parseStringExpression(config?.model, feature)
        })
    });
    rimraf.sync(output);
    logger({ message: 'Init tiling...' });
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
                logger({ message: data.toString() });
            },
            onStdErr: (data) => {
                logger({ message: data.toString(), type: 'error' });
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
        logger({
            message: '',
            type: 'success',
            options: { action: { link: `/preview/?${tableName}`, type: 'popup', label: 'Tileset preview' } }
        });
        return true;
    });
};

const initPointInstanceWorkflow = ({
    socket,
    getCollection
}) => {
    socket.on('point-instance:tileset', ({ file, config }) => {
        socket.emit(HIDE_GUI);
        logger({ message: 'Initialize tiling process' });
        getCollection(file)
            .then((collection) => {
                logger({ message: 'Features loaded!' });
                return asyncQuery(getPointInstancesTableQuery(collection, config))
                    .then(() => fromPointInstancesToTileset({ collection, config }))
                    .catch((error) => logger({ message: error?.message || error, type: 'error'}))
            })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
};

export default initPointInstanceWorkflow;
