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
    source: Optional[dict] = Field(default=None, nullable=True, sa_type=JSONB)
    batch_id: uuid.UUID | None = Field(default=None, nullable=True, index=True)


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


class PipelineBatchCreate(SQLModel):
    prefix: str
    pipeline: str = "PointCloud"
    data: Optional[dict] = None
    title: str | None = None


class PipelineSourceCreate(SQLModel):
    key: str
    pipeline: str = "PointCloud"
    data: Optional[dict] = None
    title: str | None = None


class PipelinesPublic(SQLModel):
    data: list[PipelinePublic]
    count: int


class PipelineBatchCounts(SQLModel):
    success: int = 0
    running: int = 0
    ready: int = 0
    failed: int = 0


class PipelineBatchSummary(SQLModel):
    batch_id: uuid.UUID
    label: str
    source: str | None = None
    output_prefix: str | None = None
    pipeline: str | None = None
    sample_key: str | None = None
    data: Optional[dict] = None
    total: int
    counts: PipelineBatchCounts


class PipelineOverviewEntry(SQLModel):
    # kind is "batch" (folder) or "pipeline" (standalone row)
    kind: str
    batch: PipelineBatchSummary | None = None
    pipeline: PipelinePublic | None = None


class PipelinesOverview(SQLModel):
    data: list[PipelineOverviewEntry]
    count: int


class PipelineUpdate(SQLModel):
    data: Optional[dict] = Field(nullable=True, sa_type=JSONB)


class PipelinesActionTypes(str, Enum):
    run = "run"
    cancel = "cancel"


class Message(SQLModel):
    message: str
