import os
import zipfile
from pathlib import Path

from app.worker.common.utils import get_asset_upload_path
from app.worker.tasks.citygml.processes import run_citygml_tools_merge

GML_ARCHIVE_EXTENSIONS = {".gml.zip"}

# Safety limits for ZIP extraction
MAX_ARCHIVE_FILES = 10_000
MAX_UNCOMPRESSED_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


def _is_gml_candidate(relative_path: str) -> bool:
    if not relative_path.lower().endswith(".gml"):
        return False
    parts = Path(relative_path).parts
    if any(part == "__MACOSX" for part in parts):
        return False
    basename = Path(relative_path).name
    if basename.startswith("._") or basename.startswith("."):
        return False
    return True


def find_gml_paths(directory: str) -> list[str]:
    candidates = []
    for root, _, files in os.walk(directory):
        for name in files:
            relative = os.path.relpath(os.path.join(root, name), directory)
            if _is_gml_candidate(relative):
                candidates.append(os.path.join(root, name))
    candidates.sort()
    return candidates


def extract_gml_archive(
    archive_path: str,
    extract_dir: str,
    max_files: int = MAX_ARCHIVE_FILES,
    max_uncompressed_size: int = MAX_UNCOMPRESSED_SIZE_BYTES,
) -> list[str]:
    os.makedirs(extract_dir, exist_ok=True)
    target_dir = Path(extract_dir).resolve()

    with zipfile.ZipFile(archive_path, "r") as archive:
        members = archive.infolist()

        if len(members) > max_files:
            raise ValueError(
                f"Archive contains {len(members)} files, exceeding limit of {max_files}."
            )

        total_uncompressed_size = 0
        for member in members:
            total_uncompressed_size += member.file_size
            if total_uncompressed_size > max_uncompressed_size:
                raise ValueError(
                    f"Archive uncompressed size exceeds limit of {max_uncompressed_size} bytes."
                )

            destination = (target_dir / member.filename).resolve()
            try:
                destination.relative_to(target_dir)
            except ValueError:
                raise ValueError(f"Unsafe file path in archive: {member.filename}")

        # Safe extraction after pre-validation passes
        for member in members:
            archive.extract(member, path=target_dir)

    gml_paths = find_gml_paths(extract_dir)
    if not gml_paths:
        raise FileNotFoundError(f"No .gml file found under {extract_dir}")
    return gml_paths


def resolve_citygml_input_file(asset_id: str, extension: str) -> str:
    asset_file_path = get_asset_upload_path(f"{asset_id}/index{extension}")
    if extension not in GML_ARCHIVE_EXTENSIONS:
        return asset_file_path

    extract_dir = get_asset_upload_path(f"{asset_id}/extracted")
    marker = os.path.join(extract_dir, ".resolved_gml")
    if os.path.isfile(marker):
        with open(marker) as handle:
            resolved = handle.read().strip()
        if os.path.isfile(resolved):
            return resolved

    if os.path.isdir(extract_dir):
        for root, dirs, files in os.walk(extract_dir, topdown=False):
            for name in files:
                if name == ".resolved_gml":
                    continue
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

    gml_paths = extract_gml_archive(asset_file_path, extract_dir)
    if len(gml_paths) == 1:
        resolved = gml_paths[0]
    else:
        merged_path = os.path.join(extract_dir, "merged.gml")
        run_citygml_tools_merge(gml_paths, merged_path)
        resolved = merged_path

    with open(marker, "w") as handle:
        handle.write(resolved)
    return resolved