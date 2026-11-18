"""讨论状态机：只能沿 draft → lineup_ready → running → summarizing → done 前进。"""

import anyio
import pytest

from app.fake_llm import FakeLLM
from db.seed import seed
from tests.conftest import TOPIC, api, create_discussion, rows

pytestmark = pytest.mark.anyio


async def test_draft_discussion_cannot_start_before_lineup_exists(make_app):
    app, _ = make_app(FakeLLM(script={"lineup": ["坏输出"] * 10}))
    async with api(app) as client:
        r = await client.post("/api/discussions", json={"topic": TOPIC})
        assert r.status_code == 502
        did = r.json()["details"]["discussion_id"]

        r = await client.post(f"/api/discussions/{did}/start")

    assert r.status_code == 409
    assert r.json()["code"] == "INVALID_STATE_TRANSITION"


async def test_starting_a_finished_discussion_returns_409(make_app, engine):
    seed(engine)
    done_id = rows(engine, "SELECT id FROM discussion WHERE status = 'done' LIMIT 1")[0]["id"]
    app, _ = make_app()
    async with api(app) as client:
        r = await client.post(f"/api/discussions/{done_id}/start")

    assert r.status_code == 409
    assert r.json()["code"] == "INVALID_STATE_TRANSITION"


async def test_duplicate_start_runs_only_one_background_task(make_app):
    app, _ = make_app(max_expert_turns=20)
    async with api(app) as client:
        did = (await create_discussion(client))["id"]

        codes: list[int] = []

        async def start():
            codes.append((await client.post(f"/api/discussions/{did}/start")).status_code)

        async with anyio.create_task_group() as tg:
            tg.start_soon(start)
            tg.start_soon(start)

        assert sorted(codes) == [202, 409]
        assert app.state.runner.active_ids().count(did) == 1
        await app.state.runner.cancel(did)
