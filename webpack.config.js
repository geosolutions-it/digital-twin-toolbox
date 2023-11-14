import path from 'path';
import { fileURLToPath } from 'url';
import webpack from 'webpack';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default {
    entry:  {
        'bundle': './src/client/index.js'
    },
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
            {
                test: /\.css$/i,
                use: ['style-loader', 'css-loader'],
            },
        ],
    },
    resolve: {
        extensions: ['.js'],
        fallback: {
            url: false,
            http: false,
            https: false,
            zlib: false
        }
    },
    output: {
        filename: 'dist/[name].js',
        path: path.resolve(__dirname, './static/'),
    },
    watchOptions: {
        aggregateTimeout: 200,
        poll: 1000,
        ignored: [
            '**/node_modules',
            '/static/',
            '/tmp/',
            '/src/server/'
        ]
    },
    plugins: [
        new webpack.ProvidePlugin({
            Buffer: ['buffer', 'Buffer']
        })
    ]
};
