"""大模型调用的接口契约：真实客户端（DeepSeek）和测试替身（FakeLLM）都实现它。

业务代码只依赖 LLMClient.complete，不关心背后是谁。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

# 每次调用的用途。编排器按用途组织提示词，FakeLLM 按用途返回脚本内容。
Purpose = Literal["lineup", "intents", "utterance", "host", "insights", "summary"]


@dataclass(frozen=True)
class LLMResult:
    text: str
    # 推理模型的隐藏思维链。业务代码必须丢弃它，任何接口和事件都不能带出去（P-01）
    reasoning: str | None = None


class LLMError(Exception):
    """模型服务调用失败（超时、限流、连接失败）。"""


class LLMClient(Protocol):
    async def complete(
        self,
        purpose: Purpose,
        messages: list[dict[str, str]],
        *,
        hints: dict[str, Any] | None = None,
    ) -> LLMResult:
        """messages 是 OpenAI 格式的对话。

        hints 是结构化提示（人数、嘉宾 id、发言 id 等），真实客户端忽略它；
        FakeLLM 用它生成结构正确的确定性输出，不必去解析提示词文本。
        """
        ...
