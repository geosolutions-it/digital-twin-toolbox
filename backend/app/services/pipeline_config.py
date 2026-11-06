"""Validate and normalize a pipeline's config by type.

Point-cloud and mesh have typed schemas; other types pass through. Pydantic
ValidationError subclasses ValueError, so a bad config maps to HTTP 422 via the
route's existing ValueError handler.
"""
from app.models.config import MeshConfig, PointCloudConfig


def config_model_for(geometry_type: str | None, asset_type: str | None):
    if geometry_type == "PointCloud":
        return PointCloudConfig
    if geometry_type == "Mesh" or asset_type == "Mesh":
        return MeshConfig
    return None


def validate_pipeline_config(geometry_type, asset_type, data):
    model = config_model_for(geometry_type, asset_type)
    if model is None:
        return data
    return model(**(data or {})).model_dump()
