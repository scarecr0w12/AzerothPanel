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

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


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
    for engine in list(_ac_engines.values()):
        await engine.dispose()
    _ac_engines.clear()


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


