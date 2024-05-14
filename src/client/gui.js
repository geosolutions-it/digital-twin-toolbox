
import GUI from 'lil-gui';
import logger from './logger.js';
import shpjs from 'shpjs';
import workflows from './workflows/index.js'
import { SHOW_GUI, HIDE_GUI, DATA, AVALIABLE_TILESETS } from '../constants.js';

let data = {
    file: {}
};

const getCollectionWorkflow = ({ file, collection, ...options }) => {
    const isPointCollection = (collection?.features).every(feature => ['Point'].includes(feature?.geometry?.type));
    if (isPointCollection) {
        return workflows.pointInstance({ ...options, file, collection });
    }
    return workflows.vector({ ...options, file, collection });
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
    if (['.ply'].includes(file.extension)) {
        return Promise.resolve(workflows.mesh({ ...options, file }));
    }
    return Promise.reject('Format not implemented yet');
};

const initGui = (options) => {
    const { socket, group } = options || {};
    const gui = new GUI({ width: 300 });
    let fileSelector;
    const inputDataFolder = gui.addFolder( 'Input data' );
    const tileSetFolder = gui.addFolder( 'Available tilesets' );
    socket.on(AVALIABLE_TILESETS, (payload) => {
        tileSetFolder.reset();
        const { availableTilesets } = payload || {};
        let tilesets = availableTilesets.reduce((acc, tileset) => {
            return {
                ...acc,
                [tileset.name]: false
            };
        }, {});

        Object.keys(tilesets).forEach((key) => {
            tileSetFolder.add(tilesets, key);
        });

        tileSetFolder.add({
            action: () => {
                const selectedTilesets = availableTilesets.filter(tileset => tilesets[tileset.name]);
                const actions = [
                    {
                        type:'CATALOG:ADD_LAYERS_FROM_CATALOGS',
                        layers:selectedTilesets.map(tileset => tileset.name),
                        sources:selectedTilesets.map((tileset) => ({
                            type: '3dtiles',
                            url: tileset.link
                        }))
                    }
                ];
                window.open('/mapstore/?map=../../configs/map#/?actions=' + JSON.stringify(actions), '', 'popup=true,width=800,height=600');
            }
        }, 'action').name('Show selected tilesets in MapStore');
        
    });
    let configFolder;
    socket.on(HIDE_GUI, () => {
        gui.hide();
    });
    socket.on(SHOW_GUI, () => {
        gui.show();
    });
    const reset = () => {
        group.children.forEach((mesh) => {
            mesh.geometry.dispose();
        });
        group.remove(...group.children);
        
        if (configFolder) {
            configFolder.destroy();
            configFolder =  undefined;
        }
    };
    socket.on(DATA, (payload) => {
        data.file = {};
        reset();
        if (fileSelector) {
            fileSelector.destroy();
        }
        fileSelector = inputDataFolder
            .add( data.file, 'file', [...(payload.files || [])].reduce((acc, file) => ({ ...acc, [`${file.name} (${file.extension})`]: file }), {}) )
            .name( 'Select file' )
            .onFinishChange((file) => {
                reset();
                configFolder = gui.addFolder( 'Config' );
                configFolder.reset();
                logger({ message: 'Loading file info...' })
                loadingFileInfo(file, { ...options, folder: configFolder })
                    .then(() => {
                        logger({ message: `${file.name} data loaded!`, type: 'success' })
                    })
                    .catch((error) => {
                        console.log(error);
                        logger({ message: error?.message || error, type: 'error' });
                        configFolder.destroy();
                    });
            });
    });
    return { gui };
};

export default initGui;
