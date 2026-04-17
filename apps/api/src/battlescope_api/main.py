import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from battlescope_api.api.routes import health, runs
from battlescope_api.log_setup import configure_logging
from battlescope_api.settings import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level

    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        yield
    finally:
        root.handlers[:] = old_handlers
        root.setLevel(old_level)


def create_app() -> FastAPI:
    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

    app = FastAPI(title="BattleScope API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(runs.router, prefix="/runs", tags=["runs"])
    return app


app = create_app()
