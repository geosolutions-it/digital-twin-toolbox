from typing import Any, Literal

from sqlmodel import SQLModel


class VectorField(SQLModel):
    name: str
    type: str


class VectorFields(SQLModel):
    count: int
    fields: list[VectorField]
    # first feature's values
    properties: dict[str, Any]
    geometry_type: str


class SampleGeometry(SQLModel):
    type: str
    coordinates: Any


class SampleFeature(SQLModel):
    type: Literal["Feature"]
    geometry: SampleGeometry | None
    properties: dict[str, Any] | None


class VectorSample(SQLModel):
    type: Literal["FeatureCollection"]
    features: list[SampleFeature]


class MeshBbox(SQLModel):
    key: str
    # file axes, metres
    size: tuple[float, float, float]
    # bbox centre relative to the model origin
    offset: tuple[float, float, float]
