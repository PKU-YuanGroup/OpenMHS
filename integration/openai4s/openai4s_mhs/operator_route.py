"""The host operator route: e-stop resets and permits are human decisions.

``mhs.mcp`` lists ``mhs__reset`` and ``mhs__permit`` only when it is launched
with ``--operator-tools``.  This module is the one place the OpenAI4S host
uses that flag:

* the agent connector rows built by :mod:`openai4s_mhs.mcpconfig` never carry
  it, and the governed host route (:func:`openai4s_mhs.hostroute.governed_call`)
  refuses both tools on an agent row with ``MHS.AUTH.FORBIDDEN`` before any
  endpoint call, even if the settings document sets ``operator_tools``;
* :class:`OperatorRoute` opens a dedicated ``mhs.mcp --operator-tools``
  connection for an operator who is present.  It is never a connector row, so
  ``CallMCPTool`` cannot reach it.  When ``operator_token_file`` is set, the
  connection authenticates with that token (``--token-file``), so an endpoint
  that binds principals to tokens sees the operator, not the agent;
* every request, result and refusal is appended to the host ledger
  (``operator_*`` records) with the operator's name.

A permit is bound to the session and principal that requested it, so the
permitted command runs on the same operator connection (:meth:`OperatorRoute.invoke`,
governed by the same journal and ledger as the agent route).

``python3 -m openai4s_mhs safety reset DEVICE --operator NAME`` is the CLI form;
it also requires an interactive terminal.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from mhs import canonical

from .config import MHSConfig
from .host_evidence import HostLedger, HostLedgerError
from .mcp_invoke import (
    MCPInvokeError,
    _bounded_timeout,
    _child_env,
    _config_path,
    _endpoint,
    _mcp_client_module,
    _mcp_error_payload,
    _policy_ready,
    invoke_via,
)
from .mcpconfig import connector_id, operator_argv

__all__ = ["OPERATOR_TOOLS", "OperatorRoute", "OperatorRouteError", "reset"]

#: Tools only the operator route runs (``mhs.mcp`` hides them from agents).
OPERATOR_TOOLS = frozenset({"mhs__reset", "mhs__permit"})


class OperatorRouteError(MCPInvokeError):
    """A refused or failed operator action, with a stable code."""


def _operator_token_ready(config: MHSConfig, spec: Any) -> None:
    """A configured ``operator_token_file`` must be readable before the route launches ``mhs.mcp``.

    Otherwise the child exits on start-up and the failure looks like an unreachable endpoint (exit 3)
    although it is a settings error (``MHS.HOST.CONFIG_REQUIRED``, exit 2). Nothing is sent.
    """
    token_file = getattr(config, "operator_token_file", None)
    if not token_file or not getattr(spec, "url", None) or getattr(spec, "command", None):
        return  # no token configured, or a stdio endpoint (the token is only sent over HTTP)
    path = Path(str(token_file)).expanduser()
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise OperatorRouteError(
            "MHS.HOST.CONFIG_REQUIRED",
            f"operator_token_file {str(path)!r} cannot be read ({exc.strerror or exc}); nothing was sent",
        ) from exc
    if not token:
        raise OperatorRouteError("MHS.HOST.CONFIG_REQUIRED",
                                 f"operator_token_file {str(path)!r} is empty; nothing was sent")


class _Transport:
    """The ``tool_names``/``call`` pair :func:`invoke_via` needs."""

    def __init__(self, route: "OperatorRoute") -> None:
        self.route = route

    def tool_names(self) -> set[str]:
        return self.route.tool_names()

    def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self.route.call(name, arguments)


class OperatorRoute:
    """A dedicated ``mhs.mcp --operator-tools`` connection for one endpoint.

    ``operator`` names the human who decides (for example ``"human:alice"``);
    it is recorded with every ledger record of the route.  Devices are named
    by full id or by the last segment of it.
    """

    def __init__(
        self,
        endpoint_id: str,
        config: MHSConfig | None = None,
        *,
        operator: str,
        timeout_s: float | None = None,
        connector_command: Sequence[str] | None = None,
    ) -> None:
        if not isinstance(operator, str) or not operator.strip():
            raise OperatorRouteError(
                "MHS.AUTH.FORBIDDEN",
                "the operator route needs the name of the operator who decides",
            )
        self.operator = operator.strip()
        self.config = config or MHSConfig.load()
        _policy_ready(self.config)
        self.spec = _endpoint(self.config, endpoint_id)
        _operator_token_ready(self.config, self.spec)
        self.endpoint_id = endpoint_id
        self._command = list(connector_command) if connector_command is not None else None
        self._timeout_s = timeout_s
        self.connection: Any = None
        self.tools: list[dict[str, Any]] = []

    # -- connection ---------------------------------------------------------
    def argv(self) -> list[str]:
        if self._command is not None:
            return list(self._command)
        return operator_argv(self.spec, self.config, python=sys.executable,
                             config_path=_config_path(self.config))

    def __enter__(self) -> "OperatorRoute":
        module = _mcp_client_module()
        try:
            self.connection = module.MCPConnection(
                self.argv(),
                env=_child_env(self.spec),
                timeout=_bounded_timeout(self.config, self._timeout_s),
            )
            self.tools = [item for item in self.connection.list_tools() if isinstance(item, Mapping)]
        except BaseException:
            self.close()
            raise
        missing = OPERATOR_TOOLS - self.tool_names()
        if missing:
            self.close()
            raise OperatorRouteError(
                "MHS.HOST.PROTOCOL_ERROR",
                "the operator connection does not list " + ", ".join(sorted(missing))
                + " (is the integration enabled and the SDK current?)",
            )
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            finally:
                self.connection = None

    def tool_names(self) -> set[str]:
        return {str(item.get("name")) for item in self.tools if item.get("name")}

    def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if self.connection is None:
            raise OperatorRouteError("MHS.TRANSPORT.UNAVAILABLE", "the operator connection is not open")
        return self.connection.call_tool(name, dict(arguments or {}))

    def device(self, device_id: str) -> str:
        """The full device id for ``device_id`` (a full id or its last path segment)."""
        if "://" in str(device_id):
            return str(device_id)
        response = self.call("mhs__inspect", {"device_id": str(device_id)})
        structured = (response.get("raw") or {}).get("structuredContent") or {}
        manifest = structured.get("inspect") if isinstance(structured, Mapping) else None
        if bool(response.get("is_error")) or not isinstance(manifest, Mapping) or not manifest.get("device_id"):
            payload = _mcp_error_payload(response)
            raise OperatorRouteError(
                str(payload.get("mhs_code") or "MHS.DEVICE.UNKNOWN"),
                str(payload.get("message") or f"device {device_id!r} is not served by this endpoint"),
            )
        return str(manifest["device_id"])

    # -- ledger -------------------------------------------------------------
    def _ledger(self) -> HostLedger | None:
        try:
            return HostLedger(self.config.host_ledger_path)
        except HostLedgerError:
            return None

    def _append(self, ledger: HostLedger | None, kind: str, record: Mapping[str, Any]) -> str | None:
        if ledger is None:
            return "MHS.HOST.EVIDENCE_WRITE_FAILED: host ledger unavailable"
        try:
            ledger.append(
                {
                    "kind": kind,
                    "connector_id": connector_id(self.spec),
                    "endpoint_id": self.endpoint_id,
                    "operator": self.operator,
                    "route": "operator",
                    **dict(record),
                },
                kind=kind,
            )
        except HostLedgerError as exc:
            return f"{exc.code}: {exc.message}"
        return None

    def _refused(self, ledger: HostLedger | None, action: str, response: Mapping[str, Any],
                 **details: Any) -> OperatorRouteError:
        payload = _mcp_error_payload(response)
        code = str(payload.get("mhs_code") or "MHS.HOST.TOOL_ERROR")
        message = str(payload.get("message") or f"{action} failed")
        self._append(ledger, "operator_error", {"action": action, "mhs_code": code, "error": message,
                                                **details})
        return OperatorRouteError(code, message, details={"stage": action, "mhs_error": payload})

    # -- actions ------------------------------------------------------------
    def reset(self, device_id: str, *, reason: str) -> dict[str, Any]:
        """Release the e-stop latch of ``device_id``; returns the reset receipt.

        A refused reset (latch not engaged, an interlock open or unknown, the
        endpoint wants an operator token) comes back as a receipt with status
        ``rejected``, as the endpoint wrote it.  Nothing is retried.
        """
        reason_text = str(reason or "").strip()
        if not reason_text:
            raise OperatorRouteError("MHS.PROTOCOL.INVALID_PARAMS", "a reset needs a reason")
        device_id = self.device(device_id)
        ledger = self._ledger()
        audit_error = self._append(ledger, "operator_reset_request", {
            "device_id": device_id,
            "reason_digest": canonical.digest({"reason": reason_text}),
        })
        response = self.call("mhs__reset", {"device_id": device_id})
        if bool(response.get("is_error")):
            raise self._refused(ledger, "mhs__reset", response, device_id=device_id)
        structured = (response.get("raw") or {}).get("structuredContent") or {}
        receipt = structured.get("reset") if isinstance(structured, Mapping) else None
        if not isinstance(receipt, Mapping):
            raise OperatorRouteError("MHS.HOST.PROTOCOL_ERROR", "mhs__reset returned no receipt")
        receipt = dict(receipt)
        audit_error = self._append(ledger, "operator_reset_result", {
            "device_id": device_id,
            "receipt": receipt,
            "receipt_digest": canonical.digest(receipt),
            "outcome": str(receipt.get("status") or ""),
        }) or audit_error
        return {
            "endpoint_id": self.endpoint_id,
            "device_id": device_id,
            "operator": self.operator,
            "receipt": receipt,
            "audit_error": audit_error,
        }

    def permit(
        self,
        device_id: str,
        capability_id: str,
        input: Mapping[str, Any],  # noqa: A002 - the MHS field name
        *,
        resource: str | None = None,
        ttl_s: int = 60,
        method: str = "human_click",
    ) -> dict[str, Any]:
        """Issue a single-use permit bound to ``input``; the operator approved it."""
        device_id = self.device(device_id)
        payload = dict(input or {})
        arguments: dict[str, Any] = {
            "device_id": device_id,
            "capability_id": capability_id,
            "input": payload,
            "ttl_s": int(ttl_s),
            "approvals": [{"principal": self.operator, "method": str(method)}],
        }
        if resource:
            arguments["resource"] = resource
        ledger = self._ledger()
        audit_error = self._append(ledger, "operator_permit_request", {
            "device_id": device_id,
            "capability_id": capability_id,
            "arguments_digest": canonical.digest(payload),
            "approval_method": str(method),
        })
        response = self.call("mhs__permit", arguments)
        if bool(response.get("is_error")):
            raise self._refused(ledger, "mhs__permit", response, device_id=device_id,
                                capability_id=capability_id)
        structured = (response.get("raw") or {}).get("structuredContent") or {}
        permit = structured.get("permit") if isinstance(structured, Mapping) else None
        if not isinstance(permit, Mapping) or not permit.get("permit_id"):
            raise OperatorRouteError("MHS.HOST.PROTOCOL_ERROR", "mhs__permit returned no permit")
        permit = dict(permit)
        audit_error = self._append(ledger, "operator_permit_result", {
            "device_id": device_id,
            "capability_id": capability_id,
            "permit_id": permit.get("permit_id"),
            "input_digest": permit.get("input_digest"),
            "expires_at": permit.get("expires_at"),
        }) or audit_error
        return {"permit": permit, "audit_error": audit_error}

    def invoke(
        self,
        device_id: str,
        capability_id: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        permit_id: str | None = None,
        command_id: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Run a command on this connection, governed like the agent route.

        The journal, the reconciliation gate and the host ledger are the ones
        :func:`openai4s_mhs.mcp_invoke.invoke` uses; the approval recorded is
        the operator's.
        """
        return invoke_via(
            _Transport(self),
            self.endpoint_id,
            self.device(device_id),
            capability_id,
            dict(arguments or {}),
            config=self.config,
            command_id=command_id,
            permit_id=permit_id,
            expected_revision=expected_revision,
            approvals=[{"principal": self.operator, "method": "human_click", "route": "operator"}],
            timeout_s=self._timeout_s,
        )


def reset(
    endpoint_id: str,
    device_id: str,
    *,
    operator: str,
    reason: str,
    config: MHSConfig | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Reset one device's e-stop latch through the operator route."""
    with OperatorRoute(endpoint_id, config, operator=operator, timeout_s=timeout_s) as route:
        return route.reset(device_id, reason=reason)
