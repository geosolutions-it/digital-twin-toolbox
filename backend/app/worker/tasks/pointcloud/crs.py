import re

from pyproj import CRS

_EPSG_AUTHORITY_RE = re.compile(r'AUTHORITY\["EPSG","(\d+)"\]', re.IGNORECASE)


def identify_projection(projection):
    if not projection:
        return None
    try:
        crs = CRS(projection)
        epsg = crs.to_epsg()
        if epsg is not None:
            return epsg
        authority = crs.to_authority()
        if authority and authority[0].upper() == 'EPSG':
            return int(authority[1])
    except Exception:
        pass

    matches = _EPSG_AUTHORITY_RE.findall(str(projection))
    if matches:
        return int(matches[-1])

    return None


def _epsg_codes_from_srs_json(srs_json):
    horizontal = None
    vertical = None
    if not srs_json:
        return horizontal, vertical

    for comp in srs_json.get('components', []):
        source = comp.get('source_crs') or comp
        if not isinstance(source, dict):
            continue
        cid = source.get('id')
        if not cid or str(cid.get('authority', '')).upper() != 'EPSG':
            continue
        code = int(cid['code'])
        crs_type = (source.get('type') or comp.get('type') or '').lower()
        if 'vert' in crs_type:
            vertical = code
        elif horizontal is None:
            horizontal = code

    return horizontal, vertical


def resolve_epsg_codes_from_pdal_metadata(metadata):
    srs = metadata.get('srs') or {}

    horizontal = identify_projection(srs.get('horizontal'))
    vertical = identify_projection(srs.get('vertical'))
    epsg = identify_projection(metadata.get('comp_spatialreference'))

    if horizontal is None or vertical is None:
        json_horizontal, json_vertical = _epsg_codes_from_srs_json(srs.get('json'))
        if horizontal is None:
            horizontal = json_horizontal
        if vertical is None:
            vertical = json_vertical

    if epsg is None or epsg == vertical:
        epsg = horizontal

    return {
        'epsg': epsg,
        'horizontal_epsg': horizontal,
        'vertical_epsg': vertical,
    }
