from celery.states import SUCCESS

from app.core.config import settings
from app.core.storage import output_key
from app.models.pipeline import PipelineBatch
from app.tests.api.conftest import fresh

BASE = f"{settings.API_V1_STR}/pipelines"


def laz_source(key="lidar/a.laz"):
    return {
        "key": key,
        "extension": ".laz",
        "output_base": output_key("a"),
        "pipeline": "PointCloud",
    }


def test_repoint_keeps_the_output_folder(client, db, make_pipeline, storage):
    storage.put("lidar-2026/a.laz")
    row = make_pipeline(source=laz_source())
    res = client.put(f"{BASE}/{row.id}", json={"source_key": "lidar-2026/a.laz"})
    assert res.status_code == 200
    source = fresh(db, row.id).source
    assert source["key"] == "lidar-2026/a.laz"
    assert source["output_base"] == output_key("a")


def test_repoint_rejects_a_missing_file(client, db, make_pipeline, storage):
    row = make_pipeline(source=laz_source())
    res = client.put(f"{BASE}/{row.id}", json={"source_key": "gone.laz"})
    assert res.status_code == 422
    assert "Input file not found" in res.json()["detail"]
    assert fresh(db, row.id).source["key"] == "lidar/a.laz"


def test_repoint_rejects_a_file_the_pipeline_cannot_run_on(
    client, db, make_pipeline, storage
):
    storage.put("dem/area.tif")
    row = make_pipeline(source=laz_source())
    res = client.put(f"{BASE}/{row.id}", json={"source_key": "dem/area.tif"})
    assert res.status_code == 422
    assert fresh(db, row.id).source["key"] == "lidar/a.laz"


def test_run_with_a_missing_input_is_rejected(
    client, make_pipeline, storage, fake_celery
):
    row = make_pipeline(source=laz_source(), task_id="old", task_status=SUCCESS)
    res = client.post(f"{BASE}/{row.id}/task/run")
    assert res.status_code == 422
    assert "Input file not found" in res.json()["detail"]
    assert fake_celery.sent == []


def test_batch_repoint_moves_every_member(
    client, db, make_batch, make_pipeline, storage
):
    batch = make_batch(prefix="city/")
    a = make_pipeline(source=laz_source("city/a.laz"), batch_id=batch.id)
    b = make_pipeline(source=laz_source("city/sub/b.laz"), batch_id=batch.id)
    storage.put("city-2026/a.laz", "city-2026/sub/b.laz")
    res = client.put(f"{BASE}/batch/{batch.id}", json={"prefix": "city-2026"})
    assert res.status_code == 200
    assert fresh(db, a.id).source["key"] == "city-2026/a.laz"
    assert fresh(db, b.id).source["key"] == "city-2026/sub/b.laz"
    assert fresh(db, batch.id, PipelineBatch).prefix == "city-2026/"


def test_batch_repoint_with_missing_files_changes_nothing(
    client, db, make_batch, make_pipeline, storage
):
    batch = make_batch(prefix="city/")
    a = make_pipeline(source=laz_source("city/a.laz"), batch_id=batch.id)
    make_pipeline(source=laz_source("city/b.laz"), batch_id=batch.id)
    storage.put("city-2026/a.laz")
    res = client.put(f"{BASE}/batch/{batch.id}", json={"prefix": "city-2026/"})
    assert res.status_code == 422
    assert res.json()["detail"].startswith("1 of 2 input files not found")
    assert fresh(db, a.id).source["key"] == "city/a.laz"
    assert fresh(db, batch.id, PipelineBatch).prefix == "city/"
