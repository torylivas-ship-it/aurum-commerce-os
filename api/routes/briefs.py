from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import ExecutiveBrief

router = APIRouter(prefix="/briefs")


@router.get("")
async def list_briefs(limit: int = 30, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ExecutiveBrief).order_by(desc(ExecutiveBrief.date)).limit(limit)
    )
    briefs = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "date": b.date.isoformat(),
            "products_to_launch": len(b.products_to_launch),
            "products_to_retire": len(b.products_to_retire),
            "revenue_projection": b.revenue_projection,
            "confidence_score": b.confidence_score,
        }
        for b in briefs
    ]


@router.get("/latest")
async def get_latest_brief(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ExecutiveBrief).order_by(desc(ExecutiveBrief.date)).limit(1)
    )
    brief = result.scalar_one_or_none()
    if not brief:
        raise HTTPException(status_code=404, detail="No briefs found yet")
    return {
        "id": str(brief.id),
        "date": brief.date.isoformat(),
        "content": brief.content,
        "structured_data": brief.structured_data,
        "products_to_launch": brief.products_to_launch,
        "products_to_retire": brief.products_to_retire,
        "revenue_projection": brief.revenue_projection,
        "confidence_score": brief.confidence_score,
    }


@router.post("/generate")
async def generate_brief_now():
    from core.tasks import celery_app
    task = celery_app.send_task(
        "agents.executive_advisor.tasks.generate_morning_brief",
        queue="reports",
    )
    return {"task_id": task.id, "status": "generating"}
