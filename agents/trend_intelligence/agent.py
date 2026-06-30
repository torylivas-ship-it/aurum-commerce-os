"""
Trend Intelligence Agent — detects emerging trend signals across platforms.
Provides 30/60/90-day demand forecasts with confidence scores.
"""
from agents.base import BaseAgent, AgentResult
from core.database import AsyncSessionLocal
from core.database.models import TrendSignal
from core.logging import get_logger
from datetime import datetime, timezone
from llm.router import LLMModel

logger = get_logger(__name__)


class TrendIntelligenceAgent(BaseAgent):
    name = "trend_intelligence"
    description = (
        "Monitors trend signals across TikTok, Google Trends, Pinterest, and Reddit. "
        "Provides demand forecasts with confidence scores."
    )

    async def run(self, niches=None, **kwargs) -> AgentResult:
        niches = niches or ["home kitchen", "fitness", "pets", "tech accessories"]

        prompt = f"""Analyze current trend signals for these ecommerce niches: {', '.join(niches)}.

For each niche, identify:
1. Top 3 rising keywords/products
2. Trend velocity (rising/stable/falling)
3. Demand forecast (30/60/90 days)
4. Seasonality factors

Return JSON:
{{
  "trends": [
    {{
      "keyword": "product or keyword",
      "niche": "niche name",
      "platform": "tiktok|google|reddit|pinterest",
      "strength": 75,
      "velocity": 15,
      "forecast_30d": 80,
      "forecast_60d": 85,
      "forecast_90d": 75,
      "confidence": 72,
      "seasonal_factors": ["back to school", "fall season"]
    }}
  ]
}}
"""
        try:
            result = await self.think_json(prompt, model=LLMModel.FAST)
            trends = result.get("trends", [])

            async with AsyncSessionLocal() as db:
                for t in trends:
                    signal = TrendSignal(
                        keyword=t.get("keyword", "unknown"),
                        platform=t.get("platform", "multi"),
                        signal_type="trend",
                        strength=t.get("strength", 50),
                        velocity=t.get("velocity", 0),
                        data={
                            "niche": t.get("niche"),
                            "forecast": {
                                "30d": t.get("forecast_30d"),
                                "60d": t.get("forecast_60d"),
                                "90d": t.get("forecast_90d"),
                            },
                            "confidence": t.get("confidence"),
                            "seasonal_factors": t.get("seasonal_factors", []),
                        },
                        detected_at=datetime.now(timezone.utc),
                    )
                    db.add(signal)
                await db.commit()

            return AgentResult.ok(data={"trends_detected": len(trends), "niches": niches})

        except Exception as e:
            return AgentResult.fail(str(e))
