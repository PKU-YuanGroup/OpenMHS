"""Trusted, device-bound MHS emergency stop at the integration boundary (HOST-002).

OpenAI4S dispatches ordinary MCP calls through ``CallMCPTool`` with
``requires_approval=True``.  A denied or unavailable permission decision returns
before ``MCPService`` is reached, so the software e-stop never leaves the host.
The spec's "the e-stop never sits behind an approval prompt" was therefore false
for the MCP-first path.

This module is the *narrow* trusted route that fixes it:

1. the MHS integration must be enabled (``enabled=true``) -- an operator action;
2. the endpoint must be one of the configured endpoints and the device must be
   on the configured emergency-stop allow-list (``estop_devices``; when empty,
   the device must be discovered on that configured endpoint).  An arbitrary
   connector, URL or device id is refused;
3. it calls ``mhs__estop`` through the caller's MCP transport.  At the stock
   host boundary that transport is the connector's own ``MCPService`` manager
   call (``hostroute.emergency_stop``), so this is the real host route; the
   standalone :func:`emergency_stop` helper opens the same
   ``MCPConnection`` directly.  Only the *ordinary tool-approval gate* is
   bypassed; connector authorization, the host policy (``enabled``), the
   endpoint/device allow-list and the endpoint's own safety envelope remain;
4. the request and its receipt are appended to the local hash-chained host
   ledger (``host_ledger``); a ledger failure is reported in ``audit_error`` but
   never prevents a stop.

The stock wiring is in ``openai4s/host_dispatch.py`` (the named trusted action
and the ``mcp_call`` e-stop exemption) and ``openai4s/host/mcp.py``
(``MCPService.call``/``MCPService.emergency_stop``); ``hostroute.py`` is the
adapter.  A GUI that invokes the ordinary ``mcp_call`` for ``mhs__estop`` on an
enabled MHS connector therefore reaches this route without an approval prompt.

E-stop is not a safety-rated channel: a hardware e-stop remains mandatory and
independent (MHS.SAFETY.NOT_CERTIFIED).
"""

from __future__ import annotations

from typing import Any, Mapping

from mhs import canonical

from .config import MHSConfig
from .host_evidence import HostLedger, HostLedgerError
from .mcp_invoke import MCPConnector, _mcp_error_payload
from .mcpconfig import connector_id

__all__ = ["EmergencyStopError", "emergency_stop", "emergency_stop_via"]


class EmergencyStopError(RuntimeError):
    """A refused or failed trusted e-stop, with a stable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        receipt: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.details = dict(details or {})
        self.receipt = dict(receipt) if isinstance(receipt, Mapping) else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.message,
            "mhs_code": self.code,
            "details": self.details,
            "receipt": self.receipt,
        }


def _policy_ready(config: MHSConfig) -> None:
    if not config.enabled:
        raise EmergencyStopError(
            "MHS.AUTH.FORBIDDEN",
            "the MHS integration is disabled (enabled=false); the trusted e-stop "
            "route is unavailable",
        )


def _endpoint(config: MHSConfig, endpoint_id: str):
    try:
        return config.endpoint(endpoint_id)
    except LookupError as exc:
        raise EmergencyStopError(
            "MHS.HOST.ENDPOINT_NOT_ALLOWED",
            f"endpoint {endpoint_id!r} is not in the configured allow-list: {exc}",
        ) from exc


def _matches_device(pattern: str, endpoint_id: str, device_id: str) -> bool:
    short = str(device_id).rsplit("/", 1)[-1]
    text = str(pattern)
    return text in {
        "*",
        str(device_id),
        short,
        f"{endpoint_id}:{device_id}",
        f"{endpoint_id}:{short}",
        f"{endpoint_id}:*",
    }


def _assert_device_allowed(
    config: MHSConfig, endpoint_id: str, device_id: str
) -> None:
    if not config.estop_devices:
        # Empty list means endpoint-bound discovery is the allow-list: the
        # caller cannot name an arbitrary connector, and `mhs__inspect` below
        # proves the device is really served by this configured endpoint.
        return
    if any(_matches_device(pattern, endpoint_id, device_id) for pattern in config.estop_devices):
        return
    raise EmergencyStopError(
        "MHS.HOST.DEVICE_NOT_ALLOWED",
        f"device {device_id!r} is not on the configured emergency-stop allow-list",
        details={"endpoint_id": endpoint_id, "estop_devices": list(config.estop_devices)},
    )


def _audit_failure(
    ledger: HostLedger | None,
    spec: Any,
    endpoint_id: str,
    device_id: str,
    code: str,
    message: str,
) -> None:
    """Best-effort failure record; a failed audit never blocks/alters a stop."""
    if ledger is None:
        return
    try:
        ledger.append(
            {
                "kind": "emergency_stop_error",
                "connector_id": connector_id(spec),
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "mhs_code": str(code),
                "error": str(message),
                "approval_gate": "bypassed (trusted device-bound route)",
            },
            kind="emergency_stop_error",
        )
    except HostLedgerError:
        pass


def emergency_stop_via(
    transport: Any,
    endpoint_id: str,
    device_id: str,
    reason: str,
    config: MHSConfig | None = None,
    *,
    connector: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Engage the software e-stop through a caller-owned MCP transport.

    ``transport`` only needs ``call(name, arguments) -> MCP tool result``.  The
    stock host route passes the real ``MCPManager`` call bound to the connector
    row that the dispatcher just authorized; the standalone helper passes an
    ``MCPConnection``.  The narrow policy checks and the ledger audit are the
    same on both paths.
    """
    effective = config or MHSConfig.load()
    _policy_ready(effective)
    spec = _endpoint(effective, endpoint_id)
    _assert_device_allowed(effective, endpoint_id, device_id)
    reason_text = str(reason or "trusted host emergency stop")

    ledger: HostLedger | None = None
    audit_error: str | None = None
    intent_digest: str | None = None
    try:
        ledger = HostLedger(effective.host_ledger_path)
        intent = ledger.append(
            {
                "kind": "emergency_stop_request",
                "connector_id": connector_id(spec),
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "reason_digest": canonical.digest({"reason": reason_text}),
                "approval_gate": "bypassed (trusted device-bound route)",
                "policy": {
                    "enabled": bool(effective.enabled),
                    "allow_hardware": bool(effective.allow_hardware),
                },
                **(
                    {"host_connector_id": str(connector.get("connector_id"))}
                    if connector and connector.get("connector_id")
                    else {}
                ),
            },
            kind="emergency_stop_request",
        )
        intent_digest = str(intent.get("digest"))
    except HostLedgerError as exc:
        audit_error = f"{exc.code}: {exc.message}"
        ledger = None

    try:
        inspect = transport.call("mhs__inspect", {"device_id": device_id})
        if bool(inspect.get("is_error")):
            payload = _mcp_error_payload(inspect)
            raise EmergencyStopError(
                str(payload.get("mhs_code") or "MHS.DEVICE.UNKNOWN"),
                str(payload.get("message") or "cannot inspect the e-stop target"),
                details={"stage": "inspect"},
            )
        raw = inspect.get("raw")
        structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
        manifest = structured.get("inspect") if isinstance(structured, Mapping) else None
        if not isinstance(manifest, Mapping):
            raise EmergencyStopError(
                "MHS.HOST.PROTOCOL_ERROR", "mhs__inspect returned no manifest"
            )
        if str(manifest.get("device_id")) != str(device_id):
            raise EmergencyStopError(
                "MHS.HOST.DEVICE_NOT_ALLOWED",
                f"endpoint did not return the requested device {device_id!r}",
            )
        estop = (manifest.get("safety") or {}).get("estop") or {}
        kind = str(estop.get("kind") or "software")
        if kind == "hardware":
            raise EmergencyStopError(
                "MHS.SAFETY.ESTOP_UNAVAILABLE",
                "this device exposes only a hardware e-stop; the host must "
                "present its physical_ref and MUST NOT claim to stop it",
                details={"physical_ref": estop.get("physical_ref")},
            )
        result = transport.call(
            "mhs__estop", {"device_id": device_id, "reason": reason_text}
        )
        if bool(result.get("is_error")):
            payload = _mcp_error_payload(result)
            raise EmergencyStopError(
                str(payload.get("mhs_code") or "MHS.SAFETY.ESTOP_ENGAGED"),
                str(payload.get("message") or "e-stop call failed"),
                details={"stage": "mhs__estop"},
            )
        raw_result = result.get("raw")
        structured_result = (
            raw_result.get("structuredContent") if isinstance(raw_result, Mapping) else None
        )
        receipt = (
            structured_result.get("estop") if isinstance(structured_result, Mapping) else None
        )
        if not isinstance(receipt, Mapping):
            raise EmergencyStopError(
                "MHS.HOST.PROTOCOL_ERROR", "mhs__estop returned no receipt"
            )
        receipt = dict(receipt)
    except EmergencyStopError as exc:
        _audit_failure(ledger, spec, endpoint_id, device_id, exc.code, exc.message)
        raise
    except Exception as exc:  # noqa: BLE001 - surface a coded failure
        code = getattr(exc, "code", None) or "MHS.TRANSPORT.UNAVAILABLE"
        message = getattr(exc, "message", None) or str(exc)
        _audit_failure(ledger, spec, endpoint_id, device_id, str(code), str(message))
        raise EmergencyStopError(str(code), str(message), details={"stage": "mcp"}) from exc

    latched = bool((receipt.get("output") or {}).get("latched")) if isinstance(receipt.get("output"), Mapping) else False
    audit: dict[str, Any] = {"ledger": str(effective.host_ledger_path), "intent_digest": intent_digest}
    if ledger is not None:
        try:
            outcome = ledger.append(
                {
                    "kind": "emergency_stop_result",
                    "connector_id": connector_id(spec),
                    "endpoint_id": endpoint_id,
                    "device_id": device_id,
                    "receipt": receipt,
                    "receipt_digest": canonical.digest(receipt),
                    "outcome": str(receipt.get("status") or ""),
                    "latched": latched,
                },
                kind="emergency_stop_result",
            )
            audit["result_digest"] = str(outcome.get("digest"))
        except HostLedgerError as exc:
            audit_error = f"{exc.code}: {exc.message}"
    return {
        "endpoint_id": endpoint_id,
        "device_id": device_id,
        "connector_id": connector_id(spec),
        "receipt": receipt,
        "latched": latched,
        "audit": audit,
        "audit_error": audit_error,
    }


class _ConnectorCall:
    """Minimal ``call`` adapter over an already-open ``MCPConnector``."""

    def __init__(self, connector: MCPConnector) -> None:
        self.connector = connector

    def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self.connector.call(name, arguments)


def emergency_stop(
    endpoint_id: str,
    device_id: str,
    reason: str,
    config: MHSConfig | None = None,
    *,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Engage the software e-stop through the standalone trusted MCP route."""
    effective = config or MHSConfig.load()
    # Policy is validated before a connection is opened; emergency_stop_via
    # repeats it so the host-route caller gets the same refusals.
    _policy_ready(effective)
    _endpoint(effective, endpoint_id)
    _assert_device_allowed(effective, endpoint_id, device_id)
    with MCPConnector(endpoint_id, effective, timeout_s=timeout_s) as connector:
        return emergency_stop_via(
            _ConnectorCall(connector),
            endpoint_id,
            device_id,
            reason,
            effective,
        )
