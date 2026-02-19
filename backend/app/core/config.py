"""
Boot-time configuration loaded from the .env file.

Only constants that must be known before the database is accessible belong here:
  - JWT secret and admin credentials (needed for the login endpoint)
  - Panel SQLite URL (needed to open the database itself)
  - CORS policy flag (needed at ASGI middleware setup)

Everything else (AzerothCore paths, MySQL credentials, SOAP settings, …) is
stored in the panel_settings table and accessed via panel_settings.get_settings_dict().
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- Panel Authentication ---
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    PANEL_ADMIN_USER: str = "admin"
    PANEL_ADMIN_PASSWORD: str = "admin"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # --- Panel SQLite DB (panel-specific data: settings, audit logs, …) ---
    PANEL_DB_URL: str = "sqlite+aiosqlite:////data/panel.db"

    # --- CORS ---
    # CORS_ALLOW_ALL=true (default) reflects any Origin back, which is the right
    # default for a self-hosted private panel.  Set to false and populate
    # CORS_ORIGINS to lock down to specific hosts.
    CORS_ALLOW_ALL: bool = True
    CORS_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


