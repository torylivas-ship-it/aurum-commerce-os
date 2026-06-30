from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import AgentRun, AgentStatus

router = APIRouter(prefix="/agents")


@router.get("/runs")
async def list_agent_runs(
    agent_name: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentRun).order_by(desc(AgentRun.created_at)).limit(limit)
    if agent_name:
        stmt = stmt.where(AgentRun.agent_name == agent_name)
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "agent_name": r.agent_name,
            "task": r.task,
            "status": r.status.value,
            "duration_seconds": r.duration_seconds,
            "tokens_used": r.tokens_used,
            "llm_provider": r.llm_provider,
            "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.post("/trigger/{agent_name}")
async def trigger_agent(agent_name: str, payload: Optional[Dict] = None):
    task_map = {
        "product_discovery": "agents.product_discovery.tasks.run_discovery",
        "executive_advisor": "agents.executive_advisor.tasks.generate_morning_brief",
        "risk_intelligence": "agents.risk_intelligence.tasks.run_risk_check",
        "trend_intelligence": "agents.trend_intelligence.tasks.run_trend_scan",
        "competitor_intel": "agents.competitor_intel.tasks.run_competitor_check",
    }

    task_name = task_map.get(agent_name)
    if not task_name:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")

    from core.tasks import celery_app
    task = celery_app.send_task(task_name, kwargs=payload or {})
    return {"task_id": task.id, "agent": agent_name, "status": "queued"}
