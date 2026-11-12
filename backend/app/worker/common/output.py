"""tiles/ holds what viewers load (and the download zip), artifacts/ anything else a job writes."""
import os

from app.core.storage import output_url


def publish_tiles(storage, tiles_dir, out_base, entry, artifacts=None):
    """artifacts: {name: local path}; both folders are replaced on every run."""
    storage.delete_prefix(f"{out_base}/tiles/")
    storage.upload_dir(tiles_dir, f"{out_base}/tiles")
    storage.delete_prefix(f"{out_base}/artifacts/")
    listed = []
    for name, path in (artifacts or {}).items():
        key = f"{out_base}/artifacts/{name}"
        storage.upload_file(path, key)
        listed.append({'name': name, 'url': output_url(key), 'size': os.path.getsize(path)})
    result = {
        'output': out_base,
        'tileset': output_url(f"{out_base}/tiles/{entry}"),
        'download': output_url(f"{out_base}/tiles/download.zip"),
    }
    if listed:
        result['artifacts'] = listed
    return result
