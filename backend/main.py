"""FastAPI entry point for the uZephyr hybrid backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.runtime_gateway import shutdown_runtime


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Release shared runtime resources when the API process exits."""
    try:
        yield
    finally:
        await shutdown_runtime()


def create_app() -> FastAPI:
    """Build the FastAPI application with development-friendly defaults."""
    app = FastAPI(
        title="uZephyr Hybrid API",
        version="0.1.0",
        description="HTTP bridge for the existing uZephyr core runtime.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["meta"])
    async def read_root() -> dict[str, str]:
        return {"status": "uZephyr Hybrid API online"}

    app.include_router(api_router)
    return app


app = create_app()