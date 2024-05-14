import fs from 'fs';

if (!fs.existsSync('./static/mapstore')) {
    fs.cpSync('/usr/src/mapstore/', './static/mapstore/', { recursive: true });
}

fs.copyFileSync('./static/configs/localConfig.json', './static/mapstore/configs/localConfig.json', fs.constants.COPYFILE_FICLONE);
