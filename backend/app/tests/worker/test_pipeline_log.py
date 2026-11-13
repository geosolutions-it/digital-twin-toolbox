import logging
import time
import uuid

import pytest

from app.worker.runtime import logs
from app.worker.runtime.logs import PipelineLogHandler, redact

PID = uuid.uuid4()


def test_redact_signed_urls_credentials_and_secrets():
    url = "https://s3/b/k.laz?X-Amz-Credential=AKIA%2F1&X-Amz-Signature=abc123&x-id=GetObject"
    assert (
        redact(url)
        == "https://s3/b/k.laz?X-Amz-Credential=***&X-Amz-Signature=***&x-id=GetObject"
    )
    assert (
        redact("postgresql+psycopg://app:hunter22@db:5432/app")
        == "postgresql+psycopg://app:***@db:5432/app"
    )
    assert redact("key=supersecret ok", secrets=["supersecret"]) == "key=*** ok"


def test_short_secrets_are_not_masked(monkeypatch):
    monkeypatch.setattr(logs.settings, "POSTGRES_PASSWORD", "abc")
    monkeypatch.setattr(logs.settings, "S3_SECRET_ACCESS_KEY", "longersecret")
    assert "abc" not in logs._secrets()
    assert "longersecret" in logs._secrets()


@pytest.fixture
def captured():
    batches = []
    handler = PipelineLogHandler(
        PID, write=lambda pid, rows: batches.append((pid, rows))
    )
    log = logging.getLogger("test.pipeline")
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    yield log, handler, batches
    log.removeHandler(handler)


def rows(batches):
    return [row for _, batch in batches for row in batch]


def test_records_are_written_on_close_with_level_and_stage(captured):
    log, handler, batches = captured
    log.debug("hidden")
    log.info("cropping", extra={"stage": "Roofer: cropping"})
    log.warning("pw=%s", "x")
    handler.close()
    written = rows(batches)
    assert [(r["level"], r["message"], r["stage"]) for r in written] == [
        ("INFO", "cropping", "Roofer: cropping"),
        ("WARNING", "pw=x", None),
    ]
    assert all(pid == PID for pid, _ in batches)
    assert written[0]["created_at"].tzinfo is not None


def test_full_batch_is_flushed_before_close(captured, monkeypatch):
    monkeypatch.setattr(logs, "FLUSH_SECONDS", 60)
    log, handler, batches = captured
    for i in range(logs.FLUSH_LINES):
        log.info("line %d", i)
    for _ in range(100):
        if batches:
            break
        time.sleep(0.01)
    assert len(rows(batches)) == logs.FLUSH_LINES
    handler.close()


def test_log_stage_sets_the_stage(captured, monkeypatch):
    log, handler, batches = captured
    stage_logger = logging.getLogger("app.worker.stage")
    monkeypatch.setattr(stage_logger, "level", logging.INFO)
    stage_logger.addHandler(handler)
    logs.log_stage("Tiling 3 buildings")
    stage_logger.removeHandler(handler)
    handler.close()
    assert [(r["message"], r["stage"]) for r in rows(batches)] == [
        ("Tiling 3 buildings", "Tiling 3 buildings")
    ]


def test_exception_traceback_and_length_cap(captured):
    log, handler, batches = captured
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("Task failed")
    log.info("x" * (logs.MAX_MESSAGE + 10))
    handler.close()
    failed, long = rows(batches)
    assert failed["level"] == "ERROR"
    assert "ValueError: boom" in failed["message"]
    assert len(long["message"]) == logs.MAX_MESSAGE


def test_db_records_are_ignored(captured):
    log, handler, batches = captured
    logging.getLogger("sqlalchemy.engine").addHandler(handler)
    logging.getLogger("sqlalchemy.engine").warning("from the driver")
    logging.getLogger("sqlalchemy.engine").removeHandler(handler)
    handler.close()
    assert rows(batches) == []


def test_write_errors_do_not_raise(capsys):
    def fail(_pid, _rows):
        raise RuntimeError("db down")

    handler = PipelineLogHandler(PID, write=fail)
    log = logging.getLogger("test.pipeline.fail")
    log.addHandler(handler)
    log.warning("a")
    log.removeHandler(handler)
    handler.close()
    assert "log lines dropped: db down" in capsys.readouterr().err


def test_capture_attaches_to_root_and_detaches(monkeypatch):
    batches = []
    monkeypatch.setattr(logs, "_write_rows", lambda pid, rows: batches.append(rows))
    root = logging.getLogger()
    with logs.capture_pipeline_log(PID) as handler:
        assert handler in root.handlers
        logging.getLogger("any.module").warning("seen")
    assert handler not in root.handlers
    logging.getLogger("any.module").warning("after")
    assert [r["message"] for b in batches for r in b] == ["seen"]
