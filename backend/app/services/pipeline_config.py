"""Validate and normalize a pipeline's config by type.

Only point-cloud has a typed schema today; other types pass through. Pydantic
ValidationError subclasses ValueError, so a bad config maps to HTTP 422 via the
route's existing ValueError handler.
"""
from app.models.config import PointCloudConfig


def config_model_for(geometry_type: str | None, asset_type: str | None):
    if geometry_type == "PointCloud":
        return PointCloudConfig
    return None


def validate_pipeline_config(geometry_type, asset_type, data):
    model = config_model_for(geometry_type, asset_type)
    if model is None:
        return data
    return model(**(data or {})).model_dump()
