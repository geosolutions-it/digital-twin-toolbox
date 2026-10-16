import io

import pytest

boto3 = pytest.importorskip("boto3")
pytest.importorskip("moto")
from moto import mock_aws

from app.core.storage import S3Storage, output_key

BUCKET = "test-bucket"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        yield S3Storage(bucket=BUCKET, region="us-east-1")


def test_file_roundtrip(s3, tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"hello")
    s3.upload_file(str(src), "upload/x/index.laz")
    assert s3.exists("upload/x/index.laz")
    assert not s3.exists("upload/x/missing")
    out = tmp_path / "out.bin"
    s3.download_file("upload/x/index.laz", str(out))
    assert out.read_bytes() == b"hello"


def test_fileobj(s3, tmp_path):
    s3.upload_fileobj(io.BytesIO(b"abc"), "upload/y/index.las")
    out = tmp_path / "o"
    s3.download_file("upload/y/index.las", str(out))
    assert out.read_bytes() == b"abc"


def test_upload_dir_and_delete_prefix(s3, tmp_path):
    tiles = tmp_path / "tiles"
    (tiles / "sub").mkdir(parents=True)
    (tiles / "tileset.json").write_text("{}")
    (tiles / "sub" / "r.pnts").write_bytes(b"\x00")
    s3.upload_dir(str(tiles), output_key("pid", "tiles"))
    assert s3.exists("output/pid/tiles/tileset.json")
    assert s3.exists("output/pid/tiles/sub/r.pnts")
    s3.delete_prefix(output_key("pid", "tiles"))
    assert not s3.exists("output/pid/tiles/tileset.json")


def test_iter_object(s3, tmp_path):
    s3.upload_fileobj(io.BytesIO(b"x y z\n1 2 3\n"), "upload/a/sample.xyz")
    assert b"".join(s3.iter_object("upload/a/sample.xyz")) == b"x y z\n1 2 3\n"
