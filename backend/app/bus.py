"""进程内事件总线：按 discussion_id 分频道，只转发 public 事件。

每个 SSE 连接订阅一个讨论，拿到自己的队列；发布时只投递给该讨论的订阅者，不同讨论互不可见。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, discussion_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[discussion_id].add(q)
        return q

    def unsubscribe(self, discussion_id: str, q: asyncio.Queue) -> None:
        self._subs[discussion_id].discard(q)
        if not self._subs[discussion_id]:
            self._subs.pop(discussion_id, None)

    def publish(self, events: list[dict | None]) -> None:
        """在数据库事务提交之后调用。internal 事件在这里被拦下。"""
        for e in events:
            if not e or e["visibility"] != "public":
                continue
            for q in list(self._subs.get(e["discussion_id"], ())):
                q.put_nowait(e)
