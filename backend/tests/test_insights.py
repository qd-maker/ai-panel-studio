"""共识与分歧：边讨论边增量提炼，坏输出不清空已有结果。"""

import json

import pytest
from sqlalchemy import text

from app.fake_llm import FakeLLM
from db.seed import seed
from tests.conftest import api, events_of, load, rows, run_to_end, utterances_of

pytestmark = pytest.mark.anyio


# ---------------- 编排器：每条发言后都提炼 ----------------


async def test_insights_are_extracted_after_every_utterance_not_at_the_end(make_app, engine):
    app, fake = make_app()
    async with api(app) as client:
        did = await run_to_end(app, client)

    utts = utterances_of(engine, did)
    spoken_while_running = [u for u in utts if u["act"] != "closing"]
    assert fake.calls_for("insights") == len(spoken_while_running)

    events = events_of(engine, did)
    first_insight = next(e["id"] for e in events if e["type"] == "insight.upserted")
    summarizing = next(e["id"] for e in events if e["type"] == "discussion.status_changed" and e["payload"]["to"] == "summarizing")
    assert first_insight < summarizing


async def test_bad_extraction_output_keeps_previous_insights(make_app, engine):
    # 第一次提炼给出一条有效条目，之后每次都返回坏 JSON
    fake = FakeLLM(script={"insights": [lambda h, n: json.dumps({"ops": [{
        "op": "create", "kind": "consensus", "content": "数据口径需要统一",
        "supporter_ids": h["expert_ids"][:2], "opponent_ids": [], "evidence_utterance_ids": [h["utterance_ids"][-1]],
    }]}, ensure_ascii=False)] + ["{坏的 JSON"] * 50})
    app, _ = make_app(fake)
    async with api(app) as client:
        did = await run_to_end(app, client)

    ins = rows(engine, "SELECT content, version FROM insight WHERE discussion_id = :d", d=did)
    assert ins == [{"content": "数据口径需要统一", "version": 1}]
    assert rows(engine, "SELECT status FROM discussion WHERE id = :d", d=did) == [{"status": "done"}]


# ---------------- 纯逻辑：apply_extraction 的增量语义 ----------------


@pytest.fixture
def seeded(engine):
    """借用 seed 里已结束的科技场：清掉它的条目，留下嘉宾和发言做素材。"""
    seed(engine)
    did = rows(engine, "SELECT id FROM discussion WHERE topic LIKE '%程序员%'")[0]["id"]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM insight WHERE discussion_id = :d"), {"d": did})
    experts = [r["id"] for r in rows(engine, "SELECT id FROM participant WHERE discussion_id = :d AND role = 'expert' ORDER BY seat_no", d=did)]
    utt_ids = [r["id"] for r in rows(engine, "SELECT id FROM utterance WHERE discussion_id = :d ORDER BY seq", d=did)]
    return did, experts, utt_ids


def apply(engine, did, ops):
    ins = load("app.insights")
    raw = ops if isinstance(ops, str) else json.dumps({"ops": ops}, ensure_ascii=False)
    with engine.begin() as conn:
        return ins.apply_extraction(conn, did, raw)


def insights_of(engine, did):
    out = rows(engine, "SELECT * FROM insight WHERE discussion_id = :d ORDER BY created_at, id", d=did)
    for i in out:
        for k in ("supporter_ids", "opponent_ids", "evidence_utterance_ids"):
            i[k] = json.loads(i[k])
    return out


async def test_insight_is_created_then_merged_then_changes_status(engine, seeded):
    did, e, u = seeded
    apply(engine, did, [{"op": "create", "kind": "consensus", "content": "审代码能力更重要",
                         "supporter_ids": [e[0]], "opponent_ids": [], "evidence_utterance_ids": [u[3]]}])
    [created] = insights_of(engine, did)
    assert created["version"] == 1 and created["status"] == "emerging"

    # 合并：同一条目追加认同者和证据，不新建条目
    apply(engine, did, [{"op": "update", "id": created["id"], "add_supporter_ids": [e[1]], "evidence_utterance_ids": [u[5]]}])
    [merged] = insights_of(engine, did)
    assert merged["id"] == created["id"]
    assert merged["version"] == 2
    assert merged["supporter_ids"] == [e[0], e[1]]
    assert merged["evidence_utterance_ids"] == [u[3], u[5]]

    # 状态变化
    apply(engine, did, [{"op": "set_status", "id": created["id"], "status": "confirmed"}])
    [confirmed] = insights_of(engine, did)
    assert confirmed["status"] == "confirmed" and confirmed["version"] == 3


async def test_invalid_extraction_json_leaves_existing_insights_untouched(engine, seeded):
    did, e, u = seeded
    apply(engine, did, [{"op": "create", "kind": "consensus", "content": "审代码能力更重要",
                         "supporter_ids": [e[0]], "opponent_ids": [], "evidence_utterance_ids": [u[3]]}])
    before = insights_of(engine, did)

    changes = apply(engine, did, "{这不是合法 JSON")

    assert changes == []
    assert insights_of(engine, did) == before


async def test_insight_citing_an_unknown_utterance_is_dropped(engine, seeded):
    did, e, u = seeded
    apply(engine, did, [
        {"op": "create", "kind": "consensus", "content": "引用了不存在的发言",
         "supporter_ids": [e[0]], "opponent_ids": [], "evidence_utterance_ids": [999999]},
        {"op": "create", "kind": "consensus", "content": "正常条目",
         "supporter_ids": [e[0]], "opponent_ids": [], "evidence_utterance_ids": [u[2]]},
    ])
    assert [i["content"] for i in insights_of(engine, did)] == ["正常条目"]
