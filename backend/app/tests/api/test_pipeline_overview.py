import uuid
from datetime import datetime, timezone

from celery.states import FAILURE, PENDING, STARTED, SUCCESS

from app.core.config import settings
from app.core.storage import output_key
from app.models.pipeline import PipelineLog
from app.tests.api.conftest import fresh

BASE = f"{settings.API_V1_STR}/pipelines"


def overview(client):
    return client.get(f"{BASE}/overview", params={"limit": 1000}).json()


def batch_source(prefix, name):
    return {
        "key": f"city/{name}",
        "pipeline": "PointCloud",
        "output_base": f"{prefix}/{name}",
        "batch_output_prefix": prefix,
    }


def test_overview_shows_a_batch_as_one_entry(client, make_pipeline, fake_celery):
    before = overview(client)["count"]
    batch_id = uuid.uuid4()
    prefix = output_key("City")
    make_pipeline(
        title="City / a.laz",
        source=batch_source(prefix, "a"),
        batch_id=batch_id,
        task_status=SUCCESS,
    )
    make_pipeline(
        title="City / b.laz",
        source=batch_source(prefix, "b"),
        batch_id=batch_id,
        task_status=FAILURE,
    )
    make_pipeline(
        title="City / c.laz", source=batch_source(prefix, "c"), batch_id=batch_id
    )
    solo = make_pipeline(title="single run")

    body = overview(client)
    assert body["count"] == before + 2

    [entry] = [
        e
        for e in body["data"]
        if e["kind"] == "batch" and e["batch"]["batch_id"] == str(batch_id)
    ]
    batch = entry["batch"]
    assert batch["label"] == "City"
    assert batch["total"] == 3
    assert batch["counts"] == {"success": 1, "running": 0, "ready": 1, "failed": 1}
    assert batch["output_prefix"] == prefix
    assert any(
        e["kind"] == "pipeline" and e["pipeline"]["id"] == str(solo.id)
        for e in body["data"]
    )


def test_lost_task_is_marked_failed(client, db, make_pipeline, fake_celery):
    row = make_pipeline(task_id="lost", task_status=PENDING)
    fake_celery.states["lost"] = FAILURE
    client.get(f"{BASE}/")
    assert fresh(db, row.id).task_status == FAILURE


def test_lost_task_completing_a_batch_rebuilds_it(client, make_pipeline, fake_celery):
    batch_id = uuid.uuid4()
    prefix = output_key("City")
    make_pipeline(
        source=batch_source(prefix, "a"),
        batch_id=batch_id,
        task_id="ok",
        task_status=SUCCESS,
    )
    make_pipeline(
        source=batch_source(prefix, "b"),
        batch_id=batch_id,
        task_id="lost",
        task_status=STARTED,
    )
    fake_celery.states["lost"] = FAILURE

    client.get(f"{BASE}/overview")
    finalize = [t for t in fake_celery.sent if t.name == "finalize_tileset_batch"]
    assert [t.kwargs["output_prefix"] for t in finalize] == [prefix]


def test_running_pipeline_shows_its_latest_stage(
    client, db, make_pipeline, fake_celery
):
    batch_id = uuid.uuid4()
    row = make_pipeline(batch_id=batch_id, task_id="t1", task_status=STARTED)
    now = datetime.now(timezone.utc)
    for stage in ("Downloading input", None, "Tiling"):
        db.add(
            PipelineLog(
                pipeline_id=row.id,
                created_at=now,
                level="INFO",
                message="m",
                stage=stage,
            )
        )
    db.commit()

    data = client.get(f"{BASE}/", params={"batch_id": str(batch_id)}).json()["data"]
    assert [d["stage"] for d in data] == ["Tiling"]


def test_finalize_queues_the_batch_rebuild(client, make_pipeline, fake_celery):
    batch_id = uuid.uuid4()
    prefix = output_key("City")
    make_pipeline(source=batch_source(prefix, "a"), batch_id=batch_id)
    assert client.post(f"{BASE}/batch/{batch_id}/finalize").json() == {"ok": True}
    assert [t.kwargs["output_prefix"] for t in fake_celery.sent] == [prefix]
