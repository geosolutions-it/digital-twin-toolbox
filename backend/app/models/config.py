"""Typed per-pipeline-type config, replacing the untyped JSONB `data` blob."""
from pydantic import BaseModel, ConfigDict


class PointCloudConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    colorization_image: str | None = None
    sample_radius: float | None = None
    to_ellipsoidal_height: bool = False
    ground_classification: bool = False
    geometric_error_scale_factor: float = 1.0
