from app.models.pipeline_types import PIPELINES

TASK_QUEUES = {spec.task: spec.queue for spec in PIPELINES.values()} | {
    "read_vector_fields": "vector",
    "read_vector_sample": "vector",
    "read_mesh_bbox": "mesh",
    "finalize_tileset_batch": "common",
}
