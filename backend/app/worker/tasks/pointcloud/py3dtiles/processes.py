import subprocess
import json
import os
from app.worker.common.utils import run_subprocess


def _as_float(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {name}: {value!r}") from exc


def scale_geometric_error(leaf, scale=1):
    scaled_leaf = {**leaf, 'geometricError': _as_float(leaf['geometricError'], 'geometricError') * scale}
    if "children" in leaf:
        return {**scaled_leaf, 'children': [scale_geometric_error(c, scale) for c in leaf['children']]}
    return scaled_leaf


def py3dtiles_convert(input_path, output_path, srs_in, geometric_error_scale_factor=1):
    scale = _as_float(geometric_error_scale_factor, 'geometric_error_scale_factor')

    res = run_subprocess([
        'py3dtiles', 'convert', input_path,
        '--overwrite', '--classification', '--force-srs-in',
        '--color_scale', "255",
        '--out', output_path,
        '--srs_in', srs_in,
        '--srs_out', '4978',
        '--intensity'
    ], capture_output=True, text=True)

    try:
        tileset_json_path = os.path.join(output_path, 'tileset.json')
        with open(tileset_json_path, "r") as f:
            data = json.load(f)

        updated_tileset = {
            **data,
            "properties": {"Classification": {"minimum": 0, "maximum": 255}},
            "geometricError": _as_float(data["geometricError"], 'geometricError') * scale,
            "root": scale_geometric_error(data['root'], scale)
        }

        with open(tileset_json_path, "w") as f:
            json.dump(updated_tileset, f)
    except Exception as e:
        print(res.stderr)
        raise e
