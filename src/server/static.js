import path from 'path';
import express from 'express';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const createStatic = (port) => {
    const app = express();
    app.use(express.static('./static', {
        setHeaders: (res, path, stat) => {
            if(/\.terrain$/.test(path)) {
                res.setHeader("Content-Encoding", "gzip");
            }
        }
    }));
    app.get('/', (req, res) => {
        res.sendFile(path.join(__dirname + '../../static/index.html'));
    });
    app.get('/preview', (req, res) => {
        res.sendFile(path.join(__dirname, '../../static/preview.html'));
    });
    app.listen(port,()=>{
        console.log(`Static is listening on port ${port}`);
    });
};
