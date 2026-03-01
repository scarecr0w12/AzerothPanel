"""
Seed the default worldserver instance on first startup.

If the worldserver_instances table is empty, a single "Main Worldserver"
entry is inserted that maps to the standard ``worldserver`` process name.
This preserves backward compatibility with the existing
``/server/worldserver/*`` endpoints while giving the multi-instance UI
something to display on a fresh install.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.database import PanelSessionLocal
from app.models.panel_models import WorldServerInstance

logger = logging.getLogger(__name__)


async def seed_default_instance() -> None:
    """Insert the default worldserver instance if none exist yet."""
    async with PanelSessionLocal() as db:
        result = await db.execute(select(WorldServerInstance).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # already seeded

        default = WorldServerInstance(
            display_name="Main Worldserver",
            process_name="worldserver",
            binary_path="",   # resolved at runtime from AC_BINARY_PATH
            working_dir="",   # resolved at runtime from AC_BINARY_PATH
            notes="Default worldserver instance (created automatically)",
            sort_order=0,
        )
        db.add(default)
        await db.commit()
        logger.info("Seeded default worldserver instance.")
