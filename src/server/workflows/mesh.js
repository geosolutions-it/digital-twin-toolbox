
import fs from 'fs';
import * as rimraf from 'rimraf';
import dbConfig from '../postgis.js';
import { getInfo } from '../../info.js';
import path from 'path';
import { asyncQuery } from '../query.js';
import { getPolyhedralTableQuery } from '../table.js';
import { executeCommand } from '../scripts.js';
import logger from '../logger.js';
import {
    HIDE_GUI,
    SHOW_GUI
} from '../../constants.js';

const fromPolyhedronToTileset = ({ collection, config }) => {
    const {
        tableName,
        output,
        geometryName,
        attributes,
        properties,
    } = getInfo(collection, config);
    logger({ message: 'Init tiling...' });
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
}

const initMeshWorkflow = ({
    socket,
    getCollection
}) => {
    socket.on('mesh:tileset', ({ file, config }) => {
        socket.emit(HIDE_GUI);
        logger({ message: 'Initialize tiling process' });
        getCollection(file)
            .then((collection) => {
                logger({ message: 'Features loaded!' });
                return asyncQuery(getPolyhedralTableQuery(collection, config))
                    .then(() => fromPolyhedronToTileset({ collection, config }))
                    .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
};

export default initMeshWorkflow;
