import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic.json_schema import models_json_schema
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.models.config import CONFIG_MODELS


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


def _openapi() -> dict:
    # config models are validated from a plain dict, so no route references them
    if app.openapi_schema is None:
        schema = FastAPI.openapi(app)
        _, extra = models_json_schema(
            [(m, "validation") for m in CONFIG_MODELS.values()],
            ref_template="#/components/schemas/{model}",
        )
        schema["components"]["schemas"].update(extra["$defs"])
    return app.openapi_schema


app.openapi = _openapi  # type: ignore[method-assign]
