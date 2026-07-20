"""
Aurum Commerce OS — FastAPI Backend
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("aurum.starting", env=settings.app_env)
    from core.events import event_bus
    await event_bus.connect()
    yield
    await event_bus.disconnect()
    logger.info("aurum.stopped")


app = FastAPI(
    title="Aurum Commerce OS",
    description="AI-Powered Commerce Operating System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
from api.routes import (
    products, stores, agents, approvals,
    dashboard, briefs, alerts, health, campaigns
)

app.include_router(health.router,    prefix="",            tags=["System"])
app.include_router(dashboard.router, prefix="/api/v1",     tags=["Dashboard"])
app.include_router(products.router,  prefix="/api/v1",     tags=["Products"])
app.include_router(stores.router,    prefix="/api/v1",     tags=["Stores"])
app.include_router(agents.router,    prefix="/api/v1",     tags=["Agents"])
app.include_router(approvals.router, prefix="/api/v1",     tags=["Approvals"])
app.include_router(briefs.router,    prefix="/api/v1",     tags=["Briefs"])
app.include_router(alerts.router,    prefix="/api/v1",     tags=["Alerts"])
app.include_router(campaigns.router, prefix="/api/v1",     tags=["Campaigns"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
