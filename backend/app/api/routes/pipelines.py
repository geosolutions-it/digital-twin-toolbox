from app.api.deps import CurrentUser, SessionDep
from fastapi import APIRouter, HTTPException, Query
from typing import Any
from sqlmodel import func, select
import os
import re
import uuid
from app.models.task import Pipeline, PipelinePublic, PipelinesPublic, PipelineBatchCreate, PipelineSourceCreate, Message, PipelinesActionTypes, PipelineUpdate, PipelineBatchCounts, PipelineBatchSummary, PipelineOverviewEntry, PipelinesOverview

from app.services.pipeline_config import validate_pipeline_config
from app.services.file_classify import classify_bucket_file, SUPPORTED_EXTENSIONS
from app.core.storage import get_storage, output_key, output_root, output_url
from app.core.config import settings
from app.worker.main import celery
from celery.result import AsyncResult
from celery.states import REVOKED, PENDING, SUCCESS, STARTED

router = APIRouter()

@router.get("/", response_model=PipelinesPublic)
def read_pipelines(
    session: SessionDep, skip: int = 0, limit: int = 100, batch_id: uuid.UUID | None = None
) -> Any:
    """
    Retrieve pipelines. Pass batch_id to page through one batch's members.
    """
    count_statement = select(func.count()).select_from(Pipeline)
    statement = select(Pipeline)
    if batch_id is not None:
        count_statement = count_statement.where(Pipeline.batch_id == batch_id)
        statement = statement.where(Pipeline.batch_id == batch_id)
    count = session.exec(count_statement).one()
    statement = statement.order_by(Pipeline.title.asc()).offset(skip).limit(limit)
    pipelines = session.exec(statement).all()

    return PipelinesPublic(data=pipelines, count=count)


# in-progress (PENDING/STARTED) mirrors the frontend's isCeleryTaskInProgress
_IN_PROGRESS = (PENDING, STARTED)


def _classify_status(status: str | None) -> str:
    if status == SUCCESS:
        return "success"
    if status in _IN_PROGRESS:
        return "running"
    if not status:
        return "ready"
    return "failed"


def _batch_label(title: str | None, batch_id) -> str:
    if title and " / " in title:
        return title.split(" / ")[0]
    return f"Batch {str(batch_id)[:8]}"


@router.get("/overview", response_model=PipelinesOverview)
def read_pipelines_overview(
    session: SessionDep, skip: int = 0, limit: int = 10
) -> Any:
    """
    Top-level list for the pipelines screen: each batch is one folder entry with
    a rollup over all its members, standalone pipelines are their own entries.
    Paginates over entries (folders + solo), not raw pipeline rows.
    """
    rows = session.exec(
        select(
            Pipeline.id,
            Pipeline.title,
            Pipeline.task_status,
            Pipeline.batch_id,
            Pipeline.source,
            Pipeline.data,
        )
    ).all()

    batches: dict[str, dict] = {}
    solo: list[dict] = []
    for r in rows:
        if r.batch_id:
            key = str(r.batch_id)
            b = batches.get(key)
            if b is None:
                b = {
                    "batch_id": r.batch_id,
                    "rep_title": r.title,
                    "rep_source": r.source,
                    "rep_data": r.data,
                    "counts": {"success": 0, "running": 0, "ready": 0, "failed": 0},
                    "total": 0,
                }
                batches[key] = b
            # representative = smallest title, matching the members' title ordering
            if r.title is not None and (b["rep_title"] is None or r.title < b["rep_title"]):
                b["rep_title"] = r.title
                b["rep_source"] = r.source
                b["rep_data"] = r.data
            b["counts"][_classify_status(r.task_status)] += 1
            b["total"] += 1
        else:
            solo.append({"id": r.id, "title": r.title or ""})

    entries: list[dict] = []
    for b in batches.values():
        label = _batch_label(b["rep_title"], b["batch_id"])
        src = b["rep_source"] or {}
        key = src.get("key") or ""
        src_dir = key[: key.rfind("/")] if "/" in key else ""
        entries.append(
            {
                "sort": label.lower(),
                "summary": PipelineBatchSummary(
                    batch_id=b["batch_id"],
                    label=label,
                    source=f"s3://…/{src_dir}/" if src_dir else None,
                    output_prefix=src.get("batch_output_prefix"),
                    output_url=output_url(src["batch_output_prefix"]) if src.get("batch_output_prefix") else None,
                    pipeline=src.get("pipeline") or "PointCloud",
                    sample_key=key or None,
                    data=b["rep_data"],
                    total=b["total"],
                    counts=PipelineBatchCounts(**b["counts"]),
                ),
            }
        )
    for s in solo:
        entries.append({"sort": s["title"].lower(), "solo_id": s["id"]})

    entries.sort(key=lambda e: e["sort"])
    count = len(entries)
    page = entries[skip : skip + limit]

    solo_ids = [e["solo_id"] for e in page if "solo_id" in e]
    full = {}
    if solo_ids:
        full = {
            p.id: p
            for p in session.exec(select(Pipeline).where(Pipeline.id.in_(solo_ids))).all()
        }

    data = []
    for e in page:
        if "summary" in e:
            data.append(PipelineOverviewEntry(kind="batch", batch=e["summary"]))
        else:
            pipeline = full.get(e["solo_id"])
            if pipeline is not None:
                data.append(PipelineOverviewEntry(kind="pipeline", pipeline=pipeline))

    return PipelinesOverview(data=data, count=count)

_SOURCE_TASK = {
    "PointCloud": "create_point_cloud_3dtiles",
    "Polygon": "create_polygon_3dtiles",
    "Terrain": "create_terrain_tiles",
    "Instance": "create_point_instance_3dtiles",
    "Mesh": "create_mesh_3dtiles",
}


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value or "").strip("-")
    return value or "batch"


@router.post("/source", response_model=Any)
def create_pipeline_source(
    *, session: SessionDep, current_user: CurrentUser, source_in: PipelineSourceCreate
) -> Any:
    """Create and dispatch one pipeline from a single bucket file."""
    storage = get_storage()
    if not storage.exists(source_in.key):
        raise HTTPException(status_code=404, detail=f"No such file: {source_in.key!r}")

    pipeline_type = classify_bucket_file(storage, source_in.key)
    if source_in.pipeline == "Instance" and pipeline_type == "Polygon":
        pipeline_type = "Instance"
    dispatch_task = _SOURCE_TASK.get(pipeline_type)
    if dispatch_task is None:
        raise HTTPException(status_code=422, detail=f"Unsupported file: {source_in.key!r}")

    try:
        data = validate_pipeline_config(pipeline_type, source_in.data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    key = source_in.key
    base_name = _slug(source_in.title) if source_in.title else os.path.splitext(os.path.basename(key))[0]
    output_base = _unique_output(storage, base_name)
    pipeline = Pipeline(
        title=source_in.title or os.path.basename(key),
        data=data,
        task_id=None,
        task_status=None,
        task_result=None,
        source={
            "key": key,
            "extension": os.path.splitext(key)[1],
            "output_base": output_base,
            "pipeline": pipeline_type,
        },
        batch_id=None,
        owner_id=current_user.id,
    )
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)

    task = celery.send_task(dispatch_task, kwargs={"pipeline_extended": pipeline.model_dump()})
    pipeline.sqlmodel_update({"task_id": task.id, "task_status": PENDING})
    session.add(pipeline)
    session.commit()

    return {"id": str(pipeline.id)}


def _unique_output(storage, name: str) -> str:
    out, i = name, 1
    while storage.list(output_key(out) + "/"):
        out = f"{name}-{i}"
        i += 1
    return output_key(out)


@router.post("/batch", response_model=Any)
def create_pipeline_batch(
    *, session: SessionDep, current_user: CurrentUser, batch_in: PipelineBatchCreate
) -> Any:
    """
    Create and dispatch one pipeline per supported file under a bucket prefix.
    Each file's workflow is detected from its contents (zips are peeked).
    """
    storage = get_storage()
    skip = output_root() + "/"
    candidates = [
        k for k in storage.list(batch_in.prefix)
        if k.lower().endswith(SUPPORTED_EXTENSIONS) and not k.startswith(skip)
    ]
    classified = [(k, classify_bucket_file(storage, k)) for k in candidates]
    if batch_in.pipeline == "Instance":
        classified = [(k, "Instance") for k, t in classified if t == "Polygon"]
    elif batch_in.pipeline == "Mesh":
        classified = [(k, t) for k, t in classified if t == "Mesh"]
    else:
        # meshes need their own lat/lon, so only a Mesh batch picks them up
        classified = [(k, t) for k, t in classified if t in _SOURCE_TASK and t != "Mesh"]
    if not classified:
        raise HTTPException(status_code=404, detail=f"No supported files under prefix {batch_in.prefix!r}")

    root = batch_in.prefix.strip("/")
    # name the output after the batch title (falls back to the input folder); keep it
    # unique so a new batch never overwrites another batch's output.
    base_name = _slug(batch_in.title) if batch_in.title else (root or "batch")
    out_root = _unique_output(storage, base_name)

    configs = {}
    for ptype in {t for _, t in classified}:
        try:
            configs[ptype] = validate_pipeline_config(ptype, batch_in.data)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    rels = [key[len(root):].lstrip("/") if root else key for key, _ in classified]
    stems = [os.path.splitext(r)[0] for r in rels]
    batch_id = uuid.uuid4()
    created = []
    for (key, ptype), rel, stem in zip(classified, rels, stems):
        data = configs[ptype]
        name = os.path.basename(key)
        ext = os.path.splitext(rel)[1]
        # same stem, different extension (x.las + x.laz) keeps the extension apart
        output_base = f"{out_root}/{stem}_{ext[1:]}" if stems.count(stem) > 1 else f"{out_root}/{stem}"
        pipeline = Pipeline(
            title=f"{batch_in.title} / {name}" if batch_in.title else name,
            data=data,
            task_id=None,
            task_status=None,
            task_result=None,
            source={
                "key": key,
                "extension": os.path.splitext(key)[1],
                "output_base": output_base,
                "batch_output_prefix": out_root,
                "batch_output_url": output_url(out_root),
                "pipeline": ptype,
            },
            batch_id=batch_id,
            owner_id=current_user.id,
        )
        session.add(pipeline)
        session.commit()
        session.refresh(pipeline)
        # dump while the row is fresh; a later commit would expire it and drop columns (incl. id)
        task = celery.send_task(_SOURCE_TASK[ptype], kwargs={"pipeline_extended": pipeline.model_dump()})
        pipeline.sqlmodel_update({"task_id": task.id, "task_status": PENDING})
        session.add(pipeline)
        session.commit()
        created.append(str(pipeline.id))

    return {
        "batch_id": str(batch_id),
        "count": len(created),
        "pipeline_ids": created,
    }


@router.post("/batch/{batch_id}/finalize", response_model=Any)
def finalize_pipeline_batch(
    *, session: SessionDep, batch_id: uuid.UUID
) -> Any:
    """Rebuild the combined tileset for a batch from whatever child tilesets exist."""
    pipeline = session.exec(
        select(Pipeline).where(Pipeline.batch_id == batch_id).limit(1)
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Batch not found")
    prefix = (pipeline.source or {}).get('batch_output_prefix')
    if not prefix:
        raise HTTPException(status_code=422, detail="Batch has no output prefix")
    celery.send_task(
        'finalize_tileset_batch',
        kwargs={'output_prefix': prefix, 'base': settings.API_V1_STR},
    )
    return {"ok": True}


@router.put("/batch/{batch_id}", response_model=Any)
def update_pipeline_batch(
    *, session: SessionDep, batch_id: uuid.UUID, pipeline_in: PipelineUpdate
) -> Any:
    """Apply one config to every pipeline in a batch."""
    pipelines = session.exec(select(Pipeline).where(Pipeline.batch_id == batch_id)).all()
    if not pipelines:
        raise HTTPException(status_code=404, detail="Batch not found")
    update_dict = pipeline_in.model_dump(exclude_unset=True)
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
            if k.lower().endswith(SUPPORTED_EXTENSIONS) and classify_bucket_file(storage, k) == workflow:
                return k
    raise HTTPException(status_code=404, detail=f"No {workflow.lower()} file found")


@router.get("/vector-fields", response_model=Any)
def vector_fields(
    *, key: str | None = None, prefix: str | None = None
) -> Any:
    """Attribute schema and first-feature values of a bucket vector."""
    target = _bucket_target(key, prefix, "Polygon")
    try:
        return celery.send_task(
            "read_vector_fields", kwargs={"options": {"key": target}}
        ).get(timeout=30)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read vector fields: {e}")


@router.get("/vector-sample", response_model=Any)
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
            kwargs={"options": {"key": target, "limit": limit, "ellipsoidal": ellipsoidal}},
        ).get(timeout=60)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read vector sample: {e}")


@router.get("/mesh-bbox", response_model=Any)
def mesh_bbox(*, key: str | None = None, prefix: str | None = None) -> Any:
    """Mesh size and origin offset in file axes."""
    target = _bucket_target(key, prefix, "Mesh")
    try:
        bbox = celery.send_task("read_mesh_bbox", kwargs={"options": {"key": target}}).get(timeout=120)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read mesh: {e}")
    if not bbox:
        raise HTTPException(status_code=422, detail="Mesh has no vertices")
    return {"key": target, **bbox}


def _apply_pipeline_action(session, pipeline: Pipeline, action_type: PipelinesActionTypes) -> dict:
    """Run/cancel one pipeline, persisting the new task state. Returns the applied fields.
    Raises ValueError for unsupported configs; callers decide how to surface it."""
    pipeline_out = {}
    if action_type == 'run' and pipeline.task_status not in (PENDING, STARTED):
        ptype = (pipeline.source or {}).get('pipeline') or 'PointCloud'
        task_name = _SOURCE_TASK.get(ptype)
        if not task_name:
            raise ValueError(f"Unsupported source pipeline: {ptype}")
        payload = pipeline.model_dump()
        payload['data'] = validate_pipeline_config(ptype, payload.get('data'))
        task = celery.send_task(task_name, kwargs={"pipeline_extended": payload})
        pipeline_out = {"task_id": task.id, "task_status": PENDING, "task_result": None}
        pipeline.sqlmodel_update(pipeline_out)
        session.add(pipeline)
        session.commit()
        session.refresh(pipeline)

    if action_type == 'cancel' and pipeline.task_id and pipeline.task_status in (PENDING, STARTED):
        AsyncResult(pipeline.task_id, app=celery).revoke(terminate=True)
        pipeline_out = {
            "task_id": pipeline.task_id,
            "task_status": REVOKED,
            "task_result": None
        }
        pipeline.sqlmodel_update(pipeline_out)
        session.add(pipeline)
        session.commit()
        session.refresh(pipeline)
    return pipeline_out


@router.post("/{id}/task/{action_type}", response_model=Any)
async def process_pipeline_task(
    *, session: SessionDep, id: uuid.UUID, action_type: PipelinesActionTypes
) -> Any:
    """
    Run/cancel the pipeline task.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    try:
        pipeline_out = _apply_pipeline_action(session, pipeline, action_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Unsupported pipeline config: {e}")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="It was not possible to initialize the requested task")
    return {
        **pipeline_out,
        'action_type': action_type
    }


@router.post("/batch/{batch_id}/task/{action_type}", response_model=Any)
def process_pipeline_batch_task(
    *, session: SessionDep, batch_id: uuid.UUID, action_type: PipelinesActionTypes
) -> Any:
    """Run/cancel every member of a batch, skipping rows the action does not apply to."""
    pipelines = session.exec(select(Pipeline).where(Pipeline.batch_id == batch_id)).all()
    if not pipelines:
        raise HTTPException(status_code=404, detail="Batch not found")
    affected = 0
    for pipeline in pipelines:
        try:
            if _apply_pipeline_action(session, pipeline, action_type):
                affected += 1
        except Exception:
            # skip members the action cannot apply to (already running, nothing to cancel, bad config)
            session.rollback()
    return {"batch_id": str(batch_id), "count": len(pipelines), "affected": affected, "action_type": action_type}


@router.delete("/batch/{batch_id}")
def delete_pipeline_batch(
    session: SessionDep, batch_id: uuid.UUID
) -> Message:
    """Delete every member of a batch and its combined output tree."""
    pipelines = session.exec(select(Pipeline).where(Pipeline.batch_id == batch_id)).all()
    if not pipelines:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch_prefix = None
    payloads = []
    for pipeline in pipelines:
        source = pipeline.source or {}
        batch_prefix = batch_prefix or source.get('batch_output_prefix')
        payloads.append(pipeline.model_dump())
        session.delete(pipeline)
    session.commit()

    # drop the whole batch output tree in one shot (no per-member finalize needed)
    if batch_prefix:
        try:
            get_storage().delete_prefix(batch_prefix + "/")
        except Exception:
            pass
    for payload in payloads:
        celery.send_task('complete_pipeline_remove_process', args=[{'pipeline': payload}])

    return Message(message=f"Deleted {len(payloads)} pipelines")


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
    update_dict = pipeline_in.model_dump(exclude_unset=True)
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

@router.delete("/{id}")
def delete_pipeline(
    session: SessionDep, id: uuid.UUID
) -> Message:
    """
    Delete an pipeline.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    source = pipeline.source or {}
    output_prefix = source.get('output_base') or output_key(str(pipeline.id))
    batch_prefix = source.get('batch_output_prefix')
    payload = pipeline.model_dump()

    session.delete(pipeline)
    session.commit()

    try:
        get_storage().delete_prefix(output_prefix + "/")
    except Exception:
        pass

    # rebuild the combined tileset so it stops referencing the removed child
    if batch_prefix:
        celery.send_task(
            'finalize_tileset_batch',
            kwargs={'output_prefix': batch_prefix, 'base': settings.API_V1_STR},
        )

    celery.send_task('complete_pipeline_remove_process', args=[{'pipeline': payload}])

    return Message(message="Pipeline deleted successfully")
