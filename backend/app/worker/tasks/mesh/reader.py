import io
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

AXIS_VECTORS = {
    "X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0),
    "NEGATIVE_X": (-1.0, 0.0, 0.0), "NEGATIVE_Y": (0.0, -1.0, 0.0), "NEGATIVE_Z": (0.0, 0.0, -1.0),
}


def _is_obj_candidate(relative_path):
    if not relative_path.lower().endswith(".obj"):
        return False
    if "__MACOSX" in Path(relative_path).parts:
        return False
    return not Path(relative_path).name.startswith(".")


def find_obj_path(directory):
    """Shallowest .obj under directory (macOS resource forks ignored)."""
    candidates = []
    for root, _, files in os.walk(directory):
        for name in files:
            relative = os.path.relpath(os.path.join(root, name), directory)
            if _is_obj_candidate(relative):
                candidates.append(relative)
    if not candidates:
        raise FileNotFoundError("No .obj file found in the mesh archive")
    candidates.sort(key=lambda path: (path.count(os.sep), path))
    return os.path.join(directory, candidates[0])


def extract_mesh_archive(archive_path, extract_dir):
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(extract_dir)
    return find_obj_path(extract_dir)


def resolve_obj(path, scratch):
    """Local .obj path for an uploaded .obj or .obj.zip/.zip archive."""
    if path.lower().endswith(".zip"):
        return extract_mesh_archive(path, os.path.join(scratch, "extracted"))
    return path


def axis_matrix(forward_axis="Y", up_axis="Z"):
    """3x3 file->ENU rotation: forward_axis becomes north (+Y), up_axis becomes up (+Z),
    east completes a right-handed frame (same convention as Blender's OBJ importer)."""
    forward = np.array(AXIS_VECTORS[forward_axis])
    up = np.array(AXIS_VECTORS[up_axis])
    if abs(float(forward @ up)) > 0.5:
        raise ValueError(f"forward_axis {forward_axis} and up_axis {up_axis} must differ")
    return np.stack([np.cross(forward, up), forward, up])


def bbox_from_lines(lines, batch=500_000):
    """{size, offset (bbox centre vs origin)} in file axes, or None."""
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    chunk = []

    def flush():
        nonlocal lo, hi
        xyz = np.array([row.split()[1:4] for row in chunk], dtype=np.float64)
        lo = np.minimum(lo, xyz.min(axis=0))
        hi = np.maximum(hi, xyz.max(axis=0))
        chunk.clear()

    for line in lines:
        if line[:2] == b"v ":
            chunk.append(line)
            if len(chunk) >= batch:
                flush()
    if chunk:
        flush()
    if not np.isfinite(lo).all():
        return None
    return {"size": (hi - lo).tolist(), "offset": ((lo + hi) / 2).tolist()}


def mesh_bbox_from_key(storage, key):
    """Bbox of a bucket .obj or zipped .obj; a zip is read in place, textures untouched."""
    from app.core.storage import open_range

    with open_range(storage, key) as raw:
        if not key.lower().endswith(".zip"):
            return bbox_from_lines(raw)
        with zipfile.ZipFile(raw) as archive:
            names = [n for n in archive.namelist() if _is_obj_candidate(n)]
            if not names:
                raise FileNotFoundError("No .obj file found in the mesh archive")
            names.sort(key=lambda n: (n.count("/"), n))
            with archive.open(names[0]) as member:
                return bbox_from_lines(io.BufferedReader(member, buffer_size=4 << 20))


@dataclass
class ObjMesh:
    """Triangulated OBJ; face_vt is -1 where a face has no UV, uvs have the origin bottom-left."""
    positions: np.ndarray
    uvs: np.ndarray
    face_v: np.ndarray
    face_vt: np.ndarray
    face_mat: np.ndarray
    mat_names: list
    colors: np.ndarray | None
    mtllibs: list


def _floats(chunks, min_width):
    """Join 'a b c ...' lines into an (N, width) float array; width from the first line."""
    if not chunks:
        return np.zeros((0, min_width))
    width = max(len(chunks[0].split()), min_width)
    flat = np.fromstring(b"".join(chunks), dtype=np.float64, sep=" ")
    return flat.reshape(-1, width)


def parse_obj(path):
    """Bulk OBJ parse; quads and n-gons are fan-triangulated. Fast path for all-v/vt/vn faces."""
    v_chunks, vt_chunks = [], []
    tri_chunks, quad_chunks, other_chunks = [], [], []
    tri_mat, quad_mat, other_mat = [], [], []
    mat_names, mat_index, mtllibs = [], {}, []
    current = -1

    with open(path, "rb") as handle:
        for line in handle:
            head = line[:2]
            if head == b"v ":
                v_chunks.append(line[2:].rstrip() + b"\n")
            elif head == b"vt":
                vt_chunks.append(line[3:].rstrip() + b"\n")
            elif head == b"f ":
                # all v/vt/vn tokens: 6 slashes = triangle, 8 = quad
                slashes = line.count(b"/")
                if slashes == 6 and b"//" not in line:
                    tri_chunks.append(line[2:])
                    tri_mat.append(current)
                elif slashes == 8 and b"//" not in line:
                    quad_chunks.append(line[2:])
                    quad_mat.append(current)
                else:
                    other_chunks.append(line[2:])
                    other_mat.append(current)
            elif line.startswith(b"usemtl"):
                parts = line.split(maxsplit=1)
                name = parts[1].strip().decode(errors="ignore") if len(parts) > 1 else ""
                if name not in mat_index:
                    mat_index[name] = len(mat_names)
                    mat_names.append(name)
                current = mat_index[name]
            elif line.startswith(b"mtllib"):
                parts = line.split(maxsplit=1)
                if len(parts) > 1:
                    mtllibs.append(parts[1].strip().decode(errors="ignore"))

    flat = _floats(v_chunks, 3)
    v_chunks.clear()
    positions = np.ascontiguousarray(flat[:, :3])
    colors = None
    if flat.shape[1] >= 6:
        rgb = flat[:, 3:6]
        if rgb.max() <= 1.0 + 1e-6:
            rgb = rgb * 255.0
        colors = np.clip(rgb, 0, 255).astype(np.uint8)
    uvs = np.ascontiguousarray(_floats(vt_chunks, 2)[:, :2])
    vt_chunks.clear()

    def fast(chunks, per_face):
        if not chunks:
            return np.zeros((0, per_face), np.int64), np.zeros((0, per_face), np.int64)
        raw = b"".join(chunks).replace(b"/", b" ")
        ints = np.fromstring(raw, dtype=np.int64, sep=" ").reshape(len(chunks), per_face * 3)
        return ints[:, 0::3] - 1, ints[:, 1::3] - 1

    def general(chunks, mats):
        """'v', 'v/vt', 'v//vn' and mixed arities; vt is -1 where the face has no UVs."""
        out_v, out_vt, out_mat = [], [], []
        for line, mat in zip(chunks, mats):
            vs, vts = [], []
            for token in line.split():
                parts = token.split(b"/")
                vs.append(int(parts[0]) - 1)
                vts.append(int(parts[1]) - 1 if len(parts) > 1 and parts[1] else -1)
            for i in range(1, len(vs) - 1):
                out_v.append((vs[0], vs[i], vs[i + 1]))
                out_vt.append((vts[0], vts[i], vts[i + 1]))
                out_mat.append(mat)
        if not out_v:
            return np.zeros((0, 3), np.int64), np.zeros((0, 3), np.int64), np.zeros(0, np.int32)
        return np.array(out_v, np.int64), np.array(out_vt, np.int64), np.array(out_mat, np.int32)

    tri_v, tri_vt = fast(tri_chunks, 3)
    quad_v, quad_vt = fast(quad_chunks, 4)
    other_v, other_vt, other_m = general(other_chunks, other_mat)
    fan = np.array([[0, 1, 2], [0, 2, 3]])

    face_v = np.vstack([tri_v, quad_v[:, fan].reshape(-1, 3), other_v])
    face_vt = np.vstack([tri_vt, quad_vt[:, fan].reshape(-1, 3), other_vt])
    face_mat = np.concatenate([
        np.array(tri_mat, np.int32), np.repeat(np.array(quad_mat, np.int32), 2), other_m,
    ])
    face_mat[face_mat < 0] = 0
    if len(face_v) and (face_v.min() < 0 or face_v.max() >= len(positions)):
        raise ValueError("OBJ face references a missing vertex (relative indices are not supported)")
    return ObjMesh(positions, uvs, face_v, face_vt, face_mat, mat_names, colors, mtllibs)


def parse_mtl(paths):
    """newmtl name -> diffuse texture path (map_Kd), resolved next to its .mtl."""
    textures = {}
    for path in paths:
        if not os.path.isfile(path):
            continue
        base = os.path.dirname(path)
        current = None
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "newmtl" and len(parts) > 1:
                    current = line.strip()[len("newmtl"):].strip()
                elif parts[0] == "map_Kd" and current and len(parts) > 1:
                    # options precede the name, which may contain spaces
                    whole = os.path.join(base, line.strip()[len("map_Kd"):].strip().replace("\\", "/"))
                    last = os.path.join(base, parts[-1].replace("\\", "/"))
                    textures[current] = whole if os.path.isfile(whole) else last
    return textures


def mtl_paths(obj_path, mesh):
    """mtllib entries next to the OBJ, falling back to <name>.mtl."""
    base = os.path.dirname(obj_path)
    paths = [os.path.join(base, m.replace("\\", "/")) for m in mesh.mtllibs]
    paths.append(os.path.splitext(obj_path)[0] + ".mtl")
    return list(dict.fromkeys(paths))
