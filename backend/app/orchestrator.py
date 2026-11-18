"""讨论编排。

Runner 管理后台任务：每场讨论一个独立的 asyncio.Task，按 discussion_id 登记。
讨论内的所有上下文（发言历史、调度状态）都放在该任务自己的 Discussion 对象里，不用全局变量。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI

from app import repo
from app.errors import NOT_FOUND, ApiError

log = logging.getLogger(__name__)


class Runner:
    def __init__(self, app: FastAPI):
        self.app = app
        self.tasks: dict[str, asyncio.Task] = {}

    # ---------------- 查询 ----------------

    def active_ids(self) -> list[str]:
        return [did for did, t in self.tasks.items() if not t.done()]

    async def wait(self, did: str) -> None:
        task = self.tasks.get(did)
        if task:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # ---------------- 生命周期 ----------------

    async def start(self, did: str) -> dict:
        app = self.app
        if app.state.locks.get(did) and app.state.locks[did].locked():
            raise ApiError(409, "LINEUP_GENERATING", "阵容正在生成，请稍候")
        with app.state.engine.begin() as conn:
            d = repo.get_discussion(conn, did)
            if not d:
                raise NOT_FOUND()
            cap = app.state.settings.max_starts_per_day
            if d["status"] == "lineup_ready" and cap and repo.count_today(conn, "started_at") >= cap:
                raise ApiError(429, "DAILY_LIMIT_REACHED", f"今天已进行 {cap} 场讨论，达到演示站的每日上限，请明天再来")
            if d["status"] == "lineup_ready" and repo.count_live(conn) >= app.state.settings.max_running:
                raise ApiError(429, "TOO_MANY_RUNNING", f"同时进行的讨论已达 {app.state.settings.max_running} 场，请稍后再试")
            # 条件更新：并发的两次 start 只有一次能把 lineup_ready 改成 running
            event = repo.transition(conn, did, {"lineup_ready"}, "running")
            if not event:
                raise ApiError(409, "INVALID_STATE_TRANSITION", _why_not_start(d["status"]))
            started_at = event["payload"]["at"]
        app.state.bus.publish([event])
        self.tasks[did] = asyncio.create_task(self._run(did), name=f"discussion-{did}")
        return {"id": did, "status": "running", "started_at": started_at}

    async def abort(self, did: str) -> dict:
        with self.app.state.engine.begin() as conn:
            d = repo.get_discussion(conn, did)
            if not d:
                raise NOT_FOUND()
            event = repo.transition(conn, did, repo.LIVE, "aborted", reason="用户结束讨论")
            if not event:
                raise ApiError(409, "INVALID_STATE_TRANSITION", "讨论不在进行中")
        self.app.state.bus.publish([event])
        await self.cancel(did)
        return {"id": did, "status": "aborted", "ended_at": event["payload"]["at"]}

    async def cancel(self, did: str) -> None:
        task = self.tasks.get(did)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def recover_after_restart(self) -> None:
        """进程重启后，内存里的任务都没了：把还标着进行中的讨论改成 aborted。"""
        with self.app.state.engine.begin() as conn:
            live = conn.exec_driver_sql("SELECT id FROM discussion WHERE status IN ('running', 'summarizing')").scalars().all()
            events = [repo.transition(conn, did, repo.LIVE, "aborted", reason="服务重启") for did in live]
        self.app.state.bus.publish(events)

    async def shutdown(self) -> None:
        for did in self.active_ids():
            await self.cancel(did)

    async def _run(self, did: str) -> None:
        from app.discussion import Discussion

        try:
            await Discussion(self.app, did).run()
        except asyncio.CancelledError:
            raise
        except Exception:  # 兜底：任何未预期的错误都让讨论进入 failed，而不是悬在 running
            log.exception("discussion %s crashed", did)
            with self.app.state.engine.begin() as conn:
                events = [
                    repo.discussion_error(conn, did, "INTERNAL_ERROR", "讨论意外中断"),
                    repo.transition(conn, did, repo.LIVE, "failed", reason="内部错误"),
                ]
            self.app.state.bus.publish(events)


def _why_not_start(status: str) -> str:
    return {
        "draft": "阵容还没有生成，不能开始",
        "running": "讨论已经在进行中",
        "summarizing": "讨论正在总结",
    }.get(status, "讨论已经结束，不能再次开始")
