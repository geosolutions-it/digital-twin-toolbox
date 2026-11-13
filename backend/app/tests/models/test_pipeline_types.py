from typing import get_args

import pytest

from app.models.pipeline_types import (
    PIPELINES,
    PipelineType,
    batch_targets,
    resolve_pipeline,
)
from app.worker.tasks import TASK_QUEUES

MIXED = [
    ("f/a.laz", "PointCloud"),
    ("f/b.las", "PointCloud"),
    ("f/c.gpkg", "Polygon"),
    ("f/d.zip", "Polygon"),
    ("f/e.tif", "Terrain"),
    ("f/m.zip", "Mesh"),
    ("f/g.gml", "CityGML"),
    ("f/x.json", None),
]


def test_pointcloud_keeps_only_point_clouds():
    assert batch_targets(MIXED, "PointCloud") == [
        ("f/a.laz", "PointCloud"),
        ("f/b.las", "PointCloud"),
    ]


def test_terrain_keeps_only_rasters():
    assert batch_targets(MIXED, "Terrain") == [("f/e.tif", "Terrain")]


def test_instance_runs_on_vectors():
    assert batch_targets(MIXED, "Instance") == [
        ("f/c.gpkg", "Instance"),
        ("f/d.zip", "Instance"),
    ]


def test_no_match_is_empty():
    assert batch_targets([("f/a.laz", "PointCloud")], "Terrain") == []


@pytest.mark.parametrize("workflow", ["Building", "Auto", ""])
def test_unsupported_workflow_raises(workflow):
    with pytest.raises(ValueError):
        batch_targets(MIXED, workflow)


def test_registry_matches_pipeline_type():
    assert set(PIPELINES) == set(get_args(PipelineType))


def test_every_pipeline_task_has_a_queue():
    assert all(TASK_QUEUES[spec.task] == spec.queue for spec in PIPELINES.values())


@pytest.mark.parametrize(
    ("requested", "file_type", "expected"),
    [
        ("PointCloud", "PointCloud", "PointCloud"),
        ("PointCloud", "Terrain", "Terrain"),
        ("Polygon", "Polygon", "Polygon"),
        ("Instance", "Polygon", "Instance"),
        ("Building", "Polygon", "Building"),
    ],
)
def test_resolve_pipeline(requested, file_type, expected):
    assert resolve_pipeline(requested, file_type) == expected


@pytest.mark.parametrize(
    ("requested", "file_type"),
    [("Building", "PointCloud"), ("Instance", "Terrain"), ("PointCloud", None)],
)
def test_resolve_pipeline_rejects(requested, file_type):
    with pytest.raises(ValueError):
        resolve_pipeline(requested, file_type)
