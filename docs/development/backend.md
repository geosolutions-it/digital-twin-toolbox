# Backend

The backend is one Python project in `backend/`, used by two images: the **API** (FastAPI) and the **worker** (Celery, with PDAL, GDAL, Roofer and the 3D libraries). Work on it with the [hot reload stack](./#hot-reload): the code is mounted in the containers and restarts on save.

## Dependencies

Python dependencies are managed with [uv](https://docs.astral.sh/uv/) in `backend/pyproject.toml`. Each image installs only the groups it needs; the `uv sync` line of `Dockerfile` and `Dockerfile.worker` shows which.

After adding or changing a dependency, update the lock file and rebuild the images:

```bash
cd backend
uv lock
docker compose build
```

The worker also needs system libraries such as PDAL and GDAL, installed in `Dockerfile.worker`. Run the workflows and their tests in the worker container, not on your machine.

## How a job runs

1. The frontend calls `POST /api/v1/pipelines/source` (one file) or `/pipelines/batch` (a folder).
2. The route validates the options, stores the job in Postgres and sends the Celery task of the workflow to its queue. Both are set per workflow in `app/models/pipeline_types.py`.
3. The worker service listening to that queue downloads the input from the bucket, builds the tiles in a temporary folder and uploads them under `output/`. Its log lines are stored with the job and shown in the application.
4. `PipelineDatabaseTask` writes the result and the status to the job. When the last job of a batch ends, the combined tileset task is queued.

## Worker code

The worker code in `app/worker/` is split by what it may depend on:

| Folder | Holds | May import |
| --- | --- | --- |
| `lib/` | geometry, CRS, glTF and 3D Tiles code, without Celery, database or settings | only other `lib/` modules and third-party packages |
| `runtime/` | the task base class, job logs, subprocesses, publishing the output | `lib/` and the rest of `app/` |
| `tasks/<workflow>/` | one workflow: its Celery task in `task.py` and its own helpers | `lib/`, `runtime/`, its own folder |
| `queues/` | one module per worker service, listing the tasks it runs | the `task.py` modules |

A workflow never imports another workflow: shared code goes to `lib/`. Workers in other images hand work over by task name through the queue, not by importing it. `tests/worker/test_import_rules.py` enforces these rules.

Each worker service loads its `queues/` module with `--include` in the compose files. Its `TASKS` tuple registers the tasks, and `tests/worker/test_task_registration.py` checks it matches the queues of `pipeline_types.py`.

New tilers should be covered by a test that runs `check_tileset` from `lib/tiles3d/check.py` on their output: it checks the tileset structure, the bounding volumes and the GLB content.

## Adding a workflow

Follow an existing one, e.g. CityGML: search its task name `create_citygml_3dtiles` and its workflow name `CityGML` across `backend/app` and `frontend/src`. A workflow needs:

1. A config model in `app/models/config.py`. Base it on `HeightConfig` if it converts heights.
2. A task in `app/worker/tasks/<workflow>/task.py`, built on `TaskContext` from `app/worker/runtime/task.py`, which gives the source, the config, the storage, a scratch folder and the publishing of the output.
3. The task in the `TASKS` of the `queues/` module of its worker service.
4. An entry in `app/models/pipeline_types.py`: task name, queue, config and accepted file type.
5. A form in `frontend/src/components/Pipelines/forms/`, after regenerating the API types, see [Frontend](./frontend#api-types).
6. A page in `docs/guide/workflows/`.

## Tests

From the repository root, build the test images and run every test in a clean stack:

```bash
./scripts/test.sh
```

On the hot reload stack, run them in the running containers instead. The API tests need the database, the workflow tests need the worker image:

```bash
docker compose exec backend bash /app/tests-start.sh app/tests --ignore=app/tests/worker
docker compose exec worker-vector bash /app/test.sh app/tests/worker
```

Arguments go to pytest, e.g. `-x` to stop at the first failure or `-k citygml` to filter.

## Migrations

The API container runs `alembic upgrade head` at every start. After changing a table in `app/models/`, generate a migration in the running backend:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe the change"
```

With hot reload the file lands in `backend/app/alembic/versions/`. Review it, then apply it with `docker compose restart backend`: the reload on save restarts the API but not the migrations.

Changes to the stored job options, such as a renamed option, need a data migration of the `data` column of `pipeline` and `pipeline_batch`, otherwise saved jobs lose the value.

## Lint and format

[Ruff](https://docs.astral.sh/ruff/) checks and formats the code, configured in `pyproject.toml`. CI runs the same commands:

```bash
cd backend
uv run ruff check app
uv run ruff format app
```

## Debugging

The development backend runs under [debugpy](https://github.com/microsoft/debugpy), listening on port `5678`. In VS Code, run **Attach to backend container** from `.vscode/launch.json`, then set breakpoints in `backend/app`: requests from the application stop there. Attach again when the session ends, e.g. after the container restarts.

This covers the API only, not the workers.
