"""Typed per-pipeline-type config, replacing the untyped JSONB `data` blob."""
from pydantic import BaseModel, ConfigDict, field_validator


class PointCloudConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    colorization_image: str | None = None
    sample_radius: float | None = None
    # fallback CRS, used when the point cloud or its source carry none of their own
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


AXES = ("X", "Y", "Z", "NEGATIVE_X", "NEGATIVE_Y", "NEGATIVE_Z")


class MeshConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # WGS84 position of the mesh origin (0,0,0)
    latitude: float = 0
    longitude: float = 0
    altitude: float = 0
    depth: int = 4
    tile_faces_target: int = 10000
    texture_image_size: int = 512
    # None: from the mesh diagonal
    max_geometric_error: float | None = 256
    decimate_last_depth_level: bool = True
    # file axes mapped to north (forward) and up
    forward_axis: str = "Y"
    up_axis: str = "Z"

    @field_validator("max_geometric_error", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v

    @field_validator("forward_axis", "up_axis")
    @classmethod
    def _axis(cls, v):
        if v not in AXES:
            raise ValueError(f"axis must be one of {', '.join(AXES)}")
        return v

    @field_validator("depth")
    @classmethod
    def _depth(cls, v):
        if not 0 <= v <= 8:
            raise ValueError("depth must be between 0 and 8")
        return v
