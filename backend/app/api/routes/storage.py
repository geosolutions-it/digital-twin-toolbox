from typing import Any

from app.api.deps import CurrentUser
from app.core.storage import get_storage
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/")
def list_storage(current_user: CurrentUser, prefix: str = "") -> Any:
    """List one level of the bucket under a prefix: folders and files."""
    prefix = prefix.lstrip("/")
    if ".." in prefix.split("/"):
        raise HTTPException(status_code=400, detail="Invalid prefix")
    return get_storage().list_dir(prefix)
