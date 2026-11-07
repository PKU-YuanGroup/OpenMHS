"""Dispatch-level presence probes for mandatory methods (SPEC-001 / PROTO-016).

The original check sent ``{}`` to every mandatory method and treated *any*
response other than ``METHOD_NOT_FOUND`` as proof of implementation.  The
reference server validates ``deadline_ms`` for blocking methods *before* it looks
the method up, so deleting ``mhs.operations.cancel`` or ``mhs.subscribe`` still
produced ``MHS.PROTOCOL.DEADLINE_INVALID`` and the suite counted the method as
present.

This module replaces that with one syntactically valid, non-mutating probe per
method.  Every probe:

* carries ``deadline_ms`` where the method is blocking (MHS-002 §3 flag **D**);
* uses a real session/device/resource for positive probes, and a well-formed
  but non-existent id for negative probes; and
* never changes device state, revision or evidence.

A probe reaches dispatch when the endpoint returns a result or a *method-specific
semantic* error.  A generic pre-dispatch rejection (deadline, JSON-RPC envelope)
is explicitly **not** evidence of presence, and ``METHOD_NOT_FOUND`` always means
the method is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mhs import canonical

__all__ = [
    "GENERIC_PRE_DISPATCH_CODES",
    "METHOD_PROBES",
    "PresenceProbe",
    "ProbeResult",
    "check_method_presence",
    "probe_method",
    "probe_table",
]

#: Rejections that happen before the method lookup on conforming servers.  They
#: prove nothing about whether the method exists and MUST NOT be counted.
GENERIC_PRE_DISPATCH_CODES: frozenset[str] = frozenset(
    {
        "MHS.PROTOCOL.DEADLINE_INVALID",
        "MHS.PROTOCOL.INVALID_REQUEST",
        "MHS.PROTOCOL.PARSE_ERROR",
        "MHS.PROTOCOL.BATCH_TOO_LARGE",
        "MHS.TRANSPORT.PROTOCOL_ERROR",
    }
)


@dataclass(frozen=True)
class PresenceProbe:
    """One method-presence probe.

    ``kind`` is ``"result"`` for a fully valid request that must succeed, and
    ``"semantic"`` for a well-formed request whose *content* is deliberately
    invalid (unknown operation, stream or capability).
    """

    method: str
    kind: str
    expected_codes: tuple[str, ...] = ()
    basis: str = ""


@dataclass
class ProbeResult:
    """Outcome of one probe: present, missing or inconclusive."""

    method: str
    status: str
    code: str | None = None
    detail: str = ""

    @property
    def present(self) -> bool:
        return self.status == "present"


METHOD_PROBES: dict[str, PresenceProbe] = {
    # -- CL1 ---------------------------------------------------------------
    "mhs.hello": PresenceProbe(
        "mhs.hello",
        "result",
        basis="MHS-002 §3 #1; PROTO-013",
    ),
    "mhs.devices.list": PresenceProbe(
        "mhs.devices.list",
        "result",
        basis="MHS-002 §3 #2; PROTO-021",
    ),
    "mhs.devices.get": PresenceProbe(
        "mhs.devices.get",
        "result",
        basis="MHS-002 §3 #3; PROTO-021",
    ),
    "mhs.schema.get": PresenceProbe(
        "mhs.schema.get",
        "result",
        basis="MHS-002 §3 #4; PROTO-022",
    ),
    "mhs.session.open": PresenceProbe(
        "mhs.session.open",
        "result",
        basis="MHS-002 §3 #5; SESS-001",
    ),
    "mhs.session.close": PresenceProbe(
        "mhs.session.close",
        "semantic",
        expected_codes=("MHS.SESSION.UNKNOWN",),
        basis="MHS-002 §5.3; unknown session id reaches dispatch",
    ),
    "mhs.resource.read": PresenceProbe(
        "mhs.resource.read",
        "result",
        basis="MHS-002 §3 #8; PROTO-023",
    ),
    "mhs.evidence.export": PresenceProbe(
        "mhs.evidence.export",
        "result",
        basis="MHS-002 §3 #22; EVID-015",
    ),
    # -- CL2 ---------------------------------------------------------------
    "mhs.command": PresenceProbe(
        "mhs.command",
        "semantic",
        expected_codes=("MHS.CAPABILITY.UNKNOWN", "MHS.CAPABILITY.NOT_BOUND"),
        basis="MHS-002 §3 #10; unknown but well-formed capability reaches dispatch",
    ),
    "mhs.subscribe": PresenceProbe(
        "mhs.subscribe",
        "semantic",
        expected_codes=("MHS.PROTOCOL.INVALID_PARAMS",),
        basis="MHS-002 §8.1; invalid stream reaches dispatch",
    ),
    "mhs.unsubscribe": PresenceProbe(
        "mhs.unsubscribe",
        "semantic",
        expected_codes=("MHS.SESSION.UNKNOWN",),
        basis="MHS-002 §8.2; unknown subscription id reaches dispatch",
    ),
    "mhs.operations.get": PresenceProbe(
        "mhs.operations.get",
        "semantic",
        expected_codes=("MHS.OPERATION.UNKNOWN",),
        basis="MHS-002 §7.2 / PROTO-030; unknown operation id reaches dispatch",
    ),
    # -- CL3 ---------------------------------------------------------------
    "mhs.operations.cancel": PresenceProbe(
        "mhs.operations.cancel",
        "semantic",
        expected_codes=("MHS.OPERATION.UNKNOWN",),
        basis="MHS-002 §7.4; unknown operation id reaches dispatch",
    ),
    "mhs.safety.status": PresenceProbe(
        "mhs.safety.status",
        "result",
        basis="MHS-002 §3 #18; SAFE-001",
    ),
}


class _ProbeUnavailable(RuntimeError):
    """The context needed to build a syntactically valid probe is missing."""


def _session(ctx: Any) -> str:
    try:
        return str(ctx.ensure_session())
    except BaseException as exc:  # noqa: BLE001 - reported as an inconclusive probe
        raise _ProbeUnavailable(f"no usable session: {getattr(exc, 'code', None) or exc!r}") from exc


def _primary_device(ctx: Any) -> Mapping[str, Any]:
    device = getattr(ctx, "primary_device", None)
    if not isinstance(device, Mapping) or not device.get("device_id"):
        raise _ProbeUnavailable("no primary device")
    return device


def _primary_capability(ctx: Any) -> Mapping[str, Any]:
    capability = getattr(ctx, "primary_capability", None)
    if not isinstance(capability, Mapping) or not capability.get("capability_id"):
        raise _ProbeUnavailable("no primary capability")
    return capability


def _probe_params(ctx: Any, method: str, probe: PresenceProbe) -> dict[str, Any]:
    """Build a syntactically valid request body for ``method``."""

    if method == "mhs.hello":
        return {
            "client": {"name": "mhs-conformance-presence", "version": "1.0.0"},
            "protocol_versions": ["1.0"],
        }
    if method == "mhs.devices.list":
        return {"detail": "summary"}
    if method == "mhs.devices.get":
        return {"device_id": _primary_device(ctx)["device_id"]}
    if method == "mhs.schema.get":
        return {"ref": _primary_capability(ctx)["capability_id"]}
    if method == "mhs.session.open":
        return {
            "principal": {"id": "mhs-conformance", "kind": "service"},
            "device_ids": [str(_primary_device(ctx)["device_id"])],
            "capabilities": [str(_primary_capability(ctx)["capability_id"])],
            "ttl_s": 60,
        }
    if method == "mhs.session.close":
        return {"session_id": "mhs_s_" + canonical.ulid(), "reason": "presence probe"}
    if method == "mhs.resource.read":
        return {
            "session_id": _session(ctx),
            "device_id": _primary_device(ctx)["device_id"],
            "resource_id": str(getattr(ctx, "primary_resource", "") or "state"),
            "deadline_ms": 5_000,
        }
    if method == "mhs.evidence.export":
        return {"session_id": _session(ctx)}
    if method == "mhs.command":
        return {
            "session_id": _session(ctx),
            "device_id": _primary_device(ctx)["device_id"],
            "capability_id": "cap.x.mhs-conformance.absent.v1",
            "input": {},
            "command_id": canonical.ulid(),
            "deadline_ms": 5_000,
        }
    if method == "mhs.subscribe":
        return {
            "session_id": _session(ctx),
            "streams": ["mhs-conformance-unknown-stream"],
            "deadline_ms": 5_000,
        }
    if method == "mhs.unsubscribe":
        return {
            "session_id": _session(ctx),
            "subscription_id": "sub_mhs_conformance_absent",
        }
    if method in ("mhs.operations.get", "mhs.operations.cancel"):
        return {
            "session_id": _session(ctx),
            "operation_id": canonical.ulid(),
            "deadline_ms": 5_000,
        }
    if method == "mhs.safety.status":
        return {"device_id": _primary_device(ctx)["device_id"], "deadline_ms": 5_000}
    raise _ProbeUnavailable(f"no probe parameter builder for {method}")


def _close_probe_session(client: Any, result: Any) -> None:
    if not isinstance(result, Mapping):
        return
    session_id = result.get("session_id")
    if not session_id:
        return
    try:
        client.request("mhs.session.close", {"session_id": str(session_id), "reason": "presence probe"})
    except BaseException:  # noqa: BLE001 - cleanup is best effort and never a verdict
        pass


def probe_method(ctx: Any, method: str) -> ProbeResult:
    """Run one presence probe and classify the response."""

    probe = METHOD_PROBES.get(method)
    if probe is None:
        return ProbeResult(method, "unverified", detail=f"no presence probe registered for {method}")
    try:
        params = _probe_params(ctx, method, probe)
    except _ProbeUnavailable as exc:
        return ProbeResult(method, "unverified", detail=str(exc))
    try:
        result = ctx.client.request(method, params)
    except BaseException as exc:  # noqa: BLE001 - a response is a verdict
        code = getattr(exc, "code", None)
        if code == "MHS.PROTOCOL.METHOD_NOT_FOUND":
            return ProbeResult(method, "missing", code=code, detail="METHOD_NOT_FOUND")
        if code in GENERIC_PRE_DISPATCH_CODES:
            return ProbeResult(
                method,
                "unverified",
                code=code,
                detail="generic pre-dispatch rejection is not evidence of presence",
            )
        if probe.kind == "semantic":
            # Any other structured rejection is a method-specific response: the
            # handler was dispatched.  Record unexpected codes for the reviewer.
            detail = "dispatch-level semantic response"
            if probe.expected_codes and code not in probe.expected_codes:
                detail = f"dispatch-level response {code!r} (expected one of {list(probe.expected_codes)})"
            return ProbeResult(method, "present", code=code, detail=detail)
        return ProbeResult(method, "unverified", code=code, detail="valid request was rejected")
    if method == "mhs.session.open":
        _close_probe_session(ctx.client, result)
    return ProbeResult(method, "present", detail="result returned")


def check_method_presence(ctx: Any, methods: Any) -> tuple[list[str], list[str], list[ProbeResult]]:
    """Probe ``methods``; return ``(missing, unverified, results)`` in input order."""

    missing: list[str] = []
    unverified: list[str] = []
    results: list[ProbeResult] = []
    for method in methods:
        outcome = probe_method(ctx, method)
        results.append(outcome)
        if outcome.status == "missing":
            missing.append(method)
        elif outcome.status != "present":
            unverified.append(method)
    return missing, unverified, results


def probe_table(results: Any) -> str:
    """Compact, report-friendly rendering of probe results."""

    parts = []
    for item in results:
        code = item.code or item.status
        parts.append(f"{item.method}={code}")
    return ", ".join(parts)
