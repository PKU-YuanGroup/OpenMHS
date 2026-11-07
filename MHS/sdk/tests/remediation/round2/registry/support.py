"""Fixtures for the round-2 RREG-002 external-bindings regressions.

Only inert local Python objects are used; no network, device or subprocess.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from tests.remediation.bridge import support as base

#: The review's invalid "normalized" document: flattened entries that skip the
#: canonical ``binding`` wrapper, a future version, an empty adapter id, an
#: unknown top-level key and an unbounded timeout.
FLATTENED_DOCUMENT: dict[str, Any] = {
    "mhs_bindings": "999.0",
    "adapter_id": "",
    "unknown_top_field": True,
    "bindings": [
        {
            "device_id": "mhs://localhost:7401/robosuite/Lift",
            "capability_id": "cap.world.step.v1",
            "resource": "world",
            "bridge": "python-object",
            "kind": "declarative",
            "native": "set_target",
            "args": {
                "target": {
                    "from": "input.target",
                    "clamp": {"min": 0, "max": 10},
                }
            },
            "result": {"target": {"from": "output.target"}},
            "errors": [],
            "concurrency": "exclusive",
            "timeout_ms": 0,
        }
    ],
}

LIFT_TARGET = base.LIFT_TARGET


def canonical_document(*, timeout_ms: Any = 5000, clamp: bool = True) -> dict[str, Any]:
    """A valid canonical document bound to ``FakeLift.set_target``."""

    target_rule: dict[str, Any] = {"from": "input.target", "type": "integer"}
    if clamp:
        target_rule["clamp"] = {"min": 0, "max": 10}
    return {
        "mhs_bindings": "1.0",
        "adapter_id": "org.example.fake-lift",
        "bindings": [
            {
                "device_id": "mhs://localhost:7400/lab/lift",
                "capability_id": "cap.motion.set-target.v1",
                "resource": "lift",
                "binding": {
                    "bridge": "python-object",
                    "kind": "declarative",
                    "native": "set_target",
                    "args": {"target": target_rule},
                    "result": {"map": {"target": "output.target"}},
                    "errors": [
                        {
                            "native": "^AssertionError$",
                            "mhs_code": "MHS.DEVICE.PRECONDITION_UNMET",
                            "retryable": False,
                        }
                    ],
                    "concurrency": "exclusive",
                    "timeout_ms": timeout_ms,
                },
            }
        ],
    }


def with_timeout(value: Any) -> dict[str, Any]:
    document = canonical_document()
    document["bindings"][0]["binding"]["timeout_ms"] = value
    return document


def write_document(directory: str, document: dict[str, Any], name: str = "bindings.json") -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)
    return path



class TempDir:
    """Temporary directory rooted under the harness TMPDIR (round-2 runtime)."""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory(
            prefix="rreg002-", dir=os.environ.get("TMPDIR") or None
        )

    def __enter__(self) -> str:
        return self._dir.name

    def __exit__(self, *exc: object) -> None:
        self._dir.cleanup()

    def path(self, name: str = "bindings.json") -> str:
        return os.path.join(self._dir.name, name)


def spec_example() -> dict[str, Any]:
    """Extract the published MHS-006 §4.1 example (read-only)."""

    root = Path(__file__).resolve().parents[6]
    text = (root / "MHS" / "spec" / "06-adapters.md").read_text(encoding="utf-8")
    section = text.split("### 4.1 Shape", 1)[1]
    block = section.split("```json", 1)[1].split("```", 1)[0]
    return json.loads(block)


__all__ = [
    "FLATTENED_DOCUMENT",
    "LIFT_TARGET",
    "TempDir",
    "canonical_document",
    "spec_example",
    "with_timeout",
    "write_document",
]
