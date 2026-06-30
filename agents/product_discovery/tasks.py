import asyncio
from core.tasks import celery_app
from core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="agents.product_discovery.tasks.run_discovery", bind=True, max_retries=3)
def run_discovery(self, niches=None, limit=50):
    from agents.product_discovery import ProductDiscoveryAgent
    agent = ProductDiscoveryAgent()
    result = asyncio.get_event_loop().run_until_complete(
        agent.execute(niches=niches, limit=limit)
    )
    return {"success": result.success, "data": result.data, "error": result.error}
