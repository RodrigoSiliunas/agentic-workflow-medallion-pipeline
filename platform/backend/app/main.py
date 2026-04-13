"""FastAPI application — Namastex Platform Backend."""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth,
    channels,
    chat,
    deployments,
    observability,
    pipelines,
    settings,
    templates,
    users,
    webhooks,
)
from app.core.config import settings as app_settings
from app.core.exceptions import AppError
from app.database.seed import seed_templates
from app.database.session import AsyncSessionLocal
from app.middleware.request_id import RequestIDMiddleware
from app.services.omni_service import OmniService

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    logger.info("Starting Namastex Platform Backend", version="0.1.0")

    # TODO: Initialize Redis connection pool
    # TODO: Start background tasks (subscription scheduler, etc.)

    # Seed templates (idempotente)
    if app_settings.AUTO_SEED:
        try:
            async with AsyncSessionLocal() as db:
                await seed_templates(db)
        except Exception as e:
            logger.warning("template seed skipped", error=str(e))

    # Check Omni health e iniciar poller
    omni = OmniService()
    poller_task = None
    if await omni.health_check():
        logger.info("Omni gateway: healthy")
        from app.services.omni_poller import poll_loop
        poller_task = asyncio.create_task(poll_loop())
    else:
        logger.warning("Omni gateway: unreachable (canais externos indisponiveis)")

    yield

    logger.info("Shutting down")
    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Namastex Platform API",
    version="0.1.0",
    description="Plataforma conversacional para pipelines Medallion",
    lifespan=lifespan,
    docs_url="/api/v1/docs" if app_settings.DEBUG else None,
    openapi_url="/api/v1/openapi.json" if app_settings.DEBUG else None,
)

# Exception handler for domain exceptions
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# Middleware stack (ordem importa — primeiro adicionado = mais externo)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["pipelines"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(deployments.router, prefix="/api/v1/deployments", tags=["deployments"])
app.include_router(channels.router, prefix="/api/v1/channels", tags=["channels"])
app.include_router(
    observability.router, prefix="/api/v1/observability", tags=["observability"]
)
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/health/channels")
async def health_channels():
    """Status de todas as instancias Omni."""
    omni = OmniService()
    try:
        instances = await omni.list_instances()
        return {
            "omni_healthy": True,
            "instances": [
                {
                    "name": i.get("name"),
                    "channel": i.get("channel"),
                    "state": i.get("state"),
                }
                for i in instances
            ],
        }
    except Exception as e:
        return {"omni_healthy": False, "error": str(e), "instances": []}
