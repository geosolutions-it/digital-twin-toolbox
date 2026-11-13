import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models.task import Pipeline, PipelineLog
from app.models.user import User


@pytest.fixture
def pipeline(db: Session):
    owner = db.exec(select(User)).first()
    row = Pipeline(title="logs", task_id=None, task_status=None, owner_id=owner.id)
    db.add(row)
    db.commit()
    now = datetime.now(timezone.utc)
    for i in range(5):
        db.add(PipelineLog(pipeline_id=row.id, created_at=now, level="INFO", message=f"line {i}",
                           stage="Roofer: cropping" if i == 2 else None))
    db.commit()
    yield row
    if db.get(Pipeline, row.id) is not None:
        db.delete(row)
        db.commit()


def url(pipeline_id):
    return f"{settings.API_V1_STR}/pipelines/{pipeline_id}/logs"


def test_returns_lines_oldest_first(client: TestClient, pipeline):
    data = client.get(url(pipeline.id)).json()["data"]
    assert [d["message"] for d in data] == [f"line {i}" for i in range(5)]
    assert data[2]["stage"] == "Roofer: cropping"
    assert data[0]["level"] == "INFO"


def test_after_and_limit_page_through_new_lines(client: TestClient, pipeline):
    first = client.get(url(pipeline.id), params={"limit": 2}).json()["data"]
    assert [d["message"] for d in first] == ["line 0", "line 1"]
    rest = client.get(url(pipeline.id), params={"after": first[-1]["id"]}).json()["data"]
    assert [d["message"] for d in rest] == ["line 2", "line 3", "line 4"]
    assert client.get(url(pipeline.id), params={"after": rest[-1]["id"]}).json()["data"] == []


def test_running_pipeline_lists_its_latest_stage(client: TestClient, db: Session, pipeline):
    def listed():
        rows = client.get(f"{settings.API_V1_STR}/pipelines/", params={"limit": 1000}).json()["data"]
        return next(r for r in rows if r["id"] == str(pipeline.id))

    assert listed()["stage"] is None
    pipeline.task_status = "STARTED"
    db.add(pipeline)
    db.commit()
    assert listed()["stage"] == "Roofer: cropping"
    overview = client.get(f"{settings.API_V1_STR}/pipelines/overview", params={"limit": 1000}).json()["data"]
    solo = next(e["pipeline"] for e in overview if e["pipeline"] and e["pipeline"]["id"] == str(pipeline.id))
    assert solo["stage"] == "Roofer: cropping"


def test_unknown_pipeline_is_not_found(client: TestClient):
    assert client.get(url(uuid.uuid4())).status_code == 404


def test_deleting_the_pipeline_deletes_its_log(db: Session, pipeline):
    pipeline_id = pipeline.id
    db.delete(pipeline)
    db.commit()
    assert db.exec(select(PipelineLog).where(PipelineLog.pipeline_id == pipeline_id)).all() == []


def test_worker_write_keeps_the_newest_lines(db: Session, pipeline, monkeypatch):
    from app.worker.common import logs

    monkeypatch.setattr(logs, "MAX_LINES", 3)
    now = datetime.now(timezone.utc)
    logs._write_rows(pipeline.id, [
        {"pipeline_id": pipeline.id, "created_at": now, "level": "INFO", "message": f"new {i}", "stage": None}
        for i in range(2)
    ])
    db.expire_all()
    kept = db.exec(select(PipelineLog).where(PipelineLog.pipeline_id == pipeline.id).order_by(PipelineLog.id)).all()
    assert [r.message for r in kept] == ["line 4", "new 0", "new 1"]
