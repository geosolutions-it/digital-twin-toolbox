import uuid
import posixpath
import mimetypes
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.storage import get_storage, output_key

router = APIRouter()


def _media_type(name):
    mt, _ = mimetypes.guess_type(name)
    return mt or "application/octet-stream"


@router.get("/{pipeline_id}/{path:path}")
def serve_output_artifact(pipeline_id: str, path: str):
    """Serve only public pipeline artifacts (3D Tiles + download.zip), never process/.

    Proxies the object through the storage layer so it works on any backend and
    keeps the tileset's relative references intact under one URL prefix.
    """
    try:
        uuid.UUID(pipeline_id)
    except ValueError:
        raise HTTPException(status_code=404)

    norm = posixpath.normpath(path)
    if norm.startswith("/") or norm == ".." or ".." in norm.split("/"):
        raise HTTPException(status_code=404)
    if norm != "download.zip" and norm != "tiles" and not norm.startswith("tiles/"):
        raise HTTPException(status_code=404)

    storage = get_storage()
    key = output_key(pipeline_id, norm)
    if not storage.exists(key):
        raise HTTPException(status_code=404)
    return StreamingResponse(storage.iter_object(key), media_type=_media_type(norm))
