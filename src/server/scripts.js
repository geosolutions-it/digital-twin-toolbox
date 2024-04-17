
import child_process from 'child_process';

export const executeCommand = (command, options) => {
    return new Promise((resolve, reject) => {
        const cmd = command.join(' ');
        console.log(cmd);
        const cp = child_process.exec(cmd);
        cp.stdout.on('data', (data) => {
            if (options.onStdOut) {
                options.onStdOut(data);
            }
        });
        cp.stderr.on('data', (data) => {
            if (options.onStdErr) {
                options.onStdErr(data);
            }
        });
        cp.on('error', (error) => {
            reject(error.message);
        });
        cp.on('exit', (data) => {
            resolve(data);
        });
    });
};

export const micromambaCLI = (env, params = []) => {
    return [ 'micromamba', 'run', '-n', env, ...params ];
};

export const pdalCLI = (params = []) => {
    return micromambaCLI('pdal_env', ['pdal', ...params ]);
};
