import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import ConfigDict, field_validator
from sqlalchemy import BigInteger, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.pipeline_types import PIPELINES, PipelineType


class PipelineBatch(SQLModel, table=True):
    """One run over every matching file under a bucket folder; its members are Pipeline rows."""

    __tablename__ = "pipeline_batch"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # None: shown as "Batch <id prefix>"
    title: str | None = Field(default=None, max_length=255)
    prefix: str
    pipeline: str
    data: dict | None = Field(default=None, nullable=True, sa_type=JSONB)
    output_prefix: str | None = None
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class PipelineBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    data: dict | None = Field(nullable=True, sa_type=JSONB)
    task_id: str | None
    task_status: str | None
    task_result: dict | None = Field(nullable=True, sa_type=JSONB)
    source: dict | None = Field(default=None, nullable=True, sa_type=JSONB)
    batch_id: uuid.UUID | None = Field(
        default=None,
        nullable=True,
        index=True,
        foreign_key="pipeline_batch.id",
        ondelete="CASCADE",
    )


class Pipeline(PipelineBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )


# lines kept per run: the worker drops older ones, the API pages up to this many
MAX_LOG_LINES = 5000


class PipelineLog(SQLModel, table=True):
    __tablename__ = "pipeline_log"

    id: int | None = Field(default=None, primary_key=True, sa_type=BigInteger)
    pipeline_id: uuid.UUID = Field(
        foreign_key="pipeline.id", nullable=False, ondelete="CASCADE", index=True
    )
    created_at: datetime = Field(sa_type=DateTime(timezone=True))
    level: str = Field(max_length=10)
    message: str = Field(sa_type=Text)
    stage: str | None = Field(default=None, max_length=255)


class PipelineLogPublic(SQLModel):
    id: int
    created_at: datetime
    level: str
    message: str
    stage: str | None = None


class PipelineLogsPublic(SQLModel):
    data: list[PipelineLogPublic]


class PipelineSource(SQLModel):
    """The `source` JSON column. Rows outlive code changes, so every field is optional."""

    model_config = ConfigDict(extra="ignore")

    key: str | None = None
    extension: str | None = None
    output_base: str | None = None
    pipeline: PipelineType | None = None

    @field_validator("pipeline", mode="before")
    @classmethod
    def _known_pipeline(cls, v):
        return v if v in PIPELINES else None


class OutputArtifact(SQLModel):
    name: str
    url: str
    size: int | None = None


class TaskResult(SQLModel):
    """The `task_result` JSON column a finished run writes."""

    model_config = ConfigDict(extra="ignore")

    output: str | None = None
    tileset: str | None = None
    download: str | None = None
    artifacts: list[OutputArtifact] = []
    # terrain
    extent: list[float] | None = None
    min_zoom: int | None = None
    max_zoom: int | None = None
    # point cloud
    sample_radius: float | None = None
    sample_radius_auto: bool | None = None


class PipelinePublic(PipelineBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    source: PipelineSource | None = None
    task_result: TaskResult | None = None
    # latest stage logged by a running job
    stage: str | None = None


class PipelineBatchCreate(SQLModel):
    prefix: str
    pipeline: PipelineType = "PointCloud"
    data: dict | None = None
    title: str | None = None


class PipelineSourceCreate(SQLModel):
    key: str
    pipeline: PipelineType = "PointCloud"
    data: dict | None = None
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
    # input folder as stored, and its display form
    prefix: str
    source: str | None = None
    output_prefix: str | None = None
    output_url: str | None = None
    pipeline: PipelineType | None = None
    sample_key: str | None = None
    data: dict | None = None
    total: int
    counts: PipelineBatchCounts


class PipelineOverviewEntry(SQLModel):
    kind: Literal["batch", "pipeline"]
    batch: PipelineBatchSummary | None = None
    pipeline: PipelinePublic | None = None


class PipelinesOverview(SQLModel):
    data: list[PipelineOverviewEntry]
    count: int


class PipelineUpdate(SQLModel):
    data: dict | None = None
    # re-points the pipeline to another file; the output folder stays the same
    source_key: str | None = None


class PipelineBatchUpdate(SQLModel):
    data: dict | None = None
    # re-points every member to the same relative path under another folder
    prefix: str | None = None


class PipelinesActionTypes(str, Enum):
    run = "run"
    cancel = "cancel"


class PipelineCreated(SQLModel):
    id: uuid.UUID


class PipelineBatchCreated(SQLModel):
    batch_id: uuid.UUID
    count: int
    pipeline_ids: list[uuid.UUID]


class PipelineBatchUpdated(SQLModel):
    batch_id: uuid.UUID
    count: int


class PipelineActionResult(SQLModel):
    action_type: PipelinesActionTypes
    # unset when the action did not apply (already running, nothing to cancel)
    task_id: str | None = None
    task_status: str | None = None
    task_result: dict | None = None


class PipelineBatchActionResult(SQLModel):
    batch_id: uuid.UUID
    count: int
    affected: int
    action_type: PipelinesActionTypes


class FinalizeQueued(SQLModel):
    ok: bool


class Message(SQLModel):
    message: str
