
import {
    POINT_CLOUD_COUNT,
    POINT_CLOUD_PROJECTION,
    POINT_CLOUD_PROCESS_LAS,
    POINT_CLOUD_TILESET,
    POINT_CLOUD_TO_MESH,
    POINT_CLOUD_PREVIEW,
    POINT_CLOUD_SHOW_PREVIEW
} from '../../constants.js';
import * as THREE from 'three';
let tilingOptions;

let processOptions;

let meshOptions;

const setDefaultOptions = () => {
    tilingOptions = {
        crsIn: 0,
        geometricErrorScale: 0
    };
    processOptions = {
        outputName: '',
        crsIn: '',
        crsOut: '',
        groundClassification: false,
        sampleRadius: 0,
        rasterFile: ''
    };
    meshOptions = {
        pointCloudPoissonDepth: 10,
        pointCloudPoissonScale: 1.1,
        removeVerticesThreshold: 0.1
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
        processOptions = {
            ...processOptions,
            ...options.processOptions
        };
        meshOptions = {
            ...meshOptions,
            ...options.meshOptions
        };
    } catch (e) {}
};

const resetOptions = (name) => {
    getOptions(name);
};

const mapValue = (val, v1, v2, v3, v4) => v3 + (v4 - v3) * ((val - v1) / (v2 - v1));

const material = new THREE.PointsMaterial( { size: 4, vertexColors: true } );

const updateScene = ({ group, rows }) => {
    group.children.forEach((mesh) => {
        mesh.geometry.dispose();
    });
    group.remove(...group.children);
    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const colors = [];
    const color = new THREE.Color();

    let minZ = Infinity;
    let maxZ = -Infinity;
    for ( let i = 0; i < rows.length; i ++ ) {
        const z = rows[i][2];
        if (z < minZ) { minZ = z; }
        if (z > maxZ) { maxZ = z; }
    }

    for ( let i = 0; i < rows.length; i ++ ) {
        const row = rows[i];
        // positions
        const x = row[0];
        const y = row[2];
        const z = -row[1];
        positions.push( x, y, z );
        // colors
        const grey = mapValue(row[2], minZ, maxZ, 0, 255);
        const vx = (row[3] ?? grey) / 255;
        const vy = (row[4] ?? 255 - grey) / 255;
        const vz = (row[5] ?? 255 - grey) / 255;
        color.setRGB( vx, vy, vz, THREE.SRGBColorSpace );
        colors.push( color.r, color.g, color.b );
    }

    geometry.setAttribute( 'position', new THREE.Float32BufferAttribute( positions, 3 ) );
    geometry.setAttribute( 'color', new THREE.Float32BufferAttribute( colors, 3 ) );

    const mesh = new THREE.Points( geometry, material );

    group.add(mesh);
};

const initPointCloudWorkflow = (options) => {
    const { socket, file, folder } = options;
    resetOptions(file.name);
    let actions = {
        pointCloudPoint: () => {
            socket.emit(POINT_CLOUD_COUNT, { file });
        },
        pointCloudProjection: () => {
            socket.emit(POINT_CLOUD_PROJECTION, { file });
        },
        pointCloudProcessLas: () => {
            socket.emit(POINT_CLOUD_PROCESS_LAS, { config: { ...processOptions }, file });
        },
        createTileset: () => {
            socket.emit(POINT_CLOUD_TILESET, { config: { ...tilingOptions }, file });
        },
        pointCloudToMesh: () => {
            socket.emit(POINT_CLOUD_TO_MESH, { config: { ...meshOptions }, file });
        },
        pointCloudPreview: () => {
            socket.emit(POINT_CLOUD_PREVIEW, { file });
        }
    };
    folder.onChange(() => {
        localStorage.setItem(`${file.name}Options`, JSON.stringify({
            tilingOptions,
            processOptions,
            meshOptions
        }));
    });

    const visualizationOptionsFolder = folder.addFolder( 'Visualization options' );
    visualizationOptionsFolder.add( actions, 'pointCloudPreview' ).name('Create a data sample for preview');

    const metadataFolder = folder.addFolder( 'Metadata' );
    metadataFolder.add( actions, 'pointCloudPoint' ).name('Count points');
    metadataFolder.add( actions, 'pointCloudProjection' ).name('Get projection');

    const processFolder = folder.addFolder( 'Process data' );
    processFolder.add( processOptions, 'outputName' ).name('Output file name');
    processFolder.add( processOptions, 'crsIn' ).name('From CRS');
    processFolder.add( processOptions, 'crsOut' ).name('To CRS');
    processFolder.add( processOptions, 'groundClassification' ).name('Ground classification');
    processFolder.add( processOptions, 'sampleRadius' ).name('Sample radius');
    processFolder.add( processOptions, 'rasterFile' ).name('Raster image');
    processFolder.add( actions, 'pointCloudProcessLas' ).name('Start processing');

    const tilingOptionsFolder = folder.addFolder( 'Tiling options' );
    tilingOptionsFolder.add( tilingOptions, 'crsIn' ).name('CRS number');
    tilingOptionsFolder.add( tilingOptions, 'geometricErrorScale').name('Geometric error scale factor');
    tilingOptionsFolder.add( actions, 'createTileset' ).name('Create tileset');

    const meshOptionsFolder = folder.addFolder( 'Mesh options' );
    meshOptionsFolder.add( meshOptions, 'pointCloudPoissonDepth' ).name('Point cloud poisson depth');
    meshOptionsFolder.add( meshOptions, 'pointCloudPoissonScale' ).name('Point cloud poisson scale');
    meshOptionsFolder.add( meshOptions, 'removeVerticesThreshold' ).name('Remove vertices threshold');
    meshOptionsFolder.add( actions, 'pointCloudToMesh' ).name('Create mesh');

    socket.on(POINT_CLOUD_SHOW_PREVIEW, ({ path }) => {
        fetch(path)
            .then(res => res.text())
            .then((text) => {
                const [header, ...rows] = text
                    .split(/\n/)
                    .filter(row => !!row)
                    .map(row =>
                        row.split(',')
                            .map(val => val.includes('"') ? val : parseFloat(val))
                    )
                updateScene({ ...options, rows });
            });
    });
};

export default initPointCloudWorkflow;
