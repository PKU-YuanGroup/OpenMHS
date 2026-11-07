"""Shared types of the conformance suite: levels, verdicts, test cases and code helpers.

:class:`TestCase` carries, besides its id, level and implementation:

``required``
    ``True``/``False`` or a predicate over the suite context.  A required test
    that does not pass caps the level (CON-018/CON-027).
``group``
    The fixture group the test runs in.  An in-process run
    (:func:`mhs.conformance.inprocess.run_suite_inprocess`) gives every
    mutating group (``OP``, ``SAFE``, ``FID``) its own fresh endpoint, so no
    test depends on another group's state (CON-022).  ``base`` tests are
    read-only and share the discovery instance.
``actuation``
    ``none`` (reads, discovery, static checks), ``inert`` (commands no device
    can execute: an unknown capability or operation id, or a replay-mode
    device), ``negative`` (valid-looking commands built to be refused before
    any effect, which a device *would* execute if the endpoint failed to
    refuse them) or ``effect`` (commands meant to act).  Without the operator's
    ``allow_actuation``, hardware and hybrid subjects get ``none`` and
    ``inert`` tests, and ``negative`` tests only when the in-process harness
    blocks every hardware bridge (CON-031); ``read_only`` runs ``none`` tests
    only (CON-022).
``post``
    Suite self-checks that inspect the whole run (CON-031/CON-032); they run
    after every other test.
``estops``
    The test engages the e-stop.  A declared terminal e-stop (CORE-087)
    cannot be undone, so an in-process run gives every test after one a new
    endpoint, and a run over one shared endpoint runs these tests after every
    other test that sends a command (CON-022).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

__all__ = [
    "ACTUATION_KINDS",
    "CODE_ALIASES",
    "GROUPS",
    "LEVELS",
    "ENDPOINT_PROFILES",
    "PROFILES",
    "TestCase",
    "TestOutcome",
    "code_matches",
    "normalize_code",
]

LEVELS = ("CL0", "CL1", "CL2", "CL3", "CL4", "CL5")
#: Every profile name of MHS-001 §2 (the report schema enum).
PROFILES = ("MHS-Sim", "MHS-Device", "MHS-Bridge", "MHS-Host", "MHS-Registry")
#: Profiles an endpoint subject may claim (CON-004); the only ones this runner serves.
ENDPOINT_PROFILES = ("MHS-Sim", "MHS-Device", "MHS-Bridge")
GROUPS = ("base", "OP", "SAFE", "FID")
ACTUATION_KINDS = ("none", "inert", "negative", "effect")


@dataclass
class TestOutcome:
    """One test verdict, serialisable as a report ``tests[]`` entry."""

    __test__ = False  # not a unittest case

    status: str  # "pass" | "fail" | "skip" | "warn"
    detail: str = ""
    mhs_code: str | None = None
    request_digest: str | None = None
    response_digest: str | None = None
    note: str | None = None

    @classmethod
    def passed(cls, detail: str = "", **kwargs: Any) -> "TestOutcome":
        return cls("pass", detail=detail, **kwargs)

    @classmethod
    def failed(cls, detail: str = "", **kwargs: Any) -> "TestOutcome":
        return cls("fail", detail=detail, **kwargs)

    @classmethod
    def skipped(cls, detail: str = "", **kwargs: Any) -> "TestOutcome":
        return cls("skip", detail=detail, **kwargs)

    @classmethod
    def warned(cls, detail: str = "", **kwargs: Any) -> "TestOutcome":
        return cls("warn", detail=detail, **kwargs)


@dataclass
class TestCase:
    """A stable conformance test id and its implementation."""

    __test__ = False  # not a unittest case

    id: str
    name: str
    level: str
    fn: Callable[[Any], TestOutcome]
    required: bool | Callable[[Any], bool] = True
    profiles: tuple[str, ...] = PROFILES
    group: str = "base"
    actuation: str = "none"
    post: bool = False
    estops: bool = False

    def is_required(self, ctx: Any) -> bool:
        exempt = getattr(ctx, "exempt", None)
        if callable(exempt) and exempt(self.id):
            return False
        if callable(self.required):
            return bool(self.required(ctx))
        return bool(self.required)

    @property
    def always_required(self) -> bool:
        """True when the test is required in every context (a constant ``required=True``)."""
        return self.required is True

    def applies(self, profile: str) -> bool:
        return profile in self.profiles or not self.profiles


#: Legacy reference-SDK codes mapped onto the normative MHS/spec/errors.json names.
CODE_ALIASES: dict[str, str] = {
    "MHS.SCHEMA.INVALID_INPUT": "MHS.CAPABILITY.INPUT_INVALID",
    "MHS.SCHEMA.INVALID_STATE": "MHS.CAPABILITY.OUTPUT_INVALID",
    "MHS.SAFETY.PERMIT_REQUIRED": "MHS.SAFETY.APPROVAL_REQUIRED",
    "MHS.SAFETY.LIMIT_EXCEEDED": "MHS.SAFETY.ENVELOPE_VIOLATION",
    "MHS.SAFETY.SAFE_STATE_UNREACHABLE": "MHS.SAFETY.SAFE_STATE_UNREACHED",
    "MHS.SAFETY.RISK_CLASS_DENIED": "MHS.SAFETY.RISK_CLASS_BLOCKED",
    "MHS.CONFLICT.PRECONDITION": "MHS.DEVICE.PRECONDITION_UNMET",
    "MHS.CONFLICT.SNAPSHOT": "MHS.CONFLICT.SNAPSHOT_MISMATCH",
    "MHS.CONFLICT.LEASE": "MHS.CONFLICT.LEASE_CONFLICT",
    "MHS.DEVICE.UNSUPPORTED": "MHS.CAPABILITY.NOT_BOUND",
    "MHS.DEVICE.FAILED": "MHS.DEVICE.FAULTED",
    "MHS.DEVICE.NOT_FOUND": "MHS.DEVICE.UNKNOWN",
    "MHS.EVIDENCE.NOT_FOUND": "MHS.EVIDENCE.UNKNOWN",
    "MHS.EVIDENCE.CHAIN_INVALID": "MHS.EVIDENCE.CHAIN_BROKEN",
    "MHS.SESSION.NOT_FOUND": "MHS.SESSION.UNKNOWN",
    "MHS.SESSION.INVALID_TTL": "MHS.SESSION.UNKNOWN",
    "MHS.LIMIT.TOO_LARGE": "MHS.LIMIT.PAYLOAD_TOO_LARGE",
    "MHS.LIMIT.DEADLINE_INVALID": "MHS.PROTOCOL.DEADLINE_INVALID",
}


def normalize_code(code: str | None) -> str | None:
    """Map a legacy reference-SDK error code onto its normative MHS name."""

    if not code:
        return None
    text = str(code)
    if text in CODE_ALIASES:
        return CODE_ALIASES[text]
    try:
        from mhs.errors import normalize_code as _registry_normalize

        return _registry_normalize(text)
    except Exception:  # noqa: BLE001 - the registry is optional for a standalone suite
        return text


def code_matches(code: str | None, prefixes: Iterable[str]) -> bool:
    """True when ``code`` (normalised) equals or starts with one of ``prefixes``."""

    normalized = normalize_code(code)
    if not normalized:
        return False
    for prefix in prefixes:
        candidate = normalize_code(prefix) or prefix
        if normalized == candidate or normalized.startswith(candidate) or normalized.startswith(prefix):
            return True
    return False
