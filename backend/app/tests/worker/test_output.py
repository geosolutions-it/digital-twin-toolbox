import os

from app.worker.common.output import publish_tiles


class _Storage:
    """In-memory bucket: key -> bytes."""

    def __init__(self):
        self.objects = {}

    def delete_prefix(self, prefix):
        self.objects = {
            k: v for k, v in self.objects.items() if not k.startswith(prefix)
        }

    def upload_dir(self, local, prefix):
        for root, _, files in os.walk(local):
            for name in files:
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    self.objects[f"{prefix}/{os.path.relpath(path, local)}"] = f.read()

    def upload_file(self, path, key):
        with open(path, "rb") as f:
            self.objects[key] = f.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return str(path)


def test_artifacts_go_next_to_the_tiles_and_replace_the_previous_run(tmp_path):
    storage = _Storage()
    tiles = tmp_path / "tiles"
    _write(tiles / "tileset.json", "{}")
    city = _write(tmp_path / "roofer" / "x.city.jsonl", "cityjson")
    storage.objects["output/job/artifacts/stale.txt"] = b"old run"

    result = publish_tiles(
        storage,
        str(tiles),
        "output/job",
        "tileset.json",
        {"buildings.city.jsonl": city},
    )

    assert set(storage.objects) == {
        "output/job/tiles/tileset.json",
        "output/job/artifacts/buildings.city.jsonl",
    }
    assert result["artifacts"] == [
        {
            "name": "buildings.city.jsonl",
            "url": "/api/v1/output/job/artifacts/buildings.city.jsonl",
            "size": 8,
        }
    ]
    assert result["download"].endswith("/job/tiles/download.zip")

    # a run without artifacts clears them
    result = publish_tiles(storage, str(tiles), "output/job", "tileset.json")
    assert set(storage.objects) == {"output/job/tiles/tileset.json"}
    assert "artifacts" not in result
