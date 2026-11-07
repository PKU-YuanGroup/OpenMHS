"""Adapter between the stock OpenAI4S host route and the governed MHS path.

The stock ``CallMCPTool`` -> ``HostDispatcher`` -> ``MCPService.call`` route is
where an operator-enabled MHS connector is actually reached.  ``host/mcp.py``
calls :func:`governed_call` for a capability tool and
:func:`trusted_emergency_stop` for ``mhs__estop``; this module supplies the
missing wiring without opening a second connector: the transport is the real
``MCPManager`` call pair that ``MCPService`` already resolved, so dispatcher
approval, connector enablement, the connector row's launch configuration and the
manager's connection cache are exactly the ones the generic path uses.

What is added at that seam:

* governed capability calls run through :func:`mcp_invoke.invoke_via` -- durable
  command id/intent before the effect, host-ledger intent and receipt/UNKNOWN
  after it, the same reconciliation gate and same-id replay semantics as
  :func:`mcp_invoke.invoke`;
* after completion or UNKNOWN, the endpoint evidence bundle is exported through
  the same transport and its verified head/count/digest is appended to the host
  ledger, so the host chain names verifiable endpoint evidence;
* ``mhs__estop`` goes through :func:`emergency.emergency_stop_via` (device
  allow-list, hardware e-stop refusal, audit), never through the ordinary
  approval prompt;
* ``mhs__reset`` and ``mhs__permit`` are refused on an MHS connector row with
  ``MHS.AUTH.FORBIDDEN`` before any endpoint call, whatever its settings say:
  a reset or a permit is the operator's decision and goes through the host
  operator route (:mod:`openai4s_mhs.operator_route`);
* discovery/read/safety/operations/evidence tools and every non-MHS connector
  are left untouched (``governed_call`` returns ``None`` so the generic path
  runs unchanged).

These two entry points exist only on an OpenAI4S tree with
``openai4s-core.patch`` applied (:mod:`openai4s_mhs.corepatch`).
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from mhs import canonical

from . import connector_registry
from .config import MHSConfig
from .emergency import EmergencyStopError, emergency_stop_via
from .host_evidence import HostLedger, export_package, verify_package
from .mcp_invoke import (
    MCPInvokeError,
    MCPOutcomeUnknown,
    export_evidence,
    invoke_via,
    read_evidence,
)
from .mcpconfig import connector_id as projected_connector_id
from .operator_route import OPERATOR_TOOLS

__all__ = [
    "connector_config",
    "export_host_package",
    "governed_call",
    "is_mhs_connector",
    "trusted_emergency_stop",
]

#: The stdio module that fronts an MHS endpoint (see ``mcpconfig.MCP_MODULE``).
_MHS_MODULE = "mhs.mcp"


def _argv(connector: Mapping[str, Any]) -> list[str]:
    command = connector.get("command")
    if isinstance(command, str):
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
    elif isinstance(command, (list, tuple)):
        parts = [str(part) for part in command]
    else:
        parts = []
    args = connector.get("args")
    if isinstance(args, (list, tuple)):
        parts.extend(str(part) for part in args)
    return parts


def is_mhs_connector(connector: Mapping[str, Any]) -> bool:
    """Whether this connector row launches the MHS stdio projection."""
    if not isinstance(connector, Mapping):
        return False
    return any(str(part).replace("\\", "/").endswith(_MHS_MODULE) for part in _argv(connector))


def _config_argument(connector: Mapping[str, Any]) -> str | None:
    argv = _argv(connector)
    value: str | None = None
    for index, part in enumerate(argv):
        if part == "--config" and index + 1 < len(argv):
            value = argv[index + 1]
        elif part.startswith("--config="):
            value = part.split("=", 1)[1]
    return value


def connector_config(
    connector: Mapping[str, Any], config: MHSConfig | None = None
) -> tuple[MHSConfig, Any] | None:
    """Resolve the connector row to ``(MHSConfig, EndpointSpec)``.

    The row's ``--config`` file wins when it exists (the operator's durable
    policy).  An in-memory config registered by ``mcpconfig.connector_entries``
    is the fallback; a row whose settings cannot be resolved is refused rather
    than silently run ungoverned.
    """
    row_id = str(connector.get("connector_id") or connector.get("id") or "")
    path = _config_argument(connector)
    effective: MHSConfig | None = None
    if path and Path(path).expanduser().exists():
        try:
            effective = MHSConfig.load(path)
        except Exception:  # noqa: BLE001 - malformed settings are refused below
            effective = None
    if effective is None and config is not None:
        effective = config
    if effective is None:
        effective = connector_registry.resolve(row_id, path)
    if effective is None:
        return None
    for spec in effective.endpoints:
        if projected_connector_id(spec) == row_id:
            return effective, spec
    return None


class HostMCPTransport:
    """The transport contract ``invoke_via`` needs, over the real MCPManager."""

    def __init__(
        self,
        call_tool: Callable[..., dict[str, Any]],
        connector_id: str,
        launch_config: Mapping[str, Any],
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self._call_tool = call_tool
        self._connector_id = connector_id
        self._launch_config = dict(launch_config)
        self._tools = [dict(item) for item in (tools or []) if isinstance(item, Mapping)]

    def tool_names(self) -> set[str]:
        return {str(item.get("name")) for item in self._tools if item.get("name")}

    def call(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._call_tool(
            self._connector_id, self._launch_config, name, dict(arguments or {})
        )


def _tool_entry(
    tools: Sequence[Mapping[str, Any]], tool_name: str
) -> Mapping[str, Any] | None:
    for item in tools:
        if isinstance(item, Mapping) and str(item.get("name")) == tool_name:
            return item
    return None


def _capability_marker(
    tools: Sequence[Mapping[str, Any]], tool_name: str
) -> Mapping[str, Any] | None:
    entry = _tool_entry(tools, tool_name)
    if entry is None:
        return None
    marker = entry.get("x-mhs")
    return marker if isinstance(marker, Mapping) else None


def _tool_error(
    code: str, message: str, *, details: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """An MCP-shaped error result, so ``isError`` survives the host route."""
    payload = {"mhs_code": str(code), "message": str(message)}
    payload.update({str(key): value for key, value in (details or {}).items()})
    text = f"{payload['mhs_code']}: {payload['message']}"
    return {
        "is_error": True,
        "text": text,
        "raw": {
            "isError": True,
            "content": [{"type": "text", "text": text}],
            "structuredContent": {"receipt": None, "mhs_error": payload},
        },
    }


def _record_endpoint_evidence(
    transport: HostMCPTransport,
    config: MHSConfig,
    endpoint: Any,
    connector: Mapping[str, Any],
    *,
    device_id: str | None,
    command_id: str | None,
    outcome: str,
) -> dict[str, Any] | None:
    """Append the endpoint bundle's verified identity to the host chain."""
    record: dict[str, Any] = {
        "kind": "endpoint_evidence",
        "connector_id": str(connector.get("connector_id") or ""),
        "endpoint_id": str(endpoint.id),
        "device_id": device_id,
        "command_id": command_id,
        "outcome": outcome,
    }
    try:
        bundle, verify, error = read_evidence(transport)
        if error is not None:
            record["error"] = error
        else:
            record["bundle_digest"] = canonical.digest(bundle) if bundle is not None else None
            if isinstance(verify, Mapping):
                record["head_digest"] = verify.get("head_digest")
                record["count"] = verify.get("checked")
                record["valid"] = bool(verify.get("valid"))
                record["verify"] = dict(verify)
            else:
                record["valid"] = False
        HostLedger(config.host_ledger_path).append(record, kind="endpoint_evidence")
        return record
    except Exception as exc:  # noqa: BLE001 - evidence is supplementary to the call
        failure = {
            **record,
            "kind": "endpoint_evidence_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        try:
            HostLedger(config.host_ledger_path).append(
                failure, kind="endpoint_evidence_error"
            )
        except Exception:  # noqa: BLE001 - never mask the command outcome
            pass
        return None


def governed_call(
    connector: Mapping[str, Any],
    launch_config: Mapping[str, Any],
    spec: Mapping[str, Any],
    *,
    call_tool: Callable[..., dict[str, Any]],
    list_tools: Callable[..., list[dict[str, Any]]],
    config: MHSConfig | None = None,
) -> dict[str, Any] | None:
    """Govern one ``mcp_call`` on an MHS connector.

    Returns ``None`` for a non-MHS connector or a non-capability MHS tool, so
    the generic transport path runs unchanged.  A governed call returns the
    endpoint's original MCP tool result (text/raw/isError intact).  The
    operator tools (``mhs__reset``, ``mhs__permit``) are refused.
    """
    if not is_mhs_connector(connector):
        return None
    tool_name = str(spec.get("tool") or "")
    row_id = str(connector.get("connector_id") or "")
    if tool_name in OPERATOR_TOOLS:
        # Hidden by mhs.mcp unless a settings document sets operator_tools;
        # refused here either way, before any endpoint call.
        return _tool_error(
            "MHS.AUTH.FORBIDDEN",
            f"{tool_name} is an operator tool: a reset or a permit is a human decision and "
            "is never run through an agent connector. The operator uses the host operator "
            "route (python3 -m openai4s_mhs safety reset ... / openai4s_mhs.operator_route).",
            details={
                "tool": tool_name,
                "connector_id": row_id,
                "policy": "operator_route_only",
                "retryable": False,
            },
        )
    resolved = connector_config(connector, config)
    if resolved is None:
        return _tool_error(
            "MHS.HOST.CONFIG_REQUIRED",
            "the MHS connector's settings document could not be resolved; "
            "refusing to run the call ungoverned",
            details={"connector_id": row_id},
        )
    effective, endpoint = resolved
    try:
        tools = list_tools(row_id, dict(launch_config))
    except Exception:  # noqa: BLE001 - let the generic path report the failure
        return None
    marker = _capability_marker(tools, tool_name)
    if marker is None:
        # Discovery/read/safety/operations/evidence (and non-capability tools)
        # stay on the ordinary, approval-gated transport path.
        return None
    device_id = str(marker.get("device_id") or "")
    capability_id = str(marker.get("capability_id") or "")
    if not device_id or not capability_id:
        return _tool_error(
            "MHS.HOST.PROTOCOL_ERROR",
            "the projected capability tool has no x-mhs identity",
            details={"tool": tool_name},
        )
    transport = HostMCPTransport(call_tool, row_id, launch_config, tools)
    arguments = spec.get("args") if isinstance(spec.get("args"), Mapping) else {}
    try:
        governed = invoke_via(
            transport,
            str(endpoint.id),
            device_id,
            capability_id,
            dict(arguments or {}),
            config=effective,
            return_result=True,
        )
    except MCPOutcomeUnknown as exc:
        _record_endpoint_evidence(
            transport,
            effective,
            endpoint,
            connector,
            device_id=device_id,
            command_id=str(exc.command_id or "") or None,
            outcome="unknown",
        )
        return _tool_error(
            exc.code,
            exc.message,
            details={
                "command_id": exc.command_id,
                "reconcile_required": True,
                "retry_safe": False,
                **({"cause": exc.details.get("cause")} if exc.details.get("cause") else {}),
            },
        )
    except MCPInvokeError as exc:
        _record_endpoint_evidence(
            transport,
            effective,
            endpoint,
            connector,
            device_id=device_id,
            command_id=str(exc.command_id or "") or None,
            outcome="error",
        )
        return _tool_error(
            exc.code,
            exc.message,
            details={
                "command_id": exc.command_id,
                "retry_safe": exc.retry_safe,
                **exc.details,
            },
        )
    receipt = governed["receipt"]
    _record_endpoint_evidence(
        transport,
        effective,
        endpoint,
        connector,
        device_id=device_id,
        command_id=str(governed.get("command_id") or "") or None,
        outcome=str(receipt.get("status") or "completed"),
    )
    return governed["result"]


def trusted_emergency_stop(
    connector: Mapping[str, Any],
    launch_config: Mapping[str, Any],
    spec: Mapping[str, Any],
    *,
    call_tool: Callable[..., dict[str, Any]],
    config: MHSConfig | None = None,
) -> dict[str, Any]:
    """Run ``mhs__estop`` for an enabled MHS connector without the prompt."""
    row_id = str(connector.get("connector_id") or "")
    resolved = connector_config(connector, config)
    if resolved is None:
        return {
            "error": "MHS.HOST.CONFIG_REQUIRED: the MHS connector's settings "
            "document could not be resolved"
        }
    effective, endpoint = resolved
    # ``CallMCPTool`` carries the tool arguments under ``args``; a direct host
    # call may put them at the top level.  Accept both spellings, but only for
    # this narrow action.
    arguments = spec.get("args") if isinstance(spec.get("args"), Mapping) else {}
    device_id = str(spec.get("device_id") or arguments.get("device_id") or "")
    if not device_id:
        return {"error": "MHS.PROTOCOL.INVALID_PARAMS: device_id is required"}
    reason = str(
        spec.get("reason")
        or arguments.get("reason")
        or "OpenAI4S trusted emergency stop"
    )
    transport = HostMCPTransport(call_tool, row_id, launch_config)
    try:
        result = emergency_stop_via(
            transport,
            str(endpoint.id),
            device_id,
            reason,
            effective,
            connector=connector,
        )
    except EmergencyStopError as exc:
        return {"error": f"{exc.code}: {exc.message}"}
    receipt = result["receipt"]
    text = (
        f"MHS emergency stop {receipt.get('status')} for {device_id} "
        f"(latched={bool(result.get('latched'))})"
    )
    return {
        "is_error": False,
        "text": text,
        "raw": {
            "isError": False,
            "content": [{"type": "text", "text": text}],
            "structuredContent": {
                "estop": receipt,
                "device_id": device_id,
                "endpoint_id": str(endpoint.id),
                "trusted_stop": True,
                "audit": result.get("audit"),
                "audit_error": result.get("audit_error"),
            },
        },
    }


def export_host_package(
    config: MHSConfig,
    endpoint_id: str,
    *,
    connector_command: Sequence[str] | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Export a host package containing the chain and the endpoint bundle.

    The endpoint bundle is exported through the real MCP path and every
    component is verified offline; a caller can persist the returned package
    and verify it later with :func:`host_evidence.verify_package`.
    """
    evidence = export_evidence(
        endpoint_id,
        config=config,
        connector_command=connector_command,
        timeout_s=timeout_s,
    )
    ledger = HostLedger(config.host_ledger_path)
    package = export_package(ledger, [evidence["bundle"]])
    return {
        "package": package,
        "endpoint_verify": evidence.get("verify"),
        "package_verify": verify_package(package),
    }
