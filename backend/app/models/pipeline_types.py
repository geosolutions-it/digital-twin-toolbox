"""A new pipeline type goes in both PipelineType and PIPELINES; a test checks they match."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.models.config import (
    BuildingConfig,
    CityGMLConfig,
    InstanceConfig,
    MeshConfig,
    PointCloudConfig,
    PolygonConfig,
    TerrainConfig,
)

PipelineType = Literal[
    "PointCloud", "Polygon", "Terrain", "Instance", "Mesh", "CityGML", "Building"
]


@dataclass(frozen=True)
class PipelineSpec:
    task: str
    queue: str
    config: type[BaseModel]
    # file type from services.file_classify that the pipeline runs on
    accepts: str
    batch: bool = True


PIPELINES: dict[PipelineType, PipelineSpec] = {
    "PointCloud": PipelineSpec(
        "create_point_cloud_3dtiles", "point-cloud", PointCloudConfig, "PointCloud"
    ),
    "Polygon": PipelineSpec(
        "create_polygon_3dtiles", "vector", PolygonConfig, "Polygon"
    ),
    "Terrain": PipelineSpec("create_terrain_tiles", "vector", TerrainConfig, "Terrain"),
    "Instance": PipelineSpec(
        "create_point_instance_3dtiles", "vector", InstanceConfig, "Polygon"
    ),
    "Mesh": PipelineSpec("create_mesh_3dtiles", "mesh", MeshConfig, "Mesh"),
    "CityGML": PipelineSpec(
        "create_citygml_3dtiles", "vector", CityGMLConfig, "CityGML"
    ),
    "Building": PipelineSpec(
        "create_building_3dtiles", "vector", BuildingConfig, "Polygon", batch=False
    ),
}


def pipeline_type_of(source: dict | None) -> PipelineType:
    ptype = (source or {}).get("pipeline")
    return ptype if ptype in PIPELINES else "PointCloud"


def validate_pipeline_config(pipeline_type: str, data: dict | None) -> dict | None:
    """Pydantic's ValidationError is a ValueError, so routes map it to 422."""
    spec = PIPELINES.get(pipeline_type)
    if spec is None:
        return data
    return spec.config(**(data or {})).model_dump()


def resolve_pipeline(requested: PipelineType, file_type: str | None) -> PipelineType:
    """Pipeline for one file: the requested one when it fits the file, otherwise the
    file's own. Instance and Building are explicit choices, so a mismatch is an error."""
    spec = PIPELINES[requested]
    if file_type == spec.accepts:
        return requested
    if requested != spec.accepts:
        raise ValueError(f"{requested} needs a {spec.accepts.lower()} file")
    if file_type in PIPELINES:
        return file_type
    raise ValueError("Unsupported file")


def batch_targets(classified, workflow):
    """(key, file type) pairs the batch workflow runs on, retagged as (key, workflow)."""
    spec = PIPELINES.get(workflow)
    if spec is None or not spec.batch:
        raise ValueError(f"{workflow} does not run in a batch")
    return [(k, workflow) for k, t in classified if t == spec.accepts]
