import os
import re
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

_LOD = re.compile(r"^lod(\d)")
_INT = re.compile(r"-?(0|[1-9]\d*)$")
_SURFACES = {"Polygon", "Triangle", "PolygonPatch"}
_SKIP_TYPES = {"ReliefFeature", "CityObjectGroup"}
_CASTS = {"int": int, "double": float, "measure": float}


def _local(tag):
    return tag.rpartition("}")[2]


def _child_text(el, name):
    for c in el:
        if _local(c.tag) == name:
            return c.text.strip() if c.text and c.text.strip() else None
    return None


def _ring(el):
    rows = None
    for c in el:
        name = _local(c.tag)
        if name == "posList" and c.text:
            vals = np.array(c.text.split(), dtype=np.float64)
            dim = int(c.get("srsDimension") or (3 if len(vals) % 3 == 0 else 2))
            rows = vals.reshape(-1, dim)
            break
        if name == "coordinates" and c.text:
            rows = np.array([t.split(",") for t in c.text.split()], dtype=np.float64)
            break
    if rows is None:
        pos = [c.text.split() for c in el if _local(c.tag) == "pos" and c.text]
        if not pos:
            return np.empty((0, 3))
        rows = np.array(pos, dtype=np.float64)
    if rows.shape[1] == 2:
        rows = np.column_stack([rows, np.zeros(len(rows))])
    rows = rows[:, :3]
    if len(rows) > 1 and np.array_equal(rows[0], rows[-1]):
        rows = rows[:-1]
    return rows


def _collect(el, lod, inst, out):
    """Surfaces keyed by (in an installation, LoD); xlink members have no children, so shared surfaces count once."""
    name = _local(el.tag)
    if "Implicit" in name:
        return
    m = _LOD.match(name)
    if m:
        lod = int(m.group(1))
    elif name.endswith("Installation"):
        inst = True
    if name in _SURFACES:
        if lod is not None:
            rings = [_ring(r) for b in el for r in b if _local(r.tag) == "LinearRing"]
            if rings and len(rings[0]) >= 3:
                out.setdefault((inst, lod), []).append([r for r in rings if len(r) >= 3])
        return
    for c in el:
        _collect(c, lod, inst, out)


def select_lod(groups, max_lod=None):
    """One LoD per object (highest <= max_lod); installations at their best LoD not above it."""
    main = {lod: p for (inst, lod), p in groups.items() if not inst}
    inst = {lod: p for (i, lod), p in groups.items() if i}
    pool = main or inst
    levels = [lod for lod in pool if max_lod is None or lod <= max_lod]
    if not levels:
        return []
    target = max(levels)
    polys = list(pool[target])
    fit = [lod for lod in inst if lod <= target] if main else []
    if fit:
        polys += inst[max(fit)]
    return polys


def _put(props, key, text, kind=""):
    if not key or text is None:
        return
    cast = _CASTS.get(kind.lower())
    if cast is None and _INT.match(text):
        cast = int
    try:
        props[key] = cast(text) if cast else text
    except ValueError:
        props[key] = text


def attributes(obj):
    props = {}
    for k, v in obj.attrib.items():
        if _local(k) == "id":
            props["gml_id"] = v
    for c in obj:
        name = _local(c.tag)
        if name.endswith("Attribute") and c.get("name"):
            _put(props, c.get("name"), _child_text(c, "value"), name[: -len("Attribute")])
        elif name == "genericAttribute":
            for a in c:
                _put(props, _child_text(a, "name"), _child_text(a, "value"), _local(a.tag)[: -len("Attribute")])
        elif len(c) == 0 and c.text and c.text.strip():
            _put(props, name, c.text.strip(), "measure" if c.get("uom") else "")
    return props


def iter_objects(source, max_lod=None):
    """-> (srsName, properties, [polygon rings]) per top-level city object."""
    srs, root = None, None
    for event, el in ET.iterparse(source, events=("start", "end")):
        if event == "start":
            if root is None:
                root = el
            if srs is None:
                srs = el.get("srsName")
            continue
        if _local(el.tag) != "cityObjectMember":
            continue
        for obj in el:
            kind = _local(obj.tag)
            if kind in _SKIP_TYPES:
                continue
            groups = {}
            _collect(obj, None, False, groups)
            polys = select_lod(groups, max_lod)
            if polys:
                yield srs, {"citygml_type": kind, **attributes(obj)}, polys
        root.clear()


def _is_gml(name):
    base = os.path.basename(name)
    return name.lower().endswith(".gml") and "__MACOSX" not in name and not base.startswith(".")


def iter_streams(path):
    if not zipfile.is_zipfile(path):
        yield path
        return
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist() if _is_gml(n))
        if not names:
            raise Exception("No .gml file in the archive")
        for name in names:
            with zf.open(name) as f:
                yield f
