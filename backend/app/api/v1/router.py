from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, server, instances, logs, players, database, installation,
    compilation, settings, data_extraction, modules, configs,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(server.router)
api_router.include_router(instances.router)
api_router.include_router(logs.router)
api_router.include_router(players.router)
api_router.include_router(database.router)
api_router.include_router(installation.router)
api_router.include_router(compilation.router)
api_router.include_router(settings.router)
api_router.include_router(data_extraction.router)
api_router.include_router(modules.router)
api_router.include_router(configs.router)

