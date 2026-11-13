import os
import uuid

import pytest

from app.models.config import MeshConfig
from app.worker.runtime.task import TaskContext


class _Storage:
    def __init__(self):
        self.downloads = []

    def download_file(self, key, dest):
        self.downloads.append((key, os.path.basename(dest)))
        with open(dest, "w") as f:
            f.write(key)


def _payload(**source):
    return {"id": str(uuid.uuid4()), "source": source, "data": {"depth": 2}}


def test_download_keeps_an_explicit_extension_and_lowercases_the_key_one():
    storage = _Storage()
    with TaskContext(_payload(key="a/Mesh.OBJ"), "Mesh", MeshConfig, storage) as ctx:
        ctx.download("a/Mesh.OBJ", "index")
        ctx.download("a/Mesh.OBJ", "index.zip")
        ctx.download("a/no_extension", "plain")
    assert [name for _, name in storage.downloads] == [
        "index.obj",
        "index.zip",
        "plain",
    ]


def test_config_output_and_scratch_lifetime():
    payload = _payload(key="a/mesh.obj", output_base="custom/out")
    with TaskContext(payload, "Mesh", MeshConfig, _Storage()) as ctx:
        scratch = ctx.scratch
        assert os.path.isdir(scratch)
        assert ctx.path("tiles") == os.path.join(scratch, "tiles")
        assert ctx.config.depth == 2
        assert ctx.out_base == "custom/out"
    assert not os.path.exists(scratch)


def test_scratch_is_removed_when_the_run_fails():
    with pytest.raises(RuntimeError):
        with TaskContext(
            _payload(key="a/mesh.obj"), "Mesh", MeshConfig, _Storage()
        ) as ctx:
            scratch = ctx.scratch
            raise RuntimeError("boom")
    assert not os.path.exists(scratch)


def test_missing_source_key_names_the_pipeline():
    with pytest.raises(Exception, match="Mesh pipeline requires a bucket source"):
        TaskContext(_payload(), "Mesh", MeshConfig, _Storage())
