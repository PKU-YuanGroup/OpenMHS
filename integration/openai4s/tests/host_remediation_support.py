"""Shared helpers for the HOST-001..004 remediation tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_SRC = REPO_ROOT / "MHS" / "sdk" / "src"


def child_pythonpath() -> str:
    parts = [str(SDK_SRC)]
    if os.environ.get("PYTHONPATH"):
        parts.append(os.environ["PYTHONPATH"])
    return os.pathsep.join(parts)


def connector_env() -> dict[str, str]:
    """``env`` of a test connector row.

    OpenAI4S starts MCP connectors with a least-privilege environment, so the
    source trees and the no-bytecode setting must be declared on the row.
    """
    return {"PYTHONPATH": child_pythonpath(), "PYTHONDONTWRITEBYTECODE": "1"}


def write_settings(
    directory: Path,
    url: str,
    *,
    endpoint_id: str = "hw",
    enabled: bool = True,
    allow_hardware: bool = False,
    estop_devices: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"mhs-{endpoint_id}-{int(enabled)}-{int(allow_hardware)}.json"
    document: dict[str, Any] = {
        "enabled": bool(enabled),
        "allow_hardware": bool(allow_hardware),
        "endpoints": [{"id": endpoint_id, "url": url, "label": endpoint_id}],
        "command_timeout_ms": 8000,
        "command_journal": str(Path(directory) / "commands.jsonl"),
        "host_ledger": str(Path(directory) / "host-ledger.jsonl"),
        "evidence_log": str(Path(directory) / "evidence.jsonl"),
    }
    if estop_devices is not None:
        document["estop_devices"] = list(estop_devices)
    if extra:
        document.update(extra)
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return path


def connector_config(
    url: str,
    config_path: str | os.PathLike[str],
    *,
    connector_id: str = "mhs-hw",
    timeout: float = 15.0,
    extra_command: list[str] | None = None,
    operator_tools: bool = False,
) -> dict[str, Any]:
    """A connector row; ``operator_tools`` builds the operator route's command line."""
    command = [
        sys.executable,
        "-m",
        "mhs.mcp",
        "--endpoint",
        url,
        "--config",
        str(config_path),
    ]
    if operator_tools:
        command.append("--operator-tools")
    if extra_command:
        command = list(extra_command)
    return {
        "id": connector_id,
        "command": command,
        "transport": "stdio",
        "timeout": timeout,
        "env": connector_env(),
    }


def result_structured(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("raw") or {}
    structured = raw.get("structuredContent")
    return dict(structured) if isinstance(structured, dict) else {}


def result_code(response: dict[str, Any]) -> str | None:
    structured = result_structured(response)
    error = structured.get("mhs_error")
    if isinstance(error, dict):
        return error.get("mhs_code")
    return None


def result_receipt(response: dict[str, Any]) -> dict[str, Any] | None:
    structured = result_structured(response)
    for key in ("receipt", "estop", "reset"):
        receipt = structured.get(key)
        if isinstance(receipt, dict) and receipt.get("receipt_id"):
            return dict(receipt)
    receipt = structured.get("receipt")
    return dict(receipt) if isinstance(receipt, dict) else None


def find_capability_tool(tools: list[dict[str, Any]], capability_id: str) -> dict[str, Any]:
    for tool in tools:
        marker = tool.get("x-mhs") if isinstance(tool.get("x-mhs"), dict) else {}
        if marker.get("capability_id") == capability_id:
            return tool
    raise AssertionError(f"capability tool for {capability_id!r} not advertised")


__all__ = [
    "REPO_ROOT",
    "SDK_SRC",
    "child_pythonpath",
    "connector_config",
    "connector_env",
    "find_capability_tool",
    "result_code",
    "result_receipt",
    "result_structured",
    "write_settings",
]
