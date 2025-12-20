"""工具目录加载辅助模块。

该模块负责从项目约定的 Markdown 文件中读取工具清单，并转换为可供各阶段
Agent 使用的字符串列表（例如传入 ``tool_catalog`` 参数）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TOOL_CATALOG_PATH = PROJECT_ROOT / "tools" / "tool_catalog.md"


def _ensure_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def _normalize_entries(items: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in items:
        entry = raw.strip()
        if not entry:
            continue
        if entry in seen:
            continue
        normalized.append(entry)
        seen.add(entry)
    return normalized


def load_tool_catalog(path: str | Path | None = None) -> list[str]:
    """从 Markdown 目录中读取工具清单。

    Markdown 文件的约定格式如下::

        # 工具目录

        ## Tavily MCP
        - search: 调用 Tavily 在线搜索，支持事实核验。

        ## Code Interpreter MCP
        - python: 在沙箱中执行 Python 代码。

    只有以 ``- `` 开头的条目会被识别，并保留 ``名称: 描述`` 的文本形式。
    """

    target_path = _ensure_path(path) if path else DEFAULT_TOOL_CATALOG_PATH
    try:
        content = target_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    entries: list[str] = []
    current_section: str | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if stripped.startswith("##"):
                current_section = stripped.lstrip("#").strip()
            continue
        if not stripped.startswith("- "):
            continue

        item = stripped[2:].strip()
        if not item:
            continue

        if ":" in item:
            name, description = item.split(":", 1)
            name = name.strip()
            description = description.strip()
            if current_section:
                entry_name = f"{current_section} · {name}"
            else:
                entry_name = name
            entry = f"{entry_name}: {description}" if description else entry_name
        else:
            entry = f"{current_section} · {item}" if current_section else item

        entries.append(entry)

    return _normalize_entries(entries)


def merge_tool_catalogs(*catalogs: Sequence[str] | None) -> list[str] | None:
    """合并多个工具清单，去重并保持原有顺序。"""

    combined: list[str] = []
    seen: set[str] = set()
    for catalog in catalogs:
        if not catalog:
            continue
        for item in catalog:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            combined.append(normalized)
            seen.add(normalized)
    return combined or None


__all__ = [
    "DEFAULT_TOOL_CATALOG_PATH",
    "load_tool_catalog",
    "merge_tool_catalogs",
]


