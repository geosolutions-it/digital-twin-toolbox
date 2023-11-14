import * as THREE from 'three';
import turfBbox from '@turf/bbox';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import logger from '../logger.js';
import { parseNumericExpression, parseStringExpression } from '../../expression.js';
import { convertToCartesian, translateAndRotate } from '../../cartesian.js';
import { collectionToPointInstances } from '../../instances.js';
let prevCollection;
let geometryOptions;
let tilingOptions;

const setDefaultOptions = () => {
    geometryOptions = {
        model: '',
        translateZ: '',
        rotation: '',
        scale: ''
    };
    tilingOptions = {
        maxFeaturesPerTile: 1000,
        maxGeometricError: 5000
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

const loader = new GLTFLoader();

const material = new THREE.MeshNormalMaterial();
let dummy = new THREE.Object3D();

const loadGLB = (model) => {
    return new Promise((resolve, reject) => {
        loader.load(
            `glb/${model}`,
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
    const pointInstancesCollection = collectionToPointInstances(collection, {
        computeOptions: (feature) => ({
            scale: parseNumericExpression(config?.scale, feature.properties),
            rotation: parseNumericExpression(config?.rotation, feature.properties),
            translateZ: parseNumericExpression(config?.translateZ, feature.properties),
            model: parseStringExpression(config?.model, feature.properties)
        })
    });
    const models = pointInstancesCollection.models;
    Promise.all(models.map(
        (model) => loadGLB(model)
            .then((glb) => {
                glb.scene.traverse(obj => {
                    if (obj.isMesh) {
                        const features = pointInstancesCollection.features.filter((feature) => feature?.properties?.model === model);
                        const mesh = new THREE.InstancedMesh( obj.geometry, material, features.length );
                        features.forEach((feature, idx) => {
                            const coordinates = translateAndRotate(convertToCartesian(feature.geometry.coordinates), cartesian);
                            dummy.position.set( coordinates[0], coordinates[1], coordinates[2] );
                            dummy.rotation.y = -THREE.MathUtils.degToRad(feature.properties.rotation);
                            dummy.scale.set(feature.properties.scale, feature.properties.scale, feature.properties.scale);
                            dummy.updateMatrix();
                            mesh.setMatrixAt( idx, dummy.matrix );
                        });
                        mesh.instanceMatrix.needsUpdate = true;
                        mesh.computeBoundingSphere();
                        group.add(mesh);
                    }
                });
            })
    )).catch((error) => {
        logger({ message: error?.message || error, type: 'error' });
        logger({ message: `${error?.message || error}<br><br>
        Please ensure all the models are included inside the static/glb/ folder.
        <br><br>Expected models: ${models.join(', ')}`, type: 'error' });
    });
};


const pointInstanceWorkflow = (options) => {
    const { file, collection, folder, socket } = options;
    resetOptions(file.name);
    const getConfig = () => {
        return {
            ...geometryOptions,
            ...tilingOptions,
            name: file.name,
            file
        };
    };

    let actions = {
        applyGeometryOptions: () => {
            logger({ message: 'Updating geometry...' });
            setTimeout(() => updateScene({ ...options, collection: prevCollection }, getConfig()), 100);
        },
        createTileset: () => {
            socket.emit('point-instance:tileset', {
                file,
                config: getConfig()
            });
        }
    };
    folder.onChange(() => {
        localStorage.setItem(`${file.name}Options`, JSON.stringify({
            tilingOptions,
            geometryOptions
        }));
    });
    const geometryOptionsFolder = folder.addFolder( 'Geometry options' );
    geometryOptionsFolder.add( geometryOptions, 'model' ).name('Model (.glb)');
    geometryOptionsFolder.add( geometryOptions, 'rotation' ).name('Rotation (deg)');
    geometryOptionsFolder.add( geometryOptions, 'scale' ).name('Scale (m)');
    geometryOptionsFolder.add( geometryOptions, 'translateZ' ).name('Translate z (m)');
    geometryOptionsFolder.add(actions, 'applyGeometryOptions').name('Apply');

    const tilingOptionsFolder = folder.addFolder( 'Tiling options' );
    tilingOptionsFolder.add(tilingOptions, 'maxFeaturesPerTile').name('Max features per tile');
    tilingOptionsFolder.add(tilingOptions, 'maxGeometricError').name('Max geometric error (m)');
    tilingOptionsFolder.add(actions, 'createTileset').name('Create tileset');

    logger({ message: 'Updating geometry...' });
    updateScene(options, getConfig());
    prevCollection = { ...collection };

};

export default pointInstanceWorkflow;
