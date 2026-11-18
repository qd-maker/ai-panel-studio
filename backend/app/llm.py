"""大模型调用的统一入口。

- create_llm(settings) 按 LLM_MODE 返回客户端：mock → FakeLLM，deepseek → DeepSeekLLM。
- complete_structured() 让模型输出 JSON，用 Pydantic 校验，失败按 settings.llm_retries 重试。
- DEEPSEEK_API_KEY 只从环境变量读取，不进入任何配置文件、日志和接口响应。
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.fake_llm import FakeLLM
from app.llm_base import LLMClient, LLMError, LLMResult, Purpose
from app.textutil import extract_json

T = TypeVar("T", bound=BaseModel)

# 需要 JSON 输出的用途
STRUCTURED: set[str] = {"lineup", "intents", "insights"}


class LLMBadOutput(Exception):
    """模型输出在重试后仍未通过校验。"""


class DeepSeekLLM:
    """DeepSeek 的 OpenAI 兼容接口。默认关闭思考模式：响应更快，也不会产生隐藏思维链。"""

    def __init__(self, settings: Settings, api_key: str):
        from openai import AsyncOpenAI  # 只在真实模式下需要

        self.model = settings.deepseek_model
        self.client = AsyncOpenAI(api_key=api_key, base_url=settings.deepseek_base_url, timeout=settings.llm_timeout_s)

    async def complete(
        self,
        purpose: Purpose,
        messages: list[dict[str, str]],
        *,
        hints: dict[str, Any] | None = None,  # 真实模型不用 hints，信息都在 messages 里
    ) -> LLMResult:
        from openai import OpenAIError

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 1200,
            "temperature": 0.9 if purpose in ("utterance", "host") else 0.4,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
        if purpose in STRUCTURED:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except OpenAIError as e:
            raise LLMError(f"{type(e).__name__}: {e}") from e
        msg = resp.choices[0].message
        return LLMResult(text=msg.content or "", reasoning=getattr(msg, "reasoning_content", None))


def create_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return FakeLLM()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("LLM_MODE=deepseek 时必须设置环境变量 DEEPSEEK_API_KEY")
    return DeepSeekLLM(settings, api_key)


def llm_configured(settings: Settings) -> bool:
    return settings.llm_mode == "mock" or bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


async def complete_text(
    llm: LLMClient,
    purpose: Purpose,
    messages: list[dict[str, str]],
    *,
    hints: dict[str, Any] | None = None,
    retries: int = 1,
    log: list[dict] | None = None,
) -> str:
    """普通文本输出：只在调用失败时重试。返回的 reasoning 在这里丢弃，不往下传。"""
    last: Exception | None = None
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            result = await llm.complete(purpose, messages, hints=hints)
            _log(log, purpose, attempt, t0, ok=True)
            return result.text
        except LLMError as e:
            _log(log, purpose, attempt, t0, ok=False, error=str(e))
            last = e
    raise last or LLMError("unknown")


async def complete_structured(
    llm: LLMClient,
    purpose: Purpose,
    messages: list[dict[str, str]],
    model: type[T],
    *,
    hints: dict[str, Any] | None = None,
    retries: int = 1,
    check: Callable[[T], None] | None = None,
    log: list[dict] | None = None,
) -> T:
    """要求 JSON 输出并用 Pydantic 校验。调用失败或校验失败都会重试。

    check 做跨字段的业务校验（例如人数是否等于请求人数），不通过时抛 ValueError，同样触发重试。

    全部失败时：最后一次是调用失败抛 LLMError，是输出不合格抛 LLMBadOutput。
    """
    last: Exception | None = None
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            result = await llm.complete(purpose, messages, hints=hints)
        except LLMError as e:
            _log(log, purpose, attempt, t0, ok=False, error=str(e))
            last = e
            continue
        try:
            parsed = model.model_validate(extract_json(result.text))
            if check:
                check(parsed)
            _log(log, purpose, attempt, t0, ok=True)
            return parsed
        except (ValueError, ValidationError) as e:
            _log(log, purpose, attempt, t0, ok=False, error=f"bad output: {str(e)[:200]}")
            last = LLMBadOutput(str(e))
    raise last or LLMBadOutput("unknown")


def _log(log: list[dict] | None, purpose: str, attempt: int, t0: float, *, ok: bool, error: str | None = None) -> None:
    """调用记录，由调用方写进 internal 的 llm.call 事件。"""
    if log is not None:
        log.append({
            "purpose": purpose, "attempt": attempt, "ok": ok,
            "ms": round((time.perf_counter() - t0) * 1000), "error": error,
        })
