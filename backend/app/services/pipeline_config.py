"""Validate and normalize a pipeline's config by type.

Point-cloud and mesh have typed schemas; other types pass through. Pydantic
ValidationError subclasses ValueError, so a bad config maps to HTTP 422 via the
route's existing ValueError handler.
"""
from app.models.config import MeshConfig, PointCloudConfig


_MODELS = {"PointCloud": PointCloudConfig, "Mesh": MeshConfig}


def validate_pipeline_config(pipeline_type, data):
    model = _MODELS.get(pipeline_type)
    if model is None:
        return data
    return model(**(data or {})).model_dump()
