
module.exports = (devServerDefault, projectConfig) => {
    return {
        ...devServerDefault,
        proxy: {
            ...devServerDefault?.proxy,
            '/api': {
                target: 'http://localhost'
            }
        }
    };
};
