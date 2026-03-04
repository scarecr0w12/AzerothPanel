"""
Database engine factories.

Panel DB (SQLite) is created at startup with a static engine.

AzerothCore databases (auth, characters, world) use *dynamic* engines that
are built from settings stored in the panel_settings table.  Engines are
cached by connection URL so we reuse connection pools across requests.
Calling clear_ac_engine_cache() disposes all cached engines; the next request
will create fresh ones (used when the user updates DB credentials).
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


from sqlalchemy import text

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Panel DB – SQLite (stores panel-specific data: settings, audit logs, …)
# ---------------------------------------------------------------------------
_panel_engine = create_async_engine(
    settings.PANEL_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
PanelSessionLocal = async_sessionmaker(_panel_engine, expire_on_commit=False)


async def init_panel_db() -> None:
    """Create all tables registered with Base.metadata (idempotent)."""
    async with _panel_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def run_panel_db_migrations() -> None:
    """
    Apply incremental schema changes that create_all cannot handle
    (adding columns to existing tables).  Safe to call on every startup.
    """
    async with _panel_engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(worldserver_instances)"))
        cols = {row[1] for row in result.fetchall()}

        # v1.1 – conf_path
        if "conf_path" not in cols:
            await conn.execute(
                text("ALTER TABLE worldserver_instances ADD COLUMN conf_path TEXT NOT NULL DEFAULT ''")
            )

        # v1.2 – per-instance AC path + build path overrides
        for col in ("ac_path", "build_path"):
            if col not in cols:
                await conn.execute(
                    text(f"ALTER TABLE worldserver_instances ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
                )

        # v1.2 – per-instance characters database overrides
        for col in ("char_db_host", "char_db_port", "char_db_user",
                    "char_db_password", "char_db_name"):
            if col not in cols:
                await conn.execute(
                    text(f"ALTER TABLE worldserver_instances ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
                )

        # v1.2 – per-instance SOAP overrides
        for col in ("soap_host", "soap_port", "soap_user", "soap_password"):
            if col not in cols:
                await conn.execute(
                    text(f"ALTER TABLE worldserver_instances ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
                )

        # v1.3 – backup_destinations and backup_jobs tables
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS backup_destinations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL,
                config      TEXT NOT NULL DEFAULT '{}',
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL DEFAULT ''
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS backup_jobs (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id       INTEGER,
                status               TEXT NOT NULL DEFAULT 'pending',
                include_configs      INTEGER NOT NULL DEFAULT 1,
                include_databases    INTEGER NOT NULL DEFAULT 1,
                include_server_files INTEGER NOT NULL DEFAULT 0,
                filename             TEXT NOT NULL DEFAULT '',
                local_path           TEXT NOT NULL DEFAULT '',
                size_bytes           INTEGER NOT NULL DEFAULT 0,
                started_at           TEXT NOT NULL DEFAULT '',
                completed_at         TEXT NOT NULL DEFAULT '',
                error                TEXT NOT NULL DEFAULT '',
                notes                TEXT NOT NULL DEFAULT ''
            )
        """))


async def get_panel_db() -> AsyncIterator[AsyncSession]:
    async with PanelSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# AzerothCore – dynamic engines (credentials come from panel_settings table)
# ---------------------------------------------------------------------------
_ac_engines: dict[str, AsyncEngine] = {}


def _build_mysql_url(host: str, port: str, user: str, password: str, db_name: str) -> str:
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db_name}"


def _get_or_create_engine(url: str) -> AsyncEngine:
    if url not in _ac_engines:
        _ac_engines[url] = create_async_engine(
            url, echo=False, pool_pre_ping=True, pool_size=5
        )
    return _ac_engines[url]


async def clear_ac_engine_cache() -> None:
    """Dispose all cached AC engines (called when DB credentials change)."""
    count = len(_ac_engines)
    for engine in list(_ac_engines.values()):
        await engine.dispose()
    _ac_engines.clear()
    logger.info("AC engine cache cleared (%d engine(s) disposed)", count)


async def get_auth_db() -> AsyncIterator[AsyncSession]:
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    url = _build_mysql_url(
        s["AC_AUTH_DB_HOST"], s["AC_AUTH_DB_PORT"],
        s["AC_AUTH_DB_USER"], s["AC_AUTH_DB_PASSWORD"],
        s["AC_AUTH_DB_NAME"],
    )
    factory = async_sessionmaker(_get_or_create_engine(url), expire_on_commit=False)
    async with factory() as session:
        yield session


async def get_char_db() -> AsyncIterator[AsyncSession]:
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    url = _build_mysql_url(
        s["AC_CHAR_DB_HOST"], s["AC_CHAR_DB_PORT"],
        s["AC_CHAR_DB_USER"], s["AC_CHAR_DB_PASSWORD"],
        s["AC_CHAR_DB_NAME"],
    )
    factory = async_sessionmaker(_get_or_create_engine(url), expire_on_commit=False)
    async with factory() as session:
        yield session


async def get_world_db() -> AsyncIterator[AsyncSession]:
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    url = _build_mysql_url(
        s["AC_WORLD_DB_HOST"], s["AC_WORLD_DB_PORT"],
        s["AC_WORLD_DB_USER"], s["AC_WORLD_DB_PASSWORD"],
        s["AC_WORLD_DB_NAME"],
    )
    factory = async_sessionmaker(_get_or_create_engine(url), expire_on_commit=False)
    async with factory() as session:
        yield session


async def get_playerbots_db() -> AsyncIterator[AsyncSession]:
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()
    url = _build_mysql_url(
        s["AC_PLAYERBOTS_DB_HOST"], s["AC_PLAYERBOTS_DB_PORT"],
        s["AC_PLAYERBOTS_DB_USER"], s["AC_PLAYERBOTS_DB_PASSWORD"],
        s["AC_PLAYERBOTS_DB_NAME"],
    )
    factory = async_sessionmaker(_get_or_create_engine(url), expire_on_commit=False)
    async with factory() as session:
        yield session


async def get_char_db_for_instance(instance_id: int | None) -> AsyncIterator[AsyncSession]:
    """
    Return a character-DB session scoped to a specific worldserver instance.

    If ``instance_id`` is None, or the instance has no per-instance DB
    credentials configured (all fields empty), falls back gracefully to the
    global AC_CHAR_DB_* settings – so callers never need to special-case the
    single-realm situation.
    """
    from app.services.panel_settings import get_settings_dict

    s = await get_settings_dict()
    host = s["AC_CHAR_DB_HOST"]
    port = s["AC_CHAR_DB_PORT"]
    user = s["AC_CHAR_DB_USER"]
    password = s["AC_CHAR_DB_PASSWORD"]
    db_name = s["AC_CHAR_DB_NAME"]

    if instance_id is not None:
        from sqlalchemy import select as sa_select
        from app.models.panel_models import WorldServerInstance
        async with PanelSessionLocal() as psess:
            result = await psess.execute(
                sa_select(WorldServerInstance).where(WorldServerInstance.id == instance_id)
            )
            inst = result.scalar_one_or_none()
        if inst is not None:
            if inst.char_db_host:
                host = inst.char_db_host
            if inst.char_db_port:
                port = inst.char_db_port
            if inst.char_db_user:
                user = inst.char_db_user
            if inst.char_db_password:
                password = inst.char_db_password
            if inst.char_db_name:
                db_name = inst.char_db_name

    url = _build_mysql_url(host, port, user, password, db_name)
    factory = async_sessionmaker(_get_or_create_engine(url), expire_on_commit=False)
    async with factory() as session:
        yield session
