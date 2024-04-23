# <img src="./static/img/logo.svg" height="32" /> Digital Twin Toolbox

Docker solution for inspecting data and 3D Tiles generation for urban environment.

**Important**: The application **is not** production ready. The main purpose of the current setup is a local development environment to produce 3D Tiles.

## Setup

Copy the `.env.sample` and rename it to `.env`, this file include the default variable to initialize the application then start the application with:

```bash
docker-compose up -d
```

After the docker containers are running is possible to access the client at: [http://locahost:3000](http://locahost:3000)

## Environment variables

name | description | default
--- | --- | ---
DEVELOPMENT | if `true` enable the watch listener to rebuild the client and server on file changes | false
NGINX_PORT | the webapp port | 3000
POSTGRES_USER | postgres user | postgres
POSTGRES_PASSWORD | postgres password | postgres
POSTGRES_DB | postgres database | postgres
POSTGRES_HOST_AUTH_METHOD | trust method is needed to work with `pg2b3dm` library | trust
