"""
Competitor Intelligence Agent — monitors competitor stores for:
product launches, price changes, discounts, ad activity, and review spikes.
"""
from agents.base import BaseAgent, AgentResult
from core.database import AsyncSessionLocal
from core.database.models import Competitor, RiskAlert, AlertSeverity
from core.logging import get_logger
from datetime import datetime, timezone
from sqlalchemy import select

logger = get_logger(__name__)


class CompetitorIntelAgent(BaseAgent):
    name = "competitor_intel"
    description = (
        "Monitors competitor stores for pricing changes, new product launches, "
        "promotional activity, and review trends."
    )

    async def run(self, **kwargs) -> AgentResult:
        async with AsyncSessionLocal() as db:
            competitors = (await db.execute(select(Competitor))).scalars().all()

        if not competitors:
            return AgentResult.ok(data={"message": "No competitors tracked yet. Add via /api/v1/competitors.", "checked": 0})

        changes_detected = 0
        for competitor in competitors:
            changes = await self._check_competitor(competitor)
            if changes:
                changes_detected += len(changes)

        return AgentResult.ok(data={"competitors_checked": len(competitors), "changes_detected": changes_detected})

    async def _check_competitor(self, competitor: Competitor) -> list:
        # Real implementation uses Tandem Browser to scrape competitor sites
        # Placeholder for now — Tandem integration in next phase
        return []
