"""Dashboard summary endpoint — single call for the executive overview."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import (
    AgentRun, AgentStatus, ApprovalRequest, ApprovalStatus,
    ExecutiveBrief, Product, ProductStatus, RiskAlert, AlertSeverity,
    Store, StoreMetric, TrendSignal
)

router = APIRouter(prefix="/dashboard")


@router.get("/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Product counts by status
    product_counts = {}
    for status in ProductStatus:
        count = (await db.execute(
            select(func.count(Product.id)).where(Product.status == status)
        )).scalar() or 0
        product_counts[status.value] = count

    # Pending approvals count
    pending_approvals = (await db.execute(
        select(func.count(ApprovalRequest.id))
        .where(ApprovalRequest.status == ApprovalStatus.PENDING)
    )).scalar() or 0

    # Unresolved alerts by severity
    critical_alerts = (await db.execute(
        select(func.count(RiskAlert.id))
        .where(RiskAlert.severity == AlertSeverity.CRITICAL, RiskAlert.is_resolved == False)
    )).scalar() or 0

    warning_alerts = (await db.execute(
        select(func.count(RiskAlert.id))
        .where(RiskAlert.severity == AlertSeverity.WARNING, RiskAlert.is_resolved == False)
    )).scalar() or 0

    # Recent agent activity
    recent_agents = (await db.execute(
        select(AgentRun)
        .order_by(desc(AgentRun.created_at))
        .limit(10)
    )).scalars().all()

    # Top opportunities
    top_products = (await db.execute(
        select(Product)
        .where(
            Product.status == ProductStatus.DISCOVERED,
            Product.opportunity_score.isnot(None),
        )
        .order_by(desc(Product.opportunity_score))
        .limit(5)
    )).scalars().all()

    # Latest brief
    latest_brief = (await db.execute(
        select(ExecutiveBrief)
        .order_by(desc(ExecutiveBrief.date))
        .limit(1)
    )).scalar_one_or_none()

    # Active stores
    store_count = (await db.execute(select(func.count(Store.id)))).scalar() or 0

    return {
        "timestamp": now.isoformat(),
        "portfolio": {
            "total_stores": store_count,
            "products": product_counts,
            "total_products": sum(product_counts.values()),
        },
        "pipeline": {
            "discovered": product_counts.get("discovered", 0),
            "pending_approval": pending_approvals,
            "approved": product_counts.get("approved", 0),
            "launched": product_counts.get("launched", 0),
            "scaling": product_counts.get("scaling", 0),
        },
        "alerts": {
            "critical": critical_alerts,
            "warning": warning_alerts,
            "total_unresolved": critical_alerts + warning_alerts,
        },
        "top_opportunities": [
            {
                "id": str(p.id),
                "name": p.name,
                "opportunity_score": p.opportunity_score,
                "confidence_score": p.confidence_score,
                "gross_margin": p.gross_margin,
                "selling_price": p.selling_price,
                "category": p.category,
            }
            for p in top_products
        ],
        "agents": {
            "recent_runs": [
                {
                    "agent": r.agent_name,
                    "status": r.status.value,
                    "duration_s": r.duration_seconds,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in recent_agents
            ]
        },
        "latest_brief": {
            "date": latest_brief.date.isoformat() if latest_brief else None,
            "confidence_score": latest_brief.confidence_score if latest_brief else None,
            "products_to_launch": len(latest_brief.products_to_launch) if latest_brief else 0,
            "revenue_projection": latest_brief.revenue_projection if latest_brief else None,
        } if latest_brief else None,
    }
