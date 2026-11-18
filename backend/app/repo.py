"""数据库读写。所有函数都接收一个已开启事务的连接，按 discussion_id 操作，不持有任何全局状态。

写入公共事件的函数会把事件行返回给调用方，调用方在事务提交后再推给 SSE 订阅者。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, text

from app import schemas
from app.palette import EXPERT_COLORS, HOST_COLOR

TERMINAL = {"done", "failed", "aborted"}
LIVE = {"running", "summarizing"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_id() -> str:
    return uuid.uuid4().hex


def _all(conn: Connection, sql: str, **p) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), p)]


def _one(conn: Connection, sql: str, **p) -> dict | None:
    r = conn.execute(text(sql), p).first()
    return dict(r._mapping) if r else None


# ---------------- 事件 ----------------


def append_event(conn: Connection, did: str, visibility: str, type_: str, payload: dict[str, Any]) -> dict:
    created = now()
    eid = conn.execute(
        text("INSERT INTO event (discussion_id, visibility, type, payload, created_at) VALUES (:d, :v, :t, :p, :c)"),
        {"d": did, "v": visibility, "t": type_, "p": json.dumps(payload, ensure_ascii=False), "c": created},
    ).lastrowid
    return {"id": eid, "discussion_id": did, "visibility": visibility, "type": type_, "payload": payload, "created_at": created}


def internal(conn: Connection, did: str, type_: str, payload: dict[str, Any]) -> dict:
    return append_event(conn, did, "internal", type_, {"discussion_id": did, **payload})


def public_events_after(conn: Connection, did: str, after: int) -> list[dict]:
    rows = _all(
        conn,
        "SELECT * FROM event WHERE discussion_id = :d AND visibility = 'public' AND id > :a ORDER BY id",
        d=did, a=after,
    )
    for r in rows:
        r["payload"] = json.loads(r["payload"])
    return rows


def last_public_event_id(conn: Connection, did: str) -> int:
    r = _one(conn, "SELECT COALESCE(MAX(id), 0) AS m FROM event WHERE discussion_id = :d AND visibility = 'public'", d=did)
    return int(r["m"]) if r else 0


# ---------------- 讨论与状态 ----------------


def create_discussion(conn: Connection, topic: str, expert_count: int, max_expert_turns: int) -> str:
    did, ts = new_id(), now()
    conn.execute(
        text(
            "INSERT INTO discussion (id, topic, expert_count, status, max_expert_turns, created_at, updated_at) "
            "VALUES (:id, :topic, :n, 'draft', :m, :ts, :ts)"
        ),
        {"id": did, "topic": topic, "n": expert_count, "m": max_expert_turns, "ts": ts},
    )
    return did


def get_discussion(conn: Connection, did: str) -> dict | None:
    return _one(conn, "SELECT * FROM discussion WHERE id = :d", d=did)


def count_today(conn: Connection, column: str) -> int:
    """今天（UTC 日期）created_at 或 started_at 落在当天的讨论数，用于每日用量封顶。"""
    assert column in ("created_at", "started_at")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return int(_one(conn, f"SELECT COUNT(*) AS n FROM discussion WHERE {column} LIKE :d AND is_seed = 0", d=f"{today}%")["n"])


def count_live(conn: Connection) -> int:
    return int(_one(conn, "SELECT COUNT(*) AS n FROM discussion WHERE status IN ('running', 'summarizing')")["n"])


def transition(conn: Connection, did: str, allowed_from: set[str], to: str, reason: str | None = None) -> dict | None:
    """条件更新（compare-and-set）：只有当前状态在 allowed_from 里才更新。

    并发请求里只有一个能成功，其余拿到 None，由调用方返回 409。成功时写一条 public 状态事件。
    """
    cur = get_discussion(conn, did)
    if not cur or cur["status"] not in allowed_from:
        return None
    ts = now()
    sets = ["status = :to", "updated_at = :ts", "status_reason = :reason"]
    if to == "running":
        sets.append("started_at = :ts")
    if to in TERMINAL:
        sets.append("ended_at = :ts")
    placeholders = ", ".join(f":f{i}" for i in range(len(allowed_from)))
    params = {"to": to, "ts": ts, "reason": reason, "d": did, **{f"f{i}": s for i, s in enumerate(sorted(allowed_from))}}
    changed = conn.execute(
        text(f"UPDATE discussion SET {', '.join(sets)} WHERE id = :d AND status IN ({placeholders})"), params
    ).rowcount
    if not changed:
        return None
    data = schemas.StatusEventData(discussion_id=did, from_=cur["status"], to=to, reason=reason, at=ts)
    return append_event(conn, did, "public", "discussion.status_changed", data.model_dump(mode="json", by_alias=True))


def set_expert_turns(conn: Connection, did: str, n: int) -> None:
    conn.execute(text("UPDATE discussion SET expert_turns = :n, updated_at = :ts WHERE id = :d"), {"n": n, "ts": now(), "d": did})


def set_summary(conn: Connection, did: str, summary: str, source: str) -> dict:
    ts = now()
    conn.execute(
        text("UPDATE discussion SET summary = :s, summary_source = :src, updated_at = :ts WHERE id = :d"),
        {"s": summary, "src": source, "ts": ts, "d": did},
    )
    data = schemas.SummaryEventData(discussion_id=did, summary=summary, summary_source=source, at=ts)
    return append_event(conn, did, "public", "summary.ready", data.model_dump(mode="json"))


def discussion_error(conn: Connection, did: str, code: str, message: str) -> dict:
    data = schemas.DiscussionErrorEventData(discussion_id=did, code=code, message=message)
    return append_event(conn, did, "public", "discussion.error", data.model_dump(mode="json"))


# ---------------- 嘉宾 ----------------


def replace_lineup(conn: Connection, did: str, host: dict, experts: list[dict]) -> None:
    """替换整套阵容。颜色由系统按座位分配，同一场讨论内不重复。"""
    conn.execute(text("DELETE FROM participant WHERE discussion_id = :d"), {"d": did})
    ts = now()
    seats = [("host", 0, host, HOST_COLOR)] + [("expert", i, g, EXPERT_COLORS[(i - 1) % len(EXPERT_COLORS)]) for i, g in enumerate(experts, start=1)]
    for role, seat, g, color in seats:
        pid = new_id()
        conn.execute(
            text(
                "INSERT INTO participant (id, discussion_id, role, seat_no, name, profession, title, stance, persona, color, created_at) "
                "VALUES (:id, :d, :role, :seat, :name, :profession, :title, :stance, :persona, :color, :ts)"
            ),
            {"id": pid, "d": did, "role": role, "seat": seat, "color": color, "ts": ts, **g},
        )
        conn.execute(
            text("INSERT INTO agent_state (participant_id, discussion_id, status, version, updated_at) VALUES (:p, :d, 'idle', 1, :ts)"),
            {"p": pid, "d": did, "ts": ts},
        )
    conn.execute(text("UPDATE discussion SET expert_count = :n, updated_at = :ts WHERE id = :d"), {"n": len(experts), "ts": ts, "d": did})


def participants(conn: Connection, did: str) -> list[dict]:
    return _all(conn, "SELECT * FROM participant WHERE discussion_id = :d ORDER BY seat_no", d=did)


# ---------------- 发言 ----------------


def utterances(conn: Connection, did: str) -> list[dict]:
    return _all(conn, "SELECT * FROM utterance WHERE discussion_id = :d ORDER BY seq", d=did)


def insert_utterance(
    conn: Connection, did: str, participant_id: str, act: str, content: str,
    reply_to: int | None = None, addressed: str | None = None,
) -> tuple[dict, dict]:
    seq = int(_one(conn, "SELECT COALESCE(MAX(seq), 0) + 1 AS s FROM utterance WHERE discussion_id = :d", d=did)["s"])
    ts = now()
    uid = conn.execute(
        text(
            "INSERT INTO utterance (discussion_id, participant_id, seq, act, content, reply_to_utterance_id, addressed_participant_id, created_at) "
            "VALUES (:d, :p, :seq, :act, :content, :reply, :addr, :ts)"
        ),
        {"d": did, "p": participant_id, "seq": seq, "act": act, "content": content, "reply": reply_to, "addr": addressed, "ts": ts},
    ).lastrowid
    utt = schemas.Utterance(
        id=uid, seq=seq, participant_id=participant_id, act=act, content=content,
        reply_to_utterance_id=reply_to, addressed_participant_id=addressed, created_at=ts,
    )
    event = append_event(
        conn, did, "public", "utterance.created",
        schemas.UtteranceEventData(discussion_id=did, utterance=utt).model_dump(mode="json"),
    )
    return utt.model_dump(mode="json"), event


# ---------------- 嘉宾小窗 ----------------

_KEEP = object()


def set_agent_state(conn: Connection, did: str, pid: str, status: str, focus: Any = _KEEP, thought: Any = _KEEP) -> dict:
    """更新小窗并写 public 事件。focus / thought 不传则保持原值。

    内容先过 schemas.AgentState 校验（不含发言意图）；不合格的观点不写入，保留原值。
    """
    cur = _one(conn, "SELECT * FROM agent_state WHERE participant_id = :p", p=pid)
    new_focus = cur["focus"] if focus is _KEEP else focus
    new_thought = cur["public_thought"] if thought is _KEEP else thought
    ts = now()
    try:
        state = schemas.AgentState(
            participant_id=pid, status=status, focus=new_focus, public_thought=new_thought,
            version=cur["version"] + 1, updated_at=ts,
        )
    except ValueError:
        state = schemas.AgentState(
            participant_id=pid, status=status, focus=cur["focus"], public_thought=cur["public_thought"],
            version=cur["version"] + 1, updated_at=ts,
        )
    conn.execute(
        text("UPDATE agent_state SET status = :s, focus = :f, public_thought = :t, version = :v, updated_at = :ts WHERE participant_id = :p"),
        {"s": state.status, "f": state.focus, "t": state.public_thought, "v": state.version, "ts": ts, "p": pid},
    )
    return append_event(
        conn, did, "public", "agent_state.updated",
        schemas.AgentStateEventData(discussion_id=did, agent_state=state).model_dump(mode="json"),
    )


# ---------------- 读接口 ----------------


def _insight_row(r: dict) -> dict:
    for k in ("supporter_ids", "opponent_ids", "evidence_utterance_ids"):
        r[k] = json.loads(r[k])
    return r


def insights(conn: Connection, did: str) -> list[dict]:
    return [_insight_row(r) for r in _all(conn, "SELECT * FROM insight WHERE discussion_id = :d ORDER BY created_at, id", d=did)]


def detail(conn: Connection, did: str) -> schemas.DiscussionDetail | None:
    d = get_discussion(conn, did)
    if not d:
        return None
    return schemas.DiscussionDetail(
        **d,
        participants=participants(conn, did),
        utterances=utterances(conn, did),
        insights=insights(conn, did),
        agent_states=_all(conn, "SELECT * FROM agent_state WHERE discussion_id = :d", d=did),
        last_event_id=last_public_event_id(conn, did),
    )


def summaries(conn: Connection, statuses: list[str], limit: int) -> list[schemas.DiscussionSummary]:
    placeholders = ", ".join(f":s{i}" for i in range(len(statuses)))
    rows = _all(
        conn,
        f"SELECT * FROM discussion WHERE status IN ({placeholders}) ORDER BY created_at DESC LIMIT :limit",
        limit=limit, **{f"s{i}": s for i, s in enumerate(statuses)},
    )
    out = []
    for d in rows:
        stats = _one(
            conn,
            "SELECT COUNT(*) AS n, (SELECT content FROM utterance WHERE discussion_id = :d ORDER BY seq DESC LIMIT 1) AS latest "
            "FROM utterance WHERE discussion_id = :d",
            d=d["id"],
        )
        out.append(schemas.DiscussionSummary(
            **d,
            participants=[{k: p[k] for k in ("id", "role", "name", "color")} for p in participants(conn, d["id"])],
            utterance_count=stats["n"],
            latest_utterance=stats["latest"],
        ))
    return out
