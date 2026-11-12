import io
import json

from app.core.storage import get_storage, output_url
from app.worker.main import celery
from app.worker.tasks.common.tiles3d import build_parent_tileset


@celery.task(name="finalize_tileset_batch")
def finalize_tileset_batch(*args, output_prefix, base=None):
    """Stitch whatever child tilesets exist under output_prefix into one parent."""
    storage = get_storage()
    prefix = output_prefix.rstrip('/') + '/'
    parent_key = prefix + 'tileset.json'

    children = []
    for key in storage.list(prefix):
        if not key.endswith('/tileset.json') or key == parent_key:
            continue
        data = b''.join(storage.iter_object(key))
        children.append({'uri': key[len(prefix):], 'tileset': json.loads(data)})

    if not children:
        # all children gone: drop the stale parent
        try:
            storage.delete_prefix(parent_key)
        except Exception:
            pass
        return {'tileset': None, 'count': 0}

    parent = build_parent_tileset(children)
    storage.upload_fileobj(io.BytesIO(json.dumps(parent).encode()), parent_key)

    return {
        'tileset': output_url(parent_key) if base else parent_key,
        'count': len(children),
    }
