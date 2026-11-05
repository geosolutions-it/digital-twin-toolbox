"""Publish a finished tiles folder: replace it in the bucket, add a zip download, build the task result."""
import os
import shutil

from app.core.config import settings


def publish_tiles(storage, tiles_dir, out_base, entry, scratch):
    """Upload tiles_dir to <out_base>/tiles plus <out_base>/download.zip; entry is the root file (tileset.json, layer.json)."""
    zip_base = os.path.join(scratch, 'download')
    shutil.make_archive(zip_base, 'zip', tiles_dir)
    storage.delete_prefix(f"{out_base}/tiles")
    storage.upload_dir(tiles_dir, f"{out_base}/tiles")
    storage.upload_file(zip_base + '.zip', f"{out_base}/download.zip")
    base = settings.API_V1_STR
    return {
        'output': out_base,
        'tileset': f"{base}/{out_base}/tiles/{entry}",
        'download': f"{base}/{out_base}/download.zip",
    }
