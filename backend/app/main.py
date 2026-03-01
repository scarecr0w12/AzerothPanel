"""
AzerothPanel – FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.websockets.logs import router as ws_logs_router
from app.core.config import settings
from app.core.database import init_panel_db, run_panel_db_migrations

# Import ORM models so their metadata is registered with Base before init_panel_db()
import app.models.panel_models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create / migrate panel SQLite tables
    await init_panel_db()
    # 2. Apply incremental column migrations (safe to run on every startup)
    await run_panel_db_migrations()
    # 3. Seed any missing runtime settings with defaults
    from app.services.panel_settings import seed_defaults
    await seed_defaults()
    # 4. Ensure at least one worldserver instance (the default) exists
    from app.services.azerothcore.instance_seeder import seed_default_instance
    await seed_default_instance()
    yield
    # Shutdown: nothing to clean up currently


app = FastAPI(
    title="AzerothPanel",
    description="Web-based management panel for AzerothCore WoW private server",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS
# When CORS_ALLOW_ALL=true (default) we use allow_origin_regex=".*" so that
# the middleware reflects the exact Origin back in the response header.
# This is required for allow_credentials=True to work — browsers reject
# "Access-Control-Allow-Origin: *" when credentials are present.
# ---------------------------------------------------------------------------
if settings.CORS_ALLOW_ALL:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(api_router)
app.include_router(ws_logs_router)  # WebSocket routes at /ws/...


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "azerothpanel"}

