import asyncio
from core.tasks import celery_app


@celery_app.task(name="agents.risk_intelligence.tasks.run_risk_check", bind=True)
def run_risk_check(self):
    from agents.risk_intelligence import RiskIntelligenceAgent
    agent = RiskIntelligenceAgent()
    result = asyncio.get_event_loop().run_until_complete(agent.execute())
    return {"success": result.success, "data": result.data}
