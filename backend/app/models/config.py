"""Typed per-pipeline-type config, replacing the untyped JSONB `data` blob."""
from pydantic import BaseModel, ConfigDict, field_validator


class PointCloudConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    colorization_image: str | None = None
    sample_radius: float | None = None
    # fallback CRS, used when the point cloud / asset / source carry none of their own
    horizontal_epsg: int | None = None
    vertical_epsg: int | None = None
    to_ellipsoidal_height: bool = False
    ground_classification: bool = False

    @field_validator("sample_radius", "horizontal_epsg", "vertical_epsg", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        # an empty/blank field means "not provided" (auto radius / CRS from file), not an error
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v
