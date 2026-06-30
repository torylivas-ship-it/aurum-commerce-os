import asyncio
from core.tasks import celery_app
from core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="agents.executive_advisor.tasks.generate_morning_brief", bind=True)
def generate_morning_brief(self):
    from agents.executive_advisor import ExecutiveAdvisorAgent
    agent = ExecutiveAdvisorAgent()
    result = asyncio.get_event_loop().run_until_complete(agent.execute())
    return {"success": result.success, "data": result.data}
