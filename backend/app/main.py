import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_adspower_client
from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.integrations.adspower.exceptions import (
    AdsPowerAuthFailed,
    AdsPowerError,
    AdsPowerUnavailable,
)
from app.observability.otel import init_telemetry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level, service="backend")
    init_telemetry()
    from app.ai.tools.build_registry import build_registry

    build_registry()
    logger.info("backend started", extra={"event": "backend_started", "app": settings.app_name})
    yield
    await get_adspower_client().aclose()
    logger.info("backend stopped", extra={"event": "backend_stopped"})


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "backend"}


@app.get("/livez")
async def livez():
    return {"status": "ok", "service": "backend", "environment": settings.app_env}


@app.get("/readyz")
async def readyz():
    """Readiness: DB reachable, Redis optional, maintenance banner aware."""
    from sqlalchemy import text

    from app.core.database import engine

    checks = {"database": False, "maintenance_mode": settings.maintenance_mode}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001
        checks["database"] = False
    ready = checks["database"] and not settings.maintenance_mode
    return {"ready": ready, "checks": checks, "environment": settings.app_env}


@app.exception_handler(AdsPowerUnavailable)
async def adspower_unavailable_handler(request: Request, exc: AdsPowerUnavailable):
    return JSONResponse(status_code=502, content={"code": "ADSPOWER_UNAVAILABLE", "detail": str(exc)})


@app.exception_handler(AdsPowerAuthFailed)
async def adspower_auth_handler(request: Request, exc: AdsPowerAuthFailed):
    return JSONResponse(status_code=502, content={"code": "ADSPOWER_AUTH_FAILED", "detail": str(exc)})


@app.exception_handler(AdsPowerError)
async def adspower_error_handler(request: Request, exc: AdsPowerError):
    return JSONResponse(status_code=502, content={"code": "ADSPOWER_ERROR", "detail": str(exc)})
