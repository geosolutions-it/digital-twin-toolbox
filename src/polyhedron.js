
import turfLineOffset from '@turf/line-offset';
import turfBuffer from '@turf/buffer';
import turfAngle from '@turf/angle';
import earcut from 'earcut';
import { convertToCartesian } from './cartesian.js';

const parseCoords = (coords, z, translateZ) => [
    coords[0],
    coords[1],
    (z !== undefined
        ? z
        : coords[2] || 0) + (translateZ || 0)
];

const parseRing = (ring, z, translateZ) => ring.map((coords) => parseCoords(coords, z, translateZ));

const sumUntilIndex = (arr, index) => arr.filter((value, idx) => idx < index).reduce((sum, value) => sum + value, 0);

const triangulate = (coordinates, reverse) => {
    const holes = coordinates.filter((coords, idx) => idx !== 0)
        .map(c =>
            c.flat()
        ).flat();
    const holesIndices = coordinates
        .map((coords, idx) => coordinates[idx - 1] ? coordinates[idx - 1].length : null)
        .filter(value => value !== null)
        .map((value, idx, arr) => value + sumUntilIndex(arr, idx));
    const outer = coordinates[0].flat();
    const merged =  [ ...outer, ...holes ];
    const indices = earcut(merged, holesIndices, 3);
    const vertices = coordinates.flat();
    let polyhedron = [];
    for (let i = 0; i < indices.length; i += 3) {
        polyhedron.push([
            convertToCartesian(vertices[indices[i]]),
            convertToCartesian(vertices[indices[i + (reverse ? 2 : 1)]]),
            convertToCartesian(vertices[indices[i + (reverse ? 1 : 2)]]),
            convertToCartesian(vertices[indices[i]])
        ])
    }
    return polyhedron;
};

const planeToWall = (lowerRing, upperRing) => {
    let polyhedron = [];
    for (let i = 0; i < lowerRing.length - 1; i++) {
        if (lowerRing[i + 1]) {
            const bl = convertToCartesian(lowerRing[i]);
            const br = convertToCartesian(lowerRing[i + 1]);
            const tl = convertToCartesian(upperRing[i]);
            const tr = convertToCartesian(upperRing[i + 1]);
            polyhedron.push([bl, tl, br, bl]);
            polyhedron.push([br, tl, tr, br]);
        }
    }
    return polyhedron;
}

const generateWalls = (lower, upper) => {
    return lower.map((ring, idx) => {
        return planeToWall(
            lower[idx],
            upper[idx]
        );
    }).flat();
}

const toPolyhedralSurface = (feature, [lower, upper]) => {
    if (upper === undefined) {
        return triangulate(lower);
    }
    return [
        ...triangulate(upper),
        ...generateWalls(lower, upper),
        ...triangulate(lower, true)
    ];
};

const applyBuffer = (coordinates, options = {}) => {
    const width = options.width || 1;
    const polygon = turfBuffer({ type: 'Point', coordinates }, width, { units: 'meters', steps: 4 });
    return [
        polygon.geometry.coordinates[0].map((coords) => [coords[0], coords[1], coordinates[2] || 0]).reverse()
    ];
};

const applyLineOffset = (coordinates, options = {}) => {
    const width = options.width || 1;
    const left = turfLineOffset({ type: 'LineString', coordinates }, -width / 2, { units: 'meters' })?.geometry?.coordinates || [];
    const right = turfLineOffset({ type: 'LineString', coordinates }, width / 2, { units: 'meters' })?.geometry?.coordinates || [];
    const ring = [
        ...left.map((coords, idx) => [coords[0], coords[1], coordinates[idx][2]]),
        ...right.map((coords, idx) => [coords[0], coords[1], coordinates[idx][2]]).reverse()
    ];
    return [[...ring, ring[0]]];
};

const splitCoordinatesByAngles = (coordinates) => {
    let _coordinates = [[]];
    let index = 0;
    for (let i = 0; i < coordinates.length; i++) {
        if (coordinates[i - 1] && coordinates[i + 1]) {
            const angle = Math.round(turfAngle(coordinates[i - 1], coordinates[i], coordinates[i + 1]));
            if (angle <= 90) {
                _coordinates[index].push(coordinates[i]);
                index++;
                if (!_coordinates[index]) { _coordinates[index] = [] }
            }
        }
        _coordinates[index].push(coordinates[i]);
    }
    return _coordinates;
}

const parsers = {
    'Point': (feature, { lowerLimit, upperLimit, translateZ, width } = {}) => {
        const coordinates = feature.geometry.coordinates;
        if (lowerLimit === undefined && upperLimit === undefined) {
            const lower = applyBuffer(parseCoords(coordinates, lowerLimit, translateZ), { width });
            return toPolyhedralSurface(feature, [lower]);
        }
        const lower = applyBuffer(parseCoords(coordinates, lowerLimit, translateZ), { width });
        const upper = applyBuffer(parseCoords(coordinates, upperLimit, translateZ), { width });
        const averageZLower = lower[0].reduce((sum, coords) => sum + coords[2], 0) / lower[0].length;
        const averageZUpper = upper[0].reduce((sum, coords) => sum + coords[2], 0) / upper[0].length;
        return toPolyhedralSurface(feature, averageZLower > averageZUpper ? [upper, lower] : [lower, upper]);
    },
    'MultiPoint': (feature, options) => {
        return feature.geometry.coordinates.map(coordinates => {
            return parsers.Point({ ...feature, geometry: { type: 'Point', coordinates } }, options);
        }).flat();
    },
    'LineString': (feature, { lowerLimit, upperLimit, translateZ, width } = {}) => {
        return splitCoordinatesByAngles(feature.geometry.coordinates).map((coordinates) => {
            if (lowerLimit === undefined && upperLimit === undefined) {
                const lower = parseRing(coordinates, lowerLimit, translateZ);
                const pLower = applyLineOffset(lower, { width });
                return toPolyhedralSurface(feature, [pLower]);
            }
            const lower = parseRing(coordinates, lowerLimit, translateZ);
            const upper = parseRing(coordinates, upperLimit, translateZ);
            const averageZLower = lower.reduce((sum, coords) => sum + coords[2], 0) / lower.length;
            const averageZUpper = upper.reduce((sum, coords) => sum + coords[2], 0) / upper.length;
            const pLower = applyLineOffset(lower, { width });
            const pUpper = applyLineOffset(upper, { width });
            return toPolyhedralSurface(feature, averageZLower > averageZUpper ? [pUpper, pLower] : [pLower, pUpper]);
        }).flat();
    },
    'MultiLineString': (feature, options) => {
        return feature.geometry.coordinates.map(coordinates => {
            return parsers.LineString({ ...feature, geometry: { type: 'LineString', coordinates } }, options);
        }).flat();
    },
    'Polygon': (feature, { lowerLimit, upperLimit, translateZ } = {}) => {
        if (lowerLimit === undefined && upperLimit === undefined) {
            const lower = feature.geometry.coordinates.map(ring => parseRing(ring, lowerLimit, translateZ));
            return toPolyhedralSurface(feature, [lower]);
        }
        const lower = feature.geometry.coordinates.map(ring => parseRing(ring, lowerLimit, translateZ));
        const upper = feature.geometry.coordinates.map(ring => parseRing(ring, upperLimit, translateZ));
        const averageZLower = lower[0].reduce((sum, coords) => sum + coords[2], 0) / lower[0].length;
        const averageZUpper = upper[0].reduce((sum, coords) => sum + coords[2], 0) / upper[0].length;
        return toPolyhedralSurface(feature, averageZLower > averageZUpper ? [upper, lower] : [lower, upper]);
    },
    'MultiPolygon': (feature, options) => {
        return feature.geometry.coordinates.map(coordinates => {
            return parsers.Polygon({ ...feature, geometry: { type: 'Polygon', coordinates } }, options);
        }).flat();
    }
};

export const collectionToPolyhedralSurfaceZ = (collection, {
    filter = (feature, idx) => feature,
    computeOptions = () => ({})
} = {}) => {
    if (!collection?.features) {
        return {
            type: 'FeatureCollection',
            features: []
        }
    }
    const features = collection.features.filter(filter).map(feature => {
        const options = computeOptions(feature);
        const coordinates = parsers[feature.geometry.type](feature, options);
        return {
            ...feature,
            geometry: {
                type: 'POLYHEDRALSURFACE Z',
                coordinates
            }
        }
    });
    return {
        type: 'FeatureCollection',
        features
    }
};
