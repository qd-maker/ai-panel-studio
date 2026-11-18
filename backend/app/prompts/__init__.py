"""Prompt 模板：每个模板一个 .md 文件，用 $变量 占位（string.Template），避免和 JSON 示例里的花括号冲突。"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from string import Template

DIR = Path(__file__).parent


@cache
def _load(name: str) -> tuple[str, str]:
    """模板文件用一行 `---user---` 分成 system 和 user 两段。"""
    raw = (DIR / f"{name}.md").read_text(encoding="utf-8")
    system, _, user = raw.partition("\n---user---\n")
    return system.strip(), user.strip()


def render(template: str, /, **values: object) -> list[dict[str, str]]:
    """template 只能按位置传，模板变量里可以有 $name 这类同名占位符。"""
    system, user = _load(template)
    vals = {k: str(v) for k, v in values.items()}
    return [
        {"role": "system", "content": Template(system).substitute(vals)},
        {"role": "user", "content": Template(user).substitute(vals)},
    ]
