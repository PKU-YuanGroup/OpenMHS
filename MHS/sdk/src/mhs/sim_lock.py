"""``sim.lock.json``: the record of a simulator package's passing gate on its real upstream (``--backend sim``).

The run itself happens outside CI (an isolated environment with the upstream installed at the pinned commit); this
module only reads the record and decides whether it still describes the package. A record is *fresh* when its
``fake_gate_digest`` equals ``RESULT.json`` ``gate.digest`` and its upstream commit equals the card's pin; any change
of the driver, the SDK result or the pin makes it stale, and the market then ignores it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SIM_LOCK_FILE = "sim.lock.json"
SIM_LOCK_SCHEMA = "sim-lock.schema.json"

__all__ = ["SIM_LOCK_FILE", "SIM_LOCK_SCHEMA", "read_sim_lock", "staleness", "market_sim"]


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_sim_lock(package_dir: Path) -> dict[str, Any] | None:
    """The parsed record, or ``None`` when the package has none (or it is not a JSON object)."""
    document = _json(Path(package_dir) / SIM_LOCK_FILE)
    return document if isinstance(document, dict) else None


def staleness(package_dir: Path, lock: dict[str, Any] | None = None) -> list[str]:
    """Why the record no longer describes the package (empty: fresh). No record gives no reasons."""
    package_dir = Path(package_dir)
    lock = read_sim_lock(package_dir) if lock is None else lock
    if lock is None:
        return []
    reasons = []
    result = _json(package_dir / "RESULT.json") or {}
    digest = ((result.get("gate") or {}) if isinstance(result, dict) else {}).get("digest")
    if result.get("status") != "pass" if isinstance(result, dict) else True:
        reasons.append("RESULT.json does not say pass")
    if lock.get("fake_gate_digest") != digest:
        reasons.append(f"fake_gate_digest {lock.get('fake_gate_digest')} is not RESULT.json gate.digest {digest}")
    task = _json(package_dir / "task.json") or {}
    pin = ((task.get("upstream") or {}) if isinstance(task, dict) else {}).get("commit")
    recorded = (lock.get("upstream") or {}).get("commit") if isinstance(lock.get("upstream"), dict) else None
    if recorded != pin:
        reasons.append(f"upstream.commit {recorded} is not the card's pin {pin}")
    return reasons


def market_sim(package_dir: Path) -> dict[str, Any] | None:
    """The market's ``sim`` field for a fresh record, else ``None``."""
    lock = read_sim_lock(package_dir)
    if lock is None or staleness(package_dir, lock):
        return None
    gate = lock.get("gate") or {}
    environment = lock.get("environment") or {}
    if gate.get("evidence_state") != "contract_checked":
        return None
    return {"status": "contract_checked", "platform": environment.get("platform"),
            "python": environment.get("python"), "checked_at": lock.get("checked_at")}
