"""MCP-first host adapter for the acceptance demo.

The demo does not import the native MHS tool overlay.  Every operation goes
through OpenAI4S's real ``MCPManager``:

    OpenAI4S MCPManager ──stdio──> `python -m mhs.mcp --endpoint … --operator-tools` ──MHS──> endpoint

The demo is an operator's script: it issues permits and resets an e-stop, which
only the host operator route may do, so its connectors use that route's command
line (:func:`openai4s_mhs.mcpconfig.operator_argv`).  An agent connector row
never carries ``--operator-tools``.  The settings document is the demo's own
(``--config``), never the operator's ``~/.openai4s/mhs.json``.

The adapter presents the small host API the demo needs (discover, read, command,
e-stop/reset, evidence, ledger) so the workflow can be driven exactly as a host
would drive it, while every call is an MCP ``tools/call`` (the evidence bundle
is an MCP ``resources/read``).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mhs.canonical import ulid
from mhs.evidence import verify_bundle
from openai4s.mcp_client import MCPManager
from openai4s_mhs.config import MHSConfig
from openai4s_mhs.mcpconfig import connector_env, connector_id, operator_argv


class MCPDemoError(RuntimeError):
    """A call failed at the MCP/MHS boundary (no receipt was produced)."""

    def __init__(self, message: str, code: str = "MCP.TOOL_ERROR") -> None:
        super().__init__(message)
        self.code = code


class MCPHostAdapter:
    """Drive MHS endpoints through OpenAI4S's MCPManager (no native tools)."""

    def __init__(self, config: MHSConfig, *, timeout: float = 60.0) -> None:
        self.manager = MCPManager()
        self.config = config
        self.endpoints = {spec.id: spec for spec in config.endpoints}
        self.connectors: dict[str, tuple[str, dict[str, Any]]] = {}
        self._tool_cache: dict[str, list[dict[str, Any]]] = {}
        self._device_endpoint: dict[str, str] = {}
        self._device_capability: dict[str, dict[str, dict[str, Any]]] = {}
        self._manifests: dict[str, dict[str, Any]] = {}
        self._ledger: list[dict[str, Any]] = []
        # OpenAI4S gives each connector a least-privilege environment: name the
        # source trees (the stdio conveyor is spawned by its connector) and pass
        # the caller's no-bytecode choice on.
        child_env = dict(connector_env())
        if os.environ.get("PYTHONPATH"):
            child_env["PYTHONPATH"] = os.environ["PYTHONPATH"]
        if os.environ.get("PYTHONDONTWRITEBYTECODE"):
            child_env["PYTHONDONTWRITEBYTECODE"] = os.environ["PYTHONDONTWRITEBYTECODE"]
        for spec in config.endpoints:
            row = {
                "id": connector_id(spec),
                "command": operator_argv(spec, config, python=sys.executable),
                "transport": "stdio",
                "timeout": timeout,
                "env": child_env,
            }
            self.connectors[spec.id] = (row["id"], row)

    # -- plumbing ------------------------------------------------------
    def _tools(self, endpoint_id: str) -> list[dict[str, Any]]:
        if endpoint_id not in self._tool_cache:
            connector_id, config = self.connectors[endpoint_id]
            self._tool_cache[endpoint_id] = [
                item for item in self.manager.list_tools(connector_id, config) if isinstance(item, dict)
            ]
        return self._tool_cache[endpoint_id]

    def _call(self, endpoint_id: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        connector_id, config = self.connectors[endpoint_id]
        response = self.manager.call_tool(connector_id, config, tool, arguments)
        if response.get("is_error"):
            structured = (response.get("raw") or {}).get("structuredContent") or {}
            error = structured.get("mhs_error") or {}
            code = str(error.get("mhs_code") or "MCP.TOOL_ERROR")
            raise MCPDemoError(
                f"{code}: {error.get('message') or response.get('text') or 'MCP tool failed'}",
                code=code,
            )
        return response

    @staticmethod
    def _payload(response: dict[str, Any], key: str) -> Any:
        structured = (response.get("raw") or {}).get("structuredContent") or {}
        if key in structured:
            return structured[key]
        receipt = structured.get("receipt")
        if receipt is not None:
            return receipt
        for line in reversed(str(response.get("text") or "").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise MCPDemoError(f"MCP response carried no {key!r} payload")

    def _discover(self) -> None:
        if self._manifests:
            return
        for endpoint_id in self.connectors:
            try:
                response = self._call(endpoint_id, "mhs__devices", {})
                # mhs__devices is a compact summary; the manifest (capabilities,
                # safety, fidelity) comes from mhs__inspect.
                devices = [
                    self._payload(
                        self._call(endpoint_id, "mhs__inspect", {"device_id": item["device_id"]}),
                        "inspect",
                    )
                    for item in self._payload(response, "devices") or []
                    if isinstance(item, dict) and item.get("device_id")
                ]
            except MCPDemoError:
                continue
            capabilities: dict[str, dict[str, Any]] = {}
            for tool in self._tools(endpoint_id):
                meta = tool.get("x-mhs") or {}
                capability_id = meta.get("capability_id")
                device_id = meta.get("device_id")
                if isinstance(capability_id, str) and isinstance(device_id, str):
                    capabilities.setdefault(device_id, {})[capability_id] = {
                        "tool": str(tool.get("name")),
                        "requires_permit": bool(meta.get("requires_permit")),
                    }
            for device in devices:
                device_id = str(device.get("device_id") or "")
                if not device_id:
                    continue
                self._device_endpoint[device_id] = endpoint_id
                self._device_capability[device_id] = capabilities.get(device_id, {})
                self._manifests[device_id] = dict(device)

    def _endpoint_for(self, device_id: str, endpoint_id: str | None = None) -> str:
        self._discover()
        resolved = endpoint_id or self._device_endpoint.get(device_id)
        if not resolved:
            raise MCPDemoError(f"unknown device {device_id!r} (not discovered over MCP)")
        return resolved

    # -- host surface used by the demo ---------------------------------
    def devices(self) -> list[dict[str, Any]]:
        self._discover()
        out: list[dict[str, Any]] = []
        for device_id, manifest in self._manifests.items():
            summary = dict(manifest)
            summary["endpoint_id"] = self._device_endpoint.get(device_id)
            out.append(summary)
        return out

    def read(self, device_id: str, resource_id: str | None = None, **_: Any) -> dict[str, Any]:
        endpoint_id = self._endpoint_for(device_id)
        manifest = self._manifests.get(device_id) or {}
        resources = manifest.get("resources") or []
        target = resource_id or (
            str(resources[0].get("resource_id")) if resources else "state"
        )
        response = self._call(
            endpoint_id, "mhs__read", {"device_id": device_id, "resource_id": target}
        )
        result = self._payload(response, "read")
        return dict(result or {})

    def command(
        self,
        device_id: str,
        capability_id: str,
        payload: dict[str, Any] | None = None,
        *,
        endpoint_id: str | None = None,
        expected_revision: int | None = None,
        command_id: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        resolved_endpoint = self._endpoint_for(device_id, endpoint_id)
        self._discover()
        binding = (self._device_capability.get(device_id) or {}).get(capability_id)
        if binding is None:
            raise MCPDemoError(
                f"MCP projection exposes no tool for {capability_id!r} on {device_id!r}",
                code="MCP.TOOL_NOT_FOUND",
            )
        arguments: dict[str, Any] = dict(payload or {})
        arguments["command_id"] = command_id or ulid()
        if expected_revision is not None:
            arguments["expected_revision"] = int(expected_revision)
        receipt = dict(self._payload(
            self._call(resolved_endpoint, binding["tool"], arguments), "receipt"
        ) or {})
        if binding.get("requires_permit") and receipt.get("status") == "rejected":
            error_code = str((receipt.get("error") or {}).get("mhs_code") or "")
            if error_code.startswith("MHS.SAFETY.PERMIT"):
                permit = self._request_permit(
                    resolved_endpoint, device_id, capability_id, payload or {}
                )
                retry_arguments = dict(payload or {})
                retry_arguments["command_id"] = ulid()
                retry_arguments["permit_id"] = permit
                receipt = dict(self._payload(
                    self._call(resolved_endpoint, binding["tool"], retry_arguments), "receipt"
                ) or {})
        self._record(resolved_endpoint, device_id, receipt)
        return receipt

    def _request_permit(
        self, endpoint_id: str, device_id: str, capability_id: str, payload: dict[str, Any]
    ) -> str:
        """Host approval flow over MCP: digest the exact input, request a permit."""
        response = self._call(
            endpoint_id,
            "mhs__permit",
            {
                "device_id": device_id,
                "capability_id": capability_id,
                "input": dict(payload),
                "ttl_s": 60,
                "approvals": [
                    {
                        # The demo host policy approves a simulated R1 device.
                        "principal": "openai4s:demo-operator",
                        "method": "policy_rule",
                    }
                ],
            },
        )
        permit = self._payload(response, "permit") or {}
        permit_id = permit.get("permit_id")
        if not isinstance(permit_id, str) or not permit_id:
            raise MCPDemoError("mhs__permit returned no permit_id", code="MHS.SAFETY.PERMIT_INVALID")
        return permit_id

    def estop(self, device_id: str, reason: str = "demo e-stop", endpoint_id: str | None = None) -> dict[str, Any]:
        resolved = self._endpoint_for(device_id, endpoint_id)
        receipt = dict(self._payload(
            self._call(resolved, "mhs__estop", {"device_id": device_id, "reason": reason}),
            "estop",
        ) or {})
        self._record(resolved, device_id, receipt)
        return receipt

    def reset(self, device_id: str, endpoint_id: str | None = None, **_: Any) -> dict[str, Any]:
        resolved = self._endpoint_for(device_id, endpoint_id)
        receipt = dict(self._payload(
            self._call(resolved, "mhs__reset", {"device_id": device_id}), "reset"
        ) or {})
        self._record(resolved, device_id, receipt)
        return receipt

    def safety_status(self, device_id: str) -> dict[str, Any]:
        resolved = self._endpoint_for(device_id)
        return dict(self._payload(
            self._call(resolved, "mhs__safety", {"device_id": device_id}), "safety"
        ) or {})

    def evidence_export(self, endpoint_id: str) -> dict[str, Any]:
        """The full bundle: the resource that ``mhs__evidence`` names, over ``resources/read``."""
        summary = self._payload(self._call(endpoint_id, "mhs__evidence", {"last_n": 0}), "evidence") or {}
        uri = summary.get("uri")
        if not isinstance(uri, str) or not uri:
            raise MCPDemoError("mhs__evidence named no evidence resource", code="MHS.HOST.PROTOCOL_ERROR")
        connector_id_, config = self.connectors[endpoint_id]
        document = self.manager.read_resource(connector_id_, config, uri)
        contents = document.get("contents") if isinstance(document, dict) else None
        text = contents[0].get("text") if isinstance(contents, list) and contents else None
        bundle = json.loads(text) if isinstance(text, str) else None
        if not isinstance(bundle, dict):
            raise MCPDemoError(f"{uri} returned no evidence bundle", code="MHS.HOST.PROTOCOL_ERROR")
        return bundle

    def evidence_verify(self, bundle: dict[str, Any], endpoint_id: str | None = None) -> dict[str, Any]:
        report = verify_bundle(bundle)
        payload = report.to_dict() if hasattr(report, "to_dict") else dict(report)
        return {"endpoint_id": endpoint_id, **payload}

    def ledger(self) -> list[dict[str, Any]]:
        return list(self._ledger)

    def _record(self, endpoint_id: str, device_id: str, receipt: dict[str, Any]) -> None:
        if not receipt:
            return
        self._ledger.append(
            {
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "capability_id": receipt.get("capability_id"),
                "command_id": receipt.get("command_id"),
                "receipt_id": receipt.get("receipt_id"),
                "status": receipt.get("status"),
                "state_hash_after": receipt.get("state_hash_after"),
                "evidence_digest": (receipt.get("evidence") or {}).get("digest"),
            }
        )

    def close(self) -> None:
        try:
            self.manager.shutdown()
        except Exception:  # noqa: BLE001 - teardown must not mask the reason
            pass


__all__ = ["MCPDemoError", "MCPHostAdapter"]
