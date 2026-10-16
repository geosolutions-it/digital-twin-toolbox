import json
import os
import math
import struct

from app.worker.common.utils import run_subprocess


def _pnts_point_count(pnts_path):
    try:
        with open(pnts_path, "rb") as f:
            head = f.read(28)
            if head[0:4] != b"pnts":
                return None
            ft_json_len = struct.unpack_from("<I", head, 12)[0]
            ft = json.loads(f.read(ft_json_len).decode("utf-8"))
        return ft.get("POINTS_LENGTH")
    except Exception:
        return None


def _box_projected_area(box):
    # box = [cx,cy,cz, x-half(3), y-half(3), z-half(3)]; full extent = 2*||half-axis||
    ex = 2 * math.sqrt(box[3] ** 2 + box[4] ** 2 + box[5] ** 2)
    ey = 2 * math.sqrt(box[6] ** 2 + box[7] ** 2 + box[8] ** 2)
    ez = 2 * math.sqrt(box[9] ** 2 + box[10] ** 2 + box[11] ** 2)
    dims = sorted([ex, ey, ez], reverse=True)
    return dims[0] * dims[1]


def _node_spacing(node, base_dir):
    """Point spacing of a node's content: sqrt(projected box area / point count)."""
    content = node.get("content") or {}
    uri = content.get("uri")
    box = (node.get("boundingVolume") or {}).get("box")
    if uri and uri.endswith(".pnts") and box:
        n = _pnts_point_count(os.path.join(base_dir, uri))
        if n and n > 0:
            area = _box_projected_area(box)
            if area > 0:
                return math.sqrt(area / n)
    return None


def _recompute_geometric_error(tileset_path):
    """Set each node's geometricError to its real point spacing (leaves 0), so the
    tileset refines correctly at Cesium's default maximumScreenSpaceError. Recurses
    into external sub-tilesets. Returns the root's geometricError."""
    base_dir = os.path.dirname(tileset_path)
    with open(tileset_path) as f:
        data = json.load(f)

    def visit(node):
        for child in (node.get("children") or []):
            visit(child)
        content = node.get("content") or {}
        uri = content.get("uri")
        if uri and uri.endswith(".json"):
            sub = _recompute_geometric_error(os.path.join(base_dir, uri))
            node["geometricError"] = sub if sub is not None else node.get("geometricError", 0.0)
        elif node.get("children"):
            sp = _node_spacing(node, base_dir)
            node["geometricError"] = sp if sp is not None else node.get("geometricError", 0.0)
        else:
            node["geometricError"] = 0.0

    root = data["root"]
    visit(root)
    # top-level geometricError left as-is: shrinking it culls the tileset when zoomed out
    with open(tileset_path, "w") as f:
        json.dump(data, f)
    return root.get("geometricError")


def py3dtiles_convert(input_path, output_path, srs_in, include_classification=False, include_intensity=False):
    cmd = [
        'py3dtiles', 'convert', input_path,
        '--overwrite', '--force-srs-in',
        '--color_scale', "255",
        '--out', output_path,
        '--srs_in', srs_in,
        '--srs_out', '4978',
    ]
    if include_classification:
        cmd.append('--classification')
    if include_intensity:
        cmd.append('--intensity')

    res = run_subprocess(cmd, capture_output=True, text=True)

    tileset_json_path = os.path.join(output_path, 'tileset.json')
    try:
        _recompute_geometric_error(tileset_json_path)
        if include_classification:
            with open(tileset_json_path) as f:
                data = json.load(f)
            data["properties"] = {"Classification": {"minimum": 0, "maximum": 255}}
            with open(tileset_json_path, "w") as f:
                json.dump(data, f)
    except Exception as e:
        print(res.stderr)
        raise e
