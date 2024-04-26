

import { collectionToPolyhedralSurfaceZ } from '../polyhedron.js';
import { collectionToPointInstances } from '../instances.js';
import { parseNumericExpression, parseStringExpression } from '../expression.js';
import { isNumber } from '../number.js';
import { getMetadata } from '../info.js';

const toWKTPolyhedralSurfaceZ = (feature) => {
    const coordinates = (feature.geometry.coordinates || [])
        .map(triangle => {
            return `((${triangle.map(vertex => vertex.join(' ')).join(',')}))`
        }).join(',');
    return `ST_GeomFromText('POLYHEDRALSURFACE Z (${coordinates})', 4978)`
};

const insertTableIterator = ({ limit, step, getValue = () => '' }) => {
    let offset = 0;
    let processed = 0;
    const rangeIterator = {
        next() {
            let result;
            if (offset < limit) {
                const { value, total } = getValue({ offset, step });
                result = {
                    value,
                    done: false
                };
                processed = processed + total;
                offset += step;
                return result;
            }
            return { processed, total: limit, done: true };
        },
    };
    return rangeIterator;
};

export const getPointInstancesTableQuery = (collection, config) => {
    const { tableName, geometryName } = getMetadata(collection, config);
    return {
        type: 'create-table',
        create: () => `
        DROP TABLE IF EXISTS ${tableName};

        CREATE TABLE ${tableName}(
        id serial PRIMARY KEY,
        ${geometryName} geometry(POINTZ, 4326),
        scale double precision,
        rotation double precision,
        model varchar,
        tags json
        );

        CREATE INDEX ${tableName}_geom_idx
        ON ${tableName}
        USING GIST (${geometryName});
        `,
        insert: (step = 1000) => insertTableIterator({
            limit: collection.features.length,
            step,
            getValue: ({ offset }) => {
                const pointInstancesCollection = collectionToPointInstances({
                    type: 'FeatureCollection',
                    features: collection.features.filter((value, idx) => idx >= offset && idx < (offset + step))
                }, {
                    computeOptions: (feature) => ({
                        scale: parseNumericExpression(config?.scale, feature),
                        rotation: parseNumericExpression(config?.rotation, feature),
                        translateZ: parseNumericExpression(config?.translateZ, feature),
                        model: parseStringExpression(config?.model, feature)
                    })
                });
            
                const values = pointInstancesCollection.features.map((feature) => {
                    const coordinates = feature.geometry.coordinates;
                    const geometry = `ST_GeomFromText('POINT(${coordinates[0]} ${coordinates[1]} ${coordinates[2]})', 4326)`;
                    return `(${geometry}, ${feature.properties.scale}, ${feature.properties.rotation}, '${feature.properties.model}', '${JSON.stringify(feature.properties.tags)}')`;
                });
                return {
                    value: `
                    INSERT INTO ${tableName}(${geometryName}, scale, rotation, model, tags)
                    VALUES ${values.join(',\n')};
                    `,
                    total: values.length
                };
            }
        })
    };
};

export const getPolyhedralTableQuery = (collection, config) => {
    const { tableName, geometryName, attributes } = getMetadata(collection, config);
    return {
        type: 'create-table',
        create: () => `
        DROP TABLE IF EXISTS ${tableName};

        CREATE TABLE ${tableName}(
        id serial PRIMARY KEY,
        ${geometryName} geometry(POLYHEDRALSURFACEZ, 4978),
        ${attributes.map(entry => `${entry[0]} ${entry[1]}`).join(',\n  ')}
        );
        CREATE INDEX ${tableName}_geom_idx
        ON ${tableName}
        USING gist(st_centroid(st_envelope(${geometryName})));
        `,
        insert: (step = 1000) => insertTableIterator({
            limit: collection.features.length,
            step,
            getValue: ({ offset }) => {
                const polyhedralSurfaceCollection = collectionToPolyhedralSurfaceZ({
                    type: 'FeatureCollection',
                    features: collection.features.filter((value, idx) => idx >= offset && idx < (offset + step))
                }, {
                    computeOptions: (feature) => ({
                        lowerLimit: parseNumericExpression(config?.lowerLimit, feature),
                        upperLimit: parseNumericExpression(config?.upperLimit, feature),
                        translateZ: parseNumericExpression(config?.translateZ, feature),
                        width: parseNumericExpression(config?.width, feature)
                    })
                })
                const values = polyhedralSurfaceCollection.features
                    .map(feature => {
                        const geometry = toWKTPolyhedralSurfaceZ(feature);
                        const attributes = Object.keys(feature.properties).map((key) => isNumber(feature.properties[key])
                            ? feature.properties[key]
                            : `'${((feature.properties[key] || '') + '').replace(/'/g, "''")}'`).join(', ')
                        return `(${geometry}, ${attributes})`;
                    });
                return {
                    value: `
                    INSERT INTO ${tableName}(${geometryName}, ${attributes.map(entry => entry[0]).join(', ')})
                    VALUES ${values.join(',\n')};
                    `,
                    total: values.length
                };
            }
        })
    };
};
