import uuid

from celery.states import PENDING, REVOKED, STARTED, SUCCESS

from app.core.config import settings
from app.core.storage import output_key
from app.tests.api.conftest import fresh

BASE = f"{settings.API_V1_STR}/pipelines"


def mesh_source(**extra):
    return {
        "key": "m/model.zip",
        "pipeline": "Mesh",
        "output_base": output_key("model"),
        **extra,
    }


def test_update_rejects_invalid_config_and_keeps_the_row(client, db, make_pipeline):
    row = make_pipeline(source=mesh_source(), data={"depth": 3})
    res = client.put(f"{BASE}/{row.id}", json={"data": {"forward_axis": "W"}})
    assert res.status_code == 422
    assert fresh(db, row.id).data == {"depth": 3}


def test_update_stores_the_config_with_defaults(client, db, make_pipeline):
    row = make_pipeline(source=mesh_source())
    res = client.put(f"{BASE}/{row.id}", json={"data": {"depth": 5}})
    assert res.status_code == 200
    data = fresh(db, row.id).data
    assert data["depth"] == 5
    assert data["forward_axis"] == "Y"


def test_batch_update_applies_to_every_member(client, db, make_pipeline):
    batch_id = uuid.uuid4()
    rows = [make_pipeline(source=mesh_source(), batch_id=batch_id) for _ in range(2)]
    res = client.put(f"{BASE}/batch/{batch_id}", json={"data": {"depth": 2}})
    assert res.json()["count"] == 2
    assert all(fresh(db, r.id).data["depth"] == 2 for r in rows)


def test_run_idle_pipeline_starts_a_new_task(client, db, make_pipeline, fake_celery):
    row = make_pipeline(source=mesh_source(), task_id="old", task_status=SUCCESS)
    res = client.post(f"{BASE}/{row.id}/task/run")
    assert res.status_code == 200
    row = fresh(db, row.id)
    assert row.task_status == PENDING
    assert row.task_id not in (None, "old")
    assert [(t.name, t.task_id) for t in fake_celery.sent] == [
        ("create_mesh_3dtiles", row.task_id)
    ]
    assert fake_celery.sent[0].kwargs["pipeline_extended"]["data"]["depth"] == 4


def test_run_running_pipeline_does_nothing(client, db, make_pipeline, fake_celery):
    row = make_pipeline(source=mesh_source(), task_id="t1", task_status=STARTED)
    res = client.post(f"{BASE}/{row.id}/task/run")
    assert res.json() == {
        "action_type": "run",
        "task_id": None,
        "task_status": None,
        "task_result": None,
    }
    assert fresh(db, row.id).task_id == "t1"
    assert fake_celery.sent == []


def test_cancel_running_pipeline_revokes_it(client, db, make_pipeline, fake_celery):
    row = make_pipeline(source=mesh_source(), task_id="t1", task_status=STARTED)
    client.post(f"{BASE}/{row.id}/task/cancel")
    assert fresh(db, row.id).task_status == REVOKED
    assert fake_celery.revoked == ["t1"]


def test_cancel_idle_pipeline_does_nothing(client, db, make_pipeline, fake_celery):
    row = make_pipeline(source=mesh_source(), task_id="t1", task_status=SUCCESS)
    client.post(f"{BASE}/{row.id}/task/cancel")
    assert fresh(db, row.id).task_status == SUCCESS
    assert fake_celery.revoked == []


def test_cancel_marks_revoked_even_if_revoke_fails(
    client, db, make_pipeline, fake_celery
):
    fake_celery.revoke_error = ConnectionError("broker down")
    row = make_pipeline(source=mesh_source(), task_id="t1", task_status=PENDING)
    res = client.post(f"{BASE}/{row.id}/task/cancel")
    assert res.status_code == 200
    assert fresh(db, row.id).task_status == REVOKED


def test_batch_run_counts_only_idle_members(client, make_pipeline, fake_celery):
    batch_id = uuid.uuid4()
    make_pipeline(
        source=mesh_source(), batch_id=batch_id, task_id="a", task_status=SUCCESS
    )
    make_pipeline(
        source=mesh_source(), batch_id=batch_id, task_id="b", task_status=STARTED
    )
    res = client.post(f"{BASE}/batch/{batch_id}/task/run")
    assert res.json()["count"] == 2
    assert res.json()["affected"] == 1
    assert fake_celery.names() == ["create_mesh_3dtiles"]


def test_delete_batch_member_cleans_output_and_rebuilds_batch(
    client, db, make_pipeline, storage, fake_celery
):
    batch_prefix = output_key("city")
    row = make_pipeline(
        source=mesh_source(
            output_base=f"{batch_prefix}/a", batch_output_prefix=batch_prefix
        ),
        batch_id=uuid.uuid4(),
        task_id="t1",
        task_status=STARTED,
    )
    storage.put(f"{batch_prefix}/a/tileset.json", f"{batch_prefix}/b/tileset.json")

    assert client.delete(f"{BASE}/{row.id}").status_code == 200
    assert fresh(db, row.id) is None
    assert storage.deleted == [f"{batch_prefix}/a/"]
    assert storage.exists(f"{batch_prefix}/b/tileset.json")
    assert fake_celery.revoked == ["t1"]
    finalize = [t for t in fake_celery.sent if t.name == "finalize_tileset_batch"]
    assert [t.kwargs["output_prefix"] for t in finalize] == [batch_prefix]


def test_delete_batch_removes_rows_and_output(
    client, db, make_pipeline, storage, fake_celery
):
    batch_id = uuid.uuid4()
    batch_prefix = output_key("city")
    ids = [
        make_pipeline(
            source=mesh_source(batch_output_prefix=batch_prefix), batch_id=batch_id
        ).id
        for _ in range(2)
    ]
    storage.put(f"{batch_prefix}/tileset.json")

    assert client.delete(f"{BASE}/batch/{batch_id}").status_code == 200
    assert all(fresh(db, i) is None for i in ids)
    assert storage.deleted == [f"{batch_prefix}/"]
    assert not storage.exists(f"{batch_prefix}/tileset.json")


def test_unknown_ids_are_404(client, fake_celery):
    missing = uuid.uuid4()
    assert client.post(f"{BASE}/{missing}/task/run").status_code == 404
    assert client.delete(f"{BASE}/{missing}").status_code == 404
    assert client.delete(f"{BASE}/batch/{missing}").status_code == 404
    assert client.post(f"{BASE}/batch/{missing}/finalize").status_code == 404
