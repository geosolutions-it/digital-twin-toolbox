import pkg from 'pg';
const { Client } = pkg;
import postgis from './postgis.js';

async function tableQuery(client, { create, insert }, log = console.log) {
    await client.query(create());
    log('Init insert...');
    const insetQuery = insert();
    let result = insetQuery.next();
    await client.query(result.value);
    while (!result.done) {
        result = insetQuery.next();
        if (result.value) {
            await client.query(result.value);
        }
    }
    log(`Features inserted in table ${result.processed} of ${result.total}`);
}

export function asyncQuery(query, log = console.log) {
    const client = new Client(postgis);
    log('Connecting to PostGIS');
    return client.connect()
        .then(() => {
            log('Connected!');
            log('Running query...');
            return query?.type === 'create-table'
                ? tableQuery(client, query, log)
                : client.query(query)
                .then(() => {
                    log('Table created!');
                    return true;
                })
                .finally(() => {
                    log('Disconnected from PostGIS');
                    client.end();
                    return null;
                });
        })
}
