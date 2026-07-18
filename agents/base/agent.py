"""
BaseAgent — every agent in Aurum inherits from this.
Provides: logging, DB access, LLM routing, event publishing,
agent run tracking, retry logic, and structured output.
"""
import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.config import settings
from core.database import AsyncSessionLocal
from core.database.models import AgentRun, AgentStatus
from core.events import event_bus, Events
from core.logging import get_logger
from llm.router import llm_router, LLMRequest, LLMMessage, LLMModel


@dataclass
class AgentResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any, **metadata) -> "AgentResult":
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "AgentResult":
        return cls(success=False, error=error, metadata=metadata)


class BaseAgent(ABC):
    name: str = "base"
    description: str = ""
    version: str = "1.0.0"

    def __init__(self):
        self.logger = get_logger(f"agent.{self.name}")
        self.llm = llm_router
        self.event_bus = event_bus
        self._run_id: Optional[str] = None

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def run(self, **kwargs) -> AgentResult:
        """Execute the agent's primary task. Implement in subclasses."""
        ...

    # ── Execution harness ─────────────────────────────────────────────────────

    async def execute(self, **kwargs) -> AgentResult:
        """Wraps run() with logging, timing, DB tracking, and event publishing."""
        self._run_id = str(uuid.uuid4())
        start = time.monotonic()

        self.logger.info(
            "agent.started",
            agent=self.name,
            run_id=self._run_id,
            kwargs=list(kwargs.keys()),
        )

        await self._publish(Events.AGENT_STARTED, {"agent": self.name, "run_id": self._run_id})
        await self._record_run_start(kwargs)

        try:
            result = await self.run(**kwargs)
            duration = time.monotonic() - start

            if result.success:
                self.logger.info(
                    "agent.completed",
                    agent=self.name,
                    run_id=self._run_id,
                    duration_s=round(duration, 2),
                )
                await self._publish(Events.AGENT_COMPLETED, {
                    "agent": self.name, "run_id": self._run_id,
                    "duration_s": round(duration, 2),
                })
                await self._record_run_end(AgentStatus.SUCCESS, result, duration)
            else:
                self.logger.warning(
                    "agent.failed",
                    agent=self.name,
                    run_id=self._run_id,
                    error=result.error,
                )
                await self._publish(Events.AGENT_FAILED, {
                    "agent": self.name, "error": result.error,
                })
                await self._record_run_end(AgentStatus.FAILED, result, duration)

            return result

        except Exception as e:
            duration = time.monotonic() - start
            self.logger.exception("agent.exception", agent=self.name, error=str(e))
            await self._publish(Events.AGENT_FAILED, {"agent": self.name, "error": str(e)})
            await self._record_run_end(
                AgentStatus.FAILED, AgentResult.fail(str(e)), duration
            )
            return AgentResult.fail(str(e))

    # ── LLM helpers ───────────────────────────────────────────────────────────

    async def think(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: LLMModel = LLMModel.DEFAULT,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        request = LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt=system or self._default_system(),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response = await self.llm.complete(request)
        return response.content

    async def think_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: LLMModel = LLMModel.DEFAULT,
        temperature: float = 0.3,
    ) -> dict:
        request = LLMRequest(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt=system or self._default_system(),
            model=model,
            temperature=temperature,
            json_mode=True,
        )
        return await self.llm.json_complete(request)

    def _default_system(self) -> str:
        return (
            f"You are the {self.name} agent in Aurum Commerce OS, "
            f"an AI-powered ecommerce operating system. {self.description} "
            "Always reason carefully, be concise, and back every recommendation "
            "with evidence and a confidence score."
        )

    # ── Event helpers ─────────────────────────────────────────────────────────

    async def _publish(self, event_type: str, data: Any) -> None:
        try:
            await self.event_bus.publish(event_type, data, source=self.name)
        except Exception as e:
            self.logger.warning("event.publish_failed", error=str(e))

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _record_run_start(self, input_data: dict) -> None:
        try:
            async with AsyncSessionLocal() as db:
                run = AgentRun(
                    id=uuid.UUID(self._run_id),
                    agent_name=self.name,
                    status=AgentStatus.RUNNING,
                    input_data=input_data,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(run)
                await db.commit()
        except Exception as e:
            self.logger.warning("agent.db_record_failed", error=str(e))

    async def _record_run_end(
        self,
        status: AgentStatus,
        result: AgentResult,
        duration: float,
    ) -> None:
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                stmt = select(AgentRun).where(
                    AgentRun.id == uuid.UUID(self._run_id)
                )
                run = (await db.execute(stmt)).scalar_one_or_none()
                if run:
                    run.status = status
                    run.output_data = (
                        result.data if isinstance(result.data, dict) else {"result": str(result.data)}
                    ) if result.data else {}
                    run.error = result.error
                    run.duration_seconds = round(duration, 3)
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception as e:
            self.logger.warning("agent.db_update_failed", error=str(e))
