"""
Executive Advisor Agent — generates a morning business brief every day at 7am.

The brief includes:
  - Top products to launch (with scores, margin, confidence)
  - Products to discontinue
  - Revenue projections
  - Marketing opportunities
  - Risk alerts
  - Portfolio health
  - Highest ROI opportunities

Every recommendation includes: impact, confidence score, risk, evidence, effort.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from agents.base import BaseAgent, AgentResult
from core.database import AsyncSessionLocal
from core.database.models import (
    ApprovalRequest, ApprovalStatus, ExecutiveBrief,
    Product, ProductStatus, RiskAlert, StoreMetric
)
from core.events import Events
from core.logging import get_logger
from llm.router import LLMModel
from sqlalchemy import select, func, desc

logger = get_logger(__name__)


class ExecutiveAdvisorAgent(BaseAgent):
    name = "executive_advisor"
    description = (
        "Synthesizes all business intelligence into a daily Executive Business Brief. "
        "Provides prioritized, evidence-backed recommendations with confidence scores, "
        "risk assessments, and ROI projections."
    )

    async def run(self, **kwargs) -> AgentResult:
        today = datetime.now(timezone.utc)

        self.logger.info("brief.generating", date=today.date().isoformat())

        async with AsyncSessionLocal() as db:
            context = await self._gather_context(db, today)

        brief_content = await self._generate_brief(context, today)
        structured = await self._extract_structured(brief_content, context)

        async with AsyncSessionLocal() as db:
            brief = ExecutiveBrief(
                date=today,
                content=brief_content,
                structured_data=structured,
                products_to_launch=structured.get("products_to_launch", []),
                products_to_retire=structured.get("products_to_retire", []),
                revenue_projection=structured.get("revenue_projection"),
                confidence_score=structured.get("overall_confidence"),
            )
            db.add(brief)
            await db.commit()

        await self._publish(Events.BRIEF_GENERATED, {
            "date": today.date().isoformat(),
            "products_to_launch": len(structured.get("products_to_launch", [])),
            "revenue_projection": structured.get("revenue_projection"),
        })

        await self._send_email_brief(brief_content, today)

        return AgentResult.ok(
            data={
                "brief_date": today.date().isoformat(),
                "products_to_launch": len(structured.get("products_to_launch", [])),
                "products_to_retire": len(structured.get("products_to_retire", [])),
                "revenue_projection": structured.get("revenue_projection"),
                "overall_confidence": structured.get("overall_confidence"),
            }
        )

    async def _gather_context(self, db, today: datetime) -> Dict:
        # Top pending approvals
        pending = (await db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING)
            .order_by(desc(ApprovalRequest.created_at))
            .limit(20)
        )).scalars().all()

        # Top products by opportunity score
        top_products = (await db.execute(
            select(Product)
            .where(Product.status == ProductStatus.DISCOVERED)
            .order_by(desc(Product.opportunity_score))
            .limit(10)
        )).scalars().all()

        # Active products
        active_products = (await db.execute(
            select(Product)
            .where(Product.status.in_([ProductStatus.LAUNCHED, ProductStatus.SCALING]))
            .limit(20)
        )).scalars().all()

        # Active risk alerts
        alerts = (await db.execute(
            select(RiskAlert)
            .where(RiskAlert.is_resolved == False)
            .order_by(desc(RiskAlert.created_at))
            .limit(10)
        )).scalars().all()

        return {
            "date": today.date().isoformat(),
            "pending_approvals": len(pending),
            "top_opportunities": [
                {
                    "name": p.name,
                    "opportunity_score": p.opportunity_score,
                    "confidence_score": p.confidence_score,
                    "gross_margin": f"{(p.gross_margin or 0):.1%}",
                    "selling_price": p.selling_price,
                    "profit_per_unit": round((p.selling_price or 0) - (p.supplier_cost or 0) - (p.shipping_cost or 0), 2) if p.selling_price else None,
                    "category": p.category,
                    "recommendation": "LAUNCH" if (p.opportunity_score or 0) >= 70 else "WATCH",
                }
                for p in top_products
            ],
            "active_products": [
                {
                    "name": p.name,
                    "status": p.status.value,
                    "opportunity_score": p.opportunity_score,
                }
                for p in active_products
            ],
            "unresolved_alerts": [
                {
                    "severity": a.severity.value,
                    "type": a.alert_type,
                    "title": a.title,
                    "message": a.message[:200],
                }
                for a in alerts
            ],
        }

    async def _generate_brief(self, context: Dict, today: datetime) -> str:
        prompt = f"""You are the Executive Advisor for Aurum Commerce OS.
Generate a comprehensive Executive Business Brief for {today.strftime('%A, %B %d, %Y')}.

Business Context:
{json.dumps(context, indent=2)}

Generate the brief in this exact format:

# Aurum Commerce OS — Daily Executive Brief
**Date:** {today.strftime('%A, %B %d, %Y')}
**Generated:** {today.strftime('%I:%M %p %Z')}

---

## Executive Summary
[2-3 sentence overview of today's priorities and opportunities]

---

## Top Products to Launch
[For each product with opportunity score >= 70:]
### [Product Name]
- **Opportunity Score:** X/100 | **Confidence:** X/100 | **Risk:** X/100
- **Gross Margin:** X% | **Selling Price:** $XX | **Profit/Unit:** $XX
- **Recommendation:** [STRONG_BUY / BUY]
- **Why Now:** [Evidence-backed rationale]
- **Implementation Effort:** [Low / Medium / High]
- **Expected Monthly Revenue (est.):** $X,XXX

---

## Products to Monitor or Discontinue
[Products at risk or declining]

---

## Marketing Opportunities
[Top 3 opportunities with expected ROI]

---

## Risk Alerts
[All unresolved risks with severity and recommended action]

---

## Revenue Projections
| Period | Conservative | Base Case | Optimistic |
|--------|-------------|-----------|------------|
| 30 Days | $X,XXX | $X,XXX | $X,XXX |
| 60 Days | $X,XXX | $X,XXX | $X,XXX |
| 90 Days | $X,XXX | $X,XXX | $X,XXX |

---

## Highest ROI Actions Today
1. [Action] — Expected Impact: $X | Effort: X | Confidence: X%
2. [Action] — Expected Impact: $X | Effort: X | Confidence: X%
3. [Action] — Expected Impact: $X | Effort: X | Confidence: X%

---

## Pending Human Approvals
[Items waiting for your approval]

---

*Aurum Commerce OS v1.0 | All recommendations include confidence scores and supporting evidence.*
"""

        return await self.think(prompt, model=LLMModel.DEFAULT, max_tokens=4096)

    async def _extract_structured(self, brief: str, context: Dict) -> Dict:
        prompt = f"""Extract structured data from this executive brief.
Return JSON only:
{{
  "products_to_launch": [
    {{"name": "...", "opportunity_score": 0, "confidence_score": 0, "gross_margin": 0.0, "selling_price": 0.0}}
  ],
  "products_to_retire": [
    {{"name": "...", "reason": "..."}}
  ],
  "revenue_projection": {{
    "30_day_base": 0,
    "60_day_base": 0,
    "90_day_base": 0
  }},
  "risk_count": 0,
  "top_actions": ["action1", "action2", "action3"],
  "overall_confidence": 75
}}

Brief:
{brief[:3000]}
"""
        try:
            return await self.think_json(prompt, model=LLMModel.FAST)
        except Exception:
            return {"products_to_launch": [], "products_to_retire": [], "overall_confidence": 70}

    async def _send_email_brief(self, brief: str, today: datetime) -> None:
        from core.config import settings
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        if not settings.smtp_user or not settings.smtp_password:
            self.logger.info("email.skipped", reason="SMTP not configured")
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Aurum Commerce Brief — {today.strftime('%B %d, %Y')}"
            msg["From"] = settings.smtp_user
            msg["To"] = ", ".join(settings.report_recipients_list)

            text_part = MIMEText(brief, "plain")
            msg.attach(text_part)

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(
                    settings.smtp_user,
                    settings.report_recipients_list,
                    msg.as_string(),
                )
            self.logger.info("email.sent", recipients=settings.report_recipients_list)
        except Exception as e:
            self.logger.warning("email.failed", error=str(e))
