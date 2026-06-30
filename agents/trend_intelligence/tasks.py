import asyncio
from core.tasks import celery_app


@celery_app.task(name="agents.trend_intelligence.tasks.run_trend_scan", bind=True)
def run_trend_scan(self, niches=None):
    from agents.trend_intelligence import TrendIntelligenceAgent
    agent = TrendIntelligenceAgent()
    result = asyncio.get_event_loop().run_until_complete(agent.execute(niches=niches))
    return {"success": result.success, "data": result.data}
