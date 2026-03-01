"""
Pydantic schemas used by the API endpoints.
"""
from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Server Status
# ---------------------------------------------------------------------------
class ProcessStatus(BaseModel):
    name: str                    # "worldserver" | "authserver"
    running: bool
    pid: Optional[int] = None
    uptime_seconds: Optional[float] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None


class ServerStatusResponse(BaseModel):
    worldserver: ProcessStatus
    authserver: ProcessStatus


class ServerActionResponse(BaseModel):
    success: bool
    message: str


class SoapCommandRequest(BaseModel):
    command: str


class SoapCommandResponse(BaseModel):
    success: bool
    result: str


# ---------------------------------------------------------------------------
# Worldserver Instances
# ---------------------------------------------------------------------------
class WorldServerInstanceSchema(BaseModel):
    """Read schema – returned by GET endpoints (includes live status)."""
    id: int
    display_name: str
    process_name: str
    binary_path: str
    working_dir: str
    conf_path: str
    notes: str
    sort_order: int
    status: Optional[ProcessStatus] = None

    model_config = {"from_attributes": True}


class WorldServerInstanceCreate(BaseModel):
    """POST body for creating a new worldserver instance."""
    display_name: str
    process_name: str        # unique daemon name, e.g. "worldserver-ptr"
    binary_path: str = ""    # full path to binary; empty → use AC_BINARY_PATH default
    working_dir: str = ""    # cwd; empty → use AC_BINARY_PATH default
    conf_path: str = ""      # path to worldserver.conf; empty → binary default
    notes: str = ""
    sort_order: int = 0


class WorldServerInstanceUpdate(BaseModel):
    """PUT body for updating an existing instance (all fields optional)."""
    display_name: Optional[str] = None
    binary_path: Optional[str] = None
    working_dir: Optional[str] = None
    conf_path: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


class WorldServerInstanceListResponse(BaseModel):
    instances: list[WorldServerInstanceSchema]


class WorldServerProvisionRequest(BaseModel):
    """Request body for generating a worldserver.conf for a new instance."""
    conf_output_path: str            # where to write the new .conf file
    realm_name: str = "AzerothCore 2"
    worldserver_port: int = 8086     # WorldServerPort
    instance_port: int = 8087        # InstanceserverPort
    ra_port: int = 3445              # Ra.Port
    realm_id: int = 2                # RealmID in worldserver.conf
    extra_overrides: Optional[dict[str, str]] = None  # any extra key=value patches


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------
class CharacterSummary(BaseModel):
    guid: int
    account: int
    name: str
    race: int
    class_: int
    level: int
    gender: int
    zone: int
    online: bool


class AccountSummary(BaseModel):
    id: int
    username: str
    email: str
    gmlevel: int
    locked: bool
    last_ip: Optional[str] = None
    last_login: Optional[str] = None
    banned: bool = False


class BanRequest(BaseModel):
    account_id: int
    duration: str  # "0" = permanent, "1d" "7d" etc.
    reason: str
    banned_by: str = "panel"


class ModifyPlayerRequest(BaseModel):
    guid: int
    field: str      # "level" | "money" | "speed" | etc.
    value: Any


class AnnouncementRequest(BaseModel):
    message: str
    target: str = "all"  # "all" | player name


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    source: str  # "worldserver" | "authserver"


class LogQueryParams(BaseModel):
    source: str = "worldserver"
    level: Optional[str] = None
    search: Optional[str] = None
    limit: int = 500


# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------
class SqlQueryRequest(BaseModel):
    database: str   # "auth" | "characters" | "world"
    query: str
    max_rows: int = 500


class SqlQueryResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_time_ms: float
    is_select: bool


class TableListResponse(BaseModel):
    database: str
    tables: list[str]


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool          # True = YES, False = NO
    key: str                # "PRI" | "UNI" | "MUL" | ""
    default: Optional[str] = None
    extra: str = ""         # "auto_increment", etc.


class TableSchemaResponse(BaseModel):
    database: str
    table: str
    columns: list[ColumnInfo]
    pk_columns: list[str]   # convenience: column names where key == "PRI"


class RowInsertRequest(BaseModel):
    database: str
    table: str
    data: dict[str, Any]    # column -> value


class RowUpdateRequest(BaseModel):
    database: str
    table: str
    pk_columns: dict[str, Any]   # pk col -> current value (for WHERE)
    data: dict[str, Any]         # col -> new value


class RowDeleteRequest(BaseModel):
    database: str
    table: str
    pk_columns: dict[str, Any]   # pk col -> value (for WHERE)


class ExportRequest(BaseModel):
    database: str
    query: str
    format: str = "csv"          # "csv" | "json"
    max_rows: int = 100_000


class BackupRequest(BaseModel):
    database: str  # "auth" | "characters" | "world" | "all"
    output_path: Optional[str] = None


class BackupResponse(BaseModel):
    success: bool
    path: str
    size_bytes: int


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------
class InstallStep(BaseModel):
    id: str
    label: str
    status: str       # "pending" | "running" | "done" | "error"
    output: Optional[str] = None


REPO_STANDARD = "https://github.com/azerothcore/azerothcore-wotlk.git"
REPO_PLAYERBOT = "https://github.com/mod-playerbots/azerothcore-wotlk.git"


class InstallConfig(BaseModel):
    ac_path: str = "/opt/azerothcore"
    db_host: str = "127.0.0.1"
    db_root_password: str = ""   # MySQL root password — leave empty to use UNIX socket auth
                                  # (Debian/Ubuntu default: root uses auth_socket plugin)
    db_user: str = "acore"
    db_password: str = "acore"
    clone_branch: str = "master"
    repository_url: str = REPO_STANDARD


# ---------------------------------------------------------------------------
# Panel Settings (runtime-configurable, stored in SQLite)
# ---------------------------------------------------------------------------
class PanelSettingsResponse(BaseModel):
    # AzerothCore paths
    AC_PATH: str = "/opt/azerothcore"
    AC_BUILD_PATH: str = "/opt/azerothcore/build"
    AC_BINARY_PATH: str = "/opt/azerothcore/build/bin"
    AC_CONF_PATH: str = "/opt/azerothcore/build/etc"
    AC_LOG_PATH: str = "/opt/azerothcore/build/logs"
    AC_DATA_PATH: str = "/opt/azerothcore/build/data"
    AC_WORLDSERVER_CONF: str = "/opt/azerothcore/build/etc/worldserver.conf"
    AC_AUTHSERVER_CONF: str = "/opt/azerothcore/build/etc/authserver.conf"
    # Auth database
    AC_AUTH_DB_HOST: str = "127.0.0.1"
    AC_AUTH_DB_PORT: str = "3306"
    AC_AUTH_DB_USER: str = "acore"
    AC_AUTH_DB_PASSWORD: str = "acore"
    AC_AUTH_DB_NAME: str = "acore_auth"
    # Characters database
    AC_CHAR_DB_HOST: str = "127.0.0.1"
    AC_CHAR_DB_PORT: str = "3306"
    AC_CHAR_DB_USER: str = "acore"
    AC_CHAR_DB_PASSWORD: str = "acore"
    AC_CHAR_DB_NAME: str = "acore_characters"
    # World database
    AC_WORLD_DB_HOST: str = "127.0.0.1"
    AC_WORLD_DB_PORT: str = "3306"
    AC_WORLD_DB_USER: str = "acore"
    AC_WORLD_DB_PASSWORD: str = "acore"
    AC_WORLD_DB_NAME: str = "acore_world"
    # SOAP
    AC_SOAP_HOST: str = "127.0.0.1"
    AC_SOAP_PORT: str = "7878"
    AC_SOAP_USER: str = ""
    AC_SOAP_PASSWORD: str = ""
    # Remote Access
    AC_RA_HOST: str = "127.0.0.1"
    AC_RA_PORT: str = "3443"
    # Paths (cont.)
    AC_CLIENT_PATH: str = ""
    # GitHub
    GITHUB_TOKEN: str = ""


class PanelSettingsUpdate(BaseModel):
    """Partial update – only provided (non-None) fields are written to the DB."""
    AC_PATH: Optional[str] = None
    AC_BUILD_PATH: Optional[str] = None
    AC_BINARY_PATH: Optional[str] = None
    AC_CONF_PATH: Optional[str] = None
    AC_LOG_PATH: Optional[str] = None
    AC_DATA_PATH: Optional[str] = None
    AC_WORLDSERVER_CONF: Optional[str] = None
    AC_AUTHSERVER_CONF: Optional[str] = None
    AC_AUTH_DB_HOST: Optional[str] = None
    AC_AUTH_DB_PORT: Optional[str] = None
    AC_AUTH_DB_USER: Optional[str] = None
    AC_AUTH_DB_PASSWORD: Optional[str] = None
    AC_AUTH_DB_NAME: Optional[str] = None
    AC_CHAR_DB_HOST: Optional[str] = None
    AC_CHAR_DB_PORT: Optional[str] = None
    AC_CHAR_DB_USER: Optional[str] = None
    AC_CHAR_DB_PASSWORD: Optional[str] = None
    AC_CHAR_DB_NAME: Optional[str] = None
    AC_WORLD_DB_HOST: Optional[str] = None
    AC_WORLD_DB_PORT: Optional[str] = None
    AC_WORLD_DB_USER: Optional[str] = None
    AC_WORLD_DB_PASSWORD: Optional[str] = None
    AC_WORLD_DB_NAME: Optional[str] = None
    AC_SOAP_HOST: Optional[str] = None
    AC_SOAP_PORT: Optional[str] = None
    AC_SOAP_USER: Optional[str] = None
    AC_SOAP_PASSWORD: Optional[str] = None
    AC_RA_HOST: Optional[str] = None
    AC_RA_PORT: Optional[str] = None
    AC_CLIENT_PATH: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None


class TestDbRequest(BaseModel):
    """Connection parameters for a one-off database connectivity test."""
    host: str
    port: str = "3306"
    user: str
    password: str
    db_name: str


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------
class BuildConfig(BaseModel):
    build_type: str = "RelWithDebInfo"   # Debug | Release | RelWithDebInfo
    jobs: int = 4
    cmake_extra: str = ""


class BuildStatusResponse(BaseModel):
    running: bool
    progress_percent: Optional[float] = None
    current_step: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    error: Optional[str] = None

