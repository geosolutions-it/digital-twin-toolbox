import subprocess
import json
import os


def scale_geometric_error(leaf, scale=1):
    scaled_leaf = {**leaf, 'geometricError': leaf['geometricError'] * scale}
    if "children" in leaf:
        return {**scaled_leaf, 'children': [scale_geometric_error(c, scale) for c in leaf['children']]}
    return scaled_leaf


def py3dtiles_convert(input_path, output_path, srs_in, geometric_error_scale_factor=1):
    res = subprocess.run([
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
            "geometricError": data["geometricError"] * geometric_error_scale_factor,
            "root": scale_geometric_error(data['root'], geometric_error_scale_factor)
        }

        with open(tileset_json_path, "w") as f:
            json.dump(updated_tileset, f)
    except Exception as e:
        print(res.stderr)
        raise e
