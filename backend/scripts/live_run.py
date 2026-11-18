"""用真实 DeepSeek 跑一场讨论并导出质量检查报告。

用法（在 backend 目录下，需要环境变量 DEEPSEEK_API_KEY）：
    python -m scripts.live_run --label baseline --topic "生成式 AI 会让初级程序员岗位消失吗"

输出到 data/live/<label>/：report.md（给人看）和 raw.json（完整数据）。
跑前跑后各查一次余额，用差额记录这一场的实际花费。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import text

from app.config import Settings
from app.db import create_db_engine, init_db
from app.main import create_app

OUT_ROOT = Path(__file__).resolve().parent.parent / "data" / "live"
SENT_END = re.compile(r"[。！？!?]+")


def balance() -> float:
    key = os.environ["DEEPSEEK_API_KEY"].strip()
    r = httpx.get("https://api.deepseek.com/user/balance", headers={"Authorization": f"Bearer {key}"}, timeout=15)
    r.raise_for_status()
    infos = r.json()["balance_infos"]
    return float(next(b for b in infos if b["currency"] == "CNY")["total_balance"])


def rows(engine, sql, **p):
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), p)]


async def run(label: str, topic: str, expert_count: int, max_turns: int) -> Path:
    out = OUT_ROOT / label
    out.mkdir(parents=True, exist_ok=True)
    db = out / "live.db"
    if db.exists():
        db.unlink()
    engine = create_db_engine(f"sqlite:///{db.as_posix()}")
    init_db(engine)
    settings = Settings(llm_mode="deepseek", turn_delay_s=0, max_expert_turns=max_turns)
    app = create_app(engine=engine, settings=settings)

    before = balance()
    t0 = time.perf_counter()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://live", timeout=120) as c:
        r = await c.post("/api/discussions", json={"topic": topic, "expert_count": expert_count})
        r.raise_for_status()
        did = r.json()["id"]
        (await c.post(f"/api/discussions/{did}/start")).raise_for_status()
        await app.state.runner.wait(did)
        detail = (await c.get(f"/api/discussions/{did}")).json()
    elapsed = time.perf_counter() - t0
    await asyncio.sleep(3)  # 余额扣费有少许延迟
    after = balance()

    events = rows(engine, "SELECT id, visibility, type, payload FROM event WHERE discussion_id = :d ORDER BY id", d=did)
    for e in events:
        e["payload"] = json.loads(e["payload"])
    raw = {"label": label, "topic": topic, "cost_cny": round(before - after, 4), "elapsed_s": round(elapsed, 1), "detail": detail, "events": events}
    (out / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.md").write_text(render_report(raw), encoding="utf-8")
    return out


def render_report(raw: dict) -> str:
    d = raw["detail"]
    people = {p["id"]: p for p in d["participants"]}
    utts = d["utterances"]
    by_uid = {u["id"]: u for u in utts}
    name = lambda pid: people[pid]["name"] if pid in people else "?"  # noqa: E731
    L = [f"# 质量检查报告：{raw['label']}", "", f"- 话题：{raw['topic']}", f"- 状态：{d['status']}　耗时：{raw['elapsed_s']} s　花费：¥{raw['cost_cny']}", ""]

    L += ["## 阵容", ""]
    for p in d["participants"]:
        L.append(f"- {'主持人' if p['role'] == 'host' else '专家'} {p['name']}（{p['profession']} · {p['title']}）立场：{p['stance']}")

    L += ["", "## Transcript", "", "| seq | 发言人 | act | 回应/点名 | 句数 | 内容 |", "| --- | --- | --- | --- | --- | --- |"]
    for u in utts:
        target = name(by_uid[u["reply_to_utterance_id"]]["participant_id"]) if u["reply_to_utterance_id"] in by_uid else (name(u["addressed_participant_id"]) if u["addressed_participant_id"] else "")
        n = len(SENT_END.findall(u["content"]))
        L.append(f"| {u['seq']} | {name(u['participant_id'])} | {u['act']} | {target} | {n} | {u['content']} |")

    acts = Counter(u["act"] for u in utts)
    sent = Counter(min(len(SENT_END.findall(u["content"])), 3) for u in utts)
    L += ["", f"- act 分布：{dict(acts)}", f"- 句数分布（3 表示 ≥3）：{dict(sent)}", f"- 最长发言字数：{max(len(u['content']) for u in utts)}"]

    # 共识与分歧的时间线：每个 insight 事件发生在第几条发言之后
    L += ["", "## 共识与分歧时间线", ""]
    last_seq = 0
    for e in raw["events"]:
        if e["type"] == "utterance.created":
            last_seq = e["payload"]["utterance"]["seq"]
        elif e["type"] == "insight.upserted":
            i = e["payload"]["insight"]
            ev = ",".join(str(by_uid[x]["seq"]) for x in i["evidence_utterance_ids"] if x in by_uid)
            L.append(f"- 第 {last_seq} 条后 [{e['payload']['op']} v{i['version']}] {i['kind']}/{i['status']}：{i['content']}　赞成 {[name(x) for x in i['supporter_ids']]} 反对 {[name(x) for x in i['opponent_ids']]}　证据 seq {ev}")
        elif e["type"] == "insight.rejected":
            L.append(f"- 第 {last_seq} 条后 [rejected] {e['payload'].get('reason', '')[:120]}")

    L += ["", "## 小窗公开思考摘要（全部出现过的版本）", ""]
    seen = set()
    for e in raw["events"]:
        if e["type"] == "agent_state.updated":
            s = e["payload"]["agent_state"]
            key = (s["participant_id"], s["focus"], s["public_thought"])
            if s["public_thought"] and key not in seen:
                seen.add(key)
                L.append(f"- {name(s['participant_id'])}｜关注：{s['focus']}｜思考：{s['public_thought']}")

    calls = [e["payload"] for e in raw["events"] if e["type"] == "llm.call"]
    fails = Counter(c["purpose"] for c in calls if not c["ok"])
    L += ["", "## 模型调用", "", f"- 共 {len(calls)} 次，失败 {sum(fails.values())} 次：{dict(fails)}"]
    for c in calls:
        if not c["ok"]:
            L.append(f"  - {c['purpose']} 第 {c['attempt'] + 1} 次：{(c['error'] or '')[:150]}")

    L += ["", "## 总结", "", f"来源：{d['summary_source']}", "", d["summary"] or "（无）", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--topic", default="生成式 AI 会让初级程序员岗位消失吗")
    ap.add_argument("--experts", type=int, default=4)
    ap.add_argument("--turns", type=int, default=12)
    a = ap.parse_args()
    out = asyncio.run(run(a.label, a.topic, a.experts, a.turns))
    print(f"报告：{out / 'report.md'}")
    raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
    print(f"状态 {raw['detail']['status']}，耗时 {raw['elapsed_s']} s，花费 ¥{raw['cost_cny']}")


if __name__ == "__main__":
    main()
