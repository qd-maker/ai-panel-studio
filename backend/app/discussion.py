"""单场讨论的推进逻辑。每场讨论一个 Discussion 实例，跑在自己的后台任务里。

一轮的顺序：
1. 每位专家各自调用一次模型给出发言意图（并发）。每位专家只看到话题、自己的人设、
   最近 K 条公开发言和当前共识与分歧，看不到其他专家的意图。
2. 意图写 internal 事件；想发言的专家小窗变成「准备发言」（public 事件）。
3. 调度器选人，调度决策写 internal 事件。
4. 被选中的专家生成 1～2 句发言，写 utterance + public 事件。
5. 每条发言后提炼一次共识与分歧。
每 N 条专家发言后，主持人插入一次追问或串联。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, model_validator
from sqlalchemy import Connection

from app import repo
from app.insights import OpsEnvelope, apply_extraction
from app.llm import LLMBadOutput, complete_structured, complete_text
from app.llm_base import LLMError
from app.prompts import render
from app.scheduler import ExpertIntent, pick_speaker, trailing_run
from app.textutil import clamp_sentences, to_plain_summary

HOST_TASKS = {
    "opening": "开场：用一句话介绍话题的争议点，再请嘉宾亮明观点。",
    "question": "追问：点名 $target，就刚才讨论中最模糊或最有争议的一点追问他。",
    "bridge": "串联：把刚才几位嘉宾的观点联系起来，指出共同点或真正的分歧，把讨论往前推。",
    "closing": "收尾：感谢嘉宾，说一句过渡语，引出接下来的总结。",
}
HOST_FALLBACK = {
    "opening": "欢迎来到今天的圆桌。请各位嘉宾先亮明自己的观点。",
    "question": "$target，您怎么看刚才的争论？",
    "bridge": "几位嘉宾的观点有交集也有分歧，我们继续往下聊。",
    "closing": "感谢各位嘉宾的精彩交锋，下面我来做个总结。",
}
EXPERT_TASKS = {
    "point": "提出你的核心观点。",
    "supplement": "接着 $target 的话补充一个新的角度或证据。",
    "rebut": "直接反驳 $target 刚才的说法，指出问题在哪里。",
    "answer": "直接回答主持人刚才对你的提问。",
}


class _IntentEnvelope(BaseModel):
    """模型可能返回单个意图对象，也可能返回 {"intents": [...]}，统一成列表。"""

    intents: list[dict[str, Any]]

    @model_validator(mode="before")
    @classmethod
    def _wrap(cls, data: Any) -> Any:
        if isinstance(data, dict) and "intents" not in data:
            return {"intents": [data]}
        return data


class Discussion:
    def __init__(self, app: FastAPI, did: str):
        s = app.state
        self.did, self.engine, self.llm, self.settings, self.bus = did, s.engine, s.llm, s.settings, s.bus
        with self.engine.connect() as conn:
            d = repo.get_discussion(conn, did)
            people = repo.participants(conn, did)
        self.topic: str = d["topic"]
        self.max_turns: int = d["max_expert_turns"]
        self.host = next(p for p in people if p["role"] == "host")
        self.experts = [p for p in people if p["role"] == "expert"]
        self.by_id = {p["id"]: p for p in people}
        self.by_name = {p["name"]: p for p in people}
        # 本场讨论自己的上下文，不放在任何全局变量里
        self.utts: list[dict] = []  # 公开发言
        self.history: list[str] = []  # 专家发言人顺序
        self.expert_turns = 0
        self.failures = 0
        self.interjections = 0
        self.insights: list[dict] = []

    # ---------------- 主循环 ----------------

    async def run(self) -> None:
        await self.host_say("opening")
        since_host = 0
        pending: tuple[str, dict] | None = None  # 主持人点名的专家和那句追问

        while self.expert_turns < self.max_turns:
            if since_host >= self.settings.host_every_n:
                pending = await self.interject()
                since_host = 0
                continue

            intents = await self.collect_intents()
            speaker = pending[0] if pending else pick_speaker(intents, self.history, self.settings.max_consecutive)
            if speaker is None:
                pending = await self.interject(force_question=True)
                since_host = 0
                continue

            ok = await self.expert_say(speaker, intents, answering=pending[1] if pending else None)
            pending = None
            if ok:
                since_host += 1
            elif self.failures >= self.settings.max_llm_failures:
                await self.fail("模型服务连续多次没有响应，讨论已终止")
                return
            await asyncio.sleep(self.settings.turn_delay_s)

        await self.finish()

    async def interject(self, force_question: bool = False) -> tuple[str, dict] | None:
        """主持人插话：交替追问和串联。追问时点名发言最少的专家，返回 (被点名者, 追问发言)。"""
        act = "question" if force_question or self.interjections % 2 == 0 else "bridge"
        self.interjections += 1
        target = self.quietest() if act == "question" else None
        utt = await self.host_say(act, addressed=target)
        await asyncio.sleep(self.settings.turn_delay_s)
        return (target["id"], utt) if target else None

    def quietest(self) -> dict:
        blocked, run = trailing_run(self.history)
        pool = [e for e in self.experts if not (e["id"] == blocked and run >= self.settings.max_consecutive)] or self.experts
        return min(pool, key=lambda e: (self.history.count(e["id"]), e["seat_no"]))

    # ---------------- 主持人 ----------------

    async def host_say(self, act: str, addressed: dict | None = None) -> dict:
        target = addressed["name"] if addressed else ""
        with self.tx() as (conn, ev):
            ev.append(repo.set_agent_state(conn, self.did, self.host["id"], "speaking"))
        log: list[dict] = []
        try:
            raw = await complete_text(
                self.llm, "host",
                render("host", name=self.host["name"], guests=self.guest_list(), task=HOST_TASKS[act].replace("$target", target),
                       topic=self.topic, recent=self.recent(), insights=self.insight_text()),
                hints={"act": act, "turn": self.expert_turns, "addressed_id": addressed["id"] if addressed else None},
                retries=self.settings.llm_retries, log=log,
            )
            content = clamp_sentences(raw) or HOST_FALLBACK[act].replace("$target", target)
        except LLMError:
            # 主持人的串场话可以用模板兜底，讨论不因为一句串场失败而中断
            content = HOST_FALLBACK[act].replace("$target", target)
        with self.tx() as (conn, ev):
            self._log_calls(conn, log)
            utt, e = repo.insert_utterance(conn, self.did, self.host["id"], act, content, addressed=addressed["id"] if addressed else None)
            ev += [e, repo.set_agent_state(conn, self.did, self.host["id"], "idle")]
        self.utts.append(utt)
        if act != "closing":
            await self.extract()
        return utt

    # ---------------- 专家 ----------------

    async def collect_intents(self) -> list[ExpertIntent]:
        log: list[dict] = []
        intents = await asyncio.gather(*(self._intent_of(e, log) for e in self.experts))
        with self.tx() as (conn, ev):
            self._log_calls(conn, log)
            repo.internal(conn, self.did, "expert.intent", {"turn": self.expert_turns, "intents": [i.model_dump() for i in intents]})
            for i in intents:
                ev.append(repo.set_agent_state(
                    conn, self.did, i.participant_id, "preparing" if i.wants_to_speak else "idle",
                    focus=i.focus, thought=i.public_thought,
                ))
        return list(intents)

    async def _intent_of(self, expert: dict, log: list[dict]) -> ExpertIntent:
        pid = expert["id"]

        def to_intent(env: _IntentEnvelope) -> ExpertIntent:
            raw = next((x for x in env.intents if x.get("participant_id") == pid), env.intents[0] if env.intents else {})
            target = raw.get("target_participant_id")
            if raw.get("target_name") in self.by_name:
                target = self.by_name[raw["target_name"]]["id"]
            return ExpertIntent(**{
                **{k: v for k, v in raw.items() if k in ExpertIntent.model_fields},
                "participant_id": pid,  # 不信任模型给的 id，以调用方为准
                "target_participant_id": target if target in self.by_id and target != pid else None,
            })

        try:
            env = await complete_structured(
                self.llm, "intents", render("intent", **self.persona(expert), topic=self.topic, recent=self.recent(), insights=self.insight_text()),
                _IntentEnvelope,
                # hints 只给 FakeLLM 用来生成结构正确的输出；真实模型的提示词里只有这位专家自己的信息
                hints={"expert_ids": [e["id"] for e in self.experts], "self_id": pid, "turn": self.expert_turns},
                retries=self.settings.llm_retries, check=to_intent, log=log,
            )
            return to_intent(env)
        except (LLMError, LLMBadOutput):
            # 拿不到意图时按「低紧迫度举手」处理，讨论继续
            return ExpertIntent(participant_id=pid, wants_to_speak=True, kind="raise_hand", urgency=1)

    async def expert_say(self, pid: str, intents: list[ExpertIntent], answering: dict | None) -> bool:
        intent = next((i for i in intents if i.participant_id == pid), None)
        act, reply_to, target = self._act_for(pid, intent, answering)
        with self.tx() as (conn, ev):
            repo.internal(conn, self.did, "floor.granted", {
                "turn": self.expert_turns, "speaker": pid, "answering_host": answering is not None,
                "candidates": [{"id": i.participant_id, "urgency": i.urgency, "kind": i.kind, "wants": i.wants_to_speak} for i in intents],
            })
            for i in intents:
                if i.participant_id != pid and i.wants_to_speak:
                    ev.append(repo.set_agent_state(conn, self.did, i.participant_id, "idle"))
            ev.append(repo.set_agent_state(conn, self.did, pid, "speaking"))

        expert = self.by_id[pid]
        log: list[dict] = []
        try:
            raw = await complete_text(
                self.llm, "utterance",
                render("expert", **self.persona(expert), task=EXPERT_TASKS[act].replace("$target", target or "上一位嘉宾"),
                       topic=self.topic, recent=self.recent(), insights=self.insight_text()),
                hints={"speaker_id": pid, "turn": self.expert_turns},
                retries=self.settings.llm_retries, log=log,
            )
            content = clamp_sentences(raw)
        except LLMError:
            content = ""

        with self.tx() as (conn, ev):
            self._log_calls(conn, log)
            if content:
                utt, e = repo.insert_utterance(conn, self.did, pid, act, content, reply_to=reply_to)
                ev.append(e)
                repo.set_expert_turns(conn, self.did, self.expert_turns + 1)
            ev.append(repo.set_agent_state(conn, self.did, pid, "idle"))
        if not content:
            self.failures += 1
            return False

        self.failures = 0
        self.expert_turns += 1
        self.history.append(pid)
        self.utts.append(utt)
        await self.extract()
        return True

    def _act_for(self, pid: str, intent: ExpertIntent | None, answering: dict | None) -> tuple[str, int | None, str | None]:
        """发言性质和回应对象。act 只供调度和提炼使用，Transcript 只显示「→ 姓名」。"""
        if answering:
            return "answer", answering["id"], self.host["name"]
        if intent and intent.kind in ("supplement", "rebut"):
            others = [u for u in self.utts if u["participant_id"] != pid and self.by_id[u["participant_id"]]["role"] == "expert"]
            if intent.target_participant_id:
                others = [u for u in others if u["participant_id"] == intent.target_participant_id] or others
            if others:
                ref = others[-1]
                return intent.kind, ref["id"], self.by_id[ref["participant_id"]]["name"]
        return "point", None, None

    # ---------------- 共识提炼、收尾（后续模块实现） ----------------

    async def extract(self) -> None:
        """每条发言后提炼一次。输出不合格时重试，仍不合格就保留上一版条目，讨论继续。"""
        log: list[dict] = []
        try:
            env = await complete_structured(
                self.llm, "insights",
                render("insights", topic=self.topic, guests=self.guest_ids(), recent=self.recent(with_ids=True), current=self.insight_text(with_ids=True)),
                OpsEnvelope,
                hints={
                    "utterance_ids": [u["id"] for u in self.utts],
                    "expert_ids": [e["id"] for e in self.experts],
                    "insight_ids": [i["id"] for i in self.insights],
                },
                retries=self.settings.llm_retries, log=log,
            )
        except (LLMError, LLMBadOutput) as e:
            with self.tx() as (conn, _):
                self._log_calls(conn, log)
                repo.internal(conn, self.did, "insight.rejected", {"reason": f"提炼失败，保留上一版：{type(e).__name__}"})
            return
        with self.tx() as (conn, ev):
            self._log_calls(conn, log)
            ev += apply_extraction(conn, self.did, env.model_dump_json())
            self.insights = repo.insights(conn, self.did)

    async def summarize(self) -> None:
        """总结只存自然语言。模型给了 JSON 或代码块就取出文字；取不出来重试；仍失败用条目拼兜底总结。"""
        log: list[dict] = []
        text: str | None = None
        for _ in range(self.settings.llm_retries + 1):
            try:
                raw = await complete_text(
                    self.llm, "summary",
                    render("summary", name=self.host["name"], topic=self.topic, guests=self.guest_list(),
                           transcript=self.transcript(), insights=self.insight_text()),
                    hints={}, retries=0, log=log,
                )
            except LLMError:
                continue
            text = to_plain_summary(raw)
            if text:
                break
        source = "llm" if text else "fallback"
        with self.tx() as (conn, ev):
            self._log_calls(conn, log)
            ev.append(repo.set_summary(conn, self.did, text or self.fallback_summary(), source))

    def fallback_summary(self) -> str:
        """模型一直失败时，用已有的共识与分歧拼一段中文总结，保证 done 状态一定有可读的总结。"""
        live = [i for i in self.insights if i["status"] != "dropped"]
        consensus = [i["content"] for i in live if i["kind"] == "consensus"]
        divergence = [i["content"] for i in live if i["kind"] == "divergence"]
        first = f"本场讨论围绕「{self.topic}」展开，{len(self.experts)} 位专家共发言 {self.expert_turns} 次。"
        first += f"嘉宾们形成的共识有：{'；'.join(consensus)}。" if consensus else "嘉宾们没有形成明确的共识。"
        second = f"仍存在的分歧集中在：{'；'.join(divergence)}。" if divergence else "各方观点在讨论中逐渐收拢，没有留下明显分歧。"
        return f"{first}\n\n{second}"[:600]

    def transcript(self) -> str:
        return "\n".join(f"{self.by_id[u['participant_id']]['name']}：{u['content']}" for u in self.utts)

    async def finish(self) -> None:
        with self.tx() as (conn, ev):
            ev.append(repo.transition(conn, self.did, {"running"}, "summarizing"))
        await self.host_say("closing")
        await self.summarize()
        with self.tx() as (conn, ev):
            ev.append(repo.transition(conn, self.did, {"summarizing"}, "done"))

    async def fail(self, message: str) -> None:
        with self.tx() as (conn, ev):
            ev.append(repo.discussion_error(conn, self.did, "LLM_UNAVAILABLE", message))
            ev.append(repo.transition(conn, self.did, repo.LIVE, "failed", reason=message))

    # ---------------- 工具 ----------------

    @contextmanager
    def tx(self) -> Iterator[tuple[Connection, list]]:
        """一个事务；提交成功后再把收集到的 public 事件推给 SSE 订阅者。"""
        events: list = []
        with self.engine.begin() as conn:
            yield conn, events
        self.bus.publish(events)

    def _log_calls(self, conn: Connection, log: list[dict]) -> None:
        for entry in log:
            repo.internal(conn, self.did, "llm.call", entry)

    @staticmethod
    def persona(p: dict) -> dict:
        return {k: p[k] for k in ("name", "profession", "title", "stance", "persona")}

    def guest_list(self) -> str:
        return "\n".join(f"- {e['name']}，{e['profession']}，立场：{e['stance']}" for e in self.experts)

    def guest_ids(self) -> str:
        return "\n".join(f"- {p['id']}：{p['name']}（{'主持人' if p['role'] == 'host' else p['stance']}）" for p in self.by_id.values())

    def recent(self, with_ids: bool = False) -> str:
        if not self.utts:
            return "（还没有人发言）"
        lines = []
        for u in self.utts[-self.settings.recent_k:]:
            p = self.by_id[u["participant_id"]]
            who = "主持人" if p["role"] == "host" else p["title"]
            prefix = f"[{u['id']}] " if with_ids else ""
            lines.append(f"{prefix}{p['name']}（{who}）：{u['content']}")
        return "\n".join(lines)

    def insight_text(self, with_ids: bool = False) -> str:
        live = self.insights if with_ids else [i for i in self.insights if i["status"] not in ("dropped", "resolved")]
        if not live:
            return "（暂无）"
        name = lambda ids: "、".join(self.by_id[x]["name"] for x in ids if x in self.by_id) or "无"  # noqa: E731
        return "\n".join(
            (f"- id={i['id']} 状态={i['status']} " if with_ids else "- ")
            + f"[{'共识' if i['kind'] == 'consensus' else '分歧'}] {i['content']}（认同：{name(i['supporter_ids'])}；反对：{name(i['opponent_ids'])}）"
            for i in live
        )
