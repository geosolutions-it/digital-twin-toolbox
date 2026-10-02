import os
import re
import xml.etree.ElementTree as ET

from app.worker.tasks.pointcloud.crs import identify_projection

_EPSG_CODE_RE = re.compile(r"EPSG[:\s]+(\d+)", re.IGNORECASE)
_SRS_NAME_ATTR_RE = re.compile(r'srsName="([^"]+)"', re.IGNORECASE)
_LOWER_CORNER_RE = re.compile(
    r"<(?:\w+:)?lowerCorner>([^<]+)</(?:\w+:)?lowerCorner>",
    re.IGNORECASE,
)
_UPPER_CORNER_RE = re.compile(
    r"<(?:\w+:)?upperCorner>([^<]+)</(?:\w+:)?upperCorner>",
    re.IGNORECASE,
)

_PRIMARY_LAYER_NAMES = ("Building", "CityModel", "cityObjectMember")


def parse_horizontal_epsg_from_srs_value(srs_value: str) -> int | None:
    match = _EPSG_CODE_RE.search(srs_value)
    return int(match.group(1)) if match else None


def _read_srs_from_gfs(gml_path: str) -> str | None:
    gfs_path = f"{os.path.splitext(gml_path)[0]}.gfs"
    if not os.path.isfile(gfs_path):
        return None
    try:
        root = ET.parse(gfs_path).getroot()
    except ET.ParseError:
        return None
    srs_name = root.findtext(".//SRSName")
    return srs_name.strip() if srs_name else None


def _read_srs_from_gml_header(gml_path: str) -> str | None:
    with open(gml_path, "rb") as handle:
        chunk = handle.read(65536).decode("utf-8", errors="ignore")
    match = _SRS_NAME_ATTR_RE.search(chunk)
    return match.group(1).strip() if match else None


def select_primary_layer(layers: list[dict]) -> dict:
    if not layers:
        raise ValueError("No layers found in GML file")

    for preferred_name in _PRIMARY_LAYER_NAMES:
        for layer in layers:
            if layer.get("name") == preferred_name:
                return layer

    for layer in layers:
        for geometry_field in layer.get("geometryFields") or []:
            field_type = (geometry_field.get("type") or "").lower()
            if not field_type or field_type in {"none", "unknown"}:
                continue
            return layer

    for layer in layers:
        if layer.get("geometryFields"):
            return layer

    raise ValueError("No geometry layer found in GML file")


def _read_envelope_extent(gml_path: str) -> list[float] | None:
    with open(gml_path, "rb") as handle:
        chunk = handle.read(262144).decode("utf-8", errors="ignore")

    lower_match = _LOWER_CORNER_RE.search(chunk)
    upper_match = _UPPER_CORNER_RE.search(chunk)
    if not lower_match or not upper_match:
        return None

    lower = [float(value) for value in lower_match.group(1).split()]
    upper = [float(value) for value in upper_match.group(1).split()]
    if len(lower) < 2 or len(upper) < 2:
        return None

    return [lower[0], lower[1], upper[0], upper[1]]


def resolve_epsg_code(gml_path: str, info: dict, layer: dict | None = None) -> int:
    layers = info.get("layers") or []
    if not layers:
        raise ValueError("No layers found in GML file")

    if layer is None:
        layer = select_primary_layer(layers)

    geometry_fields = layer.get("geometryFields") or []
    horizontal_epsg = None

    if geometry_fields:
        coordinate_system = geometry_fields[0].get("coordinateSystem")
        if coordinate_system:
            projjson = coordinate_system.get("projjson") or {}
            for component in projjson.get("components") or []:
                component_id = component.get("id") or {}
                if str(component_id.get("authority", "")).upper() != "EPSG":
                    continue
                component_type = (component.get("type") or "").lower()
                if "vert" in component_type:
                    continue
                horizontal_epsg = int(component_id["code"])
                break

            wkt = coordinate_system.get("wkt")
            if wkt and horizontal_epsg is None:
                horizontal_epsg = parse_horizontal_epsg_from_srs_value(wkt)
                if horizontal_epsg is None:
                    horizontal_epsg = identify_projection(wkt)

    for srs_value in (_read_srs_from_gfs(gml_path), _read_srs_from_gml_header(gml_path)):
        if not srs_value:
            continue
        parsed_horizontal = parse_horizontal_epsg_from_srs_value(srs_value)
        if horizontal_epsg is None and parsed_horizontal is not None:
            horizontal_epsg = parsed_horizontal

    if horizontal_epsg is None:
        raise ValueError("Missing spatial reference system")

    return horizontal_epsg


def resolve_layer_extent(layer: dict, gml_path: str | None = None) -> list[float] | None:
    extent = layer.get("extent")
    if extent and len(extent) >= 4:
        return [float(value) for value in extent[:4]]

    for geometry_field in layer.get("geometryFields") or []:
        field_extent = geometry_field.get("extent")
        if field_extent and len(field_extent) >= 4:
            return [float(value) for value in field_extent[:4]]

    if gml_path:
        return _read_envelope_extent(gml_path)

    return None
