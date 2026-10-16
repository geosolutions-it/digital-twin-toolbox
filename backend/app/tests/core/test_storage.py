from app.core.storage import upload_key, output_key


def test_upload_key():
    assert upload_key("a/index.laz") == "upload/a/index.laz"


def test_output_key():
    assert output_key("pid") == "output/pid"
    assert output_key("pid", "tiles", "tileset.json") == "output/pid/tiles/tileset.json"
    assert output_key("pid", "download.zip") == "output/pid/download.zip"
