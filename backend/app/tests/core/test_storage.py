import io
import os

from app.core.storage import LocalStorage, upload_key, output_key


def test_keys():
    assert upload_key("a/index.laz") == "upload/a/index.laz"
    assert output_key("pid", "tiles", "tileset.json") == "output/pid/tiles/tileset.json"


def test_local_roundtrip(tmp_path):
    s = LocalStorage(root=str(tmp_path))
    src = tmp_path / "src.bin"
    src.write_bytes(b"hello")
    s.upload_file(str(src), "upload/x/index.laz")
    assert s.exists("upload/x/index.laz")
    assert s.local_path("upload/x/index.laz") == os.path.join(str(tmp_path), "upload/x/index.laz")
    out = tmp_path / "out.bin"
    s.download_file("upload/x/index.laz", str(out))
    assert out.read_bytes() == b"hello"


def test_local_fileobj(tmp_path):
    s = LocalStorage(root=str(tmp_path))
    s.upload_fileobj(io.BytesIO(b"abc"), "upload/y/index.las")
    out = tmp_path / "o"
    s.download_file("upload/y/index.las", str(out))
    assert out.read_bytes() == b"abc"


def test_upload_dir_and_delete_prefix(tmp_path):
    s = LocalStorage(root=str(tmp_path))
    d = tmp_path / "tiles"
    (d / "sub").mkdir(parents=True)
    (d / "tileset.json").write_text("{}")
    (d / "sub" / "r.pnts").write_bytes(b"\x00")
    s.upload_dir(str(d), output_key("pid", "tiles"))
    assert s.exists("output/pid/tiles/tileset.json")
    assert s.exists("output/pid/tiles/sub/r.pnts")
    s.delete_prefix(output_key("pid", "tiles"))
    assert not s.exists("output/pid/tiles/tileset.json")
