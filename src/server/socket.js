import path from 'path';
import fs from 'fs';
import shpjs from 'shpjs';
import { Server } from 'socket.io';
import { createServer } from 'http';
import { asyncQuery } from './query.js';
import {
    getPolyhedralTableQuery,
    getPointInstancesTableQuery
} from './table.js';
import {
    countLasPoint,
    getLasCRS,
    fromLasToTileset,
    processLas,
    fromPolyhedronToTileset,
    fromPointInstancesToTileset
} from './scripts.js';

import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const supportedExtensions = ['.geojson', '.json', '.zip', '.las', '.laz'];

const NGINX_PORT = process.env.NGINX_PORT;

const readDataFiles = () => {
    const dataLocation = 'data/';
    const dataDirectoryPath = path.join(__dirname, '../../static/', dataLocation);
    return fs.readdirSync(dataDirectoryPath)
        .map(file => {
            const stats = fs.lstatSync(path.join(dataDirectoryPath, file));
            const extension = path.extname(file).replace();
            if (stats.isFile(file) && supportedExtensions.includes(extension)) {
                return {
                    name: path.parse(file).name,
                    link: `http://localhost:${NGINX_PORT}/${dataLocation}${file}`,
                    extension
                };
            }
            return null;
        }).filter(value => value !== null);
};

const getCollection = (file) => {
    const name = `${file?.name}${file?.extension}`;
    if (file?.extension === '.zip') {
        // currently the only way is to request via url
        return shpjs(`http://localhost:${NGINX_PORT}/data/${name}`);
    }
    return new Promise((resolve, reject) => {
        try {
            const filePath = path.join(__dirname, '../../static/data/', name);
            const collection = JSON.parse(fs.readFileSync(filePath));
            resolve(collection);
        } catch (e) {
            reject(e);
        }
    });
}

export const createSocket = (port) => {
    const httpServer = createServer();
    const io = new Server(httpServer);
    io.on('connection', (socket) => {
        const log = (message, type, options = {}) => {
            console.log(message);
            socket.emit('log', {
                message,
                type,
                options
            });
        };
        const files = readDataFiles();
        socket.emit('data', { files });

        socket.on('mesh:tileset', ({ file, config }) => {
            socket.emit('gui:hide');
            log('Initialize tiling process');
            getCollection(file)
                .then((collection) => {
                    log('Features loaded!');
                    return asyncQuery(getPolyhedralTableQuery(collection, config), log)
                        .then(() => fromPolyhedronToTileset({ collection, config }, log))
                        .catch((error) => log(error?.message || error, 'error'))
                })
                .catch((error) => log(error?.message || error, 'error'))
                .finally(() => socket.emit('gui:show'));
        });
        socket.on('point-instance:tileset', ({ file, config }) => {
            socket.emit('gui:hide');
            log('Initialize tiling process');
            getCollection(file)
                .then((collection) => {
                    log('Features loaded!');
                    return asyncQuery(getPointInstancesTableQuery(collection, config), log)
                        .then(() => fromPointInstancesToTileset({ collection, config }, log))
                        .catch((error) => log(error?.message || error, 'error'))
                })
                .catch((error) => log(error?.message || error, 'error'))
                .finally(() => socket.emit('gui:show'));
        });
        socket.on('point-cloud:count', ({ file }) => {
            socket.emit('gui:hide');
            countLasPoint({ file }, log)
                .catch((error) => log(error?.message || error, 'error'))
                .finally(() => socket.emit('gui:show'));
        });
        socket.on('point-cloud:projection', ({ file }) => {
            socket.emit('gui:hide');
            getLasCRS({ file }, log)
                .catch((error) => log(error?.message || error, 'error'))
                .finally(() => socket.emit('gui:show'));
        });
        socket.on('point-cloud:process-las', (config) => {
            socket.emit('gui:hide');
            processLas(config, log)
                .then(() => {
                    const updatedFiles = readDataFiles();
                    socket.emit('data', { files: updatedFiles });
                })
                .catch((error) => log(error?.message || error, 'error'))
                .finally(() => socket.emit('gui:show'));
        });
        socket.on('point-cloud:tileset', (config) => {
            socket.emit('gui:hide');
            fromLasToTileset(config, log)
                .catch((error) => log(error?.message || error, 'error'))
                .finally(() => socket.emit('gui:show'));
        });
    });
    io.listen(port);
    
    console.log(`Socket is listening on port ${port}`);
};
