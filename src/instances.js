export const collectionToPointInstances = (collection, {
    computeOptions = () => ({})
} = {}) => {
    const features = (collection?.features || []).map((feature) => {
        const options = computeOptions(feature);
        const coordinates = feature?.geometry?.coordinates || [];
        return {
            ...feature,
            properties: {
                scale: options?.scale || 1,
                rotation: options?.rotation || 0,
                model: options?.model || 'model.glb',
                tags: Object.keys(feature?.properties).map((key) => ({ [key.replace(/ /g, '_').toLowerCase()]: feature.properties[key] }))
            },
            geometry: {
                ...feature?.geometry,
                coordinates: [
                    coordinates[0],
                    coordinates[1],
                    (coordinates[2] || 0) + (options?.translateZ || 0)
                ]
            }
        };
    });
    const models = features.reduce((acc, feature) => acc.includes(feature?.properties?.model) ? acc : [...acc, feature?.properties?.model], []);
    return {
        type: 'FeatureCollection',
        features,
        models
    };
};
