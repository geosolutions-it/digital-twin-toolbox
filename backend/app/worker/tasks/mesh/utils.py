import os
import zipfile
from pathlib import Path

from app.worker.common.utils import get_asset_upload_path

MESH_ARCHIVE_EXTENSIONS = {".obj.zip", ".zip"}


def _is_mesh_obj_candidate(relative_path: str) -> bool:
    if not relative_path.lower().endswith(".obj"):
        return False
    parts = Path(relative_path).parts
    if any(part == "__MACOSX" for part in parts):
        return False
    basename = Path(relative_path).name
    if basename.startswith("._") or basename.startswith("."):
        return False
    return True


def find_obj_path(directory: str) -> str:
    candidates = []
    for root, _, files in os.walk(directory):
        for name in files:
            relative = os.path.relpath(os.path.join(root, name), directory)
            if _is_mesh_obj_candidate(relative):
                candidates.append(relative)
    if not candidates:
        raise FileNotFoundError(f"No .obj file found under {directory}")
    candidates.sort(key=lambda path: (path.count(os.sep), path))
    return os.path.join(directory, candidates[0])


def extract_mesh_archive(archive_path: str, extract_dir: str) -> str:
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(extract_dir)
    return find_obj_path(extract_dir)


def resolve_mesh_input_file(asset_id: str, extension: str) -> str:
    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")
    if extension in MESH_ARCHIVE_EXTENSIONS:
        extract_dir = get_asset_upload_path(f"{asset_id}/extracted")
        marker = os.path.join(extract_dir, ".extracted")
        if not os.path.isfile(marker):
            if os.path.isdir(extract_dir):
                for root, dirs, files in os.walk(extract_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
            obj_path = extract_mesh_archive(asset_file_path, extract_dir)
            with open(marker, "w") as f:
                f.write(obj_path)
        else:
            with open(marker) as f:
                obj_path = f.read().strip()
            if not os.path.isfile(obj_path):
                obj_path = extract_mesh_archive(asset_file_path, extract_dir)
                with open(marker, "w") as f:
                    f.write(obj_path)
        return obj_path
    return asset_file_path


def estimate_mesh_bbox_from_obj(filepath: str) -> dict | None:
    """size [w, d, h] and offset (bbox center vs model origin) [x, y, z], in meters."""
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    vertex_count = 0

    with open(filepath, encoding="utf-8", errors="ignore") as obj_file:
        for line in obj_file:
            if not line.startswith("v "):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            except ValueError:
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            min_z = min(min_z, z)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            max_z = max(max_z, z)
            vertex_count += 1

    if vertex_count == 0:
        return None

    return {
        "size": [max_x - min_x, max_y - min_y, max_z - min_z],
        "offset": [(min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2],
    }
