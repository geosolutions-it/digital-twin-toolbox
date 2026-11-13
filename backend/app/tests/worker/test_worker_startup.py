import uuid

import pytest
from celery.states import FAILURE, STARTED

from app.services import pipeline_lifecycle as lifecycle
from app.worker import main

A, B, C = (uuid.uuid4() for _ in range(3))


def test_clear_scratch_removes_only_tempfile_folders(tmp_path):
    for name in ("tmpab_12xyz", "tmpk3j9q0wd"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "tile.laz").write_bytes(b"x")
    (tmp_path / "tmpfile1234").write_text("a file, not a folder")
    (tmp_path / "tmp-keep").mkdir()
    (tmp_path / "tmpabcdefghi").mkdir()  # 9 chars, not a tempfile name
    (tmp_path / "other").mkdir()
    (tmp_path / "tmpl1nk0000").symlink_to(tmp_path / "other")

    removed = main._clear_scratch(str(tmp_path))

    assert sorted(removed) == ["tmpab_12xyz", "tmpk3j9q0wd"]
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == ["other", "tmp-keep", "tmpabcdefghi", "tmpfile1234", "tmpl1nk0000"]
    assert (tmp_path / "other").is_dir()


@pytest.fixture
def fake(monkeypatch):
    state = {
        "rows": [(A, "t-a"), (B, "t-b"), (C, "t-c")],
        "active": {"t-b"},
        "applied": True,
        "writes": [],
    }

    def write(pipeline_id, task_id, values, status=None):
        state["writes"].append((pipeline_id, task_id, values, status))
        return state["applied"]

    monkeypatch.setattr(lifecycle, "started_rows", lambda: state["rows"])
    monkeypatch.setattr(lifecycle, "active_task_ids", lambda: state["active"])
    monkeypatch.setattr(lifecycle, "write_result", write)
    return state


def test_fails_started_rows_not_running_anywhere(fake):
    assert lifecycle.fail_orphaned_rows() == 2
    failed = {"task_status": FAILURE, "task_result": None}
    assert fake["writes"] == [(A, "t-a", failed, STARTED), (C, "t-c", failed, STARTED)]


def test_no_reply_to_broadcast_changes_nothing(fake):
    fake["active"] = None
    assert lifecycle.fail_orphaned_rows() == 0
    assert fake["writes"] == []


def test_no_started_rows_skips_broadcast(fake, monkeypatch):
    fake["rows"] = []
    monkeypatch.setattr(
        lifecycle, "active_task_ids", lambda: pytest.fail("broadcast sent")
    )
    assert lifecycle.fail_orphaned_rows() == 0


def test_row_that_changed_meanwhile_is_not_counted(fake):
    fake["applied"] = False
    assert lifecycle.fail_orphaned_rows() == 0
    assert len(fake["writes"]) == 2


def test_active_task_ids_merges_workers(monkeypatch):
    class Inspect:
        def active(self):
            return {"w1": [{"id": "x"}], "w2": [{"id": "y"}, {"id": "z"}], "w3": []}

    monkeypatch.setattr(lifecycle.celery.control, "inspect", lambda timeout: Inspect())
    assert lifecycle.active_task_ids() == {"x", "y", "z"}


def test_active_task_ids_none_without_replies(monkeypatch):
    class Inspect:
        def active(self):
            return None

    monkeypatch.setattr(lifecycle.celery.control, "inspect", lambda timeout: Inspect())
    assert lifecycle.active_task_ids() is None
