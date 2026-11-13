"""Tasks of the mesh worker service (--include in docker-compose*.yml)."""

from app.worker.tasks.mesh.task import create_mesh_3dtiles, read_mesh_bbox

TASKS = (create_mesh_3dtiles, read_mesh_bbox)
