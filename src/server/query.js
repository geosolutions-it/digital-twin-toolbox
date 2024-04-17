import pkg from 'pg';
const { Client } = pkg;
import postgis from './postgis.js';
import logger from './logger.js';

async function tableQuery(client, { create, insert }) {
    await client.query(create());
    logger({ message: 'Init insert...' });
    const insetQuery = insert();
    let result = insetQuery.next();
    await client.query(result.value);
    while (!result.done) {
        result = insetQuery.next();
        if (result.value) {
            await client.query(result.value);
        }
    }
    logger({ message: `Features inserted in table ${result.processed} of ${result.total}` });
}

export function asyncQuery(query) {
    const client = new Client(postgis);
    logger({ message: 'Connecting to PostGIS' });
    return client.connect()
        .then(() => {
            logger({ message: 'Connected!' });
            logger({ message: 'Running query...' });
            return query?.type === 'create-table'
                ? tableQuery(client, query)
                : client.query(query)
                .then(() => {
                    logger({ message: 'Table created!' });
                    return true;
                })
                .finally(() => {
                    logger({ message: 'Disconnected from PostGIS' });
                    client.end();
                    return null;
                });
        })
}
