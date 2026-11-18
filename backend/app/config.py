"""运行配置。生产环境从环境变量读取（Settings.from_env），测试直接构造。"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    # 大模型
    llm_mode: Literal["mock", "deepseek"] = "mock"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_timeout_s: float = 30
    llm_retries: int = Field(default=1, ge=0)  # 结构化输出校验失败或调用失败时的重试次数

    # 讨论节奏
    turn_delay_s: float = Field(default=1.5, ge=0)  # 两条发言之间的停顿，营造现场节奏
    max_expert_turns: int = Field(default=12, ge=1)
    host_every_n: int = Field(default=3, ge=1)  # 每 N 条专家发言，主持人插一次话
    max_consecutive: int = Field(default=2, ge=1)  # 同一专家最多连续发言次数
    recent_k: int = Field(default=8, ge=1)  # 专家只看到最近 K 条公开发言
    max_llm_failures: int = Field(default=3, ge=1)  # 连续这么多次发言生成失败，讨论进入 failed

    # 资源
    max_running: int = Field(default=3, ge=1)
    # 单条 SSE 连接最长存活秒数，到时由服务端关闭，浏览器带 Last-Event-ID 自动重连续传。
    # 用来避开反向代理的长连接超时；0 表示不限制
    sse_max_stream_s: float = Field(default=0, ge=0)

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        values: dict = {"llm_mode": env.get("LLM_MODE", "mock")}
        for field, var in {
            "deepseek_model": "DEEPSEEK_MODEL",
            "deepseek_base_url": "DEEPSEEK_BASE_URL",
            "turn_delay_s": "TURN_DELAY_S",
            "max_expert_turns": "MAX_EXPERT_TURNS",
            "max_running": "MAX_RUNNING",
            "sse_max_stream_s": "SSE_MAX_STREAM_S",
        }.items():
            if var in env:
                values[field] = env[var]
        return cls(**values)
