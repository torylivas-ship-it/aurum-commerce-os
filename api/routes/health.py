from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "aurum-commerce-os",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/")
async def root():
    return {
        "service": "Aurum Commerce OS",
        "version": "1.0.0",
        "docs": "/docs",
    }
