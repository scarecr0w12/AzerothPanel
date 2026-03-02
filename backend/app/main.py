"""
AzerothPanel – FastAPI application entry point.
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.websockets.logs import router as ws_logs_router
from app.core.config import settings
from app.core.database import init_panel_db, run_panel_db_migrations

# Import ORM models so their metadata is registered with Base before init_panel_db()
import app.models.panel_models  # noqa: F401

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

_LOG_DIR = Path(os.environ.get("PANEL_LOG_DIR", "/data/logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "panel.log"

_LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s  %(message)s"
_LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# Root handler: stream to stdout
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FMT))

# Root handler: rotate at 10 MB, keep 5 files → max ~50 MB on disk
_file_handler = RotatingFileHandler(
    _LOG_FILE,
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FMT))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_stream_handler, _file_handler],
)

logger = logging.getLogger(__name__)
logger.info("Panel log file: %s", _LOG_FILE)

# Reduce noise from noisy third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AzerothPanel starting up…")
    # 1. Create / migrate panel SQLite tables
    await init_panel_db()
    logger.info("Panel DB initialised")
    # 2. Apply incremental column migrations (safe to run on every startup)
    await run_panel_db_migrations()
    # 3. Seed any missing runtime settings with defaults
    from app.services.panel_settings import seed_defaults
    await seed_defaults()
    # 4. Ensure at least one worldserver instance (the default) exists
    from app.services.azerothcore.instance_seeder import seed_default_instance
    await seed_default_instance()
    logger.info("AzerothPanel startup complete")
    yield
    logger.info("AzerothPanel shutting down")


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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = (time.monotonic() - start) * 1000
    logger.info(
        "%s %s → %s  (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "azerothpanel"}

