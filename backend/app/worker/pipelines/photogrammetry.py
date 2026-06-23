import os

from celery import chain
from app.worker.main import celery
from app.worker.common.utils import get_process_dir


def run(pipeline_extended):
    """Build the per-stage cross-worker chain; tasks stay generic, orchestration lives here."""
    data = pipeline_extended.get('data') or {}
    stage = data.get('stage', 'all')

    process_dir = get_process_dir(pipeline_extended['id'])
    dense_ply = os.path.join(process_dir, 'undistorted', 'depthmaps', 'merged.ply')
    merged_xyz = os.path.join(process_dir, 'merged.xyz')

    include_mesh = stage in ('all', 'point_cloud_to_mesh')
    include_tile = stage in ('all', 'mesh_to_3dtile')

    steps = []  # (task_name, extra_kwargs)
    if stage in ('all', 'images_to_sparse_reconstruction'):
        steps.append(('photogrammetry_images_to_sparse', {}))     # photogrammetry
    if stage in ('all', 'sparse_reconstruction_to_dense_point_cloud'):
        steps.append(('photogrammetry_sparse_to_dense', {}))      # photogrammetry
    if include_mesh:
        steps.append(('denoise_point_cloud', {'input_file': dense_ply, 'output_file': merged_xyz}))  # point-cloud
        steps.append(('photogrammetry_create_mesh', {}))          # photogrammetry
        steps.append(('photogrammetry_create_texture', {}))       # photogrammetry, emits the tile payload
    if include_tile:
        if not include_mesh:
            steps.append(('photogrammetry_resolve_tile_input', {}))  # rebuild tile payload on a tiling-only resume
        if data.get('extent_mesh'):
            steps.append(('crop_obj', {}))                        # mesh
        steps.append(('tile_obj_3dtiles', {}))                    # mesh (terminal)

    if not steps:
        raise ValueError(f"Unknown photogrammetry stage: {stage!r}")

    # Head receives pipeline_extended; later steps receive the forwarded payload.
    signatures = []
    for i, (name, kwargs) in enumerate(steps):
        if i == 0:
            signatures.append(celery.signature(name, args=(pipeline_extended,), kwargs=kwargs))
        else:
            signatures.append(celery.signature(name, kwargs=kwargs))
    return chain(*signatures).apply_async()
