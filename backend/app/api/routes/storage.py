import os
from typing import Any

from app.api.deps import CurrentUser
from app.core.storage import get_storage
from fastapi import APIRouter, HTTPException, UploadFile

router = APIRouter()


@router.get("/")
def list_storage(current_user: CurrentUser, prefix: str = "") -> Any:
    """List one level of the bucket under a prefix: folders and files."""
    prefix = prefix.lstrip("/")
    if ".." in prefix.split("/"):
        raise HTTPException(status_code=400, detail="Invalid prefix")
    return get_storage().list_dir(prefix)


def _unique_key(storage, key: str) -> str:
    if not storage.exists(key):
        return key
    stem, ext = os.path.splitext(key)
    i = 1
    while storage.exists(f"{stem}-{i}{ext}"):
        i += 1
    return f"{stem}-{i}{ext}"


@router.post("/upload")
async def upload_to_storage(
    current_user: CurrentUser, file: UploadFile, prefix: str = ""
) -> Any:
    """Drop a file into the bucket at <prefix>/<name>, auto-suffixing on collision."""
    name = os.path.basename(file.filename or "")
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    prefix = prefix.strip("/")
    if ".." in prefix.split("/"):
        raise HTTPException(status_code=400, detail="Invalid prefix")

    storage = get_storage()
    key = _unique_key(storage, f"{prefix}/{name}" if prefix else name)
    storage.upload_fileobj(file.file, key)
    return {"key": key}
