import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException

from app.api.routes import output
from app.core.storage import output_key


class _Storage:
    """In-memory bucket: key -> bytes."""

    def __init__(self, objects):
        self.objects = {output_key(k): v for k, v in objects.items()}

    def exists(self, key):
        return key in self.objects

    def list(self, prefix):
        return sorted(k for k in self.objects if k.startswith(prefix))

    def iter_object(self, key):
        yield self.objects[key]


@pytest.fixture
def storage(monkeypatch):
    s = _Storage(
        {
            "job/tiles/tileset.json": b"{}",
            "job/artifacts/a.txt": b"private",
            "city/tileset.json": b"{}",
            "city/x/tiles/tileset.json": b"{}",
            "city/y/tiles/tileset.json": b"{}",
        }
    )
    monkeypatch.setattr(output, "get_storage", lambda: s)
    return s


def _download(path):
    res = output.serve_output_artifact(path, None)

    async def read():
        return b"".join([chunk async for chunk in res.body_iterator])

    return res, asyncio.run(read())


def _names(body):
    return sorted(zipfile.ZipFile(io.BytesIO(body)).namelist())


@pytest.mark.usefixtures("storage")
def test_job_tiles_zip_is_named_after_the_job_folder():
    res, body = _download("job/tiles/download.zip")
    assert res.headers["content-disposition"] == 'attachment; filename="job.zip"'
    assert _names(body) == ["tileset.json"]


@pytest.mark.usefixtures("storage")
def test_batch_root_zip_skips_artifacts():
    res, body = _download("city/download.zip")
    assert res.headers["content-disposition"] == 'attachment; filename="city.zip"'
    assert _names(body) == [
        "tileset.json",
        "x/tiles/tileset.json",
        "y/tiles/tileset.json",
    ]


@pytest.mark.usefixtures("storage")
@pytest.mark.parametrize(
    "path",
    [
        "download.zip",
        "job/download.zip",
        "city/x/download.zip",
        "job/tiles/Invoice_URGENT.zip",
        "missing/tiles/download.zip",
    ],
)
def test_other_zip_paths_are_not_found(path):
    with pytest.raises(HTTPException) as e:
        output.serve_output_artifact(path, None)
    assert e.value.status_code == 404
