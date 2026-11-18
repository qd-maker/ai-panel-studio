"""文本处理：句子截断、从模型输出里取 JSON、把总结规整成纯文本。"""

from __future__ import annotations

import json
import re

SENTENCE_END = re.compile(r"[。！？!?]+|(?<![0-9])\.(?![0-9])")
FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def clamp_sentences(text: str, max_sentences: int = 2) -> str:
    """最多保留 max_sentences 句，超出部分直接截掉（不重新生成：更省钱，结果也确定）。"""
    text = text.strip()
    count = 0
    for m in SENTENCE_END.finditer(text):
        count += 1
        if count == max_sentences:
            return text[: m.end()].strip()
    return text


def strip_fence(text: str) -> str:
    m = FENCE.match(text)
    return m.group(1) if m else text.strip()


def extract_json(text: str):
    """解析模型输出的 JSON，兼容 ```json 代码块包裹。失败抛 ValueError。"""
    body = strip_fence(text)
    if not body:
        raise ValueError("模型输出为空")
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"不是合法 JSON：{e.msg}") from e


def looks_like_json(text: str) -> bool:
    s = text.strip()
    return s.startswith(("{", "[")) or "```" in s


def to_plain_summary(raw: str) -> str | None:
    """把模型给的总结规整成纯文本。

    模型偶尔会把总结包成 {"summary": "..."} 或代码块。能取出文字就取，
    取不出来返回 None，由调用方重试或兜底。页面上绝不出现 JSON 原文（P-06）。
    """
    text = strip_fence(raw)
    if looks_like_json(text):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            text = next((v for k, v in data.items() if k in ("summary", "text", "content") and isinstance(v, str)), "")
        else:
            return None
    text = text.strip()
    if not text or looks_like_json(text):
        return None
    return text[:600]
