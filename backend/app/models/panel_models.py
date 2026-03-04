"""
SQLAlchemy ORM models for the AzerothPanel SQLite database.

- PanelSetting  – runtime-configurable key/value settings
- WorldServerInstance – registry of managed worldserver processes
"""
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PanelSetting(Base):
    __tablename__ = "panel_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<PanelSetting {self.key}={self.value!r}>"


class WorldServerInstance(Base):
    """
    Represents a single worldserver process that the panel can manage.

    ``process_name`` is the unique identifier sent to the host daemon
    (e.g. "worldserver", "worldserver-ptr").  It must be unique across
    all instances so the daemon can track each one independently.

    ``binary_path`` and ``working_dir`` are absolute paths.  When left
    empty the panel falls back to the global AC_BINARY_PATH setting.

    Per-instance overrides (all default to "" meaning "use global setting"):
    - ``ac_path``       – AzerothCore installation root; drives compilation
                          and module management for this instance.
    - ``char_db_*``     – Characters database credentials.
    - ``soap_*``        – SOAP credentials for in-game GM commands.
    """
    __tablename__ = "worldserver_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    process_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    binary_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    working_dir: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    conf_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Per-instance AzerothCore source/build path overrides
    # (empty string → fall back to global AC_PATH / AC_BUILD_PATH settings)
    ac_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    build_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    # Per-instance characters database (empty → use global AC_CHAR_DB_* settings)
    char_db_host: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    char_db_port: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    char_db_user: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    char_db_password: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    char_db_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    # Per-instance SOAP credentials (empty → use global AC_SOAP_* settings)
    soap_host: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    soap_port: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    soap_user: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    soap_password: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    def __repr__(self) -> str:
        return f"<WorldServerInstance id={self.id} name={self.display_name!r} proc={self.process_name!r}>"


class BackupDestination(Base):
    """
    A named backup storage target.

    ``type`` must be one of: "local", "sftp", "ftp", "s3", "gdrive", "onedrive".
    ``config`` is a JSON blob whose schema depends on ``type`` – see
    backup_manager.py for the full field reference per provider.
    """
    __tablename__ = "backup_destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)   # local|sftp|ftp|s3|gdrive|onedrive
    config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    def __repr__(self) -> str:
        return f"<BackupDestination id={self.id} name={self.name!r} type={self.type!r}>"


class BackupJob(Base):
    """
    Record of a single backup run.

    ``destination_id`` references BackupDestination.id; None means the archive
    was stored locally and the absolute path is stored in ``local_path``.
    ``status`` is one of: "pending", "running", "completed", "failed".
    """
    __tablename__ = "backup_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destination_id: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    include_configs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_databases: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_server_files: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False, default="")  # archive name
    local_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")  # absolute path if local
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    completed_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<BackupJob id={self.id} status={self.status!r} dest={self.destination_id}>"

