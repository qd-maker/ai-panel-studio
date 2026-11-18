"""测试公共设施。

测试一律在 LLM_MODE=mock 下运行：大模型换成 app.fake_llm.FakeLLM，结果确定、不联网、不花钱。

TDD 约定：被测模块（app.main、app.scheduler 等）在测试函数内部用 load() 导入，
实现还不存在时，每个测试各自以 ModuleNotFoundError 失败，而不是整个文件在收集阶段报错。
"""

import importlib
import json
import os
from contextlib import asynccontextmanager

import anyio
import httpx
import pytest
from sqlalchemy import Engine, text

from app.db import create_db_engine, init_db
from app.fake_llm import FakeLLM

os.environ["LLM_MODE"] = "mock"

# 测试用的快节奏设置：不等待、讨论短、每 3 条专家发言主持人插一次话
FAST_SETTINGS = {
    "llm_mode": "mock",
    "turn_delay_s": 0,
    "max_expert_turns": 6,
    "host_every_n": 3,
    "max_consecutive": 2,
    "llm_retries": 2,
    "max_running": 3,
}

TOPIC = "远程办公会降低团队创造力吗"


def load(module: str):
    return importlib.import_module(module)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def engine(tmp_path) -> Engine:
    """每个测试一个独立的临时 SQLite 文件，已建表。"""
    eng = create_db_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def make_app(engine):
    """make_app(fake=None, **settings) -> (app, fake)"""

    def _make(fake: FakeLLM | None = None, **overrides):
        main = load("app.main")
        config = load("app.config")
        fake = fake or FakeLLM()
        settings = config.Settings(**{**FAST_SETTINGS, **overrides})
        return main.create_app(engine=engine, llm=fake, settings=settings), fake

    return _make


@asynccontextmanager
async def api(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def create_discussion(client, topic: str = TOPIC, expert_count: int = 4) -> dict:
    r = await client.post("/api/discussions", json={"topic": topic, "expert_count": expert_count})
    assert r.status_code == 201, r.text
    return r.json()


async def run_to_end(app, client, topic: str = TOPIC, expert_count: int = 4) -> str:
    """创建 → 开始 → 等后台任务跑完，返回讨论 id。"""
    d = await create_discussion(client, topic, expert_count)
    r = await client.post(f"/api/discussions/{d['id']}/start")
    assert r.status_code == 202, r.text
    with anyio.fail_after(15):
        await app.state.runner.wait(d["id"])
    return d["id"]


def rows(engine: Engine, sql: str, **params) -> list[dict]:
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def utterances_of(engine: Engine, did: str) -> list[dict]:
    return rows(
        engine,
        "SELECT u.*, p.role FROM utterance u JOIN participant p ON p.id = u.participant_id "
        "WHERE u.discussion_id = :d ORDER BY u.seq",
        d=did,
    )


def events_of(engine: Engine, did: str) -> list[dict]:
    out = rows(engine, "SELECT * FROM event WHERE discussion_id = :d ORDER BY id", d=did)
    for e in out:
        e["payload"] = json.loads(e["payload"])
    return out
