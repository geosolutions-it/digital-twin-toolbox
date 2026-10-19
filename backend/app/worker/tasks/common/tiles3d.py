"""Combine several 3D Tiles tilesets into one parent that references them by uri.

Content-agnostic: children just need a standard tileset.json in a shared global
frame (ECEF/WGS84). No tiles are read or re-tiled.
"""
import io
import json

from app.core.storage import get_storage
from app.worker.main import celery


def _box_corners(box):
    cx, cy, cz = box[0:3]
    hx = box[3:6]
    hy = box[6:9]
    hz = box[9:12]
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                corners.append((
                    cx + sx * hx[0] + sy * hy[0] + sz * hz[0],
                    cy + sx * hx[1] + sy * hy[1] + sz * hz[1],
                    cz + sx * hx[2] + sy * hy[2] + sz * hz[2],
                ))
    return corners


def _apply_transform(tf, p):
    if not tf:
        return p
    x, y, z = p
    return (
        tf[0] * x + tf[4] * y + tf[8] * z + tf[12],
        tf[1] * x + tf[5] * y + tf[9] * z + tf[13],
        tf[2] * x + tf[6] * y + tf[10] * z + tf[14],
    )


def _aabb_box(corners):
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    zs = [c[2] for c in corners]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    hx = (max(xs) - min(xs)) / 2
    hy = (max(ys) - min(ys)) / 2
    hz = (max(zs) - min(zs)) / 2
    return [cx, cy, cz, hx, 0, 0, 0, hy, 0, 0, 0, hz]


def build_parent_tileset(children):
    """children: list of {'uri': str, 'tileset': dict}. Returns a parent tileset dict."""
    child_nodes = []
    ge_values = []
    world_corners = []
    region = None
    use_region = False
    version = "1.1"
    properties = {}
    ext_used = set()
    ext_required = set()

    for child in children:
        ts = child['tileset']
        root = ts.get('root', {})
        bv = root.get('boundingVolume', {})
        # top-level GE, not the tiny root/density one, or Cesium never refines in (blank parent)
        ge = ts.get('geometricError') or root.get('geometricError', 0)
        tf = root.get('transform')
        ge_values.append(ge)
        version = ts.get('asset', {}).get('version', version)

        for name, prop in (ts.get('properties') or {}).items():
            if name not in properties:
                properties[name] = dict(prop)
                continue
            if 'minimum' in prop:
                properties[name]['minimum'] = min(
                    properties[name].get('minimum', prop['minimum']), prop['minimum']
                )
            if 'maximum' in prop:
                properties[name]['maximum'] = max(
                    properties[name].get('maximum', prop['maximum']), prop['maximum']
                )
        ext_used.update(ts.get('extensionsUsed') or [])
        ext_required.update(ts.get('extensionsRequired') or [])

        # node gets a world-space bbox and no transform: the external tileset's root
        # transform already places it, so repeating it here would double-apply
        if 'region' in bv:
            use_region = True
            r = bv['region']
            node_bv = {'region': list(r)}
            if region is None:
                region = list(r)
            else:
                region = [
                    min(region[0], r[0]), min(region[1], r[1]),
                    max(region[2], r[2]), max(region[3], r[3]),
                    min(region[4], r[4]), max(region[5], r[5]),
                ]
        elif 'box' in bv:
            corners = [_apply_transform(tf, c) for c in _box_corners(bv['box'])]
            world_corners.extend(corners)
            node_bv = {'box': _aabb_box(corners)}
        elif 'sphere' in bv:
            cx, cy, cz, rad = bv['sphere']
            fake = [cx, cy, cz, rad, 0, 0, 0, rad, 0, 0, 0, rad]
            corners = [_apply_transform(tf, c) for c in _box_corners(fake)]
            world_corners.extend(corners)
            node_bv = {'box': _aabb_box(corners)}
        else:
            node_bv = bv

        child_nodes.append({
            'boundingVolume': node_bv,
            'geometricError': ge,
            'refine': root.get('refine', 'ADD'),
            'content': {'uri': child['uri']},
        })

    root_ge = max(ge_values) if ge_values else 0
    if use_region:
        parent_bv = {'region': region}
    else:
        parent_bv = {'box': _aabb_box(world_corners)}

    tileset = {
        'asset': {'version': version},
        'geometricError': root_ge,
        'root': {
            'boundingVolume': parent_bv,
            'geometricError': root_ge,
            'refine': 'ADD',
            'children': child_nodes,
        },
    }
    if properties:
        tileset['properties'] = properties
    if ext_used:
        tileset['extensionsUsed'] = sorted(ext_used)
    if ext_required:
        tileset['extensionsRequired'] = sorted(ext_required)
    return tileset


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
        'tileset': f"{base}/{parent_key}" if base else parent_key,
        'count': len(children),
    }
