"""Validate and normalize a pipeline's config by type.

Pydantic ValidationError subclasses ValueError, so a bad config maps to HTTP 422 via the
route's existing ValueError handler.
"""
from app.models.config import CONFIG_MODELS


def validate_pipeline_config(pipeline_type, data):
    model = CONFIG_MODELS.get(pipeline_type)
    if model is None:
        return data
    return model(**(data or {})).model_dump()
