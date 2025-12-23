# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, AsyncGenerator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents import BaseAgent
from config import ModelConfig
from model import ChatResponse, OpenAIChatModel
from workflow.finish_form_utils import (
    read_live_plan,
    update_live_plan,
    update_form_section,
    read_form_section,
)
from workflow.document_orchestrator import DocumentOrchestrator
from stage4_agent.tools_bridge import ToolsBridge, ToolResult
from _logging import logger as LOGGER

PROMPT_PATH = Path(__file__).with_name("executor.md")


class Stage4ExecutorAgent(BaseAgent):
    agent_name: str = "Stage4ExecutorAgent"
    agent_stage: str = "stage4"
    agent_function: str = "live_document_execution"

    FINAL_ANSWER_LABEL_RE = re.compile(
        r"(?:^|\n)\s*(?:final answer|Final Answer)\s*[:：]\s*",
        re.IGNORECASE,
    )

    def __init__(self, max_iterations: int = 10, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._max_iterations = max_iterations

    def _load_default_prompt(self) -> str | None:
        if not PROMPT_PATH.exists():
            return None
        content = PROMPT_PATH.read_text(encoding="utf-8")
        end_marker = "<!-- REFLECTION_TEMPLATE_START -->"
        idx = content.find(end_marker)
        if idx != -1:
            content = content[:idx]
        return content.strip() or None


    async def analyze(
        self,
        *,
        context: str,
        structured_model: Any | None = None,
        tools_bridge: ToolsBridge | None = None,
        watcher_agent: Any | None = None,
        enable_tool_loop: bool = False,
        orchestrator: DocumentOrchestrator | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        objective = self._extract_section(context, "Objective")
        context_snapshot = self._extract_section(context, "Context Snapshot")

        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        if enable_tool_loop and tools_bridge and orchestrator:
            execution_plan = self._extract_section(context, "Stage 3 Execution Plan")
            finish_form_path = str(orchestrator.document_path)
            self._init_live_plan(finish_form_path, execution_plan, objective)
            final_response_text = await self._run_live_document_loop(
                messages=messages,
                structured_model=structured_model,
                tools_bridge=tools_bridge,
                watcher_agent=watcher_agent,
                objective=objective,
                context_snapshot=context_snapshot,
                finish_form_path=finish_form_path,
                orchestrator=orchestrator,
                **kwargs,
            )
        else:
            messages.append({"role": "user", "content": context.strip()})
            response = await self._model(
                messages=messages,
                structured_model=structured_model,
                **kwargs,
            )
            if inspect.isasyncgen(response):
                chunks = []
                async for item in response:
                    chunks.append(self._extract_text(item))
                final_response_text = "".join(chunks).strip()
            else:
                final_response_text = self._extract_text(response)

        class SyntheticResponse:
            def __init__(self, text: str):
                self.content = [type("TextBlock", (), {"type": "text", "text": text})()]
                self.metadata = None
                self.raw = None

        return SyntheticResponse(final_response_text)

    @staticmethod
    def _extract_section(context: str, header: str) -> str:
        lines = context.split("\n")
        capture = False
        section_lines: list[str] = []
        for line in lines:
            if line.strip().startswith(f"## {header}"):
                capture = True
                continue
            if capture:
                if line.strip().startswith("## "):
                    break
                section_lines.append(line)
        return "\n".join(section_lines).strip()

    def _init_live_plan(
        self,
        finish_form_path: str,
        execution_plan: str,
        objective: str | None,
    ) -> None:
        header = f"Objective: {objective}\n\n" if objective else ""
        initial_plan = f"{header}## Steps\n\n{execution_plan}"
        update_live_plan(finish_form_path, initial_plan)

    async def _run_live_document_loop(
        self,
        *,
        messages: list[dict[str, str]],
        structured_model: Any | None,
        tools_bridge: ToolsBridge,
        watcher_agent: Any | None,
        objective: str | None,
        context_snapshot: str | None,
        finish_form_path: str,
        orchestrator: DocumentOrchestrator | None = None,
        **kwargs: Any,
    ) -> str:
        iteration = 0
        last_response_text = ""

        LOGGER.info("[Stage4] Starting live document execution loop (max=%d)", self._max_iterations)

        while iteration < self._max_iterations:
            iteration += 1
            LOGGER.info("[Stage4] === Iteration %d/%d ===", iteration, self._max_iterations)

            live_plan = read_live_plan(finish_form_path) or ""
            iteration_prompt = self._build_iteration_prompt(live_plan, iteration)
            messages.append({"role": "user", "content": iteration_prompt})

            response = await self._model(
                messages=messages,
                structured_model=structured_model,
                **kwargs,
            )

            if inspect.isasyncgen(response):
                chunks = []
                async for item in response:
                    chunks.append(self._extract_text(item))
                response_text = "".join(chunks).strip()
            else:
                response_text = self._extract_text(response)

            messages.append({"role": "assistant", "content": response_text})
            last_response_text = response_text

            tool_calls = self._parse_tool_calls(response_text)
            if not tool_calls:
                LOGGER.info("[Stage4] No tool calls found, ending loop")
                break

            LOGGER.info("[Stage4] Parsed %d tool call(s)", len(tool_calls))

            for call in tool_calls:
                tool_name = call.get("tool", "")
                tool_args = call.get("args", {})
                LOGGER.info("[TOOL_CALL] tool=%s | args=%s", tool_name, json.dumps(tool_args, ensure_ascii=False))

                result: ToolResult = tools_bridge.call_tool(tool_name, **tool_args)

                LOGGER.info(
                    "[TOOL_RESULT] tool=%s | success=%s | error=%s | output=%s",
                    tool_name,
                    result.success,
                    result.error or "None",
                    (result.output or "")[:500],
                )

                result_text = self._format_tool_result(call, result)
                messages.append({"role": "user", "content": result_text})

                if orchestrator:
                    orchestrator.register_tool_call(
                        iteration=iteration,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_output=result.output,
                        tool_error=result.error,
                    )
                else:
                    self._append_tool_log(
                        finish_form_path,
                        iteration=iteration,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_output=result.output,
                        tool_error=result.error,
                    )

                if watcher_agent:
                    try:
                        revised = await watcher_agent.revise_plan(
                            finish_form_path=finish_form_path,
                            tool_name=tool_name,
                            tool_args=tool_args,
                            tool_output=result.output or "",
                            tool_error=result.error,
                            objective=objective,
                            context_snapshot=context_snapshot,
                        )
                        if revised:
                            LOGGER.info("[Stage4] Watcher revised the live plan")
                    except Exception as exc:
                        LOGGER.warning("[Stage4] Watcher revision failed: %s", exc)

        LOGGER.info("[Stage4] Loop ended after %d iteration(s)", iteration)

        if self._parse_tool_calls(last_response_text):
            messages.append({
                "role": "user",
                "content": "[FINAL_ANSWER_REQUIRED] Output your Final Answer now. No more tool calls.",
            })
            response = await self._model(messages=messages, structured_model=structured_model, **kwargs)
            if inspect.isasyncgen(response):
                chunks = []
                async for item in response:
                    chunks.append(self._extract_text(item))
                last_response_text = "".join(chunks).strip()
            else:
                last_response_text = self._extract_text(response)

        return last_response_text

    def _build_iteration_prompt(self, live_plan: str, iteration: int) -> str:
        return f"""# Current Live Plan (Iteration {iteration})

Read the plan below and execute the next pending step.

```plan
{live_plan}
```

Execute the next step by outputting a [TOOL_CALL] block, or output Final Answer if done."""

    @staticmethod
    def _parse_tool_calls(text: str) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        segments = text.split("[TOOL_CALL]")
        TOP_LEVEL_KEYS = {"tool", "query", "url", "format", "expression", "max_results", "provider", "fallback_queries", "min_results"}

        for segment in segments[1:]:
            if "[/TOOL_CALL]" not in segment:
                continue
            body = segment.split("[/TOOL_CALL]", 1)[0].strip()
            lines = body.splitlines()
            tool_name = ""
            args: dict[str, Any] = {}

            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                if not stripped or ":" not in stripped:
                    i += 1
                    continue

                key, val = stripped.split(":", 1)
                key = key.strip()
                val = val.strip()

                if key == "tool":
                    tool_name = val
                    i += 1
                elif key == "code":
                    code_lines: list[str] = []
                    if val:
                        try:
                            parsed_code = json.loads(val)
                            if isinstance(parsed_code, str):
                                code_lines.append(parsed_code)
                            else:
                                code_lines.append(val)
                        except Exception:
                            code_lines.append(val)
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        next_stripped = next_line.strip()
                        if not next_stripped:
                            code_lines.append("")
                            i += 1
                            continue
                        if ":" in next_stripped:
                            potential_key = next_stripped.split(":", 1)[0].strip()
                            if potential_key in TOP_LEVEL_KEYS:
                                break
                            if not next_line.startswith((' ', '\t')) and potential_key.isidentifier():
                                break
                        code_lines.append(next_line.rstrip())
                        i += 1
                    raw_code = "\n".join(code_lines)
                    args["code"] = textwrap.dedent(raw_code).strip()
                else:
                    try:
                        args[key] = json.loads(val)
                    except Exception:
                        args[key] = val
                    i += 1

            if tool_name:
                calls.append({"tool": tool_name, "args": args})
        return calls

    @staticmethod
    def _format_tool_result(call: dict[str, Any], result: ToolResult) -> str:
        parts = [
            "[TOOL_RESULT]",
            f"tool: {call.get('tool', '')}",
        ]
        if result.output:
            parts.append(f"output: {result.output}")
        if result.error:
            parts.append(f"error: {result.error}")
        return "\n".join(parts)

    @staticmethod
    def _append_tool_log(
        finish_form_path: str,
        iteration: int,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_output: str | None,
        tool_error: str | None,
    ) -> None:
        existing = read_form_section(finish_form_path, marker_name="STAGE4_TOOL_CALLS") or ""
        if existing == "`待填写`":
            existing = ""

        args_str = json.dumps(tool_args, ensure_ascii=False, indent=2)
        entry = f"""
### Iteration {iteration} | Tool: {tool_name}
**Args:**
```json
{args_str}
```
**Output:** {tool_output or '(none)'}
**Error:** {tool_error or '(none)'}
"""
        new_content = existing.strip() + "\n" + entry.strip() if existing.strip() else entry.strip()
        update_form_section(
            finish_form_path,
            marker_name="STAGE4_TOOL_CALLS",
            content=new_content,
            header="### 1. Execution Log",
        )

    async def analyze_text(self, **kwargs: Any) -> str:
        response = await self.analyze(**kwargs)

        if inspect.isasyncgen(response):
            chunks: list[str] = []
            async for item in response:
                chunks.append(self._extract_text(item))
            result_text = "".join(chunks).strip()
        else:
            result_text = self._extract_text(response)

        return result_text


__all__ = [
    "Stage4ExecutorAgent",
]
