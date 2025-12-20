# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any, AsyncGenerator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents import BaseAgent
from model import ChatResponse
from workflow.finish_form_utils import update_form_section

PROMPT_PATH = Path(__file__).with_name("selector.md")
STRATEGY_LIBRARY_DIR = PROJECT_ROOT / "strategy_library"


class CandidateSelectionAgent(BaseAgent):
    agent_name: str = "StrategyCandidateSelectionAgent"
    agent_stage: str = "stage2_candidates"
    agent_function: str = "candidate_selection"

    def _load_default_prompt(self) -> str | None:
        if not PROMPT_PATH.exists():
            return None

        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        strategy_sections: list[str] = []

        if STRATEGY_LIBRARY_DIR.exists() and STRATEGY_LIBRARY_DIR.is_dir():
            for strategy_file in sorted(STRATEGY_LIBRARY_DIR.glob("*.md")):
                data = strategy_file.read_text(encoding="utf-8").strip()
                if not data:
                    continue
                title = strategy_file.stem.replace("_", " ")
                strategy_sections.append(f"## Strategy Library: {title}\n\n{data}")

        if strategy_sections:
            merged_sections = "\n\n".join(strategy_sections).strip()
            if content:
                content = f"{content}\n\n{merged_sections}"
            else:
                content = merged_sections

        return content or None

    async def analyze_text(self, **kwargs: Any) -> str:
        finish_form_path = kwargs.pop("finish_form_path", None)
        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE2A_ANALYSIS")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## Stage 2-A: Candidate Strategies",
        )

        response = await self.analyze(**kwargs)

        if inspect.isasyncgen(response):
            chunks: list[str] = []
            async for item in response:
                chunks.append(self._extract_text(item))
            result_text = "".join(chunks).strip()
        else:
            result_text = self._extract_text(response)

        if finish_form_path:
            self._write_finish_form(
                finish_form_path,
                result_text,
                marker=finish_form_marker,
                header=finish_form_header,
            )

        return result_text

    @staticmethod
    def _write_finish_form(
        finish_form_path: str | Path,
        content: str,
        *,
        marker: str,
        header: str,
    ) -> None:
        update_form_section(
            finish_form_path,
            marker_name=marker,
            content=content,
            header=header,
        )


__all__ = [
    "CandidateSelectionAgent",
]
