from fastapi import APIRouter

from app.api.routes import utils, assets, pipelines, output, storage

api_router = APIRouter()
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(output.router, prefix="/output", tags=["output"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
