import json

import numpy as np

from app.worker.tasks.vector.citygml.crs import epsg_codes

_SKIP_TYPES = {"TINRelief", "CityObjectGroup"}


def _lod_value(lod):
    try:
        return float(lod)
    except (TypeError, ValueError):
        return None


def _polygons(geom, verts):
    kind = geom.get("type")
    b = geom.get("boundaries") or []
    if kind in ("MultiSurface", "CompositeSurface"):
        surfaces = b
    elif kind == "Solid":
        surfaces = [s for shell in b for s in shell]
    elif kind in ("MultiSolid", "CompositeSolid"):
        surfaces = [s for solid in b for shell in solid for s in shell]
    else:  # points, lines, template instances
        return []
    out = []
    for surface in surfaces:
        rings = [verts[np.asarray(r, dtype=np.int64)] for r in surface if len(r) >= 3]
        if rings:
            out.append(rings)
    return out


def _descendants(objects, oid, seen):
    for c in objects[oid].get("children") or []:
        if c in objects and c not in seen:
            seen.add(c)
            yield c
            yield from _descendants(objects, c, seen)


def _scalar(v):
    return isinstance(v, (str, int, float, bool))


def _objects(objects, verts, srs, max_lod, lod):
    for oid, obj in objects.items():
        if obj.get("parents") or obj.get("type") in _SKIP_TYPES:
            continue
        geoms = [g for i in [oid, *_descendants(objects, oid, {oid})] for g in objects[i].get("geometry") or []]
        lods = {_lod_value(g.get("lod")) for g in geoms} - {None}
        lods = {v for v in lods if (max_lod is None or int(v) <= max_lod) and (lod is None or v == lod)}
        if not lods:
            continue
        target = max(lods)
        polys = [p for g in geoms if _lod_value(g.get("lod")) == target for p in _polygons(g, verts)]
        if not polys:
            continue
        props = {"gml_id": oid, "citygml_type": obj.get("type")}
        props.update({k: v for k, v in (obj.get("attributes") or {}).items() if _scalar(v)})
        yield srs, props, polys


def _vertices(doc, transform):
    verts = np.asarray(doc.get("vertices") or [], dtype=np.float64).reshape(-1, 3)
    if transform:
        verts = verts * np.asarray(transform["scale"]) + np.asarray(transform["translate"])
    return verts


def _reference_system(doc):
    """CityJSON is always x, y, z: the short EPSG:n form keeps that order for geographic CRSs."""
    ref = (doc.get("metadata") or {}).get("referenceSystem")
    codes = epsg_codes(ref)
    return "+".join(f"EPSG:{c}" for c in codes[:2]) if codes else ref


def iter_cityjson(source, max_lod=None, lod=None):
    """max_lod caps the LoD family (2 allows 2.0-2.3), lod keeps that exact level only."""
    f = open(source, "rb") if isinstance(source, str) else source
    try:
        head = f.readline()
        try:
            first = json.loads(head)
        except ValueError:
            first = json.loads(head + f.read())  # formatted, multi-line
        if not isinstance(first, dict) or first.get("type") != "CityJSON":
            raise Exception("Not a CityJSON file")
        if first.get("CityObjects"):
            yield from _objects(first["CityObjects"], _vertices(first, first.get("transform")),
                                _reference_system(first), max_lod, lod)
            return
        # CityJSONSeq: features share the header's transform
        srs = _reference_system(first)
        for line in f:
            if line.strip():
                feat = json.loads(line)
                yield from _objects(feat["CityObjects"], _vertices(feat, first.get("transform")),
                                    srs, max_lod, lod)
    finally:
        if isinstance(source, str):
            f.close()
