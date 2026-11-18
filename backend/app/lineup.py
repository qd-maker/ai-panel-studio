"""嘉宾生成：让模型按话题生成主持人和专家，校验人数和立场，颜色由系统分配。"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.config import Settings
from app.llm import complete_structured
from app.llm_base import LLMClient
from app.prompts import render

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class GuestOut(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    profession: Short
    title: Short
    stance: Short
    persona: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class LineupOut(BaseModel):
    host: GuestOut
    experts: list[GuestOut]


def _check(expert_count: int):
    def check(lineup: LineupOut) -> None:
        if len(lineup.experts) != expert_count:
            raise ValueError(f"专家人数应为 {expert_count}，实际 {len(lineup.experts)}")
        names = [g.name for g in [lineup.host, *lineup.experts]]
        if len(set(names)) != len(names):
            raise ValueError("嘉宾姓名重复")
        stances = [g.stance for g in lineup.experts]
        if len(set(stances)) != len(stances):
            raise ValueError("专家立场重复")

    return check


async def generate_lineup(llm: LLMClient, settings: Settings, topic: str, expert_count: int, log: list[dict] | None = None) -> LineupOut:
    """失败时抛 LLMError（服务故障）或 LLMBadOutput（输出不合格）。"""
    return await complete_structured(
        llm,
        "lineup",
        render("lineup", topic=topic, expert_count=expert_count),
        LineupOut,
        hints={"expert_count": expert_count},
        retries=settings.llm_retries,
        check=_check(expert_count),
        log=log,
    )
