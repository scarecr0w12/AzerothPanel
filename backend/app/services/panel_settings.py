"""
Panel settings service.

All runtime-configurable settings (AzerothCore paths, database credentials,
SOAP config, etc.) are stored in the panel's SQLite database rather than in
environment files.  Only boot-time constants (SECRET_KEY, PANEL_DB_URL, etc.)
remain in .env.
"""
from __future__ import annotations

from sqlalchemy import select
from app.core.config import settings as boot_settings

# ---------------------------------------------------------------------------
# Default values for every runtime setting
# ---------------------------------------------------------------------------
DEFAULTS: dict[str, str] = {
    # AzerothCore file paths
    "AC_PATH":             boot_settings.AC_PATH,
    "AC_BUILD_PATH":       f"{boot_settings.AC_PATH}/var/build/obj",
    "AC_BINARY_PATH":      f"{boot_settings.AC_PATH}/env/dist/bin",
    "AC_CONF_PATH":        f"{boot_settings.AC_PATH}/env/dist/etc",
    # AzerothCore's default LogsDir="" means logs are written alongside the
    # binaries in env/dist/bin.  This matches the default worldserver.conf
    # setting; users who set an explicit LogsDir should update this in Settings.
    "AC_LOG_PATH":         f"{boot_settings.AC_PATH}/env/dist/bin",
    "AC_DATA_PATH":        f"{boot_settings.AC_PATH}/env/dist/data",
    "AC_WORLDSERVER_CONF": f"{boot_settings.AC_PATH}/env/dist/etc/worldserver.conf",
    "AC_AUTHSERVER_CONF":  f"{boot_settings.AC_PATH}/env/dist/etc/authserver.conf",
    "AC_CLIENT_PATH":      boot_settings.CLIENT_PATH,  # Path to WoW 3.3.5a client for data extraction
    # Auth database
    "AC_AUTH_DB_HOST":     "127.0.0.1",
    "AC_AUTH_DB_PORT":     "3306",
    "AC_AUTH_DB_USER":     "acore",
    "AC_AUTH_DB_PASSWORD": "acore",
    "AC_AUTH_DB_NAME":     "acore_auth",
    # Characters database
    "AC_CHAR_DB_HOST":     "127.0.0.1",
    "AC_CHAR_DB_PORT":     "3306",
    "AC_CHAR_DB_USER":     "acore",
    "AC_CHAR_DB_PASSWORD": "acore",
    "AC_CHAR_DB_NAME":     "acore_characters",
    # World database
    "AC_WORLD_DB_HOST":     "127.0.0.1",
    "AC_WORLD_DB_PORT":     "3306",
    "AC_WORLD_DB_USER":     "acore",
    "AC_WORLD_DB_PASSWORD": "acore",
    "AC_WORLD_DB_NAME":     "acore_world",
    # SOAP (in-game GM commands)
    "AC_SOAP_HOST":     "127.0.0.1",
    "AC_SOAP_PORT":     "7878",
    "AC_SOAP_USER":     "",
    "AC_SOAP_PASSWORD": "",
    # Remote Access / Telnet
    "AC_RA_HOST": "127.0.0.1",
    "AC_RA_PORT": "3443",
}

# Keys that affect MySQL connection URLs – changing these requires engine cache invalidation
_DB_KEYS: set[str] = {k for k in DEFAULTS if "_DB_" in k}


async def get_settings_dict() -> dict[str, str]:
    """
    Load all panel settings from the database.
    Any key not yet in the database falls back to DEFAULTS.
    Returns a plain dict with every key guaranteed to be present.
    """
    from app.core.database import PanelSessionLocal
    from app.models.panel_models import PanelSetting

    async with PanelSessionLocal() as session:
        result = await session.execute(select(PanelSetting))
        db_rows = {row.key: row.value for row in result.scalars()}

    return {**DEFAULTS, **db_rows}


async def update_settings(updates: dict[str, str]) -> dict[str, str]:
    """
    Persist the provided key-value pairs to the database.
    If any database-connection keys changed, the AC engine cache is cleared so
    the next request gets fresh connections with the new credentials.
    Returns the full updated settings dict.
    """
    from app.core.database import PanelSessionLocal, clear_ac_engine_cache
    from app.models.panel_models import PanelSetting

    db_keys_changed = bool(set(updates.keys()) & _DB_KEYS)

    async with PanelSessionLocal() as session:
        for key, value in updates.items():
            existing = await session.get(PanelSetting, key)
            if existing is not None:
                existing.value = str(value)
            else:
                session.add(PanelSetting(key=key, value=str(value)))
        await session.commit()

    if db_keys_changed:
        await clear_ac_engine_cache()

    return await get_settings_dict()


async def seed_defaults() -> None:
    """
    Insert any missing default settings into the database.
    Called once on application startup.  Existing values are never overwritten.
    """
    from app.core.database import PanelSessionLocal
    from app.models.panel_models import PanelSetting

    async with PanelSessionLocal() as session:
        for key, value in DEFAULTS.items():
            existing = await session.get(PanelSetting, key)
            if existing is None:
                session.add(PanelSetting(key=key, value=value))
        await session.commit()

