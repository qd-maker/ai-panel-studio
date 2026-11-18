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


@pytest.mark.parametrize("color", ["red", "#FFF", "#GGGGGG", "E4572E", "#E4572E0"])
def test_participant_rejects_invalid_color(color):
    with pytest.raises(ValidationError):
        schemas.Participant(
            id="p1", role="expert", seat_no=1, name="甲", profession="乙", title="丙",
            stance="丁", persona="戊", color=color,
        )
