import io
import posixpath
import mimetypes
import re
import zipfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.storage import get_storage

router = APIRouter()


def _media_type(name):
    mt, _ = mimetypes.guess_type(name)
    return mt or "application/octet-stream"


class _ZipSink(io.RawIOBase):
    """Unseekable buffer so zipfile emits data descriptors and we can stream it out."""

    def __init__(self):
        self._buf = bytearray()

    def writable(self):
        return True

    def write(self, b):
        self._buf += b
        return len(b)

    def drain(self):
        out = bytes(self._buf)
        del self._buf[:]
        return out


_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _zip_filename(stem):
    """Attachment name the client asked for, reduced to safe characters."""
    safe = _UNSAFE_NAME.sub("_", stem).strip("._")[:100]
    return f"{safe or 'download'}.zip"


def _stream_zip(storage, keys, prefix):
    sink = _ZipSink()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED) as zf:
        for key in keys:
            with zf.open(key[len(prefix):], "w") as dest:
                for chunk in storage.iter_object(key):
                    dest.write(chunk)
                    data = sink.drain()
                    if data:
                        yield data
            data = sink.drain()
            if data:
                yield data
    yield sink.drain()


@router.get("/{path:path}")
def serve_output_artifact(path: str):
    """Serve public pipeline/batch artifacts (3D Tiles), never process/.

    Proxies objects under the output/ area through the storage layer, keeping the
    tileset's relative references intact under one URL prefix. Works for both
    single-pipeline outputs (output/<id>/...) and batch outputs (output/<prefix>/...).
    A .zip path with no stored object is zipped on demand from its siblings, named
    after the requested file.
    """
    norm = posixpath.normpath(path)
    parts = norm.split("/")
    if norm.startswith("/") or ".." in parts or "process" in parts:
        raise HTTPException(status_code=404)

    storage = get_storage()
    key = f"output/{norm}"

    if parts[-1].endswith(".zip") and not storage.exists(key):
        prefix = key[: -len(parts[-1])]
        headers = {
            "Content-Disposition": f'attachment; filename="{_zip_filename(parts[-1][:-4])}"'
        }
        stored = f"{prefix}download.zip"
        if storage.exists(stored):
            return StreamingResponse(
                storage.iter_object(stored),
                media_type="application/zip",
                headers=headers,
            )
        keys = [k for k in storage.list(prefix) if not k.endswith(".zip")]
        if not keys:
            raise HTTPException(status_code=404)
        return StreamingResponse(
            _stream_zip(storage, keys, prefix),
            media_type="application/zip",
            headers=headers,
        )

    if not storage.exists(key):
        raise HTTPException(status_code=404)
    return StreamingResponse(storage.iter_object(key), media_type=_media_type(norm))
