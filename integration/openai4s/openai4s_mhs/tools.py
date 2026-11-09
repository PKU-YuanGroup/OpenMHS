"""Eight native OpenAI4S control tools backed by :class:`MHSHost`.

Each tool is a thin schema + description over one ``HostDispatcher`` method
(``_m_mhs_*`` below).  The dispatcher remains the policy envelope: a model call
enters through :meth:`openai4s.tools.base.Tool.invoke`, the dispatcher applies
its permission gate, and ``Tool.execute`` re-enters through the dispatcher's
control-behavior port so the actual work always runs inside the same envelope.

The tools deliberately expose *device semantics*, not shell-like freedom:

* ``mode`` (``simulated`` / ``hardware`` / ``replay``) and ``fidelity.gaps`` are
  disclosed by ``mhs_devices``/``mhs_inspect`` and never hidden;
* a command returns an MHS **receipt**, and a rejected command is a receipt, not
  a transport error;
* ``status == "unknown"`` is a hard stop: the model must re-read state before any
  retry, and this module never retries on its own;
* every receipt is appended to the host evidence ledger by :class:`MHSHost`.

``install()`` is idempotent and does not connect to any endpoint: the per
dispatcher :class:`MHSHost` is created lazy on first use.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from openai4s.tools.base import Tool
from openai4s.tools.contexts import ControlToolContext
from openai4s.tools.taxonomy import (
    EXTERNAL_WRITE,
    HIGH_RISK,
    READ_ONLY,
    WORKSPACE_WRITE,
    resource_key,
)

from .config import MHSConfig
from .host import MHSHost, MHSHostError

#: Host methods this package owns.  ``BUILTIN_CONTROL_HOST_METHODS`` in both
#: ``openai4s.tools.registry`` and ``openai4s.host_dispatch`` is extended with
#: these so a tool + an ``_m_`` handler may coexist (the conflict rule).
HOST_METHODS: tuple[str, ...] = (
    "mhs_devices",
    "mhs_inspect",
    "mhs_read",
    "mhs_command",
    "mhs_operations",
    "mhs_safety",
    "mhs_evidence",
    "mhs_connect",
)

_INSTALL_MARK = "_openai4s_mhs_installed"
_CONFIG_OVERRIDE: MHSConfig | None = None

_ENDPOINT_PROP = {
    "type": "string",
    "minLength": 1,
    "maxLength": 200,
    "description": (
        "Configured MHS endpoint id (from mhs_connect). Omit when only one "
        "endpoint is configured."
    ),
}
_DEVICE_PROP = {
    "type": "string",
    "minLength": 1,
    "maxLength": 300,
    "description": (
        "MHS device id or its unique short name, e.g. 'liquid-handler' or "
        "'mhs://localhost:7401/lab/liquid-handler'."
    ),
}
_MODE_NOTE = (
    "Devices are simulated, hardware or replay; each result carries mode and "
    "fidelity gaps. A command returns an MHS receipt; status='unknown' means the "
    "outcome is not known -- re-read state before retrying."
)


def _endpoint_id(spec: dict) -> str | None:
    value = spec.get("endpoint_id")
    return str(value) if value not in (None, "") else None


def _device_id(spec: dict) -> str:
    value = spec.get("device_id")
    if value in (None, ""):
        raise MHSHostError("MHS.HOST.DEVICE_REQUIRED", "device_id is required")
    return str(value)


def _optional_int(spec: dict, key: str) -> int | None:
    value = spec.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise MHSHostError("MHS.HOST.INVALID_ARGUMENT", f"{key} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise MHSHostError(
            "MHS.HOST.INVALID_ARGUMENT", f"{key} must be an integer"
        ) from exc


def _spec(spec: Any) -> dict:
    if spec is None:
        return {}
    if isinstance(spec, dict):
        return spec
    if isinstance(spec, str):
        return {"device_id": spec}
    raise MHSHostError(
        "MHS.HOST.INVALID_ARGUMENT",
        "arguments must be an object",
        details={"type": type(spec).__name__},
    )


def _guard(call: Callable[[], Any]) -> Any:
    """Run one host operation, returning MHS-coded failures as tool results."""
    try:
        return call()
    except MHSHostError as exc:
        return exc.to_dict()
    except LookupError as exc:
        return {"error": str(exc), "mhs_code": "MHS.HOST.NO_ENDPOINTS"}
    except Exception as exc:  # noqa: BLE001 - a tool result must stay JSON
        return {
            "error": str(exc),
            "mhs_code": str(getattr(exc, "code", "MHS.HOST.UNEXPECTED")),
        }


def _host(dispatcher: Any) -> MHSHost:
    return dispatcher.openai4s_mhs_host


def _require_endpoints(host: MHSHost) -> list[dict]:
    endpoints = host.endpoints()
    if not endpoints:
        raise MHSHostError(
            "MHS.HOST.NO_ENDPOINTS",
            "no MHS endpoints are configured; set MHS_ENDPOINTS, write "
            "~/.openai4s/mhs.json, or pass an explicit MHSConfig",
        )
    return endpoints


def _unknown_guidance(receipt: dict) -> dict:
    if str(receipt.get("status") or "") == "unknown":
        receipt = dict(receipt)
        receipt["outcome_unknown"] = True
        receipt["agent_guidance"] = (
            "The command may or may not have taken effect. Do not retry blindly: "
            "read the device state (mhs_read) and reconcile the revision and "
            "evidence chain before issuing another command."
        )
    return receipt



#: Capability families that make a resource safely readable.  A manifest that
#: declares none of them can still be read: MHS authorizes ``mhs.resource.read``
#: by *device* grant, so any granted capability opens the session and the read
#: itself mutates nothing.  This is the compatibility path for domain manifests
#: (e.g. the lab's pipette exposes ``cap.fluid.level.v1`` rather than
#: ``cap.world.state.v1``).
_READ_CAPABILITY_HINTS = (
    "cap.world.state",
    "cap.world.snapshot",
    "cap.sensing.read",
    "cap.device.describe",
    "cap.fluid.level",
    "cap.measure.spectrum",
)


def _read_session_capability(manifest: dict) -> str:
    capabilities = [str((cap or {}).get("capability_id") or "") for cap in manifest.get("capabilities") or []]
    for hint in _READ_CAPABILITY_HINTS:
        for capability_id in capabilities:
            if capability_id.startswith(hint):
                return capability_id
    for capability_id in capabilities:
        if capability_id.endswith(".v1") and "stop" in capability_id:
            return capability_id
    for capability_id in capabilities:
        if capability_id:
            return capability_id
    raise MHSHostError(
        "MHS.HOST.NO_CAPABILITIES",
        "device declares no capability, so no least-privilege session can be opened",
        details={"device_id": manifest.get("device_id")},
    )


def read_state(
    host: MHSHost,
    device_id: str,
    resource_id: str | None = None,
    endpoint_id: str | None = None,
) -> dict:
    """Read device state, tolerating manifests without an obvious read capability.

    ``MHSHost.read`` picks a ``cap.world.state``-family capability and refuses
    otherwise.  A lab instrument often exposes only domain reads (well levels,
    a spectrum), so when that lookup fails this opens a one-capability session
    for a safe read/stop capability and reads the resource directly.  MHS
    server-side read authorization is the device grant, not the capability, and
    this path never invokes the granted capability.
    """
    try:
        return host.read(device_id, resource_id, endpoint_id)
    except MHSHostError as exc:
        if exc.code not in ("MHS.HOST.NO_READ_CAPABILITY", "MHS.HOST.NO_RESOURCES"):
            raise
    spec, client, manifest = host._resolve_device(device_id, endpoint_id)  # noqa: SLF001
    resources = manifest.get("resources") or []
    if not resources:
        raise MHSHostError(
            "MHS.HOST.NO_RESOURCES",
            "device declares no resources",
            details={"device_id": manifest.get("device_id")},
        )
    target = resource_id or str(resources[0].get("resource_id"))
    capability_id = _read_session_capability(manifest)
    session_id = host._session(spec, client, manifest, capability_id)  # noqa: SLF001
    state = client.read(
        target,
        device_id=str(manifest.get("device_id")),
        session_id=session_id,
    )
    return {
        "endpoint_id": spec.id,
        "via_capability": capability_id,
        **state,
    }


# ---------------------------------------------------------------------------
# dispatcher behaviours (installed with setattr by install())
# ---------------------------------------------------------------------------


def _m_mhs_devices(self: Any, spec: dict | None = None) -> dict:
    """List every discovered MHS device with mode, risk and fidelity."""
    arguments = _spec(spec)

    def run() -> dict:
        host = _host(self)
        _require_endpoints(host)
        devices = host.devices(_endpoint_id(arguments))
        return {
            "devices": devices,
            "count": len(devices),
            "note": _MODE_NOTE,
        }

    return _guard(run)


def _m_mhs_inspect(self: Any, spec: dict | None = None) -> dict:
    """Return the full manifest of one MHS device."""
    arguments = _spec(spec)

    def run() -> dict:
        host = _host(self)
        result = host.inspect(_device_id(arguments), _endpoint_id(arguments))
        manifest = result.get("device") or {}
        return {
            "endpoint_id": result.get("endpoint_id"),
            "mode": manifest.get("mode"),
            "risk_class": (manifest.get("safety") or {}).get("risk_class"),
            "requires_permit": (manifest.get("safety") or {}).get("requires_permit")
            or [],
            "fidelity": manifest.get("fidelity"),
            "device": manifest,
        }

    return _guard(run)


def _m_mhs_read(self: Any, spec: dict | None = None) -> dict:
    """Read one resource/state document from an MHS device."""
    arguments = _spec(spec)

    def run() -> dict:
        host = _host(self)
        resource_id = arguments.get("resource_id") or arguments.get("resource")
        return read_state(
            host,
            _device_id(arguments),
            str(resource_id) if resource_id not in (None, "") else None,
            _endpoint_id(arguments),
        )

    return _guard(run)


def _m_mhs_command(self: Any, spec: dict | None = None) -> dict:
    """Invoke one MHS capability through MHSHost (sessions + permits + receipt)."""
    arguments = _spec(spec)

    def run() -> dict:
        host = _host(self)
        capability_id = arguments.get("capability_id")
        if capability_id in (None, ""):
            raise MHSHostError(
                "MHS.HOST.CAPABILITY_REQUIRED", "capability_id is required"
            )
        payload = arguments.get("input")
        if payload is None:
            payload = arguments.get("payload") or {}
        if not isinstance(payload, dict):
            raise MHSHostError(
                "MHS.HOST.INVALID_ARGUMENT",
                "input must be a JSON object",
                details={"type": type(payload).__name__},
            )
        resource_id = arguments.get("resource") or arguments.get("resource_id")
        receipt = host.command(
            _device_id(arguments),
            str(capability_id),
            payload,
            resource_id=str(resource_id) if resource_id not in (None, "") else None,
            endpoint_id=_endpoint_id(arguments),
            expected_revision=_optional_int(arguments, "expected_revision"),
            deadline_ms=_optional_int(arguments, "deadline_ms"),
        )
        return _unknown_guidance(receipt)

    return _guard(run)


def _m_mhs_operations(self: Any, spec: dict | None = None) -> dict:
    """Get, list or cancel MHS operations on one endpoint."""
    arguments = _spec(spec)
    action = str(arguments.get("action") or "list")

    def run() -> dict:
        host = _host(self)
        endpoint_id = _endpoint_id(arguments)
        if action == "list":
            result = host.operations(arguments.get("device_id"), endpoint_id)
            return result if isinstance(result, dict) else {"operations": result}
        if action == "get":
            operation_id = arguments.get("operation_id")
            if operation_id in (None, ""):
                raise MHSHostError(
                    "MHS.HOST.OPERATION_REQUIRED", "operation_id is required"
                )
            result = host.operations(arguments.get("device_id"), endpoint_id)
            operations = (
                result.get("operations") if isinstance(result, dict) else result
            )
            for item in operations or []:
                if isinstance(item, dict) and item.get("operation_id") == operation_id:
                    return {"operation": item, "endpoint_id": endpoint_id}
            raise MHSHostError(
                "MHS.HOST.OPERATION_NOT_FOUND",
                f"no operation {operation_id!r} on this endpoint",
                details={"operation_id": operation_id},
            )
        if action == "cancel":
            operation_id = arguments.get("operation_id")
            if operation_id in (None, ""):
                raise MHSHostError(
                    "MHS.HOST.OPERATION_REQUIRED", "operation_id is required"
                )
            return host.cancel(str(operation_id), endpoint_id)
        raise MHSHostError(
            "MHS.HOST.INVALID_ARGUMENT",
            "action must be one of: get, list, cancel",
            details={"action": action},
        )

    return _guard(run)


def _m_mhs_safety(self: Any, spec: dict | None = None) -> dict:
    """Read safety status or engage the e-stop of one device (never reset)."""
    arguments = _spec(spec)
    action = str(arguments.get("action") or "status")

    def run() -> dict:
        if action == "reset":
            # A reset is the operator's decision (host operator route), never
            # the model's: refused before any endpoint is contacted.
            raise MHSHostError(
                "MHS.AUTH.FORBIDDEN",
                "the model cannot reset an e-stop latch; the operator resets it through "
                "the host operator route (python3 -m openai4s_mhs safety reset DEVICE "
                "--operator NAME)",
                details={"action": action, "policy": "operator_route_only"},
            )
        host = _host(self)
        device_id = _device_id(arguments)
        endpoint_id = _endpoint_id(arguments)
        if action == "status":
            return host.safety_status(device_id, endpoint_id)
        if action == "estop":
            return host.estop(
                device_id,
                str(arguments.get("reason") or "OpenAI4S host requested e-stop"),
                endpoint_id,
            )
        raise MHSHostError(
            "MHS.HOST.INVALID_ARGUMENT",
            "action must be one of: status, estop",
            details={"action": action},
        )

    return _guard(run)


def _refuse_evidence_path() -> None:
    raise MHSHostError(
        "MHS.HOST.INVALID_ARGUMENT",
        "Native evidence tools do not access filesystem paths; export the bundle "
        "and use the host's governed file tools to save or read it.",
    )


def _m_mhs_evidence(self: Any, spec: dict | None = None) -> dict:
    """Export, verify or read the local receipt ledger."""
    arguments = _spec(spec)
    action = str(arguments.get("action") or "verify")
    endpoint_id = _endpoint_id(arguments)
    if arguments.get("path") not in (None, ""):
        return _guard(lambda: _refuse_evidence_path())

    def run() -> dict:
        host = _host(self)
        if action == "ledger":
            limit = _optional_int(arguments, "limit") or 100
            entries = host.ledger(limit)
            return {"entries": entries, "count": len(entries)}
        if action == "export":
            bundle = host.evidence_export(endpoint_id)
            return bundle
        if action == "verify":
            return host.evidence_verify(None, endpoint_id)
        raise MHSHostError(
            "MHS.HOST.INVALID_ARGUMENT",
            "action must be one of: export, verify, ledger",
            details={"action": action},
        )

    return _guard(run)


def _m_mhs_connect(self: Any, spec: dict | None = None) -> dict:
    """List configured endpoints or discover devices on one endpoint."""
    arguments = _spec(spec)
    action = str(arguments.get("action") or "endpoints")

    def run() -> dict:
        host = _host(self)
        endpoints = _require_endpoints(host)
        if action == "endpoints":
            return {"endpoints": endpoints, "count": len(endpoints)}
        if action == "discover":
            return {
                "endpoints": endpoints,
                "devices": host.devices(_endpoint_id(arguments)),
            }
        raise MHSHostError(
            "MHS.HOST.INVALID_ARGUMENT",
            "action must be one of: endpoints, discover",
            details={"action": action},
        )

    return _guard(run)


# ---------------------------------------------------------------------------
# tool classes
# ---------------------------------------------------------------------------


class MHSDevicesTool(Tool):
    name = "mhs_devices"
    host_method = "mhs_devices"
    description = (
        "List the MHS devices this host can reach, across all configured "
        "endpoints, with endpoint id, device id, mode (simulated/hardware/replay), "
        "risk class R0-R3, capability ids and the manifest's fidelity level and "
        "gaps. Use this before commanding anything: a device's mode and fidelity "
        "gaps say what the result is worth. Sessions are never opened here."
    )
    parameters = {
        "type": "object",
        "properties": {"endpoint_id": dict(_ENDPOINT_PROP)},
        "required": [],
        "additionalProperties": False,
    }
    read_only = True
    needs_network = True
    screen_untrusted_output = True
    requires_approval = False
    side_effect_class = READ_ONLY
    resource_key_prefix = "mhs"
    resource_target_default = "catalog"

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        return runtime.invoke(self.host_method, {"endpoint_id": _endpoint_id(arguments)})


class MHSInspectTool(Tool):
    name = "mhs_inspect"
    host_method = "mhs_inspect"
    description = (
        "Return the full MHS manifest of one device: display name, mode, safety "
        "envelope (risk class, interlocks, requires_permit patterns, safe state), "
        "fidelity (engine, determinism, gaps), resources and every capability with "
        "its input schema and whether it is permit-gated. Inspect before a "
        "multi-step action so the arguments match the declared capability."
    )
    parameters = {
        "type": "object",
        "properties": {
            "device_id": dict(_DEVICE_PROP),
            "endpoint_id": dict(_ENDPOINT_PROP),
        },
        "required": ["device_id"],
        "additionalProperties": False,
    }
    read_only = True
    needs_network = True
    screen_untrusted_output = True
    requires_approval = False
    side_effect_class = READ_ONLY
    resource_key_prefix = "mhs"
    resource_target_key = "device_id"
    resource_target_default = "device"

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        return runtime.invoke(self.host_method, dict(arguments))


class MHSReadTool(Tool):
    name = "mhs_read"
    host_method = "mhs_read"
    description = (
        "Read one resource/state document from an MHS device (a least-privilege "
        "read session is opened on demand). The result is the device's current "
        "state with its revision; use it to reconcile after a rejection or as the "
        "required first step after an unknown outcome. Never treat state as an "
        "acknowledgement that a command was executed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "device_id": dict(_DEVICE_PROP),
            "resource_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "description": "Resource id from mhs_inspect; defaults to the device's first resource.",
            },
            "endpoint_id": dict(_ENDPOINT_PROP),
        },
        "required": ["device_id"],
        "additionalProperties": False,
    }
    read_only = True
    needs_network = True
    screen_untrusted_output = True
    requires_approval = False
    side_effect_class = READ_ONLY
    resource_key_prefix = "mhs"
    resource_target_key = "device_id"
    resource_target_default = "device"

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        return runtime.invoke(self.host_method, dict(arguments))


class MHSCommandTool(Tool):
    name = "mhs_command"
    host_method = "mhs_command"
    description = (
        "Invoke one capability on an MHS device and return its receipt. The host "
        "opens a session granting only this capability, asks for approval when the "
        "manifest marks the capability (or its risk class) permit-gated, and issues "
        "an MHS permit bound to the exact input digest. Receipt.status is one of "
        "completed/rejected/failed/accepted/unknown: a rejection is evidence, not a "
        "transport error. status='unknown' is a hard stop -- re-read state with "
        "mhs_read before any retry; never retry blindly. Use expected_revision when "
        "the manifest declares optimistic concurrency."
    )
    parameters = {
        "type": "object",
        "properties": {
            "device_id": dict(_DEVICE_PROP),
            "capability_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "description": "Capability id from mhs_inspect, e.g. cap.world.step.v1.",
            },
            "input": {
                "type": "object",
                "additionalProperties": True,
                "description": "Capability arguments, exactly as declared by the manifest.",
            },
            "resource": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "description": "Optional resource id the capability acts on.",
            },
            "expected_revision": {
                "type": "integer",
                "minimum": 0,
                "description": "Optimistic-concurrency guard; rejected on mismatch.",
            },
            "deadline_ms": {
                "type": "integer",
                "minimum": 1,
                "maximum": 600000,
                "description": "Bounded command deadline; the endpoint returns a receipt, never an unbounded wait.",
            },
            "endpoint_id": dict(_ENDPOINT_PROP),
        },
        "required": ["device_id", "capability_id"],
        "additionalProperties": False,
    }
    read_only = False
    dangerous = True
    needs_network = True
    screen_untrusted_output = True
    requires_approval = True
    side_effect_class = HIGH_RISK
    resource_key_prefix = "mhs"
    resource_target_key = "device_id"
    resource_target_default = "device"

    def permission_target(self, arguments: Any) -> str:
        if not isinstance(arguments, dict):
            return "mhs"
        device = arguments.get("device_id") or "device"
        capability = arguments.get("capability_id") or "capability"
        return f"{device}/{capability}"

    def resource_keys(self, arguments: Any) -> tuple[str, ...]:
        return (resource_key("mhs", self.permission_target(arguments)),)

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        spec = dict(arguments)
        spec["input"] = dict(spec.get("input") or {})
        return runtime.invoke(self.host_method, spec)


class MHSOperationsTool(Tool):
    name = "mhs_operations"
    host_method = "mhs_operations"
    description = (
        "Get, list or cancel MHS operations. MHS never blocks a call for a long "
        "task: a command may return status='accepted' with an operation_id, which "
        "this tool then polls or cancels. Cancellation is best effort and is not a "
        "safety stop -- use mhs_safety action='estop' for that. An operation whose "
        "receipt is unknown must be reconciled by reading device state first."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "list", "cancel"],
                "description": "Operation action.",
            },
            "operation_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "description": "Required for get/cancel.",
            },
            "device_id": dict(_DEVICE_PROP),
            "endpoint_id": dict(_ENDPOINT_PROP),
        },
        "required": ["action"],
        "additionalProperties": False,
    }
    read_only = False
    needs_network = True
    screen_untrusted_output = True
    requires_approval = False
    side_effect_class = EXTERNAL_WRITE
    resource_key_prefix = "mhs"
    resource_target_key = "device_id"
    resource_target_default = "operations"

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        return runtime.invoke(self.host_method, dict(arguments))


class MHSSafetyTool(Tool):
    name = "mhs_safety"
    host_method = "mhs_safety"
    description = (
        "Read one device's safety state or stop it: action='status' reports the "
        "risk class, latches, e-stop and interlocks; action='estop' engages the "
        "emergency stop and returns a receipt (never approval-gated: a safety stop "
        "must always be callable). Releasing the latch is the operator's decision "
        "and is not available here. An e-stop receipt is evidence of the attempt; "
        "check the returned safety state, not the fact that the call returned."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "estop"],
                "description": "Safety action.",
            },
            "device_id": dict(_DEVICE_PROP),
            "reason": {
                "type": "string",
                "maxLength": 500,
                "description": "Human-readable reason recorded with an e-stop.",
            },
            "endpoint_id": dict(_ENDPOINT_PROP),
        },
        "required": ["action", "device_id"],
        "additionalProperties": False,
    }
    read_only = False
    dangerous = True
    needs_network = True
    screen_untrusted_output = True
    requires_approval = False
    side_effect_class = HIGH_RISK
    resource_key_prefix = "mhs"
    resource_target_key = "device_id"
    resource_target_default = "device"

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        return runtime.invoke(self.host_method, dict(arguments))


class MHSEvidenceTool(Tool):
    name = "mhs_evidence"
    host_method = "mhs_evidence"
    description = (
        "Work with MHS receipts and the evidence chain. action='export' returns an "
        "endpoint's evidence bundle for saving through the host's governed file tools; "
        "action='verify' recomputes the hash chain and reports valid/checked/"
        "head_digest; action='ledger' lists receipts this OpenAI4S host has itself "
        "observed. A rejected or unknown receipt is chained too -- evidence shows "
        "what was refused, not only what succeeded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["export", "verify", "ledger"],
                "description": "Evidence action.",
            },
            "endpoint_id": dict(_ENDPOINT_PROP),
            "path": {
                "type": "string",
                "minLength": 1,
                "maxLength": 2000,
                "description": "Deprecated: filesystem paths are refused. Use governed host file tools.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "description": "Ledger entries to return (default 100).",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }
    read_only = False
    writes_files = False
    secret_path_key = "path"
    needs_network = True
    screen_untrusted_output = True
    requires_approval = False
    side_effect_class = WORKSPACE_WRITE
    resource_key_prefix = "mhs"
    resource_target_default = "evidence"

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        return runtime.invoke(self.host_method, dict(arguments))


class MHSConnectTool(Tool):
    name = "mhs_connect"
    host_method = "mhs_connect"
    description = (
        "Show how this host reaches MHS: action='endpoints' lists configured "
        "endpoint ids, transport and target; action='discover' also runs device "
        "discovery on one endpoint. This is the zero-side-effect entry point when "
        "mhs_devices returns an unreachable-endpoint error; it does not open a "
        "device session or change device state."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["endpoints", "discover"],
                "description": "Connection action.",
            },
            "endpoint_id": dict(_ENDPOINT_PROP),
        },
        "required": ["action"],
        "additionalProperties": False,
    }
    read_only = True
    needs_network = True
    screen_untrusted_output = True
    requires_approval = False
    side_effect_class = READ_ONLY
    resource_key_prefix = "mhs"
    resource_target_default = "catalog"

    def execute(self, runtime: ControlToolContext, arguments: dict) -> Any:
        return runtime.invoke(self.host_method, dict(arguments))


TOOL_TYPES: tuple[type[Tool], ...] = (
    MHSDevicesTool,
    MHSInspectTool,
    MHSReadTool,
    MHSCommandTool,
    MHSOperationsTool,
    MHSSafetyTool,
    MHSEvidenceTool,
    MHSConnectTool,
)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def _mhs_host_property(self: Any) -> MHSHost:
    """Lazy per-dispatcher MHSHost; construction never connects."""
    existing = self.__dict__.get("_openai4s_mhs_host")
    if existing is not None:
        return existing
    host = MHSHost(_CONFIG_OVERRIDE) if _CONFIG_OVERRIDE is not None else MHSHost()
    self.__dict__["_openai4s_mhs_host"] = host
    return host


def install(config: MHSConfig | None = None) -> bool:
    """Register the eight tools and their dispatcher behaviours.

    Returns False (and registers nothing) unless the experimental MHS skill is
    enabled in settings.  ``config`` (when given) is used by every dispatcher's
    lazy host; otherwise each dispatcher calls :meth:`MHSConfig.load` on first
    use.
    """
    global _CONFIG_OVERRIDE

    effective = config if config is not None else (_CONFIG_OVERRIDE or MHSConfig.load())
    if not effective.enabled:
        # Experimental skill, default off: no tool, no dispatcher method, no way
        # for the model to reach hardware through MHS.
        return False

    from openai4s import host_dispatch as host_dispatch_module
    from openai4s.tools import registry as registry_module

    dispatcher_class = host_dispatch_module.HostDispatcher
    if config is not None:
        _CONFIG_OVERRIDE = config
    if getattr(dispatcher_class, _INSTALL_MARK, False):
        return True

    for tool_type in TOOL_TYPES:
        tool = tool_type()
        if registry_module.get_tool(tool.name) is None:
            registry_module.register_tool(tool)

    for method in HOST_METHODS:
        handler = globals()[f"_m_{method}"]
        if getattr(dispatcher_class, f"_m_{method}", None) is not handler:
            setattr(dispatcher_class, f"_m_{method}", handler)
    if not isinstance(
        dispatcher_class.__dict__.get("openai4s_mhs_host"), property
    ):
        setattr(dispatcher_class, "openai4s_mhs_host", property(_mhs_host_property))

    for module in (registry_module, host_dispatch_module):
        current = getattr(module, "BUILTIN_CONTROL_HOST_METHODS", frozenset())
        extended = frozenset(set(current) | set(HOST_METHODS))
        # host_dispatch imported the name with ``from ... import``, so it is a
        # module global there; registry owns the original. Rebind both.
        setattr(module, "BUILTIN_CONTROL_HOST_METHODS", extended)

    setattr(dispatcher_class, _INSTALL_MARK, True)
    return True


def deactivate() -> bool:
    """Remove the surface if it was installed in this process (safe to call)."""
    try:
        from openai4s import host_dispatch as host_dispatch_module
    except Exception:  # noqa: BLE001 - OpenAI4S absent: nothing to deactivate
        return True
    if not getattr(host_dispatch_module.HostDispatcher, _INSTALL_MARK, False):
        return True
    uninstall()
    return True


def uninstall() -> None:
    """Remove the native surface (tests only; not a runtime hot-unload path)."""
    global _CONFIG_OVERRIDE

    from openai4s import host_dispatch as host_dispatch_module
    from openai4s.tools import registry as registry_module

    dispatcher_class = host_dispatch_module.HostDispatcher
    for tool_type in TOOL_TYPES:
        registry_module._unregister_tool(tool_type.name)
    for method in HOST_METHODS:
        if getattr(dispatcher_class, f"_m_{method}", None) is globals()[f"_m_{method}"]:
            delattr(dispatcher_class, f"_m_{method}")
    if isinstance(dispatcher_class.__dict__.get("openai4s_mhs_host"), property):
        delattr(dispatcher_class, "openai4s_mhs_host")
    for module in (registry_module, host_dispatch_module):
        current = getattr(module, "BUILTIN_CONTROL_HOST_METHODS", frozenset())
        setattr(module, "BUILTIN_CONTROL_HOST_METHODS", frozenset(set(current) - set(HOST_METHODS)))
    setattr(dispatcher_class, _INSTALL_MARK, False)
    _CONFIG_OVERRIDE = None


__all__ = [
    "HOST_METHODS",
    "TOOL_TYPES",
    "read_state",
    "MHSCommandTool",
    "MHSConnectTool",
    "MHSDevicesTool",
    "MHSEvidenceTool",
    "MHSInspectTool",
    "MHSOperationsTool",
    "MHSReadTool",
    "MHSSafetyTool",
    "install",
    "uninstall",
]
