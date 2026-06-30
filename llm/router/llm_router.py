"""
LLM Router — always prefers local DGX Spark (Ollama).
Falls back to Claude API only when local is unavailable or task requires it.
Never sends proprietary business data to cloud unless absolutely necessary.
"""
import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    LOCAL  = "local"   # Ollama on DGX Spark
    CLOUD  = "cloud"   # Claude API (fallback)


class LLMModel(str, Enum):
    # Local models
    DEFAULT = "default"   # 70B for reasoning
    FAST    = "fast"      # 3B for quick tasks
    VISION  = "vision"    # For image analysis
    EMBED   = "embed"     # For embeddings

    # Cloud (used sparingly)
    CLOUD_STANDARD = "cloud_standard"


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class LLMResponse:
    content: str
    provider: LLMProvider
    model: str
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None


@dataclass
class LLMRequest:
    messages: List[LLMMessage]
    model: LLMModel = LLMModel.DEFAULT
    temperature: float = 0.3
    max_tokens: int = 4096
    system_prompt: Optional[str] = None
    json_mode: bool = False
    force_cloud: bool = False  # Only set True for tasks that REQUIRE cloud


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.timeout = httpx.Timeout(120.0, connect=10.0)

    def _resolve_model(self, model: LLMModel) -> str:
        mapping = {
            LLMModel.DEFAULT: settings.ollama_default_model,
            LLMModel.FAST:    settings.ollama_fast_model,
            LLMModel.VISION:  settings.ollama_vision_model,
            LLMModel.EMBED:   settings.ollama_embed_model,
        }
        return mapping.get(model, settings.ollama_default_model)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def complete(self, request: LLMRequest) -> LLMResponse:
        import time
        model_name = self._resolve_model(request.model)

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            messages.append({"role": m.role, "content": m.content})

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "think": False,  # disable thinking tokens for qwen3/deepseek-r1 style models
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        if request.json_mode:
            payload["format"] = "json"

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat", json=payload
            )
            response.raise_for_status()

        data = response.json()
        elapsed_ms = int((time.monotonic() - start) * 1000)

        msg = data.get("message", {})
        content = msg.get("content", "")
        # Thinking models (qwen3, deepseek-r1) put output in "thinking" when content is empty
        if not content and msg.get("thinking"):
            content = msg["thinking"]
        tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)

        return LLMResponse(
            content=content,
            provider=LLMProvider.LOCAL,
            model=model_name,
            tokens_used=tokens,
            duration_ms=elapsed_ms,
        )

    async def embed(self, text: str) -> List[float]:
        payload = {"model": settings.ollama_embed_model, "input": text}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self.base_url}/api/embed", json=payload)
            r.raise_for_status()
        return r.json()["embeddings"][0]


class ClaudeClient:
    def __init__(self):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def complete(self, request: LLMRequest) -> LLMResponse:
        import time

        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role != "system"
        ]

        kwargs: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt
        if request.json_mode:
            kwargs["system"] = (
                (kwargs.get("system", "") + "\n\nRespond with valid JSON only.").strip()
            )

        start = time.monotonic()
        response = await self._client.messages.create(**kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        content = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        return LLMResponse(
            content=content,
            provider=LLMProvider.CLOUD,
            model=self._model,
            tokens_used=tokens,
            duration_ms=elapsed_ms,
        )


class LLMRouter:
    """
    Routes LLM requests to local Ollama (DGX Spark) first.
    Falls back to Claude only when local is unavailable.
    Logs every call for cost and performance tracking.
    """

    def __init__(self):
        self._ollama = OllamaClient()
        self._claude: Optional[ClaudeClient] = None
        self._local_available: Optional[bool] = None

    def _get_claude(self) -> ClaudeClient:
        if not self._claude:
            if not settings.anthropic_api_key:
                raise RuntimeError(
                    "Claude fallback requested but ANTHROPIC_API_KEY not set."
                )
            self._claude = ClaudeClient()
        return self._claude

    async def _check_local(self) -> bool:
        available = await self._ollama.health_check()
        if not available:
            logger.warning("llm.local_unavailable", ollama_url=settings.ollama_base_url)
        return available

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if request.force_cloud:
            logger.info("llm.routing", provider="cloud", reason="force_cloud")
            return await self._get_claude().complete(request)

        if settings.llm_prefer_local:
            local_ok = await self._check_local()
            if local_ok:
                try:
                    result = await self._ollama.complete(request)
                    logger.debug(
                        "llm.completed",
                        provider="local",
                        model=result.model,
                        tokens=result.tokens_used,
                        ms=result.duration_ms,
                    )
                    return result
                except Exception as e:
                    logger.warning("llm.local_failed", error=str(e), fallback="cloud")

        # Fallback to cloud
        result = await self._get_claude().complete(request)
        logger.info(
            "llm.completed",
            provider="cloud",
            model=result.model,
            tokens=result.tokens_used,
        )
        return result

    async def embed(self, text: str) -> List[float]:
        local_ok = await self._check_local()
        if local_ok:
            return await self._ollama.embed(text)
        raise RuntimeError(
            "Embedding requires local Ollama (DGX Spark). Ensure Ollama is running."
        )

    async def json_complete(self, request: LLMRequest) -> dict:
        request.json_mode = True
        response = await self.complete(request)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"LLM did not return valid JSON: {response.content[:500]}")


# Singleton
llm_router = LLMRouter()
