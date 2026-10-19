"""Object storage for assets and pipeline outputs.

Keys are relative paths (e.g. "upload/<id>/index.laz", "output/<id>/tiles/tileset.json")
mapped to objects in an S3-compatible bucket. Single-box/dev runs a bundled SeaweedFS;
a cloud deploy points the S3_* settings at its own bucket. Workers download inputs to
local scratch and upload outputs back, so no shared filesystem is required. The Storage
interface stays thin so other object-store backends can be added later.
"""
import os
from abc import ABC, abstractmethod

from app.core.config import settings


def upload_key(pathname: str) -> str:
    return f"upload/{pathname}"


def output_key(pipeline_id, *parts: str) -> str:
    return "/".join(["output", str(pipeline_id), *parts])


def _iter_files(local_dir: str):
    for root, _dirs, files in os.walk(local_dir):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, local_dir).replace(os.sep, "/")
            yield full, rel


class Storage(ABC):
    @abstractmethod
    def upload_fileobj(self, fileobj, key: str) -> None: ...

    @abstractmethod
    def upload_file(self, local_path: str, key: str) -> None: ...

    @abstractmethod
    def download_file(self, key: str, local_path: str) -> None: ...

    @abstractmethod
    def upload_dir(self, local_dir: str, key_prefix: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete_prefix(self, key_prefix: str) -> None: ...

    @abstractmethod
    def iter_object(self, key: str, chunk: int = 1048576): ...

    @abstractmethod
    def size(self, key: str) -> int: ...

    @abstractmethod
    def read_range(self, key: str, start: int, length: int) -> bytes: ...

    @abstractmethod
    def list(self, prefix: str) -> list[str]: ...

    @abstractmethod
    def list_dir(self, prefix: str, delimiter: str = "/") -> dict: ...


class S3Storage(Storage):
    def __init__(self, bucket, endpoint_url=None, access_key=None, secret_key=None,
                 region=None, addressing_style="path", create_bucket=False):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(s3={"addressing_style": addressing_style}),
        )
        if create_bucket:
            self._ensure_bucket()

    def _ensure_bucket(self):
        from botocore.exceptions import ClientError
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except ClientError:
                pass

    def upload_fileobj(self, fileobj, key: str) -> None:
        fileobj.seek(0)
        self.client.upload_fileobj(fileobj, self.bucket, key)

    def upload_file(self, local_path: str, key: str) -> None:
        self.client.upload_file(local_path, self.bucket, key)

    def download_file(self, key: str, local_path: str) -> None:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.client.download_file(self.bucket, key, local_path)

    def upload_dir(self, local_dir: str, key_prefix: str) -> None:
        for full, rel in _iter_files(local_dir):
            self.upload_file(full, f"{key_prefix}/{rel}")

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def iter_object(self, key: str, chunk: int = 1048576):
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        yield from body.iter_chunks(chunk)

    def size(self, key: str) -> int:
        return self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]

    def read_range(self, key: str, start: int, length: int) -> bytes:
        rng = f"bytes={start}-{start + length - 1}"
        return self.client.get_object(Bucket=self.bucket, Key=key, Range=rng)["Body"].read()

    def list(self, prefix: str) -> list[str]:
        keys = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def list_dir(self, prefix: str, delimiter: str = "/") -> dict:
        if prefix and not prefix.endswith(delimiter):
            prefix = prefix + delimiter
        folders, files = [], []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter=delimiter):
            for cp in page.get("CommonPrefixes", []):
                folders.append(cp["Prefix"])
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key == prefix:
                    continue
                files.append({"key": key, "name": key[len(prefix):], "size": obj["Size"]})
        return {"prefix": prefix, "folders": folders, "files": files}

    def delete_prefix(self, key_prefix: str) -> None:
        paginator = self.client.get_paginator("list_objects_v2")
        batch = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=key_prefix):
            for obj in page.get("Contents", []):
                batch.append({"Key": obj["Key"]})
                if len(batch) == 1000:
                    self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch})
                    batch = []
        if batch:
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch})


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY_ID,
            secret_key=settings.S3_SECRET_ACCESS_KEY,
            region=settings.S3_REGION,
            addressing_style=settings.S3_ADDRESSING_STYLE,
            create_bucket=settings.S3_CREATE_BUCKET,
        )
    return _storage
