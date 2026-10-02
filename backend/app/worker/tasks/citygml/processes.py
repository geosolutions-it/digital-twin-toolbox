import json
import os

from app.worker.common.utils import run_subprocess

MAGO_3D_TILER_JAR = os.environ.get("MAGO_3D_TILER_JAR", "/bin/mago-3d-tiler.jar")
CITYGML_TOOLS_BIN = os.environ.get("CITYGML_TOOLS_BIN", "citygml-tools")


def _run_checked(command: list[str]) -> None:
    result = run_subprocess(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(detail or f"Command failed: {' '.join(command)}")


def run_ogrinfo_json(path: str) -> dict:
    try:
        result = run_subprocess(
            ["ogrinfo", path, "-json", "-ro"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ogrinfo is not available in the worker environment. "
            "Install gdal-bin in the vector worker image."
        ) from exc
    if not result.stdout.strip():
        raise RuntimeError(result.stderr.strip() or "ogrinfo failed")
    if result.returncode != 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(result.stderr.strip() or "ogrinfo failed") from exc
    return json.loads(result.stdout)


def run_mago_3d_tiler(
    input_path: str,
    output_dir: str,
    crs: int,
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    command = [
        "java",
        "-jar",
        MAGO_3D_TILER_JAR,
        "-input",
        input_path,
        "-output",
        output_dir,
        "-inputType",
        "citygml",
        "--crs",
        str(crs),
        "--quiet",
    ]
    _run_checked(command)


def run_citygml_tools_subset(
    input_path: str,
    output_dir: str,
    start_index: int,
    limit: int,
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    _run_checked(
        [
            CITYGML_TOOLS_BIN,
            "subset",
            input_path,
            "--start-index",
            str(start_index),
            "--limit",
            str(limit),
            "-o",
            output_dir,
        ],
    )
    basename = os.path.basename(input_path)
    output_path = os.path.join(output_dir, basename)
    if os.path.isfile(output_path):
        return output_path

    gml_files = [
        os.path.join(output_dir, name)
        for name in os.listdir(output_dir)
        if name.lower().endswith(".gml")
    ]
    if len(gml_files) == 1:
        return gml_files[0]
    if not gml_files:
        raise FileNotFoundError(f"No GML output produced in {output_dir}")
    gml_files.sort()
    return gml_files[0]


def run_citygml_tools_merge(input_paths: list[str], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    _run_checked(
        [
            CITYGML_TOOLS_BIN,
            "merge",
            *input_paths,
            "-o",
            output_path,
        ],
    )