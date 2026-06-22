import json
import os

from app.worker.tasks.mesh.create_tileset import run as create_tileset_run


def finalize_mesh_3dtiles_output(tiles_dir: str, depth: int, max_geometric_error: float) -> None:
    """Build tileset.json from info.json without loading Blender."""
    tileset_path = os.path.join(tiles_dir, 'tileset.json')
    if os.path.isfile(tileset_path):
        return

    tileset_info = {}
    info_path = os.path.join(tiles_dir, 'info.json')
    if os.path.isfile(info_path):
        with open(info_path) as f:
            tileset_info = json.load(f)

    tileset = create_tileset_run({
        **tileset_info,
        'depth': depth,
        'output_dir': tiles_dir,
        'max_geometric_error': max_geometric_error,
    })
    with open(tileset_path, 'w') as f:
        json.dump(tileset, f)
