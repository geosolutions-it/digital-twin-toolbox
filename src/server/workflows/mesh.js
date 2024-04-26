
import fs from 'fs';
import {
    HIDE_GUI,
    SHOW_GUI,
    MESH_TILESET,
    MESH_PREVIEW,
    MESH_SHOW_PREVIEW,
    MESH_UPDATE_TILESET_JSON
} from '../../constants.js';
import { executeCommand, micromambaCLI } from '../scripts.js';
import logger from '../logger.js';
import { execSync } from 'child_process';

// from  https://github.com/OpenDroneMap/Obj2Tiles/blob/1909c8fd00fde3956da42de4495426813d9fcb2c/Obj2Tiles/Stages/Model/GpsCoords.cs
function multiplyMatrix(m1, m2) {
    let res = [];
    for (var i = 0; i < 4; i++) {
        for (var j = 0; j < 4; j++) {
            res[i * 4 + j] = 0;
            for (var k = 0; k < 4; k++) {
                res[i * 4 + j] += m1[i * 4 + k] * m2[k * 4 + j];
            }
        }
    }
    return res;
}
// from  https://github.com/OpenDroneMap/Obj2Tiles/blob/1909c8fd00fde3956da42de4495426813d9fcb2c/Obj2Tiles/Stages/Model/GpsCoords.cs
function convertToColumnMajorOrder(m) {
    let res = [];
    for (var i = 0; i < 4; i++) {
        for (var j = 0; j < 4; j++) {
            res[j * 4 + i] = m[i * 4 + j];
        }
    }

    return res;
}

// from  https://github.com/OpenDroneMap/Obj2Tiles/blob/1909c8fd00fde3956da42de4495426813d9fcb2c/Obj2Tiles/Stages/Model/GpsCoords.cs
function toEcefTransform({ scale, latitude, longitude, altitude }) {
    const s = scale;
    const lat = latitude * Math.PI / 180;
    const lon = longitude * Math.PI / 180;
    const alt = altitude;

    const a = 6378137.0 / s;
    const b = 6356752.3142 / s;
    const f = (a - b) / a;

    const eSq = 2 * f - f * f;

    const sinLat = Math.sin(lat);
    const cosLat = Math.cos(lat);
    const sinLon = Math.sin(lon);
    const cosLon = Math.cos(lon);

    const nu = a / Math.sqrt(1 - eSq * sinLat * sinLat);

    const x = (nu + alt) * cosLat * cosLon;
    const y = (nu + alt) * cosLat * sinLon;
    const z = (nu * (1 - eSq) + alt) * sinLat;

    const xr = -sinLon;
    const yr = cosLon;
    const zr = 0;

    const xe = -cosLon * sinLat;
    const ye = -sinLon * sinLat;
    const ze = cosLat;

    const xs = cosLat * cosLon;
    const ys = cosLat * sinLon;
    const zs = sinLat;

    const res = [
        xr, xe, xs, x,
        yr, ye, ys, y,
        zr, ze, zs, z,
        0, 0, 0, 1
    ];

    const rot = [
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1
    ];

    const mult = multiplyMatrix(res, rot);

    return multiplyMatrix(convertToColumnMajorOrder(mult), [
        s, 0, 0, 0,
        0, s, 0, 0,
        0, 0, s, 0,
        0, 0, 0, 1
    ]);
}

const rad = (angle) => angle * Math.PI / 180;

const cs2cs = (coords, from, to) => {
    const value = execSync(
        micromambaCLI('pdal_env', [
            `cs2cs ${from} ${to} -f %.12f <<EOF
            ${coords[0]} ${coords[1]}
            EOF`
        ]).join(' ')
    )
    const [x, y, z] = value.toString().split(/\s/).map(parseFloat);
    return [x, y, z];
}

const checkUri = (outputDir, leaf) => {
    if (fs.existsSync(`${outputDir}${leaf.uri}`)) {
        return [leaf];
    }
    return [];
};

const createTileset = ({ file, config }) => {
    const outputDir = `static/tilesets/${file.name}/`;

    if (!fs.existsSync(`${outputDir}info.json`)) {
        return Promise.reject(`${outputDir}info.json not avaliable`);
    }
    
    const info = JSON.parse(fs.readFileSync(`${outputDir}info.json`, 'utf-8'));
    const {
        size,
        depth,
        center
    } = info || {};
    const {
        zOffset = 0,
        geometricErrors: geometricErrorsConfig = '200,100,20,5,0',
        crs = 'EPSG:26985',
    } = config || {};
    const geometricErrors = geometricErrorsConfig.split(',').map(parseFloat);
    const [latitude, longitude] = cs2cs([center[0], center[1]], crs, 'WGS84');
    const z = center[2] + zOffset;
    const [width, height] = size || [];
    const minZ = z - size[2] / 2;
    const maxZ = z + size[2] / 2;
    const region = ([minx, miny, maxx, maxy]) => {
        const lb = cs2cs([minx, miny], crs, 'WGS84');
        const rt = cs2cs([maxx, maxy ], crs, 'WGS84');
        return [rad(lb[1]), rad(lb[0]), rad(rt[1]), rad(rt[0]), minZ, maxZ];
    }
    function quad({
        x,
        y,
        bbox,
        level,
        uri,
        transform
    }) {
        const size = Math.pow(2, level)
        const wUnit = width / size
        const hUnit = height / size
        const leaf = {
            ...(bbox && { boundingVolume: { region: region(bbox) } }),
            geometricError: geometricErrors[level + 1],
            refine: 'REPLACE',
            ...(uri && { content: { uri } })
        };
        if (level < depth) {
            const nextLevel = level + 1;
            const nextSize = Math.pow(2, nextLevel);
            const nextWUnit = width / nextSize;
            const nextHUnit = height / nextSize;
            const translateX = (x * wUnit);
            const translateY = (y * hUnit);
            const x0 = Math.round(translateX / nextWUnit);
            const x1 = x0 + 1;
            const y0 = Math.round(translateY / nextHUnit);
            const y1 = y0 + 1;
            const centerX = bbox[0] + nextWUnit;
            const centerY = bbox[1] + nextHUnit;
            const child = {
                ...leaf,
                children: [
                    ...checkUri(outputDir, { bbox: [bbox[0], centerY, centerX, bbox[3]], x: x0, y: y0, level: nextLevel, uri: `${nextLevel}_${y0}_${x0}.glb` }),
                    ...checkUri(outputDir, { bbox: [centerX, centerY, bbox[2], bbox[3]], x: x1, y: y0, level: nextLevel, uri: `${nextLevel}_${y0}_${x1}.glb` }),
                    ...checkUri(outputDir, { bbox: [bbox[0], bbox[1], centerX, centerY], x: x0, y: y1, level: nextLevel, uri: `${nextLevel}_${y1}_${x0}.glb` }),
                    ...checkUri(outputDir, { bbox: [centerX, bbox[1], bbox[2], centerY], x: x1, y: y1, level: nextLevel, uri: `${nextLevel}_${y1}_${x1}.glb` })
                ].map(quad)
            }
            return transform
                ? {
                    ...(bbox && { boundingVolume: { region: region(bbox) } }),
                    ...(transform && { transform }),
                    geometricError: geometricErrors[level],
                    refine: 'REPLACE',
                    children: [child]
                }
                : child;
        }
        return leaf;
    }

    const transform = toEcefTransform({ scale: 1, latitude, longitude, altitude: z });

    const tileset = {
        asset: {
            version: '1.1'
        },
        root: quad({
            x: 0,
            y: 0,
            bbox: [
                center[0] - width / 2,
                center[1] - height / 2,
                center[0] + width / 2,
                center[1] + height / 2
            ],
            level: 0,
            transform,
            uri: '0_0_0.glb'
        })
    };

    fs.writeFileSync(`${outputDir}tileset.json`, JSON.stringify(tileset));
    logger({
        message: '', 
        type: 'success',
        options: { action: { link: `/preview/?${file.name}`, type: 'popup', label: 'Tileset preview' } }
    });
    return Promise.resolve(tileset);
}

const meshToTileset = ({ file, config }) => {
    logger({ message: 'Init tiling...' });
    const input = `static/data/${file.name}${file.extension}`;
    const inputImage = config.image
        ? `static/data/${config.image}`
        : '';
    return executeCommand(
        [
            'blender',
            '--background',
            '--python', 'src/scripts/ply_to_tileset.py',
            '--',
            input,
            `static/tilesets/${file.name}`,
            config.depth || 3, // depth
            config.meshFacesTargetCount || 500000, // mesh faces target
            config.tileFacesTargetCount || 50000, // tile faces target
            config.removeDoublesFactor || 0.025,
            inputImage
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
        createTileset({ file, config });
        return true;
    });
};

const previewMesh = ({ file }) => {
    const previePath = 'data/_preview/';
    const previewDirectory = `static/${previePath}`;
    const outputPreview = `${previewDirectory}${file.name}.glb`;
    const outputPath = `${previePath}${file.name}.glb`;
    if (fs.existsSync(outputPreview)) {
        return Promise.resolve(outputPath);
    }
    return executeCommand([
        'blender',
        '--background',
        '--python', 'src/scripts/ply_to_preview.py',
        '--',
        `static/data/${file.name}${file.extension}`,
        outputPreview,
        500000 // mesh faces target
    ], {}).then(() => {
        return outputPath;
    });
};

const initMeshWorkflow = ({
    socket
}) => {
    socket.on(MESH_TILESET, (options) => {
        socket.emit(HIDE_GUI);
        meshToTileset(options)
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on(MESH_UPDATE_TILESET_JSON, (options) => {
        socket.emit(HIDE_GUI);
        createTileset(options)
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
    socket.on(MESH_PREVIEW, (config) => {
        socket.emit(HIDE_GUI);
        previewMesh(config)
            .then((path) => {
                socket.emit(MESH_SHOW_PREVIEW, { path })
                return true;
            })
            .catch((error) => logger({ message: error?.message || error, type: 'error' }))
            .finally(() => socket.emit(SHOW_GUI));
    });
};

export default initMeshWorkflow;
