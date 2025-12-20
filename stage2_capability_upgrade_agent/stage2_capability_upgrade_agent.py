# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from capability_upgrade_agent.capability_upgrade_agent import (
    CapabilityUpgradeAgent,
    CapabilityUpgradeConfig,
)
from workflow.finish_form_utils import update_form_section

PROMPT_PATH = Path(__file__).with_name("thinking.md")
STRATEGY_LIBRARY_DIR = PROJECT_ROOT / "strategy_library"
STRATEGY_LIBRARY_FILE = STRATEGY_LIBRARY_DIR / "strategy.md"


@dataclass(slots=True)
class Stage2CapabilityUpgradeConfig(CapabilityUpgradeConfig):
    library_file: str | None = str(STRATEGY_LIBRARY_FILE)
    auto_apply_patch: bool = False


class Stage2CapabilityUpgradeAgent(CapabilityUpgradeAgent):
    agent_name: str = "Stage2CapabilityUpgradeAgent"
    agent_stage: str = "stage2"
    agent_function: str = "strategy_upgrade"
    _DECISION_PATTERN = re.compile(r"^DECISION:\s*(?P<value>\w+)", re.IGNORECASE | re.MULTILINE)
    _ACTION_PATTERN = re.compile(r"^ACTION:\s*(?P<value>[a-z_]+)", re.IGNORECASE | re.MULTILINE)
    _CATEGORY_PATTERN = re.compile(r"^CATEGORY:\s*(?P<value>[A-Z])", re.IGNORECASE | re.MULTILINE)
    _TARGET_PATTERN = re.compile(r"^TARGET_ID:\s*(?P<value>[A-Z0-9\-]+)", re.IGNORECASE | re.MULTILINE)
    _REFERENCE_PATTERN = re.compile(r"^REFERENCE_IDS?:\s*(?P<value>[A-Z0-9,\-\s]+)", re.IGNORECASE | re.MULTILINE)
    _JUSTIFICATION_ENTRY = re.compile(
        r"^(?P<key>coverage_gap|reuse_failure|new_value)\s*:\s*(?P<value>.+)$",
        re.IGNORECASE | re.MULTILINE,
    )
    _STRATEGY_ID_PATTERN = re.compile(r"^####\s+.*\((?P<id>[A-Z][A-Z0-9\-]+)\)\s*$", re.MULTILINE)
    _CATEGORY_HEADER_PATTERN = re.compile(r"^###\s+(?P<letter>[A-Z])\.", re.MULTILINE)

    def __init__(
        self,
        config: Stage2CapabilityUpgradeConfig | None = None,
        **overrides: Any,
    ) -> None:
        config_data = asdict(config or Stage2CapabilityUpgradeConfig())
        config_data.update(overrides)

        self._max_new_per_category = int(config_data.pop("max_new_per_category", 1) or 1)
        self._min_reference_ids = int(config_data.pop("min_reference_ids", 2) or 2)
        self._required_justifications: Tuple[str, ...] = ("coverage_gap", "reuse_failure", "new_value")
        self._session_new_counts: Dict[str, int] = defaultdict(int)

        if not config_data.get("library_file"):
            config_data["library_file"] = str(STRATEGY_LIBRARY_FILE)

        stage2_config = Stage2CapabilityUpgradeConfig(**config_data)
        super().__init__(config=stage2_config)

    def _compose_default_system_prompt(self) -> str | None:
        template = self._load_prompt_template()
        library_snapshot = self._library_snapshot

        if template and library_snapshot:
            return f"{template}\n\n## Current Strategy Library Snapshot\n\n{library_snapshot}"
        if template:
            return template
        return library_snapshot

    @staticmethod
    def _load_prompt_template() -> str | None:
        if not PROMPT_PATH.exists():
            return None
        content = PROMPT_PATH.read_text(encoding="utf-8").strip()
        return content or None

    async def evaluate_text(self, **kwargs: Any) -> str:
        finish_form_path = kwargs.pop("finish_form_path", None)
        finish_form_marker = kwargs.pop("finish_form_marker", "STAGE2C_ANALYSIS")
        finish_form_header = kwargs.pop(
            "finish_form_header",
            "## Stage 2-C: Capability Upgrade Evaluation",
        )

        result_text = await super().evaluate_text(**kwargs)
        patch_markdown = self.last_patch_markdown
        decision_info = self._parse_decision_metadata(result_text)

        applied = False
        apply_reason = ""

        if decision_info.get("decision") == "APPLY" and patch_markdown:
            should_apply, apply_reason = self._should_apply_patch(decision_info, patch_markdown)
            if should_apply:
                self.apply_patch(patch_markdown)
                new_category = decision_info.get("new_category")
                if new_category:
                    self._session_new_counts[new_category] += 1
                applied = True
            else:
                self._last_patch_markdown = None
                self._last_applied_path = None
        else:
            if not decision_info.get("decision"):
                apply_reason = "missing decision header"
            elif decision_info.get("decision") != "APPLY":
                apply_reason = f"decision={decision_info.get('decision')}"
            elif not patch_markdown:
                apply_reason = "no patch content detected"
            self._last_patch_markdown = None
            self._last_applied_path = None

        status_line = (
            f"AUTO_APPLY_STATUS: {'applied' if applied else 'skipped'}"
            + (f" ({apply_reason})" if apply_reason else "")
        )
        if "AUTO_APPLY_STATUS:" not in result_text:
            result_text = result_text.rstrip() + "\n\n" + status_line

        if finish_form_path:
            update_form_section(
                finish_form_path,
                marker_name=finish_form_marker,
                content=result_text,
                header=finish_form_header,
            )

        return result_text

    def _parse_decision_metadata(self, text: str) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        if not text:
            return metadata

        decision_match = self._DECISION_PATTERN.search(text)
        if decision_match:
            metadata["decision"] = decision_match.group("value").strip().upper()

        action_match = self._ACTION_PATTERN.search(text)
        if action_match:
            metadata["action"] = action_match.group("value").strip().lower()

        category_match = self._CATEGORY_PATTERN.search(text)
        if category_match:
            metadata["category"] = category_match.group("value").strip().upper()

        target_match = self._TARGET_PATTERN.search(text)
        if target_match:
            metadata["target_id"] = target_match.group("value").strip().upper()

        reference_match = self._REFERENCE_PATTERN.search(text)
        if reference_match:
            refs = [
                item.strip().upper()
                for item in reference_match.group("value").split(",")
                if item.strip()
            ]
            metadata["reference_ids"] = refs
        else:
            metadata["reference_ids"] = []

        justification: Dict[str, str] = {}
        for match in self._JUSTIFICATION_ENTRY.finditer(text):
            key = match.group("key").strip().lower()
            justification[key] = match.group("value").strip()
        metadata["justification"] = justification

        reason_match = re.search(r"^REASON:\s*(?P<value>.+)$", text, re.IGNORECASE | re.MULTILINE)
        if reason_match:
            metadata["reason"] = reason_match.group("value").strip()

        return metadata

    def _should_apply_patch(self, metadata: Dict[str, Any], patch: str) -> Tuple[bool, str]:
        action = (metadata.get("action") or "").lower()
        if action not in {"create_new", "enhance_existing"}:
            return False, f"unsupported action: {action or 'missing'}"

        justification: Dict[str, str] = metadata.get("justification") or {}
        for key in self._required_justifications:
            if not justification.get(key):
                return False, f"missing justification for {key}"

        reference_ids: List[str] = metadata.get("reference_ids") or []
        if len(reference_ids) < self._min_reference_ids:
            return False, "insufficient reference_ids to prove novelty"

        existing_ids = self._read_existing_strategy_ids()
        patch_info = self._parse_patch_metadata(patch)

        if action == "create_new":
            new_id = patch_info.get("primary_id")
            if not new_id:
                return False, "unable to locate new strategy id in patch"
            if new_id in existing_ids:
                return False, f"strategy id {new_id} already exists"
            category_letter = new_id[0]
            if self._session_new_counts[category_letter] >= self._max_new_per_category:
                return False, f"category {category_letter} reached new strategy quota"
            metadata["new_category"] = category_letter
            return True, f"accepted new strategy {new_id}"

        target_id = metadata.get("target_id")
        if not target_id:
            return False, "missing target_id for enhancement action"
        if target_id not in existing_ids:
            return False, f"target strategy {target_id} not found"
        metadata["new_category"] = target_id[0]
        return True, f"enhanced existing strategy {target_id}"

    def _parse_patch_metadata(self, patch: str) -> Dict[str, Optional[str]]:
        info: Dict[str, Optional[str]] = {"primary_id": None, "category_letter": None}
        if not patch:
            return info

        id_match = self._STRATEGY_ID_PATTERN.search(patch)
        if id_match:
            info["primary_id"] = id_match.group("id").strip().upper()

        cat_match = self._CATEGORY_HEADER_PATTERN.search(patch)
        if cat_match:
            info["category_letter"] = cat_match.group("letter").strip().upper()

        return info

    @staticmethod
    def _read_existing_strategy_ids() -> Set[str]:
        if not STRATEGY_LIBRARY_FILE.exists():
            return set()
        text = STRATEGY_LIBRARY_FILE.read_text(encoding="utf-8")
        ids = {
            match.group(1).strip().upper()
            for match in re.finditer(r"\(([A-Z][A-Z0-9\-]+)\)", text)
        }
        return ids

    def _load_library_snapshot(self, max_chars: int | None) -> str | None:
        if not STRATEGY_LIBRARY_FILE.exists():
            return None

        text = STRATEGY_LIBRARY_FILE.read_text(encoding="utf-8").strip()
        if not text:
            return None

        if max_chars is not None and len(text) > max_chars:
            truncated = text[: max_chars].rstrip()
            truncated += "\n\n...[Content truncated]..."
            return truncated
        return text


__all__ = [
    "Stage2CapabilityUpgradeAgent",
    "Stage2CapabilityUpgradeConfig",
]
