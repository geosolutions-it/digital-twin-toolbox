from fastapi import APIRouter

from app.api.routes import output, pipelines, storage

api_router = APIRouter()
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(output.router, prefix="/output", tags=["output"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
