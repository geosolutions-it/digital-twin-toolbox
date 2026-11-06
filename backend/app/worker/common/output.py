"""Publish a finished tiles folder: replace it in the bucket, build the task result."""
from app.core.storage import output_url


def publish_tiles(storage, tiles_dir, out_base, entry):
    """Upload tiles_dir to <out_base>/tiles; entry is the root file (tileset.json, layer.json)."""
    storage.delete_prefix(f"{out_base}/tiles/")
    storage.upload_dir(tiles_dir, f"{out_base}/tiles")
    return {
        'output': out_base,
        'tileset': output_url(f"{out_base}/tiles/{entry}"),
        'download': output_url(f"{out_base}/tiles/download.zip"),
    }
