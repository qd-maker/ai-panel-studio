"""FastAPI 应用。

运行：uvicorn app.main:create_app --factory
测试：create_app(engine=..., llm=FakeLLM(), settings=Settings(...))
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from app import api, auth, errors
from app.bus import EventBus
from app.config import Settings
from app.db import get_engine
from app.llm import create_llm
from app.llm_base import LLMClient


def create_app(*, engine: Engine | None = None, llm: LLMClient | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = engine or get_engine()
    llm = llm or create_llm(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runner.recover_after_restart()
        yield
        await app.state.runner.shutdown()

    app = FastAPI(title="AI Panel Studio", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.llm = llm
    app.state.bus = EventBus()
    # 每场讨论一把锁：阵容生成、开始、结束互斥（API.md「并发控制」）
    app.state.locks: dict[str, asyncio.Lock] = {}
    from app.orchestrator import Runner  # 避免循环导入

    app.state.runner = Runner(app)

    errors.install(app)
    auth.install(app)
    app.include_router(api.router)
    return app
