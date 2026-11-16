# Local stack

The whole toolbox runs with Docker Compose. [Getting started](/guide/getting-started) covers the first run; this page explains what runs and how to work on it.

## Services

| Service | Role | Local URL |
| --- | --- | --- |
| `proxy` | Traefik, routes the requests to frontend and backend | http://localhost, dashboard on :8090 |
| `frontend` | React application, served by nginx | http://localhost |
| `backend` | FastAPI, the REST API | http://localhost/api, docs on http://localhost/docs |
| `db` | Postgres, jobs and their status | localhost:5432 |
| `redis` | Celery queue between backend and workers | |
| `worker-vector` | Polygon, Point instance, Terrain, CityGML, Buildings | |
| `worker-point-cloud` | Point cloud | |
| `worker-mesh` | Mesh | |
| `versitygw` | S3-compatible storage, the bucket | localhost:8333 |

The three workers run the same image. Each one listens to its own queue, so they can be scaled and sized separately.

## Compose files

| File | Used for |
| --- | --- |
| `docker-compose.yml` | the base stack, shared by every environment |
| `docker-compose.override.yml` | local additions: exposed ports, storage, logs. Loaded automatically by `docker compose` |
| `docker-compose.dev.yml` | hot reload, see below |
| `docker-compose.build.yml` | building the published images (CI) |
| `docker-compose.test.yml` | running the tests |
| `docker-compose.traefik.yml` | a public Traefik for a server |

## Hot reload

The development overlay mounts `backend/app` into the backend and the workers, and restarts them when a file changes. No image rebuild is needed for code changes.

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.dev.yml up -d --build
```

To make it the default for plain `docker compose` commands, uncomment `COMPOSE_FILE` in `.env`.

`--build` is needed the first time and after dependency changes, to build the `dev` images. If changes are not picked up, e.g. Docker Desktop or a repository under `/mnt/c` in WSL2, set `WATCHFILES_FORCE_POLLING=true` in `.env`.

The frontend has no hot reload in Docker; see [Frontend](./frontend) to run its dev server. To debug the backend from VS Code, see [Backend](./backend#debugging).

## Storage

The local bucket is a folder on your machine, `data/versitygw/` by default, with one subfolder per bucket. Files uploaded from the application appear there, and files copied there appear in the application.

The folder and the user that owns its files are set in `.env`, see the storage section of `.env.copy`.

On WSL2 keep the folder on the Linux file system, not under `/mnt/c`.

## Logs

Each job has its own log, opened with **Logs** on the job in the Pipelines page. It shows the steps while the job runs and the error when it fails.

For the services themselves, follow them from the terminal:

```bash
docker compose logs -f worker-vector
```

## Reset

```bash
docker compose down -v
```

Removes the containers and the database. The files in `data/` stay; delete the folder to start from an empty bucket.
