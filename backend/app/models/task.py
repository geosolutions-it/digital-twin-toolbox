import uuid
from typing import Optional
from enum import Enum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class AssetBase(SQLModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    content_size: int | None = None
    asset_type: str | None = None
    extension: str | None = None
    geometry_type: str | None = None
    upload_id: str | None = None
    upload_status: str | None = None
    upload_result: Optional[dict | None] | None = Field(nullable=True, sa_type=JSONB)


class Asset(AssetBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )


class AssetPublic(AssetBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class AssetsPublic(SQLModel):
    data: list[AssetPublic]
    count: int


class PipelineBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    asset_id: uuid.UUID | None
    data: Optional[dict] = Field(nullable=True, sa_type=JSONB)
    task_id: str | None
    task_status: str | None
    task_result: Optional[dict | None] | None = Field(nullable=True, sa_type=JSONB)


class Pipeline(PipelineBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )


class PipelinePublic(PipelineBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class PipelinePublicExtended(PipelinePublic):
    asset: Asset | None


class PipelineCreate(PipelineBase):
    title: str = Field(min_length=1, max_length=255)


class PipelinesPublic(SQLModel):
    data: list[PipelinePublic]
    count: int


class PipelineUpdate(SQLModel):
    data: Optional[dict] = Field(nullable=True, sa_type=JSONB)


class PipelinesActionTypes(str, Enum):
    run = "run"
    cancel = "cancel"


class Message(SQLModel):
    message: str
