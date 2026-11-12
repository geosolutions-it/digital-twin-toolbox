import pytest

from app.services.file_classify import batch_targets

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
    assert batch_targets(MIXED, "PointCloud") == [("f/a.laz", "PointCloud"), ("f/b.las", "PointCloud")]


def test_terrain_keeps_only_rasters():
    assert batch_targets(MIXED, "Terrain") == [("f/e.tif", "Terrain")]


def test_instance_runs_on_vectors():
    assert batch_targets(MIXED, "Instance") == [("f/c.gpkg", "Instance"), ("f/d.zip", "Instance")]


def test_no_match_is_empty():
    assert batch_targets([("f/a.laz", "PointCloud")], "Terrain") == []


@pytest.mark.parametrize("workflow", ["Building", "Auto", ""])
def test_unsupported_workflow_raises(workflow):
    with pytest.raises(ValueError):
        batch_targets(MIXED, workflow)
