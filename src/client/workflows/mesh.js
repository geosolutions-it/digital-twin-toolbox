import * as THREE from 'three';
import turfBbox from '@turf/bbox';
import { parseNumericExpression } from '../../expression.js';
import { convertToCartesian, translateAndRotate } from '../../cartesian.js';
import { collectionToPolyhedralSurfaceZ } from '../../polyhedron.js';
import logger from '../logger.js';

let prevCollection;
let tilingOptions;
let visualizationOptions;
let geometryOptions;

const setDefaultOptions = () => {
    tilingOptions = {
        minGeometricError: 0,
        maxGeometricError: 250,
        doubleSided: false,
        maxFeaturesPerTile: 100
    };
    visualizationOptions = {
        wireframe: false,
    };
    geometryOptions = {
        lowerLimit: '',
        upperLimit: '',
        translateZ: '',
        width: ''
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
        visualizationOptions = {
            ...visualizationOptions,
            ...options.visualizationOptions
        };
        geometryOptions = {
            ...geometryOptions,
            ...options.geometryOptions
        };
    } catch (e) {}
};

const resetOptions = (name) => {
    prevCollection = undefined;
    getOptions(name);
};

const material = new THREE.MeshNormalMaterial();

const updateScene = ({ collection, setInitCameraLocation, group }, config = {}) => {
    if (!collection) {
        return null;
    }
    if (collection !== prevCollection) {
        setInitCameraLocation();
    }
    group.children.forEach((mesh) => {
        mesh.geometry.dispose();
    });
    group.remove(...group.children);
    const [minx, miny, maxx, maxy] = turfBbox(collection);
    const center = [minx + (maxx - minx) / 2, miny + (maxy - miny) / 2, 0];
    const cartesian = convertToCartesian(center);
    const polyhedralSurfaceCollection = collectionToPolyhedralSurfaceZ(collection, {
        filter: config?.filter ? config.filter : (feature, idx) => feature,
        computeOptions: (feature) => ({
            lowerLimit: parseNumericExpression(config?.lowerLimit, feature.properties),
            upperLimit: parseNumericExpression(config?.upperLimit, feature.properties),
            translateZ: parseNumericExpression(config?.translateZ, feature.properties),
            width: parseNumericExpression(config?.width, feature.properties)
        })
    });
    
    polyhedralSurfaceCollection.features.forEach((feature) => {
        const coordinates = feature.geometry.coordinates;
        const vertices = new Float32Array(coordinates.reduce((acc, triangle) => {
            const [a, b, c] = triangle;
            return [...acc, ...[a, b, c].map((vertex) => translateAndRotate(vertex, cartesian))];
        }, []).flat());
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute( 'position', new THREE.BufferAttribute( vertices, 3 ) );
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh( geometry, material );
        group.add(mesh);
    });
    logger({ message: 'Geometry update completed...' });
};

const initMeshWorkflow = (options) => {
    const { folder, collection, file, socket } = options;
    resetOptions(file.name);
    const getConfig = () => {
        return {
            ...geometryOptions,
            ...tilingOptions,
            file,
            name: file.name
        };
    };

    let actions = {
        applyGeometryOptions: () => {
            logger({ message: 'Updating geometry...' });
            setTimeout(() => updateScene({ ...options, collection: prevCollection }, getConfig()), 100);
        },
        createTileset: () => {
            socket.emit('mesh:tileset', {
                file,
                config: getConfig()
            });
        }
    };
    folder.onChange(() => {
        localStorage.setItem(`${file.name}Options`, JSON.stringify({
            tilingOptions,
            visualizationOptions,
            geometryOptions
        }));
    });
    const visualizationOptionsFolder = folder.addFolder( 'Visualization options' );
    visualizationOptionsFolder.add( visualizationOptions, 'wireframe' )
        .onChange(() => { material.wireframe = !!visualizationOptions.wireframe; });

    const geometryOptionsFolder = folder.addFolder( 'Geometry options' );
    geometryOptionsFolder.add( geometryOptions, 'lowerLimit' ).name('Lower limit height (m)');
    geometryOptionsFolder.add( geometryOptions, 'upperLimit' ).name('Upper limit height (m)');
    geometryOptionsFolder.add( geometryOptions, 'translateZ' ).name('Translate z (m)');
    geometryOptionsFolder.add( geometryOptions, 'width' ).name('Width for line and point');
    geometryOptionsFolder.add(actions, 'applyGeometryOptions').name('Apply');

    const tilingOptionsFolder = folder.addFolder( 'Tiling options' );
    tilingOptionsFolder.add(tilingOptions, 'maxFeaturesPerTile').name('Max features per tile');
    tilingOptionsFolder.add(tilingOptions, 'doubleSided').name('Double sided');
    tilingOptionsFolder.add(tilingOptions, 'maxGeometricError').name('Max geometric error (m)');
    tilingOptionsFolder.add(tilingOptions, 'minGeometricError').name('Min geometric error (m)');
    tilingOptionsFolder.add(actions, 'createTileset').name('Create tileset');

    logger({ message: 'Updating geometry...' });
    updateScene(options, getConfig());
    prevCollection = { ...collection };
};

export default initMeshWorkflow;
