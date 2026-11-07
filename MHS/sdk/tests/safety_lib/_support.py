"""Shared paths and fixtures for the safety-library tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SDK = HERE.parents[1]                 # MHS/sdk
MHS_ROOT = SDK.parent                 # MHS
SCHEMA_DIR = MHS_ROOT / "schema"
EXAMPLES = SCHEMA_DIR / "examples"
VALID = EXAMPLES / "valid"
INVALID = EXAMPLES / "invalid"
CAPABILITIES = MHS_ROOT / "spec" / "capabilities.json"


def load_json(path: Path) -> Any:
    """Return the parsed JSON document at ``path``."""
    return json.loads(path.read_text(encoding="utf-8"))


def expected_failures() -> list[dict[str, Any]]:
    """The cases of ``examples/invalid/expected-failures.json``."""
    return load_json(INVALID / "expected-failures.json")["cases"]


def valid_manifests() -> dict[str, dict[str, Any]]:
    """The valid example device manifests, keyed by device id."""
    out = {}
    for path in sorted(VALID.glob("device.*.json")):
        document = load_json(path)
        out[document["device_id"]] = document
    return out


def unescape(token: str) -> str:
    """Unescape one JSON pointer token."""
    return token.replace("~1", "/").replace("~0", "~")


def pointer_tokens(pointer: str) -> list[str]:
    """Split an RFC 6901 pointer into unescaped tokens."""
    return [unescape(part) for part in pointer.split("/")[1:]] if pointer else []
