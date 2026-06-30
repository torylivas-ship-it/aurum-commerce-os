"""
Redis-backed event bus for inter-agent communication.
Agents publish events; other agents subscribe to react.
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import redis.asyncio as aioredis

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class EventBus:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._subscribers: Dict[str, List[Callable]] = {}
        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
        logger.info("event_bus.connected", url=settings.redis_url)

    async def disconnect(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
        if self._redis:
            await self._redis.aclose()

    async def publish(self, event_type: str, data: Any, source: str = "system") -> None:
        if not self._redis:
            await self.connect()

        payload = {
            "event_type": event_type,
            "source": source,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        channel = f"aurum:events:{event_type}"
        await self._redis.publish(channel, json.dumps(payload))
        logger.debug("event.published", event_type=event_type, source=source)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def start_listening(self) -> None:
        if not self._redis:
            await self.connect()

        pubsub = self._redis.pubsub()
        patterns = [f"aurum:events:{et}" for et in self._subscribers]
        if patterns:
            await pubsub.subscribe(*patterns)

        self._listener_task = asyncio.create_task(self._listen_loop(pubsub))

    async def _listen_loop(self, pubsub) -> None:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    event_type = payload.get("event_type")
                    handlers = self._subscribers.get(event_type, [])
                    for handler in handlers:
                        asyncio.create_task(handler(payload))
                except Exception as e:
                    logger.error("event.processing_error", error=str(e))


# Singleton event bus
event_bus = EventBus()


# ── Well-Known Event Types ────────────────────────────────────────────────────
class Events:
    PRODUCT_DISCOVERED   = "product.discovered"
    PRODUCT_SCORED       = "product.scored"
    PRODUCT_APPROVED     = "product.approved"
    PRODUCT_REJECTED     = "product.rejected"
    PRODUCT_LAUNCHED     = "product.launched"
    TREND_DETECTED       = "trend.detected"
    COMPETITOR_CHANGED   = "competitor.changed"
    RISK_DETECTED        = "risk.detected"
    APPROVAL_NEEDED      = "approval.needed"
    APPROVAL_RECEIVED    = "approval.received"
    BRIEF_GENERATED      = "brief.generated"
    AGENT_STARTED        = "agent.started"
    AGENT_COMPLETED      = "agent.completed"
    AGENT_FAILED         = "agent.failed"
    METRIC_UPDATED       = "metric.updated"
