from celery import chain
from app.worker.main import celery


def run(pipeline_extended):
    # Resolve/extract the mesh asset, then tile it (both on the mesh queue).
    return chain(
        celery.signature('resolve_mesh_input', kwargs={'pipeline_extended': pipeline_extended}),
        celery.signature('tile_obj_3dtiles'),
    ).apply_async()
