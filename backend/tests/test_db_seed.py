"""数据层冒烟测试：建表 → 导入样例 → 检查数据。"""

import re

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app import schemas
from db.seed import seed


def test_seed_creates_five_discussions_each_with_one_host_and_experts(engine):
    seed(engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT d.id, d.topic, "
                "  SUM(p.role = 'host')   AS hosts, "
                "  SUM(p.role = 'expert') AS experts "
                "FROM discussion d JOIN participant p ON p.discussion_id = d.id "
                "GROUP BY d.id"
            )
        ).all()

    assert len(rows) == 5
    for row in rows:
        assert row.hosts == 1, row.topic
        assert row.experts >= 2, row.topic


def test_seed_is_idempotent(engine):
    first = seed(engine)
    second = seed(engine)

    assert first == second
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM discussion")).scalar_one() == 5


def test_done_seeds_have_transcript_insights_and_summary(engine):
    seed(engine)

    with engine.connect() as conn:
        done = conn.execute(text("SELECT id, summary FROM discussion WHERE status = 'done'")).all()
        assert len(done) == 2
        for d in done:
            assert d.summary and not d.summary.lstrip().startswith(("{", "["))
            n_utt = conn.execute(
                text("SELECT COUNT(*) FROM utterance WHERE discussion_id = :d"), {"d": d.id}
            ).scalar_one()
            n_ins = conn.execute(
                text("SELECT COUNT(*) FROM insight WHERE discussion_id = :d"), {"d": d.id}
            ).scalar_one()
            assert n_utt >= 10 and n_ins >= 3

        # 每条发言最多 2 句（P-03）
        for (content,) in conn.execute(text("SELECT content FROM utterance")):
            assert len(re.findall(r"[。！？!?]", content)) <= 2, content

        # 样例只写 public 事件，且每条发言都有对应事件
        assert conn.execute(text("SELECT COUNT(*) FROM event WHERE visibility <> 'public'")).scalar_one() == 0
        assert conn.execute(
            text("SELECT COUNT(*) FROM event WHERE type = 'utterance.created'")
        ).scalar_one() == conn.execute(text("SELECT COUNT(*) FROM utterance")).scalar_one()


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "太短了"},  # 去空白后 3 字
        {"topic": "   四个字   "},
        {"topic": "字" * 201},
        {"topic": "一个合法的话题", "expert_count": 1},
        {"topic": "一个合法的话题", "expert_count": 7},
        {"topic": "一个合法的话题", "unknown": 1},
    ],
)
def test_create_request_rejects_invalid_input(payload):
    with pytest.raises(ValidationError):
        schemas.CreateDiscussionRequest(**payload)


def test_create_request_defaults_and_strips():
    req = schemas.CreateDiscussionRequest(topic="  AI 会取代程序员吗  ")
    assert req.topic == "AI 会取代程序员吗"
    assert req.expert_count == 4


@pytest.mark.parametrize(
    "text_",
    ["想补充一下许安的说法", "准备反驳陈拓", "想接着「补充」说两句", "我要举手", "抢答：其实不对", "评估要不要接话"],
)
def test_agent_state_rejects_speaking_intent(text_):
    """专家小窗只公开观点本身，发言意图属于 internal（违规修复：公开思考摘要不含发言意图）。"""
    with pytest.raises(ValidationError):
        schemas.AgentState(
            participant_id="p1", status="preparing", public_thought=text_, version=1,
            updated_at="2026-11-18T00:00:00Z",
        )
    with pytest.raises(ValidationError):
        schemas.AgentState(
            participant_id="p1", status="preparing", focus=text_[:20], version=1,
            updated_at="2026-11-18T00:00:00Z",
        )


def test_agent_state_accepts_plain_viewpoint():
    s = schemas.AgentState(
        participant_id="p1", status="speaking", focus="中小企业的招聘数据",
        public_thought="大厂的数据不能代表整个行业，中小公司的初级岗位在增加", version=1,
        updated_at="2026-11-18T00:00:00Z",
    )
    assert s.public_thought.startswith("大厂")


def test_seed_agent_states_contain_only_viewpoints(engine):
    seed(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT focus, public_thought FROM agent_state WHERE public_thought IS NOT NULL")
        ).all()
    assert len(rows) == 8  # 两场已结束讨论 × 4 位专家
    for focus, thought in rows:
        assert not schemas.SPEAKING_INTENT.search(focus + thought), (focus, thought)


@pytest.mark.parametrize("color",["red", "#FFF", "#GGGGGG", "E4572E", "#E4572E0"])
def test_participant_rejects_invalid_color(color):
    with pytest.raises(ValidationError):
        schemas.Participant(
            id="p1", role="expert", seat_no=1, name="甲", profession="乙", title="丙",
            stance="丁", persona="戊", color=color,
        )
