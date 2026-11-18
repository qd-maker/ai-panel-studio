"""嘉宾生成：POST /api/discussions"""

import re

import pytest

from app.fake_llm import FakeLLM
from tests.conftest import TOPIC, api, rows

pytestmark = pytest.mark.anyio


async def test_lineup_size_equals_requested_count_with_exactly_one_host(make_app):
    app, _ = make_app()
    async with api(app) as client:
        r = await client.post("/api/discussions", json={"topic": TOPIC, "expert_count": 5})

    assert r.status_code == 201, r.text
    body = r.json()
    roles = [p["role"] for p in body["participants"]]
    assert roles.count("host") == 1
    assert roles.count("expert") == 5
    assert body["status"] == "lineup_ready"


async def test_lineup_invalid_json_is_retried_then_returns_502(make_app, engine):
    fake = FakeLLM(script={"lineup": ["这不是 JSON"] * 10})
    app, _ = make_app(fake, llm_retries=2)
    async with api(app) as client:
        r = await client.post("/api/discussions", json={"topic": TOPIC, "expert_count": 4})

    assert r.status_code == 502
    body = r.json()
    assert body["code"] == "LLM_BAD_OUTPUT"
    assert fake.calls_for("lineup") == 3  # 首次 + 重试 2 次
    # 讨论已创建并停在 draft，返回 id 供用户重新生成
    did = body["details"]["discussion_id"]
    assert rows(engine, "SELECT status FROM discussion WHERE id = :d", d=did) == [{"status": "draft"}]


async def test_lineup_retry_succeeds_when_next_output_is_valid(make_app):
    fake = FakeLLM(script={"lineup": ['{"host": 不完整']})
    app, _ = make_app(fake, llm_retries=2)
    async with api(app) as client:
        r = await client.post("/api/discussions", json={"topic": TOPIC, "expert_count": 4})

    assert r.status_code == 201, r.text
    assert fake.calls_for("lineup") == 2


async def test_each_guest_gets_a_distinct_valid_color(make_app):
    app, _ = make_app()
    async with api(app) as client:
        r = await client.post("/api/discussions", json={"topic": TOPIC, "expert_count": 6})

    colors = [p["color"] for p in r.json()["participants"]]
    assert len(colors) == 7
    assert len(set(c.lower() for c in colors)) == 7
    assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for c in colors)
