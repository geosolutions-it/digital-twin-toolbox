from sqlmodel import SQLModel

from app.models.pipeline_types import PipelineType


class StorageFile(SQLModel):
    key: str
    name: str
    size: int
    # the pipeline the file runs with by default; None when nothing handles it
    pipeline: PipelineType | None = None


class StorageListing(SQLModel):
    prefix: str
    folders: list[str]
    files: list[StorageFile]
