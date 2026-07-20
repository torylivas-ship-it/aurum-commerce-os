"""
Ad campaign routes — read visibility into what the advertising agent has
drafted/launched. Creation always goes through the approvals flow, not
directly through this router.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import AdCampaign, CampaignStatus

router = APIRouter(prefix="/campaigns")


class CampaignResponse(BaseModel):
    id: UUID
    product_id: Optional[UUID]
    platform: str
    name: str
    objective: str
    status: str
    daily_budget: Optional[float]
    creative: Optional[dict]
    targeting: Optional[dict]
    platform_campaign_id: Optional[str]
    metrics: Optional[dict]
    rejection_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AdCampaign).order_by(desc(AdCampaign.created_at)).limit(limit)
    if status:
        try:
            stmt = stmt.where(AdCampaign.status == CampaignStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdCampaign).where(AdCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/scan")
async def trigger_advertising_scan():
    """Manually trigger the advertising agent's candidate scan (normally
    runs daily at 8am). Only ever drafts campaigns pending approval —
    never spends anything by itself."""
    from core.tasks import celery_app
    task = celery_app.send_task("agents.advertising.tasks.run_advertising_scan")
    return {"task_id": task.id, "status": "queued"}
