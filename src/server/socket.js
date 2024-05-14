import path from 'path';
import fs from 'fs';
import shpjs from 'shpjs';
import { Server } from 'socket.io';
import { createServer } from 'http';
import { fileURLToPath } from 'url';
import { setLoggerSocket } from './logger.js';
import workflows from './workflows/index.js';
import { DATA, AVALIABLE_TILESETS } from '../constants.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const supportedExtensions = ['.geojson', '.json', '.zip', '.las', '.laz', '.ply'];

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

const readAvailableTilesets = () => {
    const tilesetsLocation = 'tilesets/';
    const tilesetsDirectoryPath = path.join(__dirname, '../../static/', tilesetsLocation);
    return fs.readdirSync(tilesetsDirectoryPath)
        .map(file => {
            const stats = fs.lstatSync(path.join(tilesetsDirectoryPath, file));
            if (stats.isDirectory(file)) {
                return {
                    name: file,
                    link: `/${tilesetsLocation}${file}/tileset.json`
                };
            }
            return null;
        }).filter(value => value !== null);
}

const getCollection = (file) => {
    const name = `${file?.name}${file?.extension}`;
    if (file?.extension === '.zip') {
        // currently the only way is to request via url
        // use internal port
        return shpjs(`http://localhost:3000/data/${name}`);
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
        setLoggerSocket(socket);
        const files = readDataFiles();
        socket.emit(DATA, { files });
        const availableTilesets = readAvailableTilesets();
        socket.emit(AVALIABLE_TILESETS, { availableTilesets });
        Object.keys(workflows).forEach(key => {
            workflows[key]({
                socket,
                getCollection,
                readDataFiles
            });
        });
    });
    io.listen(port);
    console.log(`Socket is listening on port ${port}`);
};
