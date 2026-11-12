import io
import posixpath
import mimetypes
import re
import zipfile
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.db import engine
from app.core.storage import get_storage, output_key

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


DOWNLOAD = "download.zip"
TILES = "tiles"
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _zip_name(storage, parts, prefix):
    """Named after the zipped folder; None unless it is a tiles/ folder or a batch root."""
    if len(parts) >= 3 and parts[-2] == TILES:
        folder = parts[-3]
    elif len(parts) >= 2 and storage.exists(f"{prefix}tileset.json"):
        folder = parts[-2]
    else:
        return None
    safe = _UNSAFE_NAME.sub("_", folder[:100]).strip("._")
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


ARTIFACTS = "artifacts"


def _is_artifact(parts):
    # depth 3+ so a batch named "artifacts" keeps its root tileset public
    return len(parts) >= 3 and parts[-2] == ARTIFACTS


def _check_access(parts, request):
    """Tiles are public (viewers load them anonymously), artifacts need a user."""
    if _is_artifact(parts):
        with Session(engine) as session:
            get_current_user(session, request)


@router.get("/{path:path}")
def serve_output_artifact(path: str, request: Request):
    """Serve public pipeline/batch artifacts (3D Tiles), never process/.

    Proxies objects under OUTPUT_PREFIX through the storage layer, keeping the
    tileset's relative references intact under one URL prefix. Works for both
    single-pipeline and batch outputs.
    download.zip in a tiles/ folder or a batch root is zipped on demand, artifacts excluded.
    """
    norm = posixpath.normpath(path)
    parts = norm.split("/")
    if norm.startswith("/") or ".." in parts or "process" in parts:
        raise HTTPException(status_code=404)
    _check_access(parts, request)

    storage = get_storage()
    key = output_key(norm)

    if parts[-1] == DOWNLOAD:
        prefix = key[: -len(DOWNLOAD)]
        name = _zip_name(storage, parts, prefix)
        if name is None:
            raise HTTPException(status_code=404)
        keys = [k for k in storage.list(prefix)
                if not k.endswith(".zip") and f"/{ARTIFACTS}/" not in k[len(prefix) - 1:]]
        if not keys:
            raise HTTPException(status_code=404)
        return StreamingResponse(
            _stream_zip(storage, keys, prefix),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    if not storage.exists(key):
        raise HTTPException(status_code=404)
    return StreamingResponse(storage.iter_object(key), media_type=_media_type(norm))
