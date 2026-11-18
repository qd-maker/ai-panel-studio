"""HTTP 接口，契约见 docs/API.md。"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, Request, Response
from sse_starlette.sse import EventSourceResponse

from app import repo, schemas
from app.sse import public_event_stream
from app.errors import NOT_FOUND, ApiError
from app.lineup import generate_lineup
from app.llm import LLMBadOutput, llm_configured
from app.llm_base import LLMError

router = APIRouter(prefix="/api")

LISTABLE = ["lineup_ready", "running", "summarizing", "done", "failed", "aborted"]


def _lock(request: Request, did: str) -> asyncio.Lock:
    return request.app.state.locks.setdefault(did, asyncio.Lock())


def _detail(request: Request, did: str) -> schemas.DiscussionDetail:
    with request.app.state.engine.connect() as conn:
        d = repo.detail(conn, did)
    if not d:
        raise NOT_FOUND()
    return d


async def _generate_into(request: Request, did: str, topic: str, expert_count: int, keep_status: bool) -> None:
    """生成阵容写入讨论。失败时讨论保持原状态和原阵容，抛 502。"""
    app = request.app
    log: list[dict] = []
    try:
        lineup = await generate_lineup(app.state.llm, app.state.settings, topic, expert_count, log=log)
    except (LLMBadOutput, LLMError) as e:
        with app.state.engine.begin() as conn:
            for entry in log:
                repo.internal(conn, did, "llm.call", entry)
        if isinstance(e, LLMBadOutput):
            raise ApiError(502, "LLM_BAD_OUTPUT", "嘉宾阵容生成结果不合格，请重试", {"discussion_id": did}) from e
        raise ApiError(502, "LLM_UNAVAILABLE", "模型服务暂时不可用，请稍后重试", {"discussion_id": did}) from e

    with app.state.engine.begin() as conn:
        for entry in log:
            repo.internal(conn, did, "llm.call", entry)
        repo.replace_lineup(conn, did, lineup.host.model_dump(), [g.model_dump() for g in lineup.experts])
        event = None if keep_status else repo.transition(conn, did, {"draft"}, "lineup_ready")
    app.state.bus.publish([event])


@router.post("/discussions", status_code=201, response_model=schemas.DiscussionDetail)
async def create_discussion(body: schemas.CreateDiscussionRequest, request: Request):
    app = request.app
    with app.state.engine.begin() as conn:
        did = repo.create_discussion(conn, body.topic, body.expert_count, app.state.settings.max_expert_turns)
    async with _lock(request, did):
        await _generate_into(request, did, body.topic, body.expert_count, keep_status=False)
    return _detail(request, did)


@router.post("/discussions/{did}/lineup/regenerate", response_model=schemas.DiscussionDetail)
async def regenerate_lineup(did: str, request: Request, body: schemas.RegenerateLineupRequest | None = None):
    with request.app.state.engine.connect() as conn:
        d = repo.get_discussion(conn, did)
    if not d:
        raise NOT_FOUND()
    lock = _lock(request, did)
    if lock.locked():
        raise ApiError(409, "LINEUP_GENERATING", "阵容正在生成，请稍候")
    if d["status"] not in ("draft", "lineup_ready"):
        raise ApiError(409, "INVALID_STATE_TRANSITION", "讨论已经开始，不能重新生成阵容")
    count = (body.expert_count if body and body.expert_count else None) or d["expert_count"]
    async with lock:
        await _generate_into(request, did, d["topic"], count, keep_status=d["status"] == "lineup_ready")
    return _detail(request, did)


@router.post("/discussions/{did}/start", status_code=202, response_model=schemas.StartResponse)
async def start_discussion(did: str, request: Request):
    return await request.app.state.runner.start(did)


@router.post("/discussions/{did}/abort", response_model=schemas.AbortResponse)
async def abort_discussion(did: str, request: Request):
    return await request.app.state.runner.abort(did)


@router.get("/discussions", response_model=schemas.DiscussionListResponse)
async def list_discussions(request: Request, status: str | None = None, limit: int = Query(50, ge=1, le=100)):
    statuses = LISTABLE if not status else [s.strip() for s in status.split(",") if s.strip()]
    if not statuses or any(s not in LISTABLE for s in statuses):
        raise ApiError(422, "VALIDATION_ERROR", "status 参数不合法", {"fields": [{"field": "status", "message": f"可选值：{','.join(LISTABLE)}"}]})
    with request.app.state.engine.connect() as conn:
        return {"items": repo.summaries(conn, statuses, limit)}


@router.get("/discussions/{did}", response_model=schemas.DiscussionDetail)
async def get_discussion(did: str, request: Request):
    return _detail(request, did)


@router.get("/discussions/{did}/stream")
async def stream(did: str, request: Request, after: int | None = Query(None, ge=0)):
    """SSE。起点优先级：请求头 Last-Event-ID > 查询参数 after > 只推新事件。"""
    with request.app.state.engine.connect() as conn:
        if not repo.get_discussion(conn, did):
            raise NOT_FOUND()
        tail = repo.last_public_event_id(conn, did)
    header = request.headers.get("last-event-id", "")
    # Last-Event-ID 由浏览器自动发送，格式不对时忽略（报错会让 EventSource 反复重连失败）
    start = int(header) if header.isdigit() else after if after is not None else tail

    async def frames():
        async for f in public_event_stream(request.app, did, start):
            yield {"id": str(f["id"]), "event": f["event"], "data": json.dumps(f["data"], ensure_ascii=False)}

    return EventSourceResponse(frames(), ping=15, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}, send_timeout=30)


@router.get("/health", response_model=schemas.HealthResponse)
async def health(request: Request, response: Response):
    return {"status": "ok", "llm_configured": llm_configured(request.app.state.settings)}
