from fastapi import APIRouter

from app.api.routes import login, users, utils, assets, pipelines

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
