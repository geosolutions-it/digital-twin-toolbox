import os
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings

router = APIRouter()

_OUTPUT_DIR = os.path.join(settings.ASSETS_DATA, "output")

@router.get("/{pipeline_id}/{path:path}")
def serve_output_artifact(pipeline_id: str, path: str):
    """Serve only the public pipeline artifacts (3D Tiles + download.zip), never process/."""
    try:
        uuid.UUID(pipeline_id)
    except ValueError:
        raise HTTPException(status_code=404)

    base = os.path.realpath(os.path.join(_OUTPUT_DIR, pipeline_id))
    target = os.path.realpath(os.path.join(base, path))
    if target != base and not target.startswith(base + os.sep):
        raise HTTPException(status_code=404)

    rel = os.path.relpath(target, base)
    if rel != 'download.zip' and rel != 'tiles' and not rel.startswith('tiles' + os.sep):
        raise HTTPException(status_code=404)
    if not os.path.isfile(target):
        raise HTTPException(status_code=404)
    return FileResponse(target)
