from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import Product, ProductStatus, ProductLifecycle

router = APIRouter(prefix="/products")


class ProductResponse(BaseModel):
    id: UUID
    name: str
    category: Optional[str]
    status: str
    opportunity_score: Optional[float]
    confidence_score: Optional[float]
    risk_score: Optional[float]
    gross_margin: Optional[float]
    selling_price: Optional[float]
    supplier_cost: Optional[float]
    shipping_cost: Optional[float]
    lifecycle: Optional[str]
    supplier_name: Optional[str]
    shipping_days: Optional[int]
    source_platform: Optional[str]
    image_url: Optional[str]
    score_breakdown: Optional[dict]
    evidence: Optional[dict]

    class Config:
        from_attributes = True


@router.get("", response_model=List[ProductResponse])
async def list_products(
    status: Optional[str] = None,
    min_score: float = Query(0, ge=0, le=100),
    category: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product).order_by(desc(Product.opportunity_score)).offset(offset).limit(limit)

    if status:
        try:
            stmt = stmt.where(Product.status == ProductStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if min_score > 0:
        stmt = stmt.where(Product.opportunity_score >= min_score)

    if category:
        stmt = stmt.where(Product.category.ilike(f"%{category}%"))

    result = await db.execute(stmt)
    products = result.scalars().all()
    return products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}/status")
async def update_product_status(
    product_id: UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        product.status = ProductStatus(status)
        await db.commit()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    return {"id": str(product.id), "status": product.status.value}


@router.post("/discover")
async def trigger_discovery(niches: Optional[List[str]] = None):
    from core.tasks import celery_app
    task = celery_app.send_task(
        "agents.product_discovery.tasks.run_discovery",
        kwargs={"niches": niches, "limit": 50},
        queue="agents",
    )
    return {"task_id": task.id, "status": "queued"}
