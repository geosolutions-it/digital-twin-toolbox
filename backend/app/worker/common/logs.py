import logging
import re
import sys
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import delete, insert, select
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.models.pipeline import PipelineLog

MAX_LINES = 5000
FLUSH_SECONDS = 1.0
FLUSH_LINES = 100
MAX_MESSAGE = 4000

_PATTERNS = [
    (
        re.compile(
            r"(X-Amz-(?:Signature|Credential|Security-Token)=)[^&\s\"']+", re.IGNORECASE
        ),
        r"\1***",
    ),
    (re.compile(r"(://[^/\s:@]+:)[^@\s/]+@"), r"\1***@"),
]
# records raised while writing the log itself
_IGNORED_LOGGERS = ("sqlalchemy", "psycopg")


_stage_logger = logging.getLogger("app.worker.stage")


def log_stage(name):
    """Progress marker: the latest one is shown as the running job's stage."""
    _stage_logger.info(name, extra={"stage": name})


def _secrets():
    values = (
        settings.POSTGRES_PASSWORD,
        settings.S3_ACCESS_KEY_ID,
        settings.S3_SECRET_ACCESS_KEY,
        str(settings.SENTRY_DSN or ""),
    )
    # short values would mask ordinary words
    return sorted({v for v in values if v and len(v) >= 6}, key=len, reverse=True)


def redact(message, secrets=()):
    for pattern, replacement in _PATTERNS:
        message = pattern.sub(replacement, message)
    for secret in secrets:
        message = message.replace(secret, "***")
    return message


def _write_rows(pipeline_id, rows):
    with Session(engine) as session:
        session.execute(insert(PipelineLog), rows)
        cutoff = (
            select(PipelineLog.id)
            .where(PipelineLog.pipeline_id == pipeline_id)
            .order_by(PipelineLog.id.desc())
            .offset(MAX_LINES)
            .limit(1)
            .scalar_subquery()
        )
        session.execute(
            delete(PipelineLog).where(
                PipelineLog.pipeline_id == pipeline_id, PipelineLog.id <= cutoff
            )
        )
        session.commit()


class PipelineLogHandler(logging.Handler):
    """Copies the records of one running task to pipeline_log, written in batches by a background thread."""

    def __init__(self, pipeline_id, write=None):
        super().__init__(logging.INFO)
        self.pipeline_id = uuid.UUID(str(pipeline_id))
        self._write = write or _write_rows
        self._secrets = _secrets()
        self._rows = []
        self._wake = threading.Event()
        self._stop = False
        self._failed = False
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="pipeline-log"
        )
        self._thread.start()

    def emit(self, record):
        if threading.current_thread() is self._thread or record.name.startswith(
            _IGNORED_LOGGERS
        ):
            return
        message = record.getMessage()
        if record.exc_info:
            message += "\n" + logging.Formatter().formatException(record.exc_info)
        self._rows.append(
            {
                "pipeline_id": self.pipeline_id,
                "created_at": datetime.fromtimestamp(record.created, timezone.utc),
                "level": record.levelname,
                "message": redact(message, self._secrets)[:MAX_MESSAGE],
                "stage": getattr(record, "stage", None),
            }
        )
        if len(self._rows) >= FLUSH_LINES:
            self._wake.set()

    def _flush(self):
        self.acquire()
        try:
            rows, self._rows = self._rows, []
        finally:
            self.release()
        if not rows:
            return
        try:
            self._write(self.pipeline_id, rows)
        except Exception as error:
            if not self._failed:
                self._failed = True
                sys.stderr.write(
                    f"pipeline {self.pipeline_id}: log lines dropped: {error}\n"
                )

    def _run(self):
        while not self._stop:
            self._wake.wait(FLUSH_SECONDS)
            self._wake.clear()
            self._flush()

    def close(self):
        self._stop = True
        self._wake.set()
        self._thread.join()
        self._flush()
        super().close()


@contextmanager
def capture_pipeline_log(pipeline_id):
    handler = PipelineLogHandler(pipeline_id)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)
        handler.close()
