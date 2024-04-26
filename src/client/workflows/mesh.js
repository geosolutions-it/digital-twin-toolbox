import { MESH_TILESET, MESH_UPDATE_TILESET_JSON, MESH_PREVIEW, MESH_SHOW_PREVIEW } from '../../constants.js';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import logger from '../logger.js';

let tilingOptions;
let tilesetJSONOptions;

const setDefaultOptions = () => {
    tilingOptions = {
        meshFacesTargetCount: 500000,
        tileFacesTargetCount: 50000,
        zOffset: 0,
        crs: '',
        depth: 3,
        geometricErrors: '200,100,20,5,0',
        removeDoublesFactor: 0.01,
        image: ''
    };
    tilesetJSONOptions = {
        zOffset: 0,
        crs: '',
        geometricErrors: '200,100,20,5,0'
    };
};

const getOptions = (name) => {
    setDefaultOptions();
    try {
        const options = JSON.parse(localStorage.getItem(`${name}Options`));
        tilingOptions = {
            ...tilingOptions,
            ...options.tilingOptions
        };
        tilesetJSONOptions = {
            ...tilesetJSONOptions,
            ...options.tilesetJSONOptions
        };
    } catch (e) {}
};

const resetOptions = (name) => {
    getOptions(name);
};

const loader = new GLTFLoader();

const material = new THREE.MeshNormalMaterial();

const loadGLB = (path) => {
    return new Promise((resolve, reject) => {
        loader.load(path,
            ( glb ) => {
                resolve(glb);
            },
            ( xhr ) => {
                logger({ message: ( xhr.loaded / xhr.total * 100 ) + '% glb loaded' });
            },
            ( error ) => {
                reject(error);
            }
        );
    });
}

const updateScene = ({ group, path }, config = {}) => {
    group.children.forEach((mesh) => {
        mesh.geometry.dispose();
    });
    group.remove(...group.children);

    loadGLB(path)
        .then((glb) => {
            glb.scene.traverse(obj => {
                if (obj.isMesh) {
                    obj.material = material;
                    group.add(obj);
                }
            });
        }).catch((error) => {
            logger({ message: error?.message || error, type: 'error' });
        });
};

const initMeshWorkflow = (options) => {
    const { socket, file, folder } = options;
    resetOptions(file.name);
    let actions = {
        createTileset: () => {
            socket.emit(MESH_TILESET, { config: { ...tilingOptions }, file });
        },
        updateTilesetJSON: () => {
            socket.emit(MESH_UPDATE_TILESET_JSON, { config: { ...tilesetJSONOptions }, file });
        },
        meshPreview: () => {
            socket.emit(MESH_PREVIEW, { file });
        }
    };
    folder.onChange(() => {
        localStorage.setItem(`${file.name}Options`, JSON.stringify({
            tilingOptions,
            tilesetJSONOptions
        }));
    });

    const visualizationOptionsFolder = folder.addFolder( 'Visualization options' );
    visualizationOptionsFolder.add( actions, 'meshPreview' ).name('Create a data sample for preview');

    const tilingOptionsFolder = folder.addFolder( 'Tiling options' );
    tilingOptionsFolder.add( tilingOptions, 'crs' ).name('CRS (eg EPSG:26985)');
    tilingOptionsFolder.add( tilingOptions, 'depth' ).name('Tilset depth');
    tilingOptionsFolder.add( tilingOptions, 'geometricErrors' ).name('Geometric errors');
    tilingOptionsFolder.add( tilingOptions, 'zOffset' ).name('Z offset (m)');
    tilingOptionsFolder.add( tilingOptions, 'meshFacesTargetCount' ).name('Mesh faces count');
    tilingOptionsFolder.add( tilingOptions, 'tileFacesTargetCount' ).name('Tile faces count');
    tilingOptionsFolder.add( tilingOptions, 'removeDoublesFactor' ).name('Remove doubles factor');
    tilingOptionsFolder.add( tilingOptions, 'image' ).name('Orthophoto image');
    tilingOptionsFolder.add( actions, 'createTileset' ).name('Create tileset');

    const tilesetJSONOptionsFolder = folder.addFolder( 'Tileset.json options' );
    tilesetJSONOptionsFolder.add( tilesetJSONOptions, 'crs' ).name('CRS (eg EPSG:26985)');
    tilesetJSONOptionsFolder.add( tilesetJSONOptions, 'geometricErrors' ).name('Geometric errors');
    tilesetJSONOptionsFolder.add( tilesetJSONOptions, 'zOffset' ).name('Z offset (m)');
    tilesetJSONOptionsFolder.add( actions, 'updateTilesetJSON' ).name('Update tileset.json');

    socket.on(MESH_SHOW_PREVIEW, ({ path }) => {
        updateScene({ ...options, path });
    });
};

export default initMeshWorkflow;
