"""Tasks of the vector worker service (--include in docker-compose*.yml)."""

from app.worker.tasks.building.task import create_building_3dtiles
from app.worker.tasks.citygml.task import create_citygml_3dtiles
from app.worker.tasks.inspect.task import read_vector_fields, read_vector_sample
from app.worker.tasks.instance.task import create_point_instance_3dtiles
from app.worker.tasks.polygon.task import create_polygon_3dtiles
from app.worker.tasks.terrain.task import create_terrain_tiles

TASKS = (
    create_building_3dtiles,
    create_citygml_3dtiles,
    create_point_instance_3dtiles,
    create_polygon_3dtiles,
    create_terrain_tiles,
    read_vector_fields,
    read_vector_sample,
)
