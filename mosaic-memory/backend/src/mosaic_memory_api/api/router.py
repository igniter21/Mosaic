from fastapi import APIRouter

from mosaic_memory_api.api.routes import (
    events,
    health,
    memory,
    privacy,
    sources,
    tab_context,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(tab_context.router, prefix="/context", tags=["context"])
api_router.include_router(privacy.router, prefix="/privacy", tags=["privacy"])
