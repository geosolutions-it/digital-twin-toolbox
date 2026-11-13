import os
import re
import uuid
from typing import Any

from celery.states import SUCCESS
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.dialects.postgresql import distinct_on
from sqlmodel import delete, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.celery_app import celery
from app.core.storage import get_storage, output_key, output_root, output_url
from app.models.inspect import MeshBbox, VectorFields, VectorSample
from app.models.pipeline import (
    MAX_LOG_LINES,
    FinalizeQueued,
    Message,
    Pipeline,
    PipelineActionResult,
    PipelineBatch,
    PipelineBatchActionResult,
    PipelineBatchCounts,
    PipelineBatchCreate,
    PipelineBatchCreated,
    PipelineBatchSummary,
    PipelineBatchUpdated,
    PipelineCreated,
    PipelineLog,
    PipelineLogsPublic,
    PipelineOverviewEntry,
    PipelinePublic,
    PipelinesActionTypes,
    PipelineSourceCreate,
    PipelinesOverview,
    PipelinesPublic,
    PipelineUpdate,
)
from app.models.pipeline_types import (
    PIPELINES,
    batch_targets,
    pipeline_type_of,
    resolve_pipeline,
    validate_pipeline_config,
)
from app.services.file_classify import SUPPORTED_EXTENSIONS, classify_bucket_file
from app.services.pipeline_lifecycle import (
    IN_PROGRESS,
    apply_action,
    create_and_dispatch,
    queue_batch_finalize,
    revoke_running,
    sync_lost_tasks,
)

router = APIRouter()


@router.get("/", response_model=PipelinesPublic)
def read_pipelines(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    batch_id: uuid.UUID | None = None,
) -> Any:
    """
    Retrieve pipelines. Pass batch_id to page through one batch's members.
    """
    sync_lost_tasks(session)
    count_statement = select(func.count()).select_from(Pipeline)
    statement = select(Pipeline)
    if batch_id is not None:
        count_statement = count_statement.where(Pipeline.batch_id == batch_id)
        statement = statement.where(Pipeline.batch_id == batch_id)
    count = session.exec(count_statement).one()
    statement = statement.order_by(Pipeline.title.asc()).offset(skip).limit(limit)
    pipelines = session.exec(statement).all()

    return PipelinesPublic(data=_with_stage(session, pipelines), count=count)


def _with_stage(session, pipelines) -> list[PipelinePublic]:
    running = [p.id for p in pipelines if p.task_status in IN_PROGRESS]
    stages = {}
    if running:
        latest = (
            select(func.max(PipelineLog.id))
            .where(PipelineLog.pipeline_id.in_(running), PipelineLog.stage.is_not(None))
            .group_by(PipelineLog.pipeline_id)
        )
        stages = dict(
            session.exec(
                select(PipelineLog.pipeline_id, PipelineLog.stage).where(
                    PipelineLog.id.in_(latest)
                )
            ).all()
        )
    return [
        PipelinePublic.model_validate(p, update={"stage": stages.get(p.id)})
        for p in pipelines
    ]


def _classify_status(status: str | None) -> str:
    if status == SUCCESS:
        return "success"
    if status in IN_PROGRESS:
        return "running"
    if not status:
        return "ready"
    return "failed"


def _batch_label(batch: PipelineBatch) -> str:
    return batch.title or f"Batch {str(batch.id)[:8]}"


def _batch_counts(session, batch_ids) -> dict[uuid.UUID, PipelineBatchCounts]:
    counts: dict[uuid.UUID, PipelineBatchCounts] = {}
    if not batch_ids:
        return counts
    rows = session.exec(
        select(Pipeline.batch_id, Pipeline.task_status, func.count())
        .where(Pipeline.batch_id.in_(batch_ids))
        .group_by(Pipeline.batch_id, Pipeline.task_status)
    ).all()
    for batch_id, status, n in rows:
        c = counts.setdefault(batch_id, PipelineBatchCounts())
        key = _classify_status(status)
        setattr(c, key, getattr(c, key) + n)
    return counts


def _first_keys(session, batch_ids) -> dict[uuid.UUID, str | None]:
    """Each batch's member with the smallest title: its file feeds the edit dialog's preview."""
    if not batch_ids:
        return {}
    rows = session.exec(
        select(Pipeline.batch_id, Pipeline.source)
        .where(Pipeline.batch_id.in_(batch_ids))
        .ext(distinct_on(Pipeline.batch_id))
        .order_by(Pipeline.batch_id, Pipeline.title)
    ).all()
    return {batch_id: (source or {}).get("key") for batch_id, source in rows}


def _batch_summary(batch, counts, sample_key) -> PipelineBatchSummary:
    folder = batch.prefix.strip("/")
    return PipelineBatchSummary(
        batch_id=batch.id,
        label=_batch_label(batch),
        source=f"s3://…/{folder}/" if folder else None,
        output_prefix=batch.output_prefix,
        output_url=output_url(batch.output_prefix) if batch.output_prefix else None,
        pipeline=batch.pipeline,
        sample_key=sample_key,
        data=batch.data,
        total=counts.success + counts.running + counts.ready + counts.failed,
        counts=counts,
    )


@router.get("/overview", response_model=PipelinesOverview)
def read_pipelines_overview(session: SessionDep, skip: int = 0, limit: int = 10) -> Any:
    """
    Top-level list for the pipelines screen: each batch is one folder entry with
    a rollup over all its members, standalone pipelines are their own entries.
    Paginates over entries (folders + solo), not raw pipeline rows.
    """
    sync_lost_tasks(session)
    batches = session.exec(select(PipelineBatch)).all()
    solo = session.exec(
        select(Pipeline.id, Pipeline.title).where(Pipeline.batch_id.is_(None))
    ).all()
    entries = [(_batch_label(b).lower(), b) for b in batches] + [
        ((title or "").lower(), pipeline_id) for pipeline_id, title in solo
    ]
    entries.sort(key=lambda e: e[0])
    page = [item for _, item in entries[skip : skip + limit]]

    page_batches = [item for item in page if isinstance(item, PipelineBatch)]
    page_batch_ids = [b.id for b in page_batches]
    counts = _batch_counts(session, page_batch_ids)
    first_keys = _first_keys(session, page_batch_ids)
    solo_ids = [item for item in page if not isinstance(item, PipelineBatch)]
    solo_rows = {}
    if solo_ids:
        solo_rows = {
            p.id: p
            for p in _with_stage(
                session,
                session.exec(select(Pipeline).where(Pipeline.id.in_(solo_ids))).all(),
            )
        }

    data = []
    for item in page:
        if isinstance(item, PipelineBatch):
            summary = _batch_summary(
                item,
                counts.get(item.id, PipelineBatchCounts()),
                first_keys.get(item.id),
            )
            data.append(PipelineOverviewEntry(kind="batch", batch=summary))
        elif item in solo_rows:
            data.append(
                PipelineOverviewEntry(kind="pipeline", pipeline=solo_rows[item])
            )

    return PipelinesOverview(data=data, count=len(entries))


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value or "").strip("-")
    return value or "batch"


@router.post("/source", response_model=PipelineCreated)
def create_pipeline_source(
    *, session: SessionDep, current_user: CurrentUser, source_in: PipelineSourceCreate
) -> Any:
    """Create and dispatch one pipeline from a single bucket file."""
    storage = get_storage()
    if not storage.exists(source_in.key):
        raise HTTPException(status_code=404, detail=f"No such file: {source_in.key!r}")

    try:
        pipeline_type = resolve_pipeline(
            source_in.pipeline, classify_bucket_file(storage, source_in.key)
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"{e}: {source_in.key!r}")

    try:
        data = validate_pipeline_config(pipeline_type, source_in.data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    key = source_in.key
    base_name = (
        _slug(source_in.title)
        if source_in.title
        else os.path.splitext(os.path.basename(key))[0]
    )
    pipeline = create_and_dispatch(
        session,
        title=source_in.title or os.path.basename(key),
        data=data,
        source={
            "key": key,
            "extension": os.path.splitext(key)[1],
            "output_base": _unique_output(storage, base_name),
            "pipeline": pipeline_type,
        },
        owner_id=current_user.id,
    )
    return {"id": str(pipeline.id)}


def _unique_output(storage, name: str) -> str:
    out, i = name, 1
    while storage.list(output_key(out) + "/"):
        out = f"{name}-{i}"
        i += 1
    return output_key(out)


@router.post("/batch", response_model=PipelineBatchCreated)
def create_pipeline_batch(
    *, session: SessionDep, current_user: CurrentUser, batch_in: PipelineBatchCreate
) -> Any:
    """
    Run the picked workflow on every matching file under a bucket prefix, one pipeline
    per file. File types are detected from contents (zips are peeked).
    """
    if not PIPELINES[batch_in.pipeline].batch:
        raise HTTPException(
            status_code=422, detail=f"{batch_in.pipeline} does not run in a batch"
        )
    try:
        data = validate_pipeline_config(batch_in.pipeline, batch_in.data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")
    storage = get_storage()
    skip = output_root() + "/"
    candidates = [
        k
        for k in storage.list(batch_in.prefix)
        if k.lower().endswith(SUPPORTED_EXTENSIONS) and not k.startswith(skip)
    ]
    classified = batch_targets(
        [(k, classify_bucket_file(storage, k)) for k in candidates], batch_in.pipeline
    )
    if not classified:
        raise HTTPException(
            status_code=404,
            detail=f"No {batch_in.pipeline} files under prefix {batch_in.prefix!r}",
        )

    root = batch_in.prefix.strip("/")
    # name the output after the batch title (falls back to the input folder); keep it
    # unique so a new batch never overwrites another batch's output.
    base_name = _slug(batch_in.title) if batch_in.title else (root or "batch")
    out_root = _unique_output(storage, base_name)

    rels = [key[len(root) :].lstrip("/") if root else key for key, _ in classified]
    stems = [os.path.splitext(r)[0] for r in rels]
    batch = PipelineBatch(
        title=batch_in.title or None,
        prefix=batch_in.prefix,
        pipeline=batch_in.pipeline,
        data=data,
        output_prefix=out_root,
        owner_id=current_user.id,
    )
    session.add(batch)
    session.commit()
    created = []
    for (key, ptype), rel, stem in zip(classified, rels, stems, strict=True):
        name = os.path.basename(key)
        ext = os.path.splitext(rel)[1]
        # same stem, different extension (x.las + x.laz) keeps the extension apart
        output_base = (
            f"{out_root}/{stem}_{ext[1:]}"
            if stems.count(stem) > 1
            else f"{out_root}/{stem}"
        )
        pipeline = create_and_dispatch(
            session,
            title=f"{batch_in.title} / {name}" if batch_in.title else name,
            data=data,
            source={
                "key": key,
                "extension": os.path.splitext(key)[1],
                "output_base": output_base,
                "pipeline": ptype,
            },
            owner_id=current_user.id,
            batch_id=batch.id,
        )
        created.append(str(pipeline.id))

    return {
        "batch_id": str(batch.id),
        "count": len(created),
        "pipeline_ids": created,
    }


@router.post("/batch/{batch_id}/finalize", response_model=FinalizeQueued)
def finalize_pipeline_batch(*, session: SessionDep, batch_id: uuid.UUID) -> Any:
    """Rebuild the combined tileset for a batch from whatever child tilesets exist."""
    batch = session.get(PipelineBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    if not batch.output_prefix:
        raise HTTPException(status_code=422, detail="Batch has no output prefix")
    queue_batch_finalize(batch.output_prefix)
    return {"ok": True}


def _validated_update(pipeline: Pipeline, pipeline_in: PipelineUpdate) -> dict:
    update_dict = pipeline_in.model_dump(exclude_unset=True)
    if "data" in update_dict:
        ptype = pipeline_type_of(pipeline.source)
        try:
            update_dict["data"] = validate_pipeline_config(ptype, update_dict["data"])
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid config: {e}")
    return update_dict


@router.put("/batch/{batch_id}", response_model=PipelineBatchUpdated)
def update_pipeline_batch(
    *, session: SessionDep, batch_id: uuid.UUID, pipeline_in: PipelineUpdate
) -> Any:
    """Apply one config to the batch and every pipeline in it."""
    batch = session.get(PipelineBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    pipelines = session.exec(
        select(Pipeline).where(Pipeline.batch_id == batch_id)
    ).all()
    update_dict = pipeline_in.model_dump(exclude_unset=True)
    if "data" in update_dict:
        try:
            update_dict["data"] = validate_pipeline_config(
                batch.pipeline, update_dict["data"]
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid config: {e}")
        batch.data = update_dict["data"]
        session.add(batch)
    for pipeline in pipelines:
        pipeline.sqlmodel_update(update_dict)
        session.add(pipeline)
    session.commit()
    return {"batch_id": str(batch_id), "count": len(pipelines)}


def _bucket_target(key: str | None, prefix: str | None, workflow: str) -> str:
    """The given key, or the first file under prefix that classifies as workflow."""
    if key:
        return key
    if prefix:
        storage = get_storage()
        for k in storage.list(prefix):
            if (
                k.lower().endswith(SUPPORTED_EXTENSIONS)
                and classify_bucket_file(storage, k) == workflow
            ):
                return k
    raise HTTPException(status_code=404, detail=f"No {workflow.lower()} file found")


@router.get("/vector-fields", response_model=VectorFields)
def vector_fields(*, key: str | None = None, prefix: str | None = None) -> Any:
    """Attribute schema and first-feature values of a bucket vector."""
    target = _bucket_target(key, prefix, "Polygon")
    try:
        return celery.send_task(
            "read_vector_fields", kwargs={"options": {"key": target}}
        ).get(timeout=30)
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Could not read vector fields: {e}"
        )


@router.get("/vector-sample", response_model=VectorSample)
def vector_sample(
    *,
    key: str | None = None,
    prefix: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    ellipsoidal: bool = False,
) -> Any:
    """Neighbouring features of a bucket vector as WGS84 GeoJSON."""
    target = _bucket_target(key, prefix, "Polygon")
    try:
        return celery.send_task(
            "read_vector_sample",
            kwargs={
                "options": {"key": target, "limit": limit, "ellipsoidal": ellipsoidal}
            },
        ).get(timeout=60)
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Could not read vector sample: {e}"
        )


@router.get("/mesh-bbox", response_model=MeshBbox)
def mesh_bbox(*, key: str | None = None, prefix: str | None = None) -> Any:
    """Mesh size and origin offset in file axes."""
    target = _bucket_target(key, prefix, "Mesh")
    try:
        bbox = celery.send_task(
            "read_mesh_bbox", kwargs={"options": {"key": target}}
        ).get(timeout=120)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read mesh: {e}")
    if not bbox:
        raise HTTPException(status_code=422, detail="Mesh has no vertices")
    return {"key": target, **bbox}


@router.post("/{id}/task/{action_type}", response_model=PipelineActionResult)
def process_pipeline_task(
    *, session: SessionDep, id: uuid.UUID, action_type: PipelinesActionTypes
) -> Any:
    """
    Run/cancel the pipeline task.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    try:
        pipeline_out = apply_action(session, pipeline, action_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Unsupported pipeline config: {e}")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="It was not possible to initialize the requested task",
        )
    return {**pipeline_out, "action_type": action_type}


@router.post(
    "/batch/{batch_id}/task/{action_type}", response_model=PipelineBatchActionResult
)
def process_pipeline_batch_task(
    *, session: SessionDep, batch_id: uuid.UUID, action_type: PipelinesActionTypes
) -> Any:
    """Run/cancel every member of a batch, skipping rows the action does not apply to."""
    pipelines = session.exec(
        select(Pipeline).where(Pipeline.batch_id == batch_id)
    ).all()
    if not pipelines:
        raise HTTPException(status_code=404, detail="Batch not found")
    affected = 0
    for pipeline in pipelines:
        try:
            if apply_action(session, pipeline, action_type):
                affected += 1
        except Exception:
            # skip members the action cannot apply to (already running, nothing to cancel, bad config)
            session.rollback()
    return {
        "batch_id": str(batch_id),
        "count": len(pipelines),
        "affected": affected,
        "action_type": action_type,
    }


@router.delete("/batch/{batch_id}")
def delete_pipeline_batch(session: SessionDep, batch_id: uuid.UUID) -> Message:
    """Delete a batch, every member (database cascade) and its combined output tree."""
    batch = session.get(PipelineBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch_prefix = batch.output_prefix
    pipelines = session.exec(
        select(Pipeline).where(Pipeline.batch_id == batch_id)
    ).all()
    for pipeline in pipelines:
        revoke_running(pipeline)
    session.exec(delete(PipelineBatch).where(PipelineBatch.id == batch_id))
    session.commit()

    # drop the whole batch output tree in one shot (no per-member finalize needed)
    if batch_prefix:
        try:
            get_storage().delete_prefix(batch_prefix + "/")
        except Exception:
            pass

    return Message(message=f"Deleted {len(pipelines)} pipelines")


@router.put("/{id}", response_model=PipelinePublic)
def update_pipeline(
    *,
    session: SessionDep,
    id: uuid.UUID,
    pipeline_in: PipelineUpdate,
) -> Any:
    """
    Update a pipeline.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    update_dict = _validated_update(pipeline, pipeline_in)
    pipeline.sqlmodel_update(update_dict)
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    return pipeline


@router.get("/{id}", response_model=PipelinePublic)
def read_pipeline(session: SessionDep, id: uuid.UUID) -> Any:
    """
    Get pipeline by ID.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.get("/{id}/logs", response_model=PipelineLogsPublic)
def read_pipeline_logs(
    session: SessionDep,
    _user: CurrentUser,
    id: uuid.UUID,
    after: int = Query(0, ge=0),
    limit: int = Query(MAX_LOG_LINES, ge=1, le=MAX_LOG_LINES),
) -> Any:
    """
    Log lines of the pipeline's latest run with id > after, oldest first. Poll with the last id received.
    """
    if session.get(Pipeline, id) is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    statement = (
        select(PipelineLog)
        .where(PipelineLog.pipeline_id == id, PipelineLog.id > after)
        .order_by(PipelineLog.id)
        .limit(limit)
    )
    return PipelineLogsPublic(data=session.exec(statement).all())


@router.delete("/{id}")
def delete_pipeline(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an pipeline.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    source = pipeline.source or {}
    output_prefix = source.get("output_base") or output_key(str(pipeline.id))
    batch = session.get(PipelineBatch, pipeline.batch_id) if pipeline.batch_id else None
    batch_prefix = batch.output_prefix if batch else None

    revoke_running(pipeline)
    session.delete(pipeline)
    session.commit()
    if batch is not None:
        remaining = session.exec(
            select(func.count()).where(Pipeline.batch_id == batch.id)
        ).one()
        if remaining == 0:
            session.delete(batch)
            session.commit()

    try:
        get_storage().delete_prefix(output_prefix + "/")
    except Exception:
        pass

    # rebuild the combined tileset so it stops referencing the removed child
    if batch_prefix:
        queue_batch_finalize(batch_prefix)

    return Message(message="Pipeline deleted successfully")
