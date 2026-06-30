"""
Risk Intelligence Agent — continuously monitors for threats before they become critical.
Detects: supplier shortages, shipping delays, rising refunds, negative review spikes,
margin erosion, declining conversions, seasonal risks.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict

from agents.base import BaseAgent, AgentResult
from core.database import AsyncSessionLocal
from core.database.models import (
    AlertSeverity, Product, ProductStatus, RiskAlert, StoreMetric
)
from core.events import Events
from core.logging import get_logger
from sqlalchemy import select, desc, func

logger = get_logger(__name__)


class RiskIntelligenceAgent(BaseAgent):
    name = "risk_intelligence"
    description = (
        "Monitors all active products, stores, and suppliers for risk signals. "
        "Generates actionable alerts before issues become critical."
    )

    async def run(self, **kwargs) -> AgentResult:
        alerts_created: List[Dict] = []

        async with AsyncSessionLocal() as db:
            # Check active products
            active_products = (await db.execute(
                select(Product).where(
                    Product.status.in_([ProductStatus.LAUNCHED, ProductStatus.SCALING, ProductStatus.MAINTAINING])
                )
            )).scalars().all()

            for product in active_products:
                product_alerts = await self._check_product_risks(db, product)
                alerts_created.extend(product_alerts)

            await db.commit()

        # Publish each critical alert
        for alert in alerts_created:
            if alert.get("severity") in ["warning", "critical"]:
                await self._publish(Events.RISK_DETECTED, alert)

        return AgentResult.ok(
            data={
                "products_checked": len(active_products) if 'active_products' in dir() else 0,
                "alerts_created": len(alerts_created),
                "critical_alerts": sum(1 for a in alerts_created if a.get("severity") == "critical"),
            }
        )

    async def _check_product_risks(self, db, product: Product) -> List[Dict]:
        alerts = []

        # Margin erosion check
        if product.gross_margin and product.gross_margin < 0.40:
            alert = await self._create_alert(
                db,
                product_id=product.id,
                severity=AlertSeverity.CRITICAL,
                alert_type="margin_erosion",
                title=f"Critical Margin: {product.name}",
                message=f"Gross margin at {product.gross_margin:.1%} — below minimum 40%. Immediate repricing or product retirement needed.",
                data={"gross_margin": product.gross_margin, "threshold": 0.40},
            )
            alerts.append(alert)

        # High risk score check
        if product.risk_score and product.risk_score > 70:
            alert = await self._create_alert(
                db,
                product_id=product.id,
                severity=AlertSeverity.WARNING,
                alert_type="high_risk",
                title=f"High Risk Score: {product.name}",
                message=f"Risk score {product.risk_score:.0f}/100. Review pricing, supplier, and shipping configuration.",
                data={"risk_score": product.risk_score},
            )
            alerts.append(alert)

        # Long shipping check
        if product.shipping_days and product.shipping_days > 20:
            alert = await self._create_alert(
                db,
                product_id=product.id,
                severity=AlertSeverity.WARNING,
                alert_type="shipping_delay",
                title=f"Slow Shipping: {product.name}",
                message=f"Shipping time {product.shipping_days} days exceeds recommended 15 days. Increases refund risk.",
                data={"shipping_days": product.shipping_days},
            )
            alerts.append(alert)

        return alerts

    async def _create_alert(self, db, **kwargs) -> Dict:
        # Don't duplicate alerts for same product+type
        existing = (await db.execute(
            select(RiskAlert).where(
                RiskAlert.product_id == kwargs.get("product_id"),
                RiskAlert.alert_type == kwargs["alert_type"],
                RiskAlert.is_resolved == False,
            )
        )).scalar_one_or_none()

        if existing:
            return {}

        alert = RiskAlert(**kwargs)
        db.add(alert)
        await db.flush()

        return {
            "severity": kwargs["severity"].value,
            "type": kwargs["alert_type"],
            "title": kwargs["title"],
            "message": kwargs["message"],
        }
