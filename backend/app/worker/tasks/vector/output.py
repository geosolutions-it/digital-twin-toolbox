"""Publish a finished tiles folder: replace it in the bucket, build the task result."""
from app.core.config import settings


def publish_tiles(storage, tiles_dir, out_base, entry):
    """Upload tiles_dir to <out_base>/tiles; entry is the root file (tileset.json, layer.json)."""
    storage.delete_prefix(f"{out_base}/tiles")
    storage.upload_dir(tiles_dir, f"{out_base}/tiles")
    base = settings.API_V1_STR
    return {
        'output': out_base,
        'tileset': f"{base}/{out_base}/tiles/{entry}",
        'download': f"{base}/{out_base}/tiles/download.zip",
    }
