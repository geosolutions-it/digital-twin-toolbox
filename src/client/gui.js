
import GUI from 'lil-gui';
import logger from './logger.js';
import shpjs from 'shpjs';
import workflows from './workflows/index.js'

let data = {
    file: {}
};

const getCollectionWorkflow = ({ file, collection, ...options }) => {
    const isPointCollection = (collection?.features).every(feature => ['Point'].includes(feature.geometry.type));
    if (isPointCollection) {
        return workflows.pointInstance({ ...options, file, collection });
    }
    return workflows.mesh({ ...options, file, collection });
};

const loadingFileInfo = (file, options) => {
    if (['.json', '.geojson'].includes(file.extension)) {
        return fetch(file.link)
            .then(res => res.json())
            .then((collection) => {
                return getCollectionWorkflow({ ...options, file, collection });
            })
    }
    if (['.zip'].includes(file.extension)) {
        return shpjs(file.link)
            .then((collection) => {
                return getCollectionWorkflow({ ...options, file, collection });
            })
    }
    if (['.laz', '.las'].includes(file.extension)) {
        return Promise.resolve(workflows.pointCloud({ ...options, file }));
    }
    return Promise.reject('Format not implemented yet');
};

const initGui = (options) => {
    const { socket, group } = options || {};
    const gui = new GUI({ width: 300 });
    let fileSelector;
    const inputDataFolder = gui.addFolder( 'Input data' );
    let configFolder;
    socket.on('gui:hide', () => {
        gui.hide();
    });
    socket.on('gui:show', () => {
        gui.show();
    });
    socket.on('data', (payload) => {
        if (fileSelector) {
            fileSelector.destroy();
        }
        fileSelector = inputDataFolder
            .add( data.file, 'file', [...(payload.files || [])].reduce((acc, file) => ({ ...acc, [`${file.name} (${file.extension})`]: file }), {}) )
            .name( 'Select file' )
            .onFinishChange((file) => {
                group.children.forEach((mesh) => {
                    mesh.geometry.dispose();
                });
                group.remove(...group.children);
                logger({ message: 'Loading file info...' })
                if (configFolder) {
                    configFolder.destroy();
                    configFolder =  undefined;
                }
                configFolder = gui.addFolder( 'Config' );
                configFolder.reset();
                loadingFileInfo(file, { ...options, folder: configFolder })
                    .then(() => {
                        logger({ message: `${file.name} data loaded!`, type: 'success' })
                    })
                    .catch((error) => {
                        logger({ message: error?.message || error, type: 'error' });
                        configFolder.destroy();
                    });
            });
    });
    return { gui };
};

export default initGui;
