"""Capability-catalogue view for the registry tools (stdlib only).

Risk floors and verbs come from the normative catalogue through
:mod:`mhs.catalog` (``MHS/spec/capabilities.json``), never from a private
table: the registry, the runtime and conformance must agree on every class
(FIT-06, SC-01).  The repo's own SDK source tree is put on ``sys.path``; no
installed package is required.
"""

from __future__ import annotations

import functools
import os
import sys
from typing import Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
SDK_SRC = os.path.join(WORKSPACE, "MHS", "sdk", "src")
CAPABILITIES_JSON = os.path.join(WORKSPACE, "MHS", "spec", "capabilities.json")

if SDK_SRC not in sys.path:
    sys.path.insert(0, SDK_SRC)

from mhs import catalog as _catalog  # noqa: E402  (repo SDK, stdlib only)

RISK_ORDER = ("R0", "R1", "R2", "R3")


@functools.lru_cache(maxsize=1)
def catalog() -> "_catalog.Catalog":
    """The checkout's capability catalogue (an explicit path, so a stale wheel copy never wins)."""
    return _catalog.Catalog.load(CAPABILITIES_JSON)


def class_risk(capability_id: str) -> str | None:
    """``risk_class`` of a catalogued class, or None for extensions and unknown ids."""
    entry = catalog().get(capability_id)
    return entry.get("risk_class") if isinstance(entry, dict) else None


def risk_floor(capability_ids: Iterable[str]) -> str:
    """Highest class risk over the given capability ids (CAP-017); ``R0`` when none is catalogued."""
    return _catalog.risk_at_least(*(class_risk(cap) for cap in capability_ids))


def verb(capability_id: str) -> str | None:
    """The class verb (read, write or invoke), or None for extensions and unknown ids."""
    entry = catalog().get(capability_id)
    return entry.get("verb") if isinstance(entry, dict) else None
