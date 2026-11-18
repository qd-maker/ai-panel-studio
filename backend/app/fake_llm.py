"""FakeLLM：LLM_MODE=mock 时使用的可控大模型替身。

- 不联网、不花钱，输出完全确定，测试结果可复现。
- 每种用途（purpose）都有一个默认生成器，产出结构正确的内容，让一场讨论能完整跑完。
- 测试可以用 script 按用途覆盖：列表里的元素按调用顺序依次消费，用完后回到默认生成器。
  元素可以是：
    str                      原样作为模型输出（可以是非法 JSON，用来测重试和兜底）
    Exception 实例           调用时抛出（例如 LLMError，模拟服务故障）
    callable(hints, n) -> str  按提示和本用途的第 n 次调用动态生成
- 每次调用都记录在 calls 里，测试可以断言「调了几次、按什么顺序」。
- reasoning 模拟推理模型的隐藏思维链，默认带一个哨兵字符串，用来测试它绝不外泄。

各用途的 hints 约定（编排器负责传入）：
    lineup     {"expert_count": int}
    intents    {"expert_ids": [str], "self_id": str, "turn": int}
               每位专家各调一次。默认生成器为 expert_ids 里的每个人都生成一条意图，
               编排器只取 self_id 那一条；真实模型的提示词里只有这位专家自己的信息
    utterance  {"speaker_id": str, "turn": int}
    host       {"act": "opening"|"question"|"bridge"|"closing", "turn": int, "addressed_id": str | None}
    insights   {"utterance_ids": [int], "expert_ids": [str], "insight_ids": [str]}
               utterance_ids 是本场到目前为止的全部发言 id，最后一个是最新一条
    summary    {}
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from app.llm_base import LLMResult, Purpose

SECRET_COT = "SECRET_COT_不应出现在任何接口里"

ScriptItem = str | Exception | Callable[[dict[str, Any], int], str]

INTENT_KINDS = ["raise_hand", "interrupt", "supplement", "rebut"]


def _lineup(hints: dict[str, Any], n: int) -> str:
    count = int(hints.get("expert_count", 4))
    stances = ["坚定支持", "有条件支持", "中立观望", "有条件反对", "坚决反对", "另辟蹊径"]
    return json.dumps(
        {
            "host": {
                "name": "主持人甲", "profession": "节目主持人", "title": "圆桌节目主持人",
                "stance": "保持中立，追问论据", "persona": "擅长把抽象争论拉回具体案例。",
            },
            "experts": [
                {
                    "name": f"专家{i + 1}号", "profession": f"职业{i + 1}", "title": f"某机构研究员{i + 1}",
                    "stance": f"{stances[i % len(stances)]}这个观点", "persona": f"第 {i + 1} 位专家的背景介绍。",
                }
                for i in range(count)
            ],
        },
        ensure_ascii=False,
    )


def _intents(hints: dict[str, Any], n: int) -> str:
    ids: list[str] = hints.get("expert_ids", [])
    turn = int(hints.get("turn", n))
    return json.dumps(
        {
            "intents": [
                {
                    "participant_id": pid,
                    "wants_to_speak": True,
                    "kind": INTENT_KINDS[(i + turn) % len(INTENT_KINDS)],
                    "urgency": 1 + (i * 2 + turn) % 5,
                    "target_participant_id": None,
                    "focus": f"关注点{i + 1}",
                    "public_thought": f"第{i + 1}位专家认为数据还不充分",
                }
                for i, pid in enumerate(ids)
            ]
        },
        ensure_ascii=False,
    )


def _utterance(hints: dict[str, Any], n: int) -> str:
    return f"这是第 {n + 1} 条专家发言的观点。数据支持这个判断。"


def _host(hints: dict[str, Any], n: int) -> str:
    act = hints.get("act", "question")
    text = {
        "opening": "欢迎来到今天的圆桌。请各位嘉宾先亮明观点。",
        "question": "我想追问一下刚才的说法。依据是什么？",
        "bridge": "两位的观点有交集。我们换个角度继续。",
        "closing": "感谢各位嘉宾。下面是本场总结。",
    }
    return text.get(act, text["question"])


def _insights(hints: dict[str, Any], n: int) -> str:
    utt: list[int] = hints.get("utterance_ids", [])
    experts: list[str] = hints.get("expert_ids", [])
    existing: list[str] = hints.get("insight_ids", [])
    if not utt or not experts:
        return json.dumps({"ops": []})
    last = utt[-1]
    if not existing:
        op = {
            "op": "create", "kind": "consensus", "content": "新人的能力要求正在变化",
            "supporter_ids": [experts[0]], "opponent_ids": [], "evidence_utterance_ids": [last],
        }
    elif len(existing) == 1 and len(experts) >= 2:
        op = {
            "op": "create", "kind": "divergence", "content": "岗位总量会显著减少",
            "supporter_ids": [experts[0]], "opponent_ids": [experts[1]], "evidence_utterance_ids": [last],
        }
    else:
        op = {
            "op": "update", "id": existing[n % len(existing)],
            "add_supporter_ids": [experts[n % len(experts)]], "evidence_utterance_ids": [last],
        }
    return json.dumps({"ops": [op]}, ensure_ascii=False)


def _summary(hints: dict[str, Any], n: int) -> str:
    return "本场讨论形成了一项共识：新人的能力要求正在变化。\n\n分歧集中在岗位总量上，嘉宾们各执一词。"


DEFAULTS: dict[str, Callable[[dict[str, Any], int], str]] = {
    "lineup": _lineup,
    "intents": _intents,
    "utterance": _utterance,
    "host": _host,
    "insights": _insights,
    "summary": _summary,
}


class FakeLLM:
    def __init__(self, script: dict[str, list[ScriptItem]] | None = None, reasoning: str | None = SECRET_COT):
        self.script: dict[str, list[ScriptItem]] = {k: list(v) for k, v in (script or {}).items()}
        self.reasoning = reasoning
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._count: dict[str, int] = defaultdict(int)

    def calls_for(self, purpose: Purpose) -> int:
        return sum(1 for p, _ in self.calls if p == purpose)

    async def complete(
        self,
        purpose: Purpose,
        messages: list[dict[str, str]],
        *,
        hints: dict[str, Any] | None = None,
    ) -> LLMResult:
        hints = hints or {}
        n = self._count[purpose]
        self._count[purpose] += 1
        self.calls.append((purpose, hints))

        queue = self.script.get(purpose)
        item: ScriptItem = queue.pop(0) if queue else DEFAULTS[purpose]
        if isinstance(item, Exception):
            raise item
        text = item(hints, n) if callable(item) else item
        return LLMResult(text=text, reasoning=self.reasoning)
