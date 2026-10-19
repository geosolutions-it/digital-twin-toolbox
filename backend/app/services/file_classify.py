"""Pick a workflow for a bucket file: by extension, or for a .zip by its inner
contents (central directory read via range requests, so a big batch stays cheap)."""
import struct

_EXT_WORKFLOW = {
    ".las": "PointCloud",
    ".laz": "PointCloud",
    ".fgb": "Polygon",
    ".gpkg": "Polygon",
    ".geojson": "Polygon",
    ".tif": "Terrain",
    ".tiff": "Terrain",
    ".vrt": "Terrain",
}

# inner-file suffix -> workflow, checked in order
_ZIP_SIGNATURES = [
    (".shp", "Polygon"),
]

SUPPORTED_EXTENSIONS = tuple(_EXT_WORKFLOW) + (".zip",)

_EOCD_SIG = b"PK\x05\x06"
_CD_SIG = 0x02014B50
_MAX_COMMENT = 65535


def _zip_entry_names(storage, key):
    """Entry filenames from a zip's central directory, read via range requests."""
    size = storage.size(key)
    tail_len = min(size, 22 + _MAX_COMMENT)
    tail = storage.read_range(key, size - tail_len, tail_len)

    eocd = tail.rfind(_EOCD_SIG)
    if eocd < 0:
        return None  # not a zip, or zip64 we do not parse

    total, cd_size, cd_offset = struct.unpack_from("<HII", tail, eocd + 10)
    if cd_offset == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:
        return None  # zip64

    tail_start = size - tail_len
    if cd_offset >= tail_start:
        cd = tail[cd_offset - tail_start: cd_offset - tail_start + cd_size]
    else:
        cd = storage.read_range(key, cd_offset, cd_size)

    names = []
    pos = 0
    for _ in range(total):
        if struct.unpack_from("<I", cd, pos)[0] != _CD_SIG:
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", cd, pos + 28)
        name = cd[pos + 46: pos + 46 + name_len]
        names.append(name.decode("utf-8", "replace").lower())
        pos += 46 + name_len + extra_len + comment_len
    return names


def _classify_zip(storage, key):
    try:
        names = _zip_entry_names(storage, key)
    except Exception:
        return None
    if not names:
        return None
    for suffix, workflow in _ZIP_SIGNATURES:
        if any(n.endswith(suffix) for n in names):
            return workflow
    return None


def classify_bucket_file(storage, key):
    """Workflow name for a bucket key, or None if nothing handles it."""
    lower = key.lower()
    if lower.endswith(".zip"):
        return _classify_zip(storage, key)
    for ext, workflow in _EXT_WORKFLOW.items():
        if lower.endswith(ext):
            return workflow
    return None
