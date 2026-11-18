"""发言调度。

前半部分直接测纯函数 pick_speaker（输入意图和历史，输出下一位发言人）；
后半部分用 FakeLLM 跑完整讨论，检查编排器的行为。
"""

import json
import re
from itertools import groupby

import pytest
from pydantic import ValidationError

from app.fake_llm import FakeLLM
from tests.conftest import api, events_of, load, run_to_end, utterances_of

pytestmark = pytest.mark.anyio


def intent(pid: str, urgency: int, kind: str = "raise_hand", wants: bool = True):
    return load("app.scheduler").ExpertIntent(participant_id=pid, wants_to_speak=wants, kind=kind, urgency=urgency)


# ---------------- 纯函数：pick_speaker ----------------


async def test_scheduler_picks_the_most_urgent_expert():
    s = load("app.scheduler")
    picked = s.pick_speaker([intent("e1", 2), intent("e2", 5), intent("e3", 3)], history=[])
    assert picked == "e2"


async def test_scheduler_breaks_ties_by_longest_silence():
    s = load("app.scheduler")
    # e1 上次发言比 e2 更早，同分时 e1 优先
    assert s.pick_speaker([intent("e1", 4), intent("e2", 4)], history=["e3", "e1", "e2"]) == "e1"
    # 从没发过言的人沉默最久
    assert s.pick_speaker([intent("e1", 4), intent("e4", 4)], history=["e1"]) == "e4"


async def test_scheduler_ignores_experts_who_do_not_want_to_speak():
    s = load("app.scheduler")
    picked = s.pick_speaker([intent("e1", 5, wants=False), intent("e2", 1)], history=[])
    assert picked == "e2"


async def test_expert_cannot_speak_more_than_twice_in_a_row():
    s = load("app.scheduler")
    # 已连续说了 2 次，紧迫度再高也轮不到
    assert s.pick_speaker([intent("e1", 5), intent("e2", 1)], history=["e1", "e1"], max_consecutive=2) == "e2"
    # 只连续说了 1 次，还可以再说
    assert s.pick_speaker([intent("e1", 5), intent("e2", 1)], history=["e2", "e1"], max_consecutive=2) == "e1"
    # 唯一想发言的人被限制时，返回 None，交给主持人
    assert s.pick_speaker([intent("e1", 5)], history=["e1", "e1"], max_consecutive=2) is None


@pytest.mark.parametrize("kind", ["raise_hand", "interrupt", "supplement", "rebut"])
async def test_intent_accepts_the_four_kinds(kind):
    assert intent("e1", 3, kind=kind).kind == kind


@pytest.mark.parametrize(("kind", "urgency"), [("shout", 3), ("rebut", 0), ("rebut", 6)])
async def test_intent_rejects_unknown_kind_or_out_of_range_urgency(kind, urgency):
    with pytest.raises(ValidationError):
        intent("e1", urgency, kind=kind)


# ---------------- 编排器：完整跑一场 ----------------


async def test_host_speaks_first_with_an_opening(make_app, engine):
    app, _ = make_app()
    async with api(app) as client:
        did = await run_to_end(app, client)

    first = utterances_of(engine, did)[0]
    assert first["role"] == "host"
    assert first["act"] == "opening"


async def test_host_interjects_after_every_n_expert_turns(make_app, engine):
    app, _ = make_app(max_expert_turns=7, host_every_n=3)
    async with api(app) as client:
        did = await run_to_end(app, client)

    utts = utterances_of(engine, did)
    # 去掉开场和收尾，剩下的序列里专家连续发言段长度都不超过 N，段与段之间是主持人的追问或串联
    middle = utts[1:-1]
    runs, current = [], 0
    for u in middle:
        if u["role"] == "expert":
            current += 1
        else:
            assert u["act"] in ("question", "bridge")
            runs.append(current)
            current = 0
    runs.append(current)
    assert all(r <= 3 for r in runs), runs
    assert runs[0] == 3, "专家说满 3 条后，主持人应当插话"
    assert sum(runs) == 7


async def test_one_expert_never_speaks_more_than_twice_in_a_row_in_a_real_run(make_app, engine):
    # 每轮都让第一位专家紧迫度最高，逼调度器做限制
    def always_first(hints, n):
        ids = hints["expert_ids"]
        return json.dumps({"intents": [
            {"participant_id": pid, "wants_to_speak": True, "kind": "rebut", "urgency": 5 if i == 0 else 1,
             "target_participant_id": None, "focus": "数据口径", "public_thought": "样本只覆盖了大公司"}
            for i, pid in enumerate(ids)
        ]})

    app, _ = make_app(FakeLLM(script={"intents": [always_first] * 50}), max_expert_turns=8, host_every_n=10)
    async with api(app) as client:
        did = await run_to_end(app, client)

    experts_in_order = [u["participant_id"] for u in utterances_of(engine, did) if u["role"] == "expert"]
    longest_run = max(len(list(group)) for _, group in groupby(experts_in_order))
    assert longest_run <= 2, experts_in_order


async def test_long_utterance_is_clamped_to_two_sentences(make_app, engine):
    four = "第一句。第二句！第三句？第四句。"
    app, _ = make_app(FakeLLM(script={"utterance": [four] * 50, "host": [four] * 50}))
    async with api(app) as client:
        did = await run_to_end(app, client)

    for u in utterances_of(engine, did):
        assert len(re.findall(r"[。！？!?]", u["content"])) <= 2, u["content"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("第一句。第二句！第三句？", "第一句。第二句！"),
        ("只有一句", "只有一句"),
        ("Really? Yes! No.", "Really? Yes!"),
        ("  前后有空白。第二句。第三句。  ", "前后有空白。第二句。"),
    ],
)
async def test_clamp_sentences_keeps_at_most_two(raw, expected):
    assert load("app.textutil").clamp_sentences(raw, max_sentences=2) == expected


async def test_speaking_intents_are_written_only_as_internal_events(make_app, engine):
    app, _ = make_app()
    async with api(app) as client:
        did = await run_to_end(app, client)

    events = events_of(engine, did)
    intent_events = [e for e in events if e["type"] == "expert.intent"]
    expert_turns = sum(1 for u in utterances_of(engine, did) if u["role"] == "expert")
    assert len(intent_events) >= expert_turns
    assert all(e["visibility"] == "internal" for e in intent_events)

    # public 事件里看不到意图字段
    public_text = json.dumps([e["payload"] for e in events if e["visibility"] == "public"], ensure_ascii=False)
    for word in ("urgency", "raise_hand", "interrupt", "wants_to_speak"):
        assert word not in public_text

    # 发言表里只有发言正文，没有意图
    for u in utterances_of(engine, did):
        assert "urgency" not in u["content"] and "raise_hand" not in u["content"]
