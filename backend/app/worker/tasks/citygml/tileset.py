import json
import math
import os


def _read_tileset(path: str) -> dict:
    with open(path) as handle:
        return json.load(handle)


def _region_from_tileset(tileset: dict) -> list[float] | None:
    root = tileset.get("root") or {}
    bounding_volume = root.get("boundingVolume") or {}
    region = bounding_volume.get("region")
    if not region or len(region) < 6:
        return None
    return [float(value) for value in region[:6]]


def _union_regions(regions: list[list[float]]) -> list[float]:
    west = min(region[0] for region in regions)
    south = min(region[1] for region in regions)
    east = max(region[2] for region in regions)
    north = max(region[3] for region in regions)
    min_height = min(region[4] for region in regions)
    max_height = max(region[5] for region in regions)
    return [west, south, east, north, min_height, max_height]


def build_parent_tileset(tiles_dir: str, child_names: list[str]) -> str:
    children = []
    regions = []
    max_geometric_error = 0.0

    for child_name in child_names:
        child_tileset_path = os.path.join(tiles_dir, child_name, "tileset.json")
        if not os.path.isfile(child_tileset_path):
            raise FileNotFoundError(f"Missing child tileset: {child_tileset_path}")

        child_tileset = _read_tileset(child_tileset_path)
        child_root = child_tileset.get("root") or {}
        child_region = _region_from_tileset(child_tileset)
        if child_region is None:
            raise ValueError(f"Child tileset has no region bounding volume: {child_tileset_path}")

        regions.append(child_region)
        child_geometric_error = float(
            child_root.get("geometricError", child_tileset.get("geometricError", 0.0))
        )
        max_geometric_error = max(max_geometric_error, child_geometric_error)

        children.append({
            "boundingVolume": {"region": child_region},
            "geometricError": child_geometric_error,
            "content": {"uri": f"{child_name}/tileset.json"},
        })

    parent_region = _union_regions(regions)
    parent_geometric_error = max_geometric_error * 2 if max_geometric_error > 0 else 500.0

    parent_tileset = {
        "asset": {"version": "1.0"},
        "geometricError": parent_geometric_error,
        "root": {
            "boundingVolume": {"region": parent_region},
            "geometricError": parent_geometric_error,
            "refine": "ADD",
            "children": children,
        },
    }

    parent_path = os.path.join(tiles_dir, "tileset.json")
    with open(parent_path, "w") as handle:
        json.dump(parent_tileset, handle, indent=2)
    return parent_path


def tileset_region_to_wgs84_degrees(region: list[float]) -> list[float]:
    return [
        math.degrees(region[0]),
        math.degrees(region[1]),
        math.degrees(region[2]),
        math.degrees(region[3]),
    ]
