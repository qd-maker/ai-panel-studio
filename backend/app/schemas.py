"""API 请求、响应和 SSE 数据的 Pydantic 模型，对应 docs/API.md。

响应模型即白名单：接口只序列化这里声明的字段，
模型返回的额外字段（例如 reasoning_content）无法进入响应。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

# ---------- 枚举 ----------

DiscussionStatus = Literal[
    "draft", "lineup_ready", "running", "summarizing", "done", "failed", "aborted"
]
Role = Literal["host", "expert"]
UtteranceAct = Literal[
    "opening", "question", "bridge", "closing",  # 主持人
    "point", "supplement", "rebut", "answer",  # 专家
]
AgentStatus = Literal["idle", "preparing", "speaking"]
InsightKind = Literal["consensus", "divergence"]
InsightStatus = Literal["emerging", "confirmed", "resolved", "dropped"]
SummarySource = Literal["llm", "fallback"]
ErrorCode = Literal[
    "DISCUSSION_NOT_FOUND",
    "INVALID_STATE_TRANSITION",
    "LINEUP_GENERATING",
    "VALIDATION_ERROR",
    "TOO_MANY_RUNNING",
    "LLM_UNAVAILABLE",
    "LLM_BAD_OUTPUT",
    "INTERNAL_ERROR",
    "UNAUTHORIZED",
    "TOO_MANY_ATTEMPTS",
    "DAILY_LIMIT_REACHED",
]

# ---------- 可复用的字段约束 ----------

Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
ExpertCount = Annotated[int, Field(ge=2, le=6)]
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
Id = Annotated[str, StringConstraints(min_length=1)]

# 专家小窗只公开「观点本身」。发言意图（想补充、想反驳、举手、抢答⋯⋯）属于 internal 事件，
# 不能出现在 focus / public_thought 里。模型输出命中这些说法时校验失败，由调用方重试。
SPEAKING_INTENT = re.compile(
    r"(想|准备|打算|急着|等着).{0,6}?(补充|反驳|回应|接话|插话|发言|说两句|接着说|反问|追问)"
    r"|举手|抢答|抢话|插话|接话|拿到发言权|轮到我"
)


def _no_speaking_intent(v: str | None) -> str | None:
    if v is not None and SPEAKING_INTENT.search(v):
        raise ValueError("只能写观点本身，不能包含发言意图（如想补充、想反驳、举手）")
    return v


PublicViewText = Annotated[str | None, AfterValidator(_no_speaking_intent)]

MIN_EXPERTS, MAX_EXPERTS, DEFAULT_EXPERTS = 2, 6, 4
MAX_UTTERANCE_CHARS = 120
MAX_INSIGHT_CHARS = 80
MAX_FOCUS_CHARS = 20
MAX_PUBLIC_THOUGHT_CHARS = 60


class _Request(BaseModel):
    """请求体：拒绝未声明的字段。"""

    model_config = ConfigDict(extra="forbid")


class _Response(BaseModel):
    """响应体：可直接从数据库行（dict 或对象属性）构造。"""

    model_config = ConfigDict(from_attributes=True)


# ---------- 错误 ----------


class ErrorResponse(_Response):
    code: ErrorCode
    message: str
    details: dict | None = None


# ---------- 请求 ----------


class CreateDiscussionRequest(_Request):
    topic: Topic
    expert_count: ExpertCount = DEFAULT_EXPERTS


class RegenerateLineupRequest(_Request):
    expert_count: ExpertCount | None = None


# ---------- 实体 ----------


class Participant(_Response):
    id: Id
    role: Role
    seat_no: int = Field(ge=0)
    name: str = Field(min_length=1)
    profession: str = Field(min_length=1)
    title: str = Field(min_length=1)
    stance: str = Field(min_length=1, max_length=40)
    persona: str = Field(min_length=1, max_length=120)
    color: HexColor


class ParticipantBrief(_Response):
    """首页列表用的精简嘉宾信息。"""

    id: Id
    role: Role
    name: str
    color: HexColor


class Utterance(_Response):
    id: int
    seq: int = Field(ge=1)
    participant_id: Id
    act: UtteranceAct
    content: str = Field(min_length=1, max_length=MAX_UTTERANCE_CHARS)
    reply_to_utterance_id: int | None = None
    addressed_participant_id: Id | None = None
    created_at: datetime


class AgentState(_Response):
    participant_id: Id
    status: AgentStatus
    focus: PublicViewText = Field(default=None, max_length=MAX_FOCUS_CHARS)
    public_thought: PublicViewText = Field(default=None, max_length=MAX_PUBLIC_THOUGHT_CHARS)
    version: int = Field(ge=1)
    updated_at: datetime


class Insight(_Response):
    id: Id
    kind: InsightKind
    content: str = Field(min_length=1, max_length=MAX_INSIGHT_CHARS)
    supporter_ids: list[Id]
    opponent_ids: list[Id]
    status: InsightStatus
    evidence_utterance_ids: list[int] = Field(min_length=1)
    version: int = Field(ge=1)
    updated_at: datetime


# ---------- 讨论 ----------


class DiscussionSummary(_Response):
    """首页列表项。"""

    id: Id
    topic: str
    status: DiscussionStatus
    expert_count: int
    is_seed: bool
    participants: list[ParticipantBrief]
    utterance_count: int = Field(ge=0)
    latest_utterance: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None


class DiscussionListResponse(_Response):
    items: list[DiscussionSummary]


class DiscussionDetail(_Response):
    """讨论快照，用于进入演播厅和中途加入。"""

    id: Id
    topic: str
    status: DiscussionStatus
    status_reason: str | None = None
    expert_count: int
    max_expert_turns: int
    expert_turns: int
    is_seed: bool
    summary: str | None = None
    summary_source: SummarySource | None = None
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    participants: list[Participant]
    utterances: list[Utterance]
    insights: list[Insight]
    agent_states: list[AgentState]
    last_event_id: int = Field(ge=0)


class StartResponse(_Response):
    id: Id
    status: Literal["running"]
    started_at: datetime


class AbortResponse(_Response):
    id: Id
    status: Literal["aborted"]
    ended_at: datetime


class HealthResponse(_Response):
    status: Literal["ok"]
    llm_configured: bool


# ---------- SSE 事件数据 ----------
# 每条 data 都带 discussion_id，前端据此丢弃串台数据。

SseEventName = Literal["status", "utterance", "agent_state", "insight", "summary", "discussion_error"]


class StatusEventData(_Response):
    discussion_id: Id
    from_: DiscussionStatus | None = Field(alias="from", serialization_alias="from")
    to: DiscussionStatus
    reason: str | None = None
    at: datetime

    model_config = ConfigDict(from_attributes=True, validate_by_name=True, validate_by_alias=True)


class UtteranceEventData(_Response):
    discussion_id: Id
    utterance: Utterance


class AgentStateEventData(_Response):
    discussion_id: Id
    agent_state: AgentState


class InsightEventData(_Response):
    discussion_id: Id
    op: Literal["created", "updated"]
    insight: Insight


class SummaryEventData(_Response):
    discussion_id: Id
    summary: str = Field(min_length=1, max_length=600)
    summary_source: SummarySource
    at: datetime


class DiscussionErrorEventData(_Response):
    discussion_id: Id
    code: ErrorCode
    message: str
