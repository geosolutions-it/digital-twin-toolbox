from app.core.config import settings


def test_listing_tells_which_pipeline_a_file_runs_with(client, storage):
    storage.put("lidar/a.laz", "lidar/notes.txt", "lidar/sub/b.laz")
    body = client.get(f"{settings.API_V1_STR}/storage/", params={"prefix": "lidar/"})
    data = body.json()
    assert data["folders"] == ["lidar/sub/"]
    assert {f["name"]: f["pipeline"] for f in data["files"]} == {
        "a.laz": "PointCloud",
        "notes.txt": None,
    }
