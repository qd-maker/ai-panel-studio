"""核对共识与分歧的「站队」是否有证据：每位赞成者 / 反对者，必须是某条证据发言的发言人。

用法：python -m scripts.check_attribution baseline [after ...]
统计每个 run 最终条目里的站队总数、无证据站队数，并列出无证据的明细。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "live"


def check(label: str) -> dict:
    raw = json.loads((ROOT / label / "raw.json").read_text(encoding="utf-8"))
    d = raw["detail"]
    name = {p["id"]: p["name"] for p in d["participants"]}
    speaker = {u["id"]: u["participant_id"] for u in d["utterances"]}
    seq = {u["id"]: u["seq"] for u in d["utterances"]}
    total, bad, details = 0, 0, []
    for i in d["insights"]:
        authors = {speaker.get(x) for x in i["evidence_utterance_ids"]}
        for side, ids in (("赞成", i["supporter_ids"]), ("反对", i["opponent_ids"])):
            for pid in ids:
                total += 1
                if pid not in authors:
                    bad += 1
                    details.append(f"[{i['kind']}] {i['content'][:30]}… {side} {name.get(pid)}，证据 seq {sorted(seq[x] for x in i['evidence_utterance_ids'] if x in seq)} 里没有他的发言")
    rejected = sum(1 for e in raw["events"] if e["type"] == "insight.rejected")
    return {"label": label, "insights": len(d["insights"]), "attributions": total, "unsupported": bad, "rejected_ops": rejected, "details": details}


if __name__ == "__main__":
    for label in sys.argv[1:]:
        r = check(label)
        print(f"== {r['label']}: 条目 {r['insights']}，站队 {r['attributions']}，无证据站队 {r['unsupported']}，被拒操作 {r['rejected_ops']}")
        for line in r["details"]:
            print("   -", line)
