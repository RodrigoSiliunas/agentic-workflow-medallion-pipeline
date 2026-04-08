"""FastAPI application — Namastex Platform Backend."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes import auth, chat, pipelines, settings, users, webhooks
from app.core.config import settings as app_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    # Startup
    logger.info("Starting Namastex Platform Backend", version="0.1.0")
    # TODO: Initialize Redis, check Omni health, start background tasks
    yield
    # Shutdown
    logger.info("Shutting down")
    # TODO: Close Redis, dispose DB engines, cancel tasks


app = FastAPI(
    title="Namastex Platform API",
    version="0.1.0",
    description="Plataforma conversacional para pipelines Medallion",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["pipelines"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
