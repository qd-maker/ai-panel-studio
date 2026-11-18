"""共识与分歧的增量更新。

模型每次只输出「操作」，不重写整张表：
    create      新建一条共识或分歧
    update      合并：给已有条目追加认同者 / 反对者 / 证据，或改写措辞
    set_status  改状态：emerging → confirmed，分歧 resolved，条目 dropped
每条操作单独校验，引用了不存在的发言或嘉宾就丢弃这一条（写 internal 事件），其余照常写入。
整段输出不是合法 JSON 时什么都不改，保留上一版。
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, TypeAdapter, ValidationError
from sqlalchemy import Connection, text

from app import repo, schemas
from app.textutil import extract_json

Content = Annotated[str, BeforeValidator(lambda v: v.strip()[:80] if isinstance(v, str) else v), Field(min_length=1)]


class CreateOp(BaseModel):
    op: Literal["create"]
    kind: schemas.InsightKind
    content: Content
    supporter_ids: list[str] = []
    opponent_ids: list[str] = []
    evidence_utterance_ids: list[int] = Field(min_length=1)


class UpdateOp(BaseModel):
    op: Literal["update"]
    id: str
    content: Content | None = None
    add_supporter_ids: list[str] = []
    add_opponent_ids: list[str] = []
    evidence_utterance_ids: list[int] = []


class StatusOp(BaseModel):
    op: Literal["set_status"]
    id: str
    status: schemas.InsightStatus


Op = Annotated[CreateOp | UpdateOp | StatusOp, Field(discriminator="op")]
_op_adapter: TypeAdapter[Op] = TypeAdapter(Op)


class OpsEnvelope(BaseModel):
    """只校验外层结构；每条操作在 apply_extraction 里单独校验。"""

    ops: list[dict[str, Any]]


def apply_extraction(conn: Connection, did: str, raw: str) -> list[dict]:
    """应用一次提炼结果，返回写入的 public 事件（insight.upserted）。"""
    try:
        envelope = OpsEnvelope.model_validate(extract_json(raw))
    except (ValueError, ValidationError) as e:
        repo.internal(conn, did, "insight.rejected", {"reason": f"整段输出无效：{str(e)[:200]}"})
        return []

    people = {p["id"] for p in repo.participants(conn, did)}
    utt_ids = {u["id"] for u in repo.utterances(conn, did)}
    current = {i["id"]: i for i in repo.insights(conn, did)}
    events: list[dict] = []

    for item in envelope.ops:
        try:
            op = _op_adapter.validate_python(item)
            row, verb = _apply_one(op, people, utt_ids, current)
        except (ValueError, ValidationError) as e:
            repo.internal(conn, did, "insight.rejected", {"op": item, "reason": str(e)[:200]})
            continue
        if row is None:
            continue
        _save(conn, did, row, verb)
        current[row["id"]] = row
        events.append(repo.append_event(
            conn, did, "public", "insight.upserted",
            schemas.InsightEventData(discussion_id=did, op=verb, insight=schemas.Insight(**row)).model_dump(mode="json"),
        ))
    return events


def _apply_one(op: Op, people: set[str], utt_ids: set[int], current: dict[str, dict]) -> tuple[dict | None, str]:
    ts = repo.now()
    if isinstance(op, CreateOp):
        _require_known(op.supporter_ids + op.opponent_ids, people, "嘉宾")
        _require_known(op.evidence_utterance_ids, utt_ids, "发言")
        if op.kind == "consensus" and not op.supporter_ids:
            raise ValueError("共识至少要有一位认同者")
        if op.kind == "divergence" and not (op.supporter_ids and op.opponent_ids):
            raise ValueError("分歧两边都至少要有一位嘉宾")
        if any(i["content"] == op.content and i["kind"] == op.kind for i in current.values()):
            return None, ""  # 重复条目，忽略
        return {
            "id": repo.new_id(), "kind": op.kind, "content": op.content,
            "supporter_ids": _uniq(op.supporter_ids), "opponent_ids": _uniq(op.opponent_ids),
            "status": "emerging", "evidence_utterance_ids": _uniq(op.evidence_utterance_ids),
            "version": 1, "created_at": ts, "updated_at": ts,
        }, "created"

    row = current.get(op.id)
    if not row:
        raise ValueError(f"条目 {op.id} 不存在")
    new = dict(row)

    if isinstance(op, UpdateOp):
        _require_known(op.add_supporter_ids + op.add_opponent_ids, people, "嘉宾")
        _require_known(op.evidence_utterance_ids, utt_ids, "发言")
        # 有人改变立场：加入一边时从另一边移除
        new["supporter_ids"] = _uniq([x for x in row["supporter_ids"] if x not in op.add_opponent_ids] + op.add_supporter_ids)
        new["opponent_ids"] = _uniq([x for x in row["opponent_ids"] if x not in op.add_supporter_ids] + op.add_opponent_ids)
        new["evidence_utterance_ids"] = _uniq(row["evidence_utterance_ids"] + op.evidence_utterance_ids)
        if op.content:
            new["content"] = op.content
    else:
        if op.status == "resolved" and row["kind"] != "divergence":
            raise ValueError("只有分歧可以标记为已化解")
        new["status"] = op.status

    # 更新后仍要满足建表时的约束：分歧两边都至少一人，共识至少一位认同者
    if new["kind"] == "divergence" and new["status"] in ("emerging", "confirmed") and not (new["supporter_ids"] and new["opponent_ids"]):
        raise ValueError("更新后分歧只剩一边，应改为 set_status resolved 或新建共识")
    if new["kind"] == "consensus" and not new["supporter_ids"]:
        raise ValueError("更新后共识没有认同者")
    if all(new[k] == row[k] for k in ("content", "supporter_ids", "opponent_ids", "evidence_utterance_ids", "status")):
        return None, ""  # 没有实际变化，不升版本
    new["version"] = row["version"] + 1
    new["updated_at"] = ts
    return new, "updated"


def _save(conn: Connection, did: str, row: dict, verb: str) -> None:
    params = {
        **row, "d": did,
        "supporter_ids": json.dumps(row["supporter_ids"]), "opponent_ids": json.dumps(row["opponent_ids"]),
        "evidence_utterance_ids": json.dumps(row["evidence_utterance_ids"]),
    }
    if verb == "created":
        conn.execute(text(
            "INSERT INTO insight (id, discussion_id, kind, content, supporter_ids, opponent_ids, status, evidence_utterance_ids, version, created_at, updated_at) "
            "VALUES (:id, :d, :kind, :content, :supporter_ids, :opponent_ids, :status, :evidence_utterance_ids, :version, :created_at, :updated_at)"
        ), params)
    else:
        conn.execute(text(
            "UPDATE insight SET content = :content, supporter_ids = :supporter_ids, opponent_ids = :opponent_ids, status = :status, "
            "evidence_utterance_ids = :evidence_utterance_ids, version = :version, updated_at = :updated_at WHERE id = :id AND discussion_id = :d"
        ), params)


def _require_known(values: list, known: set, what: str) -> None:
    unknown = [v for v in values if v not in known]
    if unknown:
        raise ValueError(f"引用了不存在的{what}：{unknown}")


def _uniq(values: list) -> list:
    return list(dict.fromkeys(values))
