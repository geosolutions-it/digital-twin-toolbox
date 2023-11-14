
let tilingOptions;

let processOptions;

const setDefaultOptions = () => {
    tilingOptions = {
        crsIn: 0
    };
    processOptions = {
        outputName: '',
        crsIn: 0,
        crsOut: 0,
        geodeticCrs: 0,
        groundClassification: false,
        sampleRadius: 0
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
    } catch (e) {}
};

const resetOptions = (name) => {
    getOptions(name);
};

const initPointCloudWorkflow = (options) => {
    const { socket, file, folder } = options;
    resetOptions(file.name);
    let actions = {
        pointCloudPoint: () => {
            socket.emit('point-cloud:count', { file });
        },
        pointCloudProjection: () => {
            socket.emit('point-cloud:projection', { file });
        },
        pointCloudProcessLas: () => {
            socket.emit('point-cloud:process-las', { config: { ...processOptions }, file });
        },
        createTileset: () => {
            socket.emit('point-cloud:tileset', { config: { ...tilingOptions }, file });
        }
    };
    folder.onChange(() => {
        localStorage.setItem(`${file.name}Options`, JSON.stringify({
            tilingOptions,
            processOptions
        }));
    });
    const metadataFolder = folder.addFolder( 'Metadata' );
    metadataFolder.add( actions, 'pointCloudPoint' ).name('Count points');
    metadataFolder.add( actions, 'pointCloudProjection' ).name('Get projection');

    const processFolder = folder.addFolder( 'Process data' );
    processFolder.add( processOptions, 'outputName' ).name('Output file name');
    processFolder.add( processOptions, 'crsIn' ).name('From CRS');
    processFolder.add( processOptions, 'crsOut' ).name('To CRS');
    processFolder.add( processOptions, 'geodeticCrs' ).name('Geodetic CRS');
    processFolder.add( processOptions, 'groundClassification' ).name('Ground classification');
    processFolder.add( processOptions, 'sampleRadius' ).name('Sample radius');
    processFolder.add( actions, 'pointCloudProcessLas' ).name('Start processing');

    const tilingOptionsFolder = folder.addFolder( 'Tiling options' );
    tilingOptionsFolder.add( tilingOptions, 'crsIn' ).name('CRS number');
    tilingOptionsFolder.add( actions, 'createTileset' ).name('Create tileset');
};

export default initPointCloudWorkflow;
