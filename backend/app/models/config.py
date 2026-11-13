"""Typed per-pipeline-type config, replacing the untyped JSONB `data` blob."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# a constant, or an expression array evaluated per feature by worker/common/expression.py
Expression = float | str | list[Any]


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


Axis = Literal["X", "Y", "Z", "NEGATIVE_X", "NEGATIVE_Y", "NEGATIVE_Z"]


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
    forward_axis: Axis = "Y"
    up_axis: Axis = "Z"

    @field_validator("max_geometric_error", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v

    @field_validator("depth")
    @classmethod
    def _depth(cls, v):
        if not 0 <= v <= 8:
            raise ValueError("depth must be between 0 and 8")
        return v


class CityGMLConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # None: the highest each object has
    lod: int | None = None
    to_ellipsoidal_height: bool = False
    # used when the file declares none
    horizontal_epsg: int | None = None
    vertical_epsg: int | None = None
    max_tile_size_kb: float = 400
    orthophoto: str | None = None
    # m per texel; None: the orthophoto's
    texture_resolution: float | None = None

    @field_validator("lod", "horizontal_epsg", "vertical_epsg", "orthophoto", "texture_resolution", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v

    @field_validator("texture_resolution")
    @classmethod
    def _resolution(cls, v):
        if v is not None and v <= 0:
            raise ValueError("texture_resolution must be positive")
        return v

    @field_validator("lod")
    @classmethod
    def _lod(cls, v):
        if v is not None and not 0 <= v <= 4:
            raise ValueError("lod must be between 0 and 4")
        return v


BuildingLod = Literal["1.2", "1.3", "2.2"]


class BuildingConfig(BaseModel):
    """The footprint file is the pipeline source."""
    model_config = ConfigDict(extra="ignore")

    # LAS/LAZ key, or a folder ending with /
    point_cloud: str = ""
    orthophoto: str | None = None
    dtm: str | None = None
    lod: BuildingLod = "2.2"
    building_class: int = 6
    ground_class: int = 2
    to_ellipsoidal_height: bool = False
    # m per texel; None: the orthophoto's
    texture_resolution: float | None = None
    max_tile_size_kb: float = 400

    @field_validator("orthophoto", "dtm", "texture_resolution", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v

    @field_validator("point_cloud")
    @classmethod
    def _point_cloud(cls, v):
        if not v or not v.strip():
            raise ValueError("point_cloud is required")
        return v.strip()

    @field_validator("lod", mode="before")
    @classmethod
    def _lod(cls, v):
        return str(v or "2.2")

    @field_validator("texture_resolution")
    @classmethod
    def _resolution(cls, v):
        if v is not None and v <= 0:
            raise ValueError("texture_resolution must be positive")
        return v


class PolygonConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lower_limit_height: Expression | None = None
    upper_limit_height: Expression | None = None
    to_ellipsoidal_height: bool = False
    remove_bottom_surface: bool = True
    max_tile_size_kb: float = Field(400, gt=0)

    @field_validator("lower_limit_height", "upper_limit_height", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v


class TerrainConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    to_ellipsoidal_height: bool = False
    # vertical CRS of the DEM heights
    source_vertical_epsg: int = 3855
    min_zoom: int = Field(0, ge=0)
    # None: from the DEM resolution
    max_zoom: int | None = Field(None, ge=0)
    vertex_normals: bool = True
    # vector key of the water mask
    water_key: str | None = None

    @field_validator("max_zoom", "water_key", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v


class InstanceConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # glb name, appended to models_prefix
    model: str | list[Any] = "model.glb"
    models_prefix: str = ""
    # degrees
    rotation: Expression = 0.0
    scale: Expression = 1.0
    # None: the point's own height
    elevation: Expression | None = None
    to_ellipsoidal_height: bool = False
    max_tile_size_kb: float = Field(1024, gt=0)
    max_geometric_error: float = Field(500, gt=0)

    @field_validator("elevation", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v


CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "PointCloud": PointCloudConfig,
    "Polygon": PolygonConfig,
    "Terrain": TerrainConfig,
    "Instance": InstanceConfig,
    "Mesh": MeshConfig,
    "CityGML": CityGMLConfig,
    "Building": BuildingConfig,
}
