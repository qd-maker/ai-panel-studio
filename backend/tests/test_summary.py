"""总结：存库和接口返回的都是自然语言，不是 JSON（P-06）；隐藏思维链不外泄（P-01）。"""

import json

import pytest

from app.fake_llm import SECRET_COT, FakeLLM
from app.llm_base import LLMError
from tests.conftest import api, events_of, rows, run_to_end

pytestmark = pytest.mark.anyio


def assert_natural_language(s: str):
    assert s and s.strip()
    assert not s.lstrip().startswith(("{", "["))
    assert "```" not in s
    with pytest.raises(json.JSONDecodeError):
        json.loads(s)


async def test_summary_is_stored_and_returned_as_natural_language(make_app, engine):
    app, _ = make_app()
    async with api(app) as client:
        did = await run_to_end(app, client)
        detail = (await client.get(f"/api/discussions/{did}")).json()

    stored = rows(engine, "SELECT status, summary, summary_source FROM discussion WHERE id = :d", d=did)[0]
    assert stored["status"] == "done"
    assert stored["summary_source"] == "llm"
    assert_natural_language(stored["summary"])
    assert detail["summary"] == stored["summary"]
    assert isinstance(detail["summary"], str)


async def test_summary_returned_as_json_by_the_model_is_unwrapped_to_text(make_app, engine):
    fake = FakeLLM(script={"summary": ['```json\n{"summary": "本场讨论形成了两点共识。\\n\\n分歧集中在岗位总量上。"}\n```']})
    app, _ = make_app(fake)
    async with api(app) as client:
        did = await run_to_end(app, client)

    summary = rows(engine, "SELECT summary FROM discussion WHERE id = :d", d=did)[0]["summary"]
    assert_natural_language(summary)
    assert summary.startswith("本场讨论形成了两点共识。")


async def test_summary_falls_back_to_text_built_from_insights_when_model_keeps_failing(make_app, engine):
    fake = FakeLLM(script={"summary": [LLMError("timeout")] * 10})
    app, _ = make_app(fake)
    async with api(app) as client:
        did = await run_to_end(app, client)

    d = rows(engine, "SELECT status, summary, summary_source FROM discussion WHERE id = :d", d=did)[0]
    assert d["status"] == "done"
    assert d["summary_source"] == "fallback"
    assert_natural_language(d["summary"])


async def test_hidden_reasoning_never_reaches_api_or_events(make_app, engine):
    """FakeLLM 每次都返回 reasoning=SECRET_COT，它不能出现在任何接口和事件里。"""
    app, _ = make_app()
    async with api(app) as client:
        did = await run_to_end(app, client)
        detail = (await client.get(f"/api/discussions/{did}")).text
        listing = (await client.get("/api/discussions")).text

    assert SECRET_COT not in detail and SECRET_COT not in listing
    assert "reasoning" not in detail
    assert SECRET_COT not in json.dumps([e["payload"] for e in events_of(engine, did)], ensure_ascii=False)
