# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents import BaseAgent
from config import ModelConfig
from model import ChatResponse, OpenAIChatModel
from workflow.finish_form_utils import read_live_plan, update_live_plan, update_form_section
from Memory_system.memory_bridge import create_watcher_audit_context

PROMPT_PATH = Path(__file__).with_name("watcher.md")


class WatcherAgent(BaseAgent):
    agent_name: str = "WatcherAgent"
    agent_stage: str = "audit"
    agent_function: str = "live_document_revision"

    def __init__(self, **kwargs: Any) -> None:
        if "stream" not in kwargs:
            kwargs["stream"] = False
        super().__init__(**kwargs)

    def _load_default_prompt(self) -> str | None:
        if not PROMPT_PATH.exists():
            return None
        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        return content or None

    async def revise_plan(
        self,
        *,
        finish_form_path: str | Path,
        tool_name: str,
        tool_args: Mapping[str, Any],
        tool_output: str,
        tool_error: str | None,
        objective: str | None = None,
        context_snapshot: str | None = None,
    ) -> bool:
        current_plan = read_live_plan(finish_form_path) or ""
        if not current_plan.strip():
            return False

        # 获取 Watcher 审计专用的上下文
        audit_context = create_watcher_audit_context(
            finish_form_path=finish_form_path,
            objective=objective or "",
        )

        context = self._build_revision_context(
            current_plan=current_plan,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_output=tool_output,
            tool_error=tool_error,
            objective=objective,
            context_snapshot=context_snapshot,
            audit_context=audit_context,
        )

        messages = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": context})

        response = await self._model(messages=messages)
        response_text = self._extract_text(response)

        revised_plan = self._extract_revised_plan(response_text)
        if revised_plan and revised_plan.strip() != current_plan.strip():
            update_live_plan(finish_form_path, revised_plan)
            self._write_audit_log(finish_form_path, tool_name, response_text)
            return True

        return False

    def _build_revision_context(
        self,
        *,
        current_plan: str,
        tool_name: str,
        tool_args: Mapping[str, Any],
        tool_output: str,
        tool_error: str | None,
        objective: str | None,
        context_snapshot: str | None,
        audit_context: str | None,
    ) -> str:
        sections = ["# Plan Revision Request"]

        if objective:
            sections.append(f"\n## Objective\n{objective.strip()}")

        sections.append(f"\n## Current Live Plan\n```\n{current_plan}\n```")

        sections.append("\n## Tool Execution Result")
        sections.append(f"- Tool: {tool_name}")
        try:
            args_str = json.dumps(tool_args, ensure_ascii=False)
        except Exception:
            args_str = str(tool_args)
        sections.append(f"- Args: {args_str}")

        output_preview = (tool_output or "")[:2000]
        if len(tool_output or "") > 2000:
            output_preview += "... [truncated]"
        sections.append(f"- Output: {output_preview}")

        if tool_error:
            sections.append(f"- Error: {tool_error}")

        if audit_context:
            sections.append(f"\n## Audit Context\n{audit_context}")

        if context_snapshot:
            sections.append(f"\n## Context\n{context_snapshot.strip()}")

        sections.append("""
## Your Task

Analyze the tool result and decide if the plan needs revision.

If the tool execution failed or returned inadequate results:
1. Diagnose the root cause
2. Revise the current step in the plan with corrected parameters/approach
3. Output the COMPLETE revised plan

If the tool execution succeeded:
1. Mark the current step as completed
2. Ensure the next step is ready for execution
3. Output the COMPLETE plan (with status updates)

## Output Format

Output ONLY the revised plan in this exact format:

```plan
[Your complete revised plan here, with step statuses]
```

If NO revision is needed, output:
```plan
NO_CHANGE
```
""")

        return "\n".join(sections)

    def _extract_revised_plan(self, response_text: str) -> str | None:
        pattern = re.compile(r"```plan\s*(.*?)\s*```", re.DOTALL)
        match = pattern.search(response_text)
        if match:
            content = match.group(1).strip()
            if content == "NO_CHANGE":
                return None
            return content
        return None

    def _write_audit_log(
        self,
        finish_form_path: str | Path,
        tool_name: str,
        audit_text: str,
    ) -> None:
        update_form_section(
            finish_form_path,
            marker_name="WATCHER_AUDIT",
            content=f"Last revision for tool: {tool_name}\n\n{audit_text}",
            header="## Watcher Audit Report",
        )


__all__ = [
    "WatcherAgent",
]
