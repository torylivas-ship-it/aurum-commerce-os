from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import AlertSeverity, RiskAlert

router = APIRouter(prefix="/alerts")


@router.get("")
async def list_alerts(
    resolved: bool = False,
    severity: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(RiskAlert)
        .where(RiskAlert.is_resolved == resolved)
        .order_by(desc(RiskAlert.created_at))
        .limit(limit)
    )
    if severity:
        stmt = stmt.where(RiskAlert.severity == AlertSeverity(severity))

    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "severity": a.severity.value,
            "alert_type": a.alert_type,
            "title": a.title,
            "message": a.message,
            "is_resolved": a.is_resolved,
            "product_id": str(a.product_id) if a.product_id else None,
            "store_id": str(a.store_id) if a.store_id else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.patch("/{alert_id}/resolve")
async def resolve_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskAlert).where(RiskAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return {"error": "Alert not found"}
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": str(alert.id), "resolved": True}
