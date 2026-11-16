# Configuration

The whole stack reads one file, `.env` at the root of the repository. `./scripts/init-env.sh` creates it from `.env.copy` and fills in the secrets.

`.env.copy` is the reference: every variable is listed there with a comment. This page only explains the changes you are most likely to make.

After editing `.env`, apply it with:

```bash
docker compose up -d
```

## Access

There is no login: `AUTH_PROVIDER=standalone` lets anyone who reaches the application use it. Run the stack on your machine or on a private network only.

## Workers

Each worker runs several jobs in parallel. Point cloud and mesh jobs use several cores each, so they run fewer at a time by default. Raise the values on a large machine, lower them if jobs run out of memory.

The concurrency of each worker and a memory cap for the point cloud and mesh containers are set in the workers section of `.env.copy`. The cap keeps one large job from taking down the whole machine.

## Height conversions

The workers download geoid grids on first use for the [height conversions](/guide/heights), so they need internet access. `PROJ_NETWORK=ON` in `docker-compose.yml` enables it. Without a grid, the jobs that convert heights fail with a message about the missing grid.

## Storage

The bucket is a local folder, see [Local stack](./#storage).

## Domain and paths

`DOMAIN` is the host name the proxy answers to, `localhost` by default. The `DTT_*` variables set the API URL and the base paths of the frontend, e.g. to serve it under a sub path.

## Images

`TAG` selects the version of the images pulled from Docker Hub, `latest` by default. Set it to a release, e.g. `1.0.0`, to run that version.
