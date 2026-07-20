import asyncio
from core.tasks import celery_app


@celery_app.task(name="agents.advertising.tasks.run_advertising_scan", bind=True)
def run_advertising_scan(self):
    from agents.advertising import AdvertisingAgent
    agent = AdvertisingAgent()
    result = asyncio.get_event_loop().run_until_complete(agent.execute())
    return {"success": result.success, "data": result.data}
