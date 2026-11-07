"""Test support: an in-process MHS JSON-RPC endpoint and OpenAI4S bootstrap.

``FakeMHSServer`` speaks the MHS request/result shapes over a dictionary
transport (no sockets), so the native path -- HostDispatcher -> MHSHost ->
client -- can be exercised without the SDK's server/client transport.  It uses
the SDK's real ``EvidenceLog`` when importable so evidence verification tests
check a genuine hash chain.
"""

from __future__ import annotations

import json
import threading
from typing import Any

try:  # the SDK's canonical/evidence core is present while client/server land
    from mhs.canonical import digest as _digest
    from mhs.evidence import EvidenceLog
except Exception:  # pragma: no cover - only when the SDK is absent
    _digest = None
    EvidenceLog = None  # type: ignore[assignment]


class FakeMHSError(RuntimeError):
    """An MHS error carrying the frozen ``.code``/``.data``/``.message`` shape."""

    def __init__(self, code: str, message: str, data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


def _digest_of(payload: Any) -> str:
    if _digest is not None:
        return _digest(payload)
    import hashlib

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class FakeMHSServer:
    """One in-process endpoint with one device.

    ``mode`` selects simulated/hardware; ``risk_class`` and ``permit_patterns``
    shape the safety envelope.  ``unknown_once`` makes the next mutating command
    return an ``unknown`` receipt (the lost-receipt case).
    """

    _RECEIPT_SEQ = 0

    def __init__(
        self,
        *,
        endpoint_id: str = "mhs://fake",
        device_id: str = "mhs://fake/conveyor",
        display_name: str = "Fake conveyor (simulated)",
        mode: str = "simulated",
        risk_class: str = "R1",
        permit_patterns: tuple[str, ...] = (),
        unknown_once: bool = False,
        resources: int = 1,
    ) -> None:
        self.endpoint_id = endpoint_id
        self.device_id = device_id
        self.display_name = display_name
        self.mode = mode
        self.risk_class = risk_class
        self.permit_patterns = list(permit_patterns)
        self.unknown_once = unknown_once
        self.revision = 0
        self.tick = 0
        self.sessions: dict[str, dict] = {}
        self.permits: dict[str, dict] = {}
        self.operations: dict[str, dict] = {}
        self.session_seq = 0
        self.permit_seq = 0
        self.receipts: list[dict] = []
        self.resources = [f"world{i}" if i else "world" for i in range(resources)]
        self._log = EvidenceLog(self.endpoint_id) if EvidenceLog is not None else None
        self._lock = threading.Lock()

    # -- JSON-RPC envelope -------------------------------------------------
    def handle(self, request: dict) -> dict:
        """Handle one JSON-RPC request object and return a response object."""
        request_id = request.get("id")
        method = request.get("method")
        params = dict(request.get("params") or {})
        try:
            result = self.dispatch(str(method), params)
        except FakeMHSError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": exc.message,
                    "data": {"mhs_code": exc.code, **exc.data},
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(exc),
                    "data": {"mhs_code": "MHS.INTERNAL.ERROR"},
                },
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    # -- MHS methods -------------------------------------------------------
    def dispatch(self, method: str, params: dict) -> Any:
        if method == "hello":
            return {
                "mhs_version": "1.0",
                "endpoint_id": self.endpoint_id,
                "conformance": {"level": "CL3"},
                "limits": {"receipt_retention_days": 30},
            }
        if method == "devices":
            return [{"device_id": self.device_id, "mode": self.mode}]
        if method == "inspect":
            return self.manifest()
        if method == "open_session":
            return self.open_session(
                device_ids=params.get("device_ids"),
                capabilities=params.get("capabilities"),
                mode=params.get("mode"),
                ttl_s=int(params.get("ttl_s", 600)),
            )
        if method == "read":
            return self.read(
                params.get("resource"),
                device_id=params.get("device_id"),
                session_id=params.get("session_id"),
            )
        if method == "command":
            return self.invoke(
                params["capability_id"],
                params.get("input"),
                device_id=params.get("device_id"),
                resource=params.get("resource"),
                expected_revision=params.get("expected_revision"),
                permit_id=params.get("permit_id"),
                session_id=params.get("session_id"),
                command_id=params.get("command_id"),
            )
        if method == "permit":
            return self.permit(
                params["capability_id"],
                params["input_digest"],
                ttl_s=int(params.get("ttl_s", 60)),
                approvals=params.get("approvals") or [],
                session_id=params.get("session_id"),
            )
        if method == "safety_status":
            return self.safety_status()
        if method == "estop":
            return self.estop(params.get("reason") or "test")
        if method == "reset":
            return self.reset()
        if method == "operations":
            return {"operations": list(self.operations.values())}
        if method == "cancel":
            operation_id = params["operation_id"]
            operation = self.operations.get(operation_id)
            if operation is None:
                raise FakeMHSError(
                    "MHS.HOST.OPERATION_NOT_FOUND", f"unknown operation {operation_id}"
                )
            operation["status"] = "cancelled"
            return {"operation_id": operation_id, "status": "cancelled", "cancelled": True}
        if method == "export_evidence":
            return self.export_evidence()
        if method == "close_session":
            self.sessions.pop(params.get("session_id"), None)
            return {"closed": True}
        if method == "close":
            return {"closed": True}
        raise FakeMHSError("MHS.PROTOCOL.METHOD_NOT_FOUND", f"unknown method {method!r}")

    # -- state -------------------------------------------------------------
    def manifest(self) -> dict:
        capabilities = [
            {
                "capability_id": "cap.world.state.v1",
                "title": "Read the world state",
                "resource": self.resources[0],
            },
            {
                "capability_id": "cap.world.step.v1",
                "title": "Advance the world",
                "resource": self.resources[0],
            },
            {
                "capability_id": "cap.actuation.valve.v1",
                "title": "Set the diverter gate",
                "resource": self.resources[0],
                "requires_permit": bool(self.permit_patterns),
            },
        ]
        return {
            "device_id": self.device_id,
            "display_name": self.display_name,
            "mode": self.mode,
            "resources": [
                {"resource_id": rid, "kind": "world.sim"} for rid in self.resources
            ],
            "capabilities": capabilities,
            "safety": {
                "risk_class": self.risk_class,
                "requires_permit": list(self.permit_patterns),
                "safe_state": {"description": "drive stopped"},
            },
            "fidelity": {
                "engine": "fake",
                "fidelity_level": "F0",
                "determinism": {"kind": "exact"},
                "gaps": ["test double: no physics"],
            },
            "profile": {"summary": "In-process fake endpoint for integration tests."},
        }

    def open_session(
        self,
        *,
        device_ids: list[str] | None = None,
        capabilities: list[str] | None = None,
        mode: str | None = None,
        ttl_s: int = 600,
    ) -> dict:
        for device_id in device_ids or [self.device_id]:
            if device_id != self.device_id:
                raise FakeMHSError(
                    "MHS.DEVICE.UNKNOWN", f"unknown device {device_id!r}"
                )
        if mode != self.mode:
            raise FakeMHSError(
                "MHS.SESSION.MODE_MISMATCH",
                f"session mode {mode!r} does not match device mode {self.mode!r}",
            )
        self.session_seq += 1
        session_id = f"mhs_s_{self.session_seq:04d}"
        self.sessions[session_id] = {
            "capabilities": list(capabilities or []),
            "ttl_s": ttl_s,
        }
        return {"session_id": session_id, "expires_in_s": ttl_s}

    def read(
        self,
        resource: str | None,
        *,
        device_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        del device_id
        if session_id is not None and session_id not in self.sessions:
            raise FakeMHSError("MHS.SESSION.UNKNOWN", f"unknown session {session_id!r}")
        if resource not in self.resources:
            raise FakeMHSError("MHS.RESOURCE.UNKNOWN", f"unknown resource {resource!r}")
        return {
            "resource_id": resource,
            "revision": self.revision,
            "state": {"tick": self.tick, "drive": "stopped", "estop": self.estop_state},
        }

    def permit(
        self,
        capability_id: str,
        input_digest: str,
        *,
        ttl_s: int = 60,
        approvals: list[dict] | None = None,
        session_id: str | None = None,
    ) -> dict:
        self.permit_seq += 1
        permit_id = f"permit-{self.permit_seq:04d}"
        self.permits[permit_id] = {
            "capability_id": capability_id,
            "input_digest": input_digest,
            "ttl_s": ttl_s,
            "approvals": list(approvals or []),
            "session_id": session_id,
        }
        return {"permit_id": permit_id, "expires_in_s": ttl_s}

    def invoke(
        self,
        capability_id: str,
        payload: dict | None,
        *,
        device_id: str | None = None,
        resource: str | None = None,
        expected_revision: int | None = None,
        permit_id: str | None = None,
        session_id: str | None = None,
        command_id: str | None = None,
    ) -> dict:
        payload = dict(payload or {})
        del device_id
        session = self.sessions.get(str(session_id))
        if session is None:
            raise FakeMHSError("MHS.SESSION.UNKNOWN", f"unknown session {session_id!r}")
        if capability_id not in session["capabilities"]:
            return self._receipt(
                capability_id,
                payload,
                status="rejected",
                command_id=command_id,
                error={
                    "mhs_code": "MHS.SESSION.CAPABILITY_NOT_GRANTED",
                    "message": "capability was not granted to this session",
                },
            )
        if resource is not None and resource not in self.resources:
            return self._receipt(
                capability_id,
                payload,
                status="rejected",
                command_id=command_id,
                error={"mhs_code": "MHS.RESOURCE.UNKNOWN", "message": "unknown resource"},
            )
        if expected_revision is not None and expected_revision != self.revision:
            return self._receipt(
                capability_id,
                payload,
                status="rejected",
                command_id=command_id,
                error={
                    "mhs_code": "MHS.CONFLICT.REVISION",
                    "message": f"expected {expected_revision}, at {self.revision}",
                },
            )
        required = any(
            capability_id.startswith(pattern[:-1]) if pattern.endswith(".*") else capability_id == pattern
            for pattern in self.permit_patterns
        )
        if required:
            permit = self.permits.get(str(permit_id))
            if permit is None:
                return self._receipt(
                    capability_id,
                    payload,
                    status="rejected",
                    command_id=command_id,
                    error={
                        "mhs_code": "MHS.SAFETY.PERMIT_INVALID",
                        "message": "capability requires a permit",
                    },
                )
            if permit["input_digest"] != _digest_of(payload):
                return self._receipt(
                    capability_id,
                    payload,
                    status="rejected",
                    command_id=command_id,
                    error={
                        "mhs_code": "MHS.SAFETY.PERMIT_INVALID",
                        "message": "permit is bound to a different input",
                    },
                )
        if self.unknown_once:
            self.unknown_once = False
            return self._receipt(
                capability_id,
                payload,
                status="unknown",
                command_id=command_id,
                error={
                    "mhs_code": "MHS.OUTCOME.UNKNOWN",
                    "message": "simulated lost receipt: effect may have applied",
                },
            )
        if capability_id == "cap.world.step.v1":
            if self.estop_state != "released":
                return self._receipt(
                    capability_id,
                    payload,
                    status="rejected",
                    command_id=command_id,
                    error={
                        "mhs_code": "MHS.SAFETY.INTERLOCK_OPEN",
                        "message": "e-stop is engaged",
                    },
                )
            self.tick += int(payload.get("ticks") or 0)
            self.revision += 1
        elif capability_id == "cap.actuation.valve.v1":
            self.revision += 1
        elif capability_id != "cap.world.state.v1":
            return self._receipt(
                capability_id,
                payload,
                status="failed",
                command_id=command_id,
                error={
                    "mhs_code": "MHS.CAPABILITY.NOT_BOUND",
                    "message": f"no capability {capability_id}",
                },
            )
        return self._receipt(capability_id, payload, status="completed", command_id=command_id)

    def safety_status(self) -> dict:
        return {
            "estop": self.estop_state,
            "latched": self.estop_state != "released",
            "interlocks": [],
        }

    def estop(self, reason: str) -> dict:
        self.estop_state = "engaged"
        self.estop_reason = reason
        return self._receipt(
            "cap.device.estop.v1",
            {"reason": reason},
            status="completed",
            command_id=None,
        )

    def reset(self) -> dict:
        self.estop_state = "released"
        return self._receipt(
            "cap.device.reset.v1", {}, status="completed", command_id=None
        )

    estop_state = "released"
    estop_reason = ""

    def export_evidence(self) -> dict:
        if self._log is not None:
            return self._log.export()
        return {
            "endpoint": self.endpoint_id,
            "receipts": list(self.receipts),
            "head_digest": self.receipts[-1]["evidence"]["digest"] if self.receipts else None,
            "count": len(self.receipts),
        }

    # -- receipts ----------------------------------------------------------
    def _receipt(
        self,
        capability_id: str,
        payload: dict,
        *,
        status: str,
        command_id: str | None,
        error: dict | None = None,
    ) -> dict:
        with self._lock:
            FakeMHSServer._RECEIPT_SEQ += 1
            seq = FakeMHSServer._RECEIPT_SEQ
            receipt: dict[str, Any] = {
                "receipt_id": f"01J8ZQ3V6Y7M2N4P6R8S0T{seq:04X}",
                "command_id": command_id or f"01J8ZQ3V6Y7M2N4P6R8S0Z{seq:04X}",
                "session_id": "mhs_s_0001",
                "endpoint_id": self.endpoint_id,
                "device_id": self.device_id,
                "capability_id": capability_id,
                "input_digest": _digest_of(payload),
                "status": status,
                "mode": self.mode,
                "accepted_at": "2026-01-01T00:00:00Z",
                "state_revision_after": self.revision,
                "state_hash_after": _digest_of({"tick": self.tick, "rev": self.revision}),
                "output": {"ok": status == "completed"},
            }
            if error is not None:
                receipt["error"] = {
                    "code": error["mhs_code"],
                    "message": error["message"],
                    "retryable": False,
                }
            if self._log is not None:
                receipt = self._log.append(receipt)
            self.receipts.append(receipt)
            return json.loads(json.dumps(receipt))


class FakeMHSClient:
    """A dict-transport MHS client whose methods match the SDK's client."""

    def __init__(self, server: FakeMHSServer):
        self.server = server
        self._id = 0
        self.closed = False

    def _call(self, method: str, params: dict | None = None) -> Any:
        self._id += 1
        response = self.server.handle(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        )
        if "error" in response:
            error = response["error"]
            data = dict(error.get("data") or {})
            code = data.pop("mhs_code", "MHS.INTERNAL.ERROR")
            raise FakeMHSError(code, error.get("message", ""), data)
        return response.get("result")

    def hello(self) -> dict:
        return self._call("hello")

    def devices(self) -> list[dict]:
        return self._call("devices")

    def inspect(self, device_id: str | None = None) -> dict:
        device_id = device_id or self.server.device_id
        result = self._call("inspect", {"device_id": device_id})
        if isinstance(result, dict) and "devices" in result:
            for item in result["devices"]:
                if item.get("device_id") == device_id:
                    return item
        return result

    def open_session(self, **kwargs: Any) -> dict:
        return self._call("open_session", kwargs)

    def read(self, resource_id: str, **kwargs: Any) -> dict:
        return self._call("read", {"resource": resource_id, **kwargs})

    def invoke(self, capability_id: str, input: dict | None = None, **kwargs: Any) -> dict:
        return self._call(
            "command", {"capability_id": capability_id, "input": input or {}, **kwargs}
        )

    def permit(self, capability_id: str, input_digest: str, **kwargs: Any) -> dict:
        return self._call(
            "permit",
            {"capability_id": capability_id, "input_digest": input_digest, **kwargs},
        )

    def safety_status(self, **kwargs: Any) -> dict:
        return self._call("safety_status", kwargs)

    def estop(self, reason: str = "", **kwargs: Any) -> dict:
        return self._call("estop", {"reason": reason, **kwargs})

    def reset(self, **kwargs: Any) -> dict:
        return self._call("reset", kwargs)

    def operations(self, **kwargs: Any) -> dict:
        return self._call("operations", kwargs)

    def cancel(self, operation_id: str, **kwargs: Any) -> dict:
        return self._call("cancel", {"operation_id": operation_id, **kwargs})

    def export_evidence(self) -> dict:
        return self._call("export_evidence")

    def close_session(self, session_id: str) -> dict:
        return self._call("close_session", {"session_id": session_id})

    def close(self) -> None:
        self.closed = True


def fake_connect(server: FakeMHSServer):
    """Return an ``sdk_connect`` callable bound to one fake server."""
    clients: list[FakeMHSClient] = []

    def connect(target: Any) -> FakeMHSClient:
        client = FakeMHSClient(server)
        clients.append(client)
        return client

    connect.clients = clients  # type: ignore[attr-defined]
    return connect


__all__ = [
    "FakeMHSClient",
    "FakeMHSError",
    "FakeMHSServer",
    "fake_connect",
]
