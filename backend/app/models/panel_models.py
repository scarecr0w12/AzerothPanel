"""
SQLAlchemy ORM model for storing runtime-configurable panel settings.
Settings are persisted as key-value pairs in the panel SQLite database,
allowing users to change paths, DB credentials, SOAP settings, etc.
without touching environment files.
"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PanelSetting(Base):
    __tablename__ = "panel_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<PanelSetting {self.key}={self.value!r}>"

