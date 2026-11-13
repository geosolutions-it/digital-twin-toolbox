"""Typed per-pipeline-type config, replacing the untyped JSONB `data` blob."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def _blank_is_none(v):
    # a blank form field means "not provided" (use the default), not an error
    return None if isinstance(v, str) and not v.strip() else v


_Blank = BeforeValidator(_blank_is_none)
OptionalInt = Annotated[int | None, _Blank]
OptionalFloat = Annotated[float | None, _Blank]
OptionalStr = Annotated[str | None, _Blank]

# a constant, or an expression array evaluated per feature by worker/common/expression.py
Expression = float | str | list[Any]
OptionalExpression = Annotated[Expression | None, _Blank]


class PointCloudConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    colorization_image: str | None = None
    sample_radius: OptionalFloat = None
    # fallback CRS, used when the point cloud or its source carry none of their own
    horizontal_epsg: OptionalInt = None
    vertical_epsg: OptionalInt = None
    to_ellipsoidal_height: bool = False
    ground_classification: bool = False


Axis = Literal["X", "Y", "Z", "NEGATIVE_X", "NEGATIVE_Y", "NEGATIVE_Z"]


class MeshConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # WGS84 position of the mesh origin (0,0,0)
    latitude: float = 0
    longitude: float = 0
    altitude: float = 0
    depth: int = Field(4, ge=0, le=8)
    tile_faces_target: int = 10000
    texture_image_size: int = 512
    # None: from the mesh diagonal
    max_geometric_error: OptionalFloat = 256
    decimate_last_depth_level: bool = True
    # file axes mapped to north (forward) and up
    forward_axis: Axis = "Y"
    up_axis: Axis = "Z"


class CityGMLConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # None: the highest each object has
    lod: OptionalInt = Field(None, ge=0, le=4)
    to_ellipsoidal_height: bool = False
    # used when the file declares none
    horizontal_epsg: OptionalInt = None
    vertical_epsg: OptionalInt = None
    max_tile_size_kb: float = 400
    orthophoto: OptionalStr = None
    # m per texel; None: the orthophoto's
    texture_resolution: OptionalFloat = Field(None, gt=0)


BuildingLod = Literal["1.2", "1.3", "2.2"]


class BuildingConfig(BaseModel):
    """The footprint file is the pipeline source."""

    model_config = ConfigDict(extra="ignore")

    # LAS/LAZ key, or a folder ending with /
    point_cloud: str = ""
    orthophoto: OptionalStr = None
    dtm: OptionalStr = None
    lod: BuildingLod = "2.2"
    building_class: int = 6
    ground_class: int = 2
    to_ellipsoidal_height: bool = False
    # m per texel; None: the orthophoto's
    texture_resolution: OptionalFloat = Field(None, gt=0)
    max_tile_size_kb: float = 400

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


class PolygonConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lower_limit_height: OptionalExpression = None
    upper_limit_height: OptionalExpression = None
    to_ellipsoidal_height: bool = False
    remove_bottom_surface: bool = True
    max_tile_size_kb: float = Field(400, gt=0)


class TerrainConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    to_ellipsoidal_height: bool = False
    # vertical CRS of the DEM heights
    source_vertical_epsg: int = 3855
    min_zoom: int = Field(0, ge=0)
    # None: from the DEM resolution
    max_zoom: OptionalInt = Field(None, ge=0)
    vertex_normals: bool = True
    # vector key of the water mask
    water_key: OptionalStr = None


class InstanceConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # glb name, appended to models_prefix
    model: str | list[Any] = "model.glb"
    models_prefix: str = ""
    # degrees
    rotation: Expression = 0.0
    scale: Expression = 1.0
    # None: the point's own height
    elevation: OptionalExpression = None
    to_ellipsoidal_height: bool = False
    max_tile_size_kb: float = Field(1024, gt=0)
    max_geometric_error: float = Field(500, gt=0)
