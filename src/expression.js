import { compileExpression } from 'filtrex';
import { isNumber } from './number.js';

const getGeometryValues = (geometry) => {
    let values = {
        $minZ: 0
    };
    if (!geometry?.coordinates || !geometry?.type) {
        return values;
    }
    if (geometry.type === 'Point') {
        values.$minZ = geometry.coordinates[2] ?? 0;
        return values;
    }
    if (geometry.type === 'MultiPoint') {
        values.$minZ = geometry.coordinates.map(coords => coords[2]);
        return values;
    }
    if (geometry.type === 'Polygon') {
        values.$minZ = Math.min(...geometry.coordinates.map(ring => Math.min(...ring.map(coords => coords[2] ?? 0))));
        return values;
    }
    if (geometry.type === 'MultyPolygon') {
        values.$minZ = Math.min(...geometry.coordinates.map(polygon =>
            Math.min(...polygon.map(ring => Math.min(...ring.map(coords => coords[2] ?? 0))))
        ));
        return values;
    }
    return values;
}

export const parseNumericExpression = (value, { properties, geometry }) => {
    if (!value) {
        return undefined;
    }
    try {
        const result = compileExpression(value)({ ...properties, ...getGeometryValues(geometry) });
        return isNumber(result) ? result : undefined;
    } catch (e) {
        console.log(e);
        return undefined;
    }
};

export const parseStringExpression = (value, { properties }) => {
    if (!value) {
        return undefined;
    }
    try {
        const result = compileExpression(value)({ ...properties });
        return `${result}`;
    } catch (e) {
        console.log(e);
        return undefined;
    }
};