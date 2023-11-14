
import { isNumber } from './number.js';

export const getMetadata = (collection, config) => {
    const tableName = (config?.file?.name || 'tiles').toLowerCase().replace(/ /g, '_');
    const geometryName = 'geom';
    const properties = collection?.features?.[0]?.properties || {};
    const attributes = Object.keys(properties)
        .map(key => {
            return [key.replace(/ /g, '_').toLowerCase(), isNumber(properties[key]) ? 'double precision' : 'varchar' ];
        });
    return { tableName, geometryName, attributes };
};

export const getInfo = (collection, config) => {
    const { tableName, geometryName, attributes } = getMetadata(collection, config);
    const output =  `./static/tilesets/${config?.name || 'tiles'}`;
    return {
        tableName,
        output,
        attributes,
        geometryName,
        properties: attributes.reduce((acc, entry) => ({ ...acc, [entry[0]]: entry[1] === 'double precision' ? { minimum: 1, maximum: 1 } : { } }), {})
    }
};
