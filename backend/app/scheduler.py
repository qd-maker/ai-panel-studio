"""发言调度：纯函数，输入各专家的意图和发言历史，输出下一位发言人。

规则：
1. 只考虑想发言的专家。
2. 已经连续发言 max_consecutive 次的专家这一轮不能再选。
3. 紧迫度最高者优先；同分时，最久没发言的优先（从没发过言的人最优先）。
4. 没有候选人时返回 None，由主持人介入。
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

from app.schemas import PublicViewText

IntentKind = Literal["raise_hand", "interrupt", "supplement", "rebut"]


def _truncate(n: int):
    return lambda v: v[:n] if isinstance(v, str) else v


class ExpertIntent(BaseModel):
    """一位专家在一轮里的发言意图。只写进 internal 事件，不进 Transcript。"""

    participant_id: str
    wants_to_speak: bool = True
    kind: IntentKind = "raise_hand"
    urgency: int = Field(ge=1, le=5)
    target_participant_id: str | None = None
    # 公开给小窗的观点：先截到字段上限，再校验不含发言意图
    focus: Annotated[PublicViewText, BeforeValidator(_truncate(20))] = None
    public_thought: Annotated[PublicViewText, BeforeValidator(_truncate(60))] = None


def trailing_run(history: list[str]) -> tuple[str | None, int]:
    """历史末尾同一个人连续发言了几次。"""
    if not history:
        return None, 0
    last, n = history[-1], 0
    for pid in reversed(history):
        if pid != last:
            break
        n += 1
    return last, n


def pick_speaker(intents: list[ExpertIntent], history: list[str], max_consecutive: int = 2) -> str | None:
    last, run = trailing_run(history)
    blocked = last if run >= max_consecutive else None
    last_spoke = {pid: i for i, pid in enumerate(history)}
    candidates = [i for i in intents if i.wants_to_speak and i.participant_id != blocked]
    if not candidates:
        return None
    best = min(candidates, key=lambda i: (-i.urgency, last_spoke.get(i.participant_id, -1)))
    return best.participant_id
