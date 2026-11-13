from app.core.storage import output_key
from app.models.pipeline import PipelineSource


def task_source(pipeline_extended: dict, label: str) -> PipelineSource:
    source = PipelineSource.model_validate(pipeline_extended.get("source") or {})
    if not source.key:
        raise Exception(f"{label} pipeline requires a bucket source")
    return source


def task_output_base(pipeline_extended: dict, source: PipelineSource) -> str:
    return source.output_base or output_key(pipeline_extended["id"])
