import os
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from app.worker.main import celery
from app.worker.common.utils import run_subprocess

DENOISE_DEFAULTS = {
    'sample_radius': 0.1,
    'outlier_mean_k': 32,
    'outlier_multiplier': 2.2,
    'divider_capacity': 5000000,
    'max_workers': 8,
    'order': 'X,Y,Z,NormalX,NormalY,NormalZ',
}


def _run_pdal(stages, pipeline_path):
    with open(pipeline_path, 'w') as f:
        json.dump(stages, f)
    run_subprocess(['pdal', 'pipeline', pipeline_path], check=True)


def _denoise_partition(work_dir, file, params):
    _run_pdal([
        {"type": "readers.las", "filename": os.path.join(work_dir, file)},
        {"type": "filters.sample", "radius": params['sample_radius']},
        {"type": "filters.assign", "assignment": "Classification[:]=0"},
        {"type": "filters.outlier", "method": "statistical",
         "mean_k": params['outlier_mean_k'], "multiplier": params['outlier_multiplier']},
        {"type": "filters.range", "limits": "Classification![7:7]"},
        {"type": "writers.las", "filename": os.path.join(work_dir, f"processed_{file}"), "extra_dims": "all"},
    ], os.path.join(work_dir, f"{file}.pipeline.json"))


def denoise(input_file, output_file, params=None):
    """Generic pdal denoise: partition, per-part sample + outlier removal, merge."""
    params = {**DENOISE_DEFAULTS, **(params or {})}
    work_dir = f"{output_file}.parts"
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir)
    if os.path.exists(output_file):
        os.remove(output_file)

    reader = "readers.ply" if input_file.lower().endswith(".ply") else "readers.las"
    _run_pdal([
        {"type": reader, "filename": input_file},
        {"type": "filters.divider", "capacity": params['divider_capacity']},
        {"type": "writers.las", "filename": os.path.join(work_dir, 'out_#.laz'), "extra_dims": "all"},
    ], os.path.join(work_dir, "divide.pipeline.json"))

    parts = [f for f in os.listdir(work_dir) if f.startswith('out_')]
    with ThreadPoolExecutor(max_workers=params['max_workers']) as executor:
        for f in parts:
            executor.submit(_denoise_partition, work_dir, f, params)

    processed = [os.path.join(work_dir, f) for f in os.listdir(work_dir) if f.startswith('processed_')]
    _run_pdal(processed + [
        {"type": "filters.merge"},
        {"type": "writers.text", "format": "csv", "order": params['order'],
         "keep_unspecified": False, "filename": output_file},
    ], os.path.join(work_dir, "merge.pipeline.json"))

    shutil.rmtree(work_dir, ignore_errors=True)


@celery.task(name="denoise_point_cloud")
def denoise_point_cloud(payload, input_file, output_file, denoise_params=None):
    """Generic denoise step; pipeline supplies paths, forwards the payload unchanged."""
    denoise(input_file, output_file, denoise_params)
    return payload
