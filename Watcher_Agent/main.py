# -*- coding: utf-8 -*-
"""Command-line interface for running WatcherAgent."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from getpass import getpass
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

try:
    from .Watcher_agent import WatcherAgent
except ImportError:  # pragma: no cover
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from Watcher_agent import WatcherAgent  # type: ignore  # pylint: disable=import-error
from config import ModelConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

VALID_STAGES = {"stage1", "stage2a", "stage2b", "stage3", "stage4"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="watcher-agent",
        description="Run the cross-stage WatcherAgent for quality auditing.",
    )
    parser.add_argument(
        "--stage",
        required=True,
        choices=sorted(VALID_STAGES),
        help="Stage name to audit (stage1/stage2a/stage2b/stage3/stage4).",
    )
    parser.add_argument(
        "--payload",
        type=Path,
        help="Path to a JSON file containing additional audit parameters.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="DeepSeek API key (falls back to DEEPSEEK_API_KEY environment variable).",
    )
    parser.add_argument(
        "--model",
        default="deepseek-chat",
        help="DeepSeek model name (default: deepseek-chat).",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming responses (default: disabled).",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.deepseek.com",
        help="DeepSeek API base URL (default: https://api.deepseek.com).",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="medium",
        help="Reasoning effort level for the DeepSeek model (default: medium).",
    )
    parser.add_argument(
        "--system-prompt",
        dest="system_prompt",
        help="Optional custom system prompt. If omitted, the default prompt from watcher.md is used.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON payload from STDIN (ignored when --payload is provided).",
    )
    return parser.parse_args()


def _ensure_api_key(cli_api_key: str | None) -> str:
    api_key = cli_api_key or os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    while not api_key:
        api_key = getpass("请输入 DeepSeek API Key (回车确认): ").strip()
    return api_key


def _load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload:
        path = args.payload.expanduser().resolve()
        text = path.read_text(encoding="utf-8")
        return json.loads(text)

    if args.stdin:
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)

    return {}


async def _run_once(agent: WatcherAgent, *, stage: str, payload: Mapping[str, Any]) -> str:
    normalized_payload = dict(payload)
    normalized_payload["stage_name"] = stage
    return await agent.audit_text(**normalized_payload)


def main() -> None:
    args = _parse_args()

    config = ModelConfig(
        api_key=_ensure_api_key(args.api_key),
        model_name=args.model,
        stream=args.stream,
        base_url=args.base_url,
        reasoning_effort=args.reasoning_effort,
    )

    agent = WatcherAgent(config=config, system_prompt=args.system_prompt)
    payload = _load_payload(args)

    try:
        result = asyncio.run(_run_once(agent, stage=args.stage, payload=payload))
    except KeyboardInterrupt:
        print("\n已中断。")
        return
    except Exception as exc:  # pylint: disable=broad-except
        print(f"执行失败: {exc}")
        raise

    print(result or "<无结果>")


if __name__ == "__main__":
    main()

