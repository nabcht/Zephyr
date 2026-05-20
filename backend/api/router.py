"""Top-level API router for the hybrid backend."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes.chat import router as chat_router
from backend.api.routes.command_center import router as command_center_router
from backend.api.routes.documentation import router as documentation_router
from backend.api.routes.missions import router as missions_router
from backend.api.routes.runtime import router as runtime_router
from backend.api.routes.sessions import router as sessions_router
from backend.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(chat_router)
api_router.include_router(command_center_router)
api_router.include_router(documentation_router)
api_router.include_router(missions_router)
api_router.include_router(runtime_router)
api_router.include_router(sessions_router)
api_router.include_router(system_router)