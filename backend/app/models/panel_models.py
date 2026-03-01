"""
SQLAlchemy ORM models for the AzerothPanel SQLite database.

- PanelSetting  – runtime-configurable key/value settings
- WorldServerInstance – registry of managed worldserver processes
"""
from sqlalchemy import Integer, String, Text
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

    def __repr__(self) -> str:
        return f"<WorldServerInstance id={self.id} name={self.display_name!r} proc={self.process_name!r}>"

