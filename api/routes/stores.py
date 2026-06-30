from typing import Optional
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
    shopify_access_token: Optional[str] = None
    config: dict = {}


class StoreConnect(BaseModel):
    shopify_store_url: str
    shopify_access_token: str


def _store_dict(s: Store, include_token: bool = False) -> dict:
    connected = bool(s.shopify_store_url and s.config.get("shopify_access_token"))
    d = {
        "id": str(s.id),
        "name": s.name,
        "niche": s.niche,
        "platform": s.platform,
        "domain": s.domain,
        "shopify_store_url": s.shopify_store_url,
        "connected": connected,
        "status": s.status.value,
        "created_at": s.created_at.isoformat(),
    }
    if include_token:
        tok = s.config.get("shopify_access_token", "")
        d["shopify_access_token_hint"] = f"{tok[:8]}..." if tok else None
    return d


@router.get("")
async def list_stores(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Store))
    return [_store_dict(s) for s in result.scalars().all()]


@router.post("", status_code=201)
async def create_store(store_data: StoreCreate, db: AsyncSession = Depends(get_db)):
    cfg = dict(store_data.config)
    if store_data.shopify_access_token:
        cfg["shopify_access_token"] = store_data.shopify_access_token

    store = Store(
        name=store_data.name,
        niche=store_data.niche,
        platform=store_data.platform,
        shopify_store_url=store_data.shopify_store_url,
        config=cfg,
        status=StoreStatus.ACTIVE,
    )
    db.add(store)
    await db.commit()
    return _store_dict(store)


@router.get("/{store_id}")
async def get_store(store_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return _store_dict(store, include_token=True)


@router.post("/{store_id}/connect")
async def connect_shopify(
    store_id: UUID,
    data: StoreConnect,
    db: AsyncSession = Depends(get_db),
):
    """Save Shopify credentials for a store and verify the connection."""
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    url = data.shopify_store_url.replace("https://", "").replace("http://", "").rstrip("/")
    store.shopify_store_url = url
    store.config = {**store.config, "shopify_access_token": data.shopify_access_token}

    # Verify credentials
    from integrations.shopify import ShopifyClient
    client = ShopifyClient(url, data.shopify_access_token)
    try:
        products = await client.list_products(limit=1)
        store.meta = {**(store.meta or {}), "shopify_verified": True}
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not connect to Shopify: {exc}",
        )

    await db.commit()
    return {**_store_dict(store), "verified": True}


@router.delete("/{store_id}/connect")
async def disconnect_shopify(store_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    cfg = dict(store.config)
    cfg.pop("shopify_access_token", None)
    store.config = cfg
    store.shopify_store_url = None
    await db.commit()
    return {"disconnected": True}
