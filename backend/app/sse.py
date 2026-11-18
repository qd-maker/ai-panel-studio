"""SSE 事件流：只下发本场讨论的 public 事件，支持断点续传。

先订阅实时通道，再从数据库补发 id > after 的事件，最后接实时事件，按 id 去重。
这样补发和订阅之间产生的事件不会丢，也不会重复。收到终态（done / failed / aborted）后结束。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI

from app import repo

# 事件类型 → SSE event 名（docs/API.md「事件列表」）
EVENT_NAMES = {
    "discussion.status_changed": "status",
    "utterance.created": "utterance",
    "agent_state.updated": "agent_state",
    "insight.upserted": "insight",
    "summary.ready": "summary",
    "discussion.error": "discussion_error",
}


def _frame(row: dict) -> dict:
    return {"id": row["id"], "event": EVENT_NAMES[row["type"]], "data": row["payload"]}


def _is_terminal(row: dict) -> bool:
    return row["type"] == "discussion.status_changed" and row["payload"]["to"] in repo.TERMINAL


async def public_event_stream(app: FastAPI, discussion_id: str, after: int = 0) -> AsyncIterator[dict]:
    bus = app.state.bus
    queue = bus.subscribe(discussion_id)
    try:
        last = after
        with app.state.engine.connect() as conn:
            backlog = repo.public_events_after(conn, discussion_id, after)
            status = (repo.get_discussion(conn, discussion_id) or {}).get("status")
        for row in backlog:
            if row["type"] not in EVENT_NAMES:
                continue
            yield _frame(row)
            last = row["id"]
            if _is_terminal(row):
                return
        if status in repo.TERMINAL:
            return  # 终态之后的重连：补发完立即结束
        while True:
            row = await queue.get()
            if row["id"] <= last or row["type"] not in EVENT_NAMES:
                continue
            yield _frame(row)
            last = row["id"]
            if _is_terminal(row):
                return
    finally:
        bus.unsubscribe(discussion_id, queue)
