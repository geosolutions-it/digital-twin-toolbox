from collections.abc import Generator
from types import SimpleNamespace

import pytest
from celery.states import PENDING
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.api.routes import pipelines as pipelines_routes
from app.api.routes import storage as storage_routes
from app.core.celery_app import celery
from app.core.db import engine, init_db
from app.main import app
from app.models.pipeline import Pipeline, PipelineBatch
from app.models.user import User
from app.services import pipeline_lifecycle


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        existing = session.exec(select(User)).first()
        init_db(session)
        yield session
        # only remove what this run added: the suite may point at a real database
        if existing is None:
            session.rollback()
            for user in session.exec(select(User)).all():
                session.delete(user)
            session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner(db: Session) -> User:
    return db.exec(select(User)).first()


@pytest.fixture
def cleanup(db: Session):
    """Delete the pipeline and batch rows a test created."""
    pipelines_before = list(db.exec(select(Pipeline.id)).all())
    batches_before = list(db.exec(select(PipelineBatch.id)).all())
    yield
    db.rollback()
    db.exec(delete(Pipeline).where(Pipeline.id.not_in(pipelines_before)))
    db.exec(delete(PipelineBatch).where(PipelineBatch.id.not_in(batches_before)))
    db.commit()
    db.expire_all()


@pytest.fixture
def make_pipeline(db: Session, owner: User, cleanup):
    def make(**fields) -> Pipeline:
        values = {"title": "job", "task_id": None, "task_status": None, "source": None}
        row = Pipeline(**{**values, **fields}, owner_id=owner.id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return make


@pytest.fixture
def make_batch(db: Session, owner: User, cleanup):
    def make(**fields) -> PipelineBatch:
        values = {"prefix": "city/", "pipeline": "PointCloud"}
        row = PipelineBatch(**{**values, **fields}, owner_id=owner.id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return make


def fresh(db: Session, row_id, model=Pipeline):
    db.expire_all()
    return db.get(model, row_id)


class FakeStorage:
    """In-memory bucket: key -> bytes."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put(self, *keys: str, data: bytes = b"x") -> None:
        for key in keys:
            self.objects[key] = data

    def exists(self, key):
        return key in self.objects

    def list(self, prefix):
        return sorted(k for k in self.objects if k.startswith(prefix))

    def size(self, key):
        return len(self.objects[key])

    def read_range(self, key, start, length):
        return self.objects[key][start : start + length]

    def list_dir(self, prefix):
        folders, files = set(), []
        for key, data in sorted(self.objects.items()):
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix) :]
            if "/" in rest:
                folders.add(prefix + rest.split("/")[0] + "/")
            else:
                files.append({"key": key, "name": rest, "size": len(data)})
        return {"prefix": prefix, "folders": sorted(folders), "files": files}

    def delete_prefix(self, prefix):
        self.deleted.append(prefix)
        for key in self.list(prefix):
            del self.objects[key]


@pytest.fixture
def storage(monkeypatch) -> FakeStorage:
    fake = FakeStorage()
    monkeypatch.setattr(pipelines_routes, "get_storage", lambda: fake)
    monkeypatch.setattr(storage_routes, "get_storage", lambda: fake)
    return fake


class FakeCelery:
    """Records sent tasks and revokes; task states are set per test."""

    def __init__(self):
        self.sent: list[SimpleNamespace] = []
        self.states: dict[str, str] = {}
        self.revoked: list[str] = []
        self.revoke_error: Exception | None = None

    def send_task(self, name, kwargs=None, task_id=None, **_):
        self.sent.append(SimpleNamespace(name=name, kwargs=kwargs, task_id=task_id))

    def names(self) -> list[str]:
        return [t.name for t in self.sent]

    def async_result(self, task_id, app=None):
        def revoke(terminate=False):
            if self.revoke_error is not None:
                raise self.revoke_error
            self.revoked.append(task_id)

        return SimpleNamespace(state=self.states.get(task_id, PENDING), revoke=revoke)


@pytest.fixture
def fake_celery(monkeypatch) -> FakeCelery:
    fake = FakeCelery()
    monkeypatch.setattr(celery, "send_task", fake.send_task)
    monkeypatch.setattr(pipeline_lifecycle, "AsyncResult", fake.async_result)
    return fake
