"""多场讨论并行时互相隔离（P-08），SSE 只下发本场的 public 事件（P-05）。"""

import json

import anyio
import pytest

from tests.conftest import api, create_discussion, events_of, load, rows, utterances_of

pytestmark = pytest.mark.anyio

PUBLIC_SSE_EVENTS = {"status", "utterance", "agent_state", "insight", "summary", "discussion_error"}


async def _start_two(app, client):
    a = (await create_discussion(client, "远程办公会降低团队创造力吗"))["id"]
    b = (await create_discussion(client, "城市应该限制网约车数量吗"))["id"]
    for did in (a, b):
        assert (await client.post(f"/api/discussions/{did}/start")).status_code == 202
    return a, b


async def test_concurrent_discussions_keep_transcript_events_and_insights_separate(make_app, engine):
    app, _ = make_app()
    async with api(app) as client:
        a, b = await _start_two(app, client)
        with anyio.fail_after(20):
            await app.state.runner.wait(a)
            await app.state.runner.wait(b)
        detail_a = (await client.get(f"/api/discussions/{a}")).json()

    people = {d: {r["id"] for r in rows(engine, "SELECT id FROM participant WHERE discussion_id = :d", d=d)} for d in (a, b)}
    utt_ids = {d: {u["id"] for u in utterances_of(engine, d)} for d in (a, b)}

    for me, other in ((a, b), (b, a)):
        assert utt_ids[me], "两场讨论都应当有发言"
        assert all(u["participant_id"] in people[me] for u in utterances_of(engine, me))
        for e in events_of(engine, me):
            assert e["payload"].get("discussion_id", me) == me
        for i in rows(engine, "SELECT * FROM insight WHERE discussion_id = :d", d=me):
            assert set(json.loads(i["supporter_ids"]) + json.loads(i["opponent_ids"])) <= people[me]
            assert set(json.loads(i["evidence_utterance_ids"])) <= utt_ids[me]

    # A 的详情接口里找不到 B 的任何 id
    blob = json.dumps(detail_a, ensure_ascii=False)
    assert b not in blob
    assert not any(pid in blob for pid in people[b])


async def test_sse_stream_of_a_only_yields_a_public_events(make_app):
    app, _ = make_app()
    frames: list[dict] = []
    async with api(app) as client:
        a, b = await _start_two(app, client)
        sse = load("app.sse")
        with anyio.fail_after(20):
            async for frame in sse.public_event_stream(app, a, after=0):
                frames.append(frame)  # {"id": int, "event": str, "data": dict}
        await app.state.runner.wait(b)

    assert frames, "应当收到 A 的事件"
    assert all(f["data"]["discussion_id"] == a for f in frames)
    assert {f["event"] for f in frames} <= PUBLIC_SSE_EVENTS
    blob = json.dumps(frames, ensure_ascii=False)
    for word in ("expert.intent", "urgency", "raise_hand", "floor.granted", b):
        assert word not in blob
    ids = [f["id"] for f in frames]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    assert frames[-1]["event"] == "status" and frames[-1]["data"]["to"] == "done"
