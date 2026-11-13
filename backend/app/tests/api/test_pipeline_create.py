import uuid

import pytest
from celery.states import PENDING
from sqlmodel import func, select

from app.core.config import settings
from app.core.storage import output_key
from app.models.pipeline import Pipeline
from app.tests.api.conftest import fresh

pytestmark = pytest.mark.usefixtures("cleanup")

BASE = f"{settings.API_V1_STR}/pipelines"


def count_rows(db):
    db.expire_all()
    return db.exec(select(func.count()).select_from(Pipeline)).one()


def test_source_creates_pending_row_and_sends_its_task(
    client, db, storage, fake_celery
):
    storage.put("lidar/a.laz")
    res = client.post(
        f"{BASE}/source", json={"key": "lidar/a.laz", "pipeline": "PointCloud"}
    )
    assert res.status_code == 200
    row = fresh(db, uuid.UUID(res.json()["id"]))

    assert row.task_status == PENDING
    assert row.title == "a.laz"
    assert row.source["key"] == "lidar/a.laz"
    assert row.source["pipeline"] == "PointCloud"
    assert row.source["output_base"] == output_key("a")
    assert row.data["to_ellipsoidal_height"] is False
    assert [(t.name, t.task_id) for t in fake_celery.sent] == [
        ("create_point_cloud_3dtiles", row.task_id)
    ]
    assert fake_celery.sent[0].kwargs["pipeline_extended"]["id"] == row.id


def test_source_missing_file_is_404(client, db, storage, fake_celery):
    before = count_rows(db)
    res = client.post(f"{BASE}/source", json={"key": "nope.laz"})
    assert res.status_code == 404
    assert count_rows(db) == before
    assert fake_celery.sent == []


@pytest.mark.parametrize(
    ("key", "requested", "data", "expected"),
    [
        ("v/roads.gpkg", "Instance", {}, "Instance"),
        ("v/roofs.gpkg", "Building", {"point_cloud": "lidar/"}, "Building"),
        ("dem/area.tif", "PointCloud", {}, "Terrain"),
    ],
)
def test_source_picks_the_pipeline_for_the_file(
    client, db, storage, fake_celery, key, requested, data, expected
):
    storage.put(key)
    res = client.post(
        f"{BASE}/source", json={"key": key, "pipeline": requested, "data": data}
    )
    assert res.status_code == 200
    assert fresh(db, uuid.UUID(res.json()["id"])).source["pipeline"] == expected


@pytest.mark.parametrize(
    ("key", "requested"),
    [
        ("lidar/a.laz", "Building"),
        ("dem/area.tif", "Instance"),
        ("notes.txt", "PointCloud"),
    ],
)
def test_source_rejects_a_file_the_pipeline_cannot_run_on(
    client, db, storage, fake_celery, key, requested
):
    storage.put(key)
    before = count_rows(db)
    res = client.post(f"{BASE}/source", json={"key": key, "pipeline": requested})
    assert res.status_code == 422
    assert count_rows(db) == before
    assert fake_celery.sent == []


def test_source_invalid_config_is_422_and_creates_nothing(
    client, db, storage, fake_celery
):
    storage.put("lidar/a.laz")
    before = count_rows(db)
    res = client.post(
        f"{BASE}/source", json={"key": "lidar/a.laz", "data": {"sample_radius": "wide"}}
    )
    assert res.status_code == 422
    assert count_rows(db) == before
    assert fake_celery.sent == []


def test_source_output_name_does_not_overwrite_existing_output(
    client, db, storage, fake_celery
):
    storage.put("lidar/a.laz", output_key("a", "tileset.json"))
    res = client.post(f"{BASE}/source", json={"key": "lidar/a.laz"})
    row = fresh(db, uuid.UUID(res.json()["id"]))
    assert row.source["output_base"] == output_key("a-1")


def test_batch_creates_one_row_per_matching_file(client, db, storage, fake_celery):
    storage.put(
        "city/a.laz",
        "city/sub/b.las",
        "city/dem.tif",
        "city/readme.txt",
        output_key("old", "c.laz"),
    )
    res = client.post(
        f"{BASE}/batch",
        json={"prefix": "city/", "pipeline": "PointCloud", "title": "City"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 2

    db.expire_all()
    rows = db.exec(
        select(Pipeline).where(Pipeline.batch_id == uuid.UUID(body["batch_id"]))
    ).all()
    assert sorted(r.title for r in rows) == ["City / a.laz", "City / b.las"]
    out_root = output_key("City")
    assert {r.source["batch_output_prefix"] for r in rows} == {out_root}
    assert sorted(r.source["output_base"] for r in rows) == [
        f"{out_root}/a",
        f"{out_root}/sub/b",
    ]
    assert fake_celery.names() == ["create_point_cloud_3dtiles"] * 2


def test_batch_keeps_same_stem_files_apart(client, db, storage, fake_celery):
    storage.put("city/x.las", "city/x.laz")
    body = client.post(
        f"{BASE}/batch", json={"prefix": "city/", "pipeline": "PointCloud"}
    ).json()
    db.expire_all()
    bases = sorted(
        r.source["output_base"]
        for r in db.exec(
            select(Pipeline).where(Pipeline.batch_id == uuid.UUID(body["batch_id"]))
        ).all()
    )
    assert [b.rsplit("/", 1)[1] for b in bases] == ["x_las", "x_laz"]


def test_batch_rejects_building_and_empty_folders(client, storage, fake_celery):
    storage.put("city/roofs.gpkg")
    building = client.post(
        f"{BASE}/batch",
        json={"prefix": "city/", "pipeline": "Building", "data": {"point_cloud": "x/"}},
    )
    assert building.status_code == 422
    empty = client.post(
        f"{BASE}/batch", json={"prefix": "city/", "pipeline": "Terrain"}
    )
    assert empty.status_code == 404
    assert fake_celery.sent == []
