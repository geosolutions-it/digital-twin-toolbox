"""Tasks of the point-cloud worker service (--include in docker-compose*.yml)."""

from app.worker.tasks.pointcloud.task import create_point_cloud_3dtiles

TASKS = (create_point_cloud_3dtiles,)
