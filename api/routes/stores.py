from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import Store, StoreStatus

router = APIRouter(prefix="/stores")


class StoreCreate(BaseModel):
    name: str
    niche: Optional[str] = None
    platform: str = "shopify"
    shopify_store_url: Optional[str] = None
    config: dict = {}


@router.get("")
async def list_stores(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Store))
    stores = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "niche": s.niche,
            "platform": s.platform,
            "domain": s.domain,
            "shopify_store_url": s.shopify_store_url,
            "status": s.status.value,
            "created_at": s.created_at.isoformat(),
        }
        for s in stores
    ]


@router.post("", status_code=201)
async def create_store(store_data: StoreCreate, db: AsyncSession = Depends(get_db)):
    store = Store(
        name=store_data.name,
        niche=store_data.niche,
        platform=store_data.platform,
        shopify_store_url=store_data.shopify_store_url,
        config=store_data.config,
        status=StoreStatus.ACTIVE,
    )
    db.add(store)
    await db.commit()
    return {"id": str(store.id), "name": store.name, "status": store.status.value}


@router.get("/{store_id}")
async def get_store(store_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return {
        "id": str(store.id),
        "name": store.name,
        "niche": store.niche,
        "platform": store.platform,
        "shopify_store_url": store.shopify_store_url,
        "status": store.status.value,
        "config": store.config,
        "meta": store.meta,
        "created_at": store.created_at.isoformat(),
    }
