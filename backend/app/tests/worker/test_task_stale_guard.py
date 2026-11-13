import uuid
from contextlib import nullcontext

import pytest
from celery.states import FAILURE, IGNORED, STARTED, SUCCESS
from sqlalchemy.dialects import postgresql

from app.core.celery_app import celery
from app.services import pipeline_lifecycle as lifecycle
from app.worker.runtime import task as runtime_task
from app.worker.runtime.task import PipelineDatabaseTask

PID = str(uuid.uuid4())
calls = {}


@celery.task(name="test_stale_guard_task", base=PipelineDatabaseTask)
def guarded(**_kwargs):
    calls["run"] = calls.get("run", 0) + 1
    return {"ok": True}


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    calls.clear()
    state = {"owned": True, "claims": [], "writes": []}

    def claim(pipeline_id, task_id):
        state["claims"].append((pipeline_id, task_id))
        return state["owned"]

    def write(pipeline_id, task_id, values):
        state["writes"].append((pipeline_id, task_id, values))

    monkeypatch.setattr(runtime_task, "claim_row", claim)
    monkeypatch.setattr(runtime_task, "write_result", write)
    monkeypatch.setattr(
        runtime_task, "capture_pipeline_log", lambda _pid: nullcontext()
    )
    return state


def run(task_id="t-1", **kwargs):
    kwargs.setdefault("pipeline_extended", {"id": PID})
    return guarded.apply(kwargs=kwargs, task_id=task_id)


def test_not_owned_is_ignored_without_run_or_write(fake_db):
    fake_db["owned"] = False
    result = run()
    assert result.state == IGNORED
    assert "run" not in calls
    # Celery skips after_return for IGNORED, so the row is never written
    assert fake_db["writes"] == []
    assert fake_db["claims"] == [(PID, "t-1")]


def test_owned_runs_and_writes_result(fake_db):
    result = run()
    assert result.state == SUCCESS
    assert calls["run"] == 1
    assert fake_db["writes"] == [
        (PID, "t-1", {"task_status": SUCCESS, "task_result": {"ok": True}})
    ]


def test_failure_writes_status_without_result(fake_db, monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr(guarded, "run", boom)
    result = run()
    assert result.state == FAILURE
    assert fake_db["writes"] == [(PID, "t-1", {"task_status": FAILURE})]


def test_without_pipeline_payload_skips_guard(fake_db):
    guarded.apply(kwargs={}, task_id="t-2")
    assert calls["run"] == 1
    assert fake_db["claims"] == []
    assert fake_db["writes"] == []


def _sql(stmt):
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_owned_update_is_conditional_and_keeps_task_id():
    sql = _sql(lifecycle.owned_update(PID, "t-1", {"task_status": STARTED}))
    where = sql.split("WHERE", 1)[1]
    assert "pipeline.task_id =" in where
    assert "pipeline.task_status IS DISTINCT FROM" in where
    assert "task_id" not in sql.split("WHERE", 1)[0].split("SET", 1)[1]


class FakeResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class FakeSession:
    rowcount = 1

    def __init__(self, *_):
        self.got = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def exec(self, _stmt):
        return FakeResult(FakeSession.rowcount)

    def commit(self):
        pass

    def get(self, _model, pid):
        self.got.append(pid)
        return object()


@pytest.mark.parametrize("rowcount, owned", [(1, True), (0, False)])
def test_claim_row_reports_ownership(monkeypatch, rowcount, owned):
    monkeypatch.undo()
    monkeypatch.setattr(lifecycle, "Session", FakeSession)
    monkeypatch.setattr(FakeSession, "rowcount", rowcount)
    assert lifecycle.claim_row(PID, "t-1") is owned


@pytest.mark.parametrize("rowcount, finalized", [(1, 1), (0, 0)])
def test_write_result_finalizes_only_when_owned(monkeypatch, rowcount, finalized):
    monkeypatch.undo()
    seen = []
    monkeypatch.setattr(lifecycle, "Session", FakeSession)
    monkeypatch.setattr(FakeSession, "rowcount", rowcount)
    monkeypatch.setattr(lifecycle, "maybe_finalize_batch", lambda s, p: seen.append(p))
    lifecycle.write_result(PID, "t-1", {"task_status": SUCCESS})
    assert len(seen) == finalized


@pytest.mark.usefixtures("fake_db")
def test_job_log_gets_start_and_end_lines(caplog, monkeypatch):
    caplog.set_level("INFO", logger="app.worker.runtime.task")
    run()

    def boom(**_kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr(guarded, "run", boom)
    run(task_id="t-3")
    messages = [
        r.getMessage() for r in caplog.records if r.name == "app.worker.runtime.task"
    ]
    assert messages[0] == "Started test_stale_guard_task"
    assert messages[1].startswith("Finished in ")
    assert messages[2] == "Started test_stale_guard_task"
    assert messages[3].startswith("Failed after ")


@pytest.mark.parametrize(
    "seconds, text", [(4.4, "4 s"), (60, "1 min 00 s"), (1985, "33 min 05 s")]
)
def test_duration(seconds, text):
    assert runtime_task._duration(seconds) == text
