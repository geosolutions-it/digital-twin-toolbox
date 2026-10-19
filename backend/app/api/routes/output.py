import posixpath
import mimetypes
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.storage import get_storage

router = APIRouter()


def _media_type(name):
    mt, _ = mimetypes.guess_type(name)
    return mt or "application/octet-stream"


@router.get("/{path:path}")
def serve_output_artifact(path: str):
    """Serve public pipeline/batch artifacts (3D Tiles + download.zip), never process/.

    Proxies objects under the output/ area through the storage layer, keeping the
    tileset's relative references intact under one URL prefix. Works for both
    single-pipeline outputs (output/<id>/...) and batch outputs (output/<prefix>/...).
    """
    norm = posixpath.normpath(path)
    parts = norm.split("/")
    if norm.startswith("/") or ".." in parts or "process" in parts:
        raise HTTPException(status_code=404)

    storage = get_storage()
    key = f"output/{norm}"
    if not storage.exists(key):
        raise HTTPException(status_code=404)
    return StreamingResponse(storage.iter_object(key), media_type=_media_type(norm))
