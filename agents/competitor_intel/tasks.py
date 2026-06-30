import asyncio
from core.tasks import celery_app


@celery_app.task(name="agents.competitor_intel.tasks.run_competitor_check", bind=True)
def run_competitor_check(self):
    from agents.competitor_intel import CompetitorIntelAgent
    agent = CompetitorIntelAgent()
    result = asyncio.get_event_loop().run_until_complete(agent.execute())
    return {"success": result.success, "data": result.data}
