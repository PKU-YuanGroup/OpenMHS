"""MHSHost — the OpenAI4S-side host library for OpenMHS endpoints.

One object owns every endpoint the host knows about.  It is deliberately thin:
discovery, sessions, permits, hardware gating and the evidence ledger live here;
the wire protocol lives in the ``mhs`` SDK; the physical meaning lives in the
device manifest the endpoint publishes.

The invariants this class enforces (MHS host profile, spec 09):

* a ``hardware`` device is never driven unless ``allow_hardware`` is on;
* a session is opened per (endpoint, device, capability) with only the
  capability being invoked granted (least privilege);
* a capability that declares ``requires_permit`` is only invoked after an
  approval is obtained and an MHS permit is issued for the exact input digest;
* every receipt is appended to a local JSONL evidence ledger, so the host can
  answer "what did the agent actually do" without trusting the agent;
* an ``unknown`` outcome is surfaced as such and never retried automatically.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from .config import EndpointSpec, MHSConfig

ApprovalProvider = Callable[[dict], dict]


class MHSHostError(RuntimeError):
    """Host-level failure carrying a stable MHS-ish code."""

    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": self.message, "mhs_code": self.code, "details": self.details}


def _deny_all(_request: dict) -> dict:
    return {"approved": False, "reason": "no approval channel is configured"}


def _auto_approve_simulated(request: dict) -> dict:
    """Default provider: approve R0/R1 *simulated* actions only."""
    if request.get("mode") == "simulated" and request.get("risk_class") in ("R0", "R1"):
        return {
            "approved": True,
            "principal": "openai4s:sandbox-policy",
            "method": "policy_rule",
            "reason": "R0/R1 simulated device, auto-approved by host policy",
        }
    return {
        "approved": False,
        "reason": (
            f"risk {request.get('risk_class')} on {request.get('mode')} device "
            "requires a human approval channel"
        ),
    }


def _capability_patterns(manifest: dict) -> list[str]:
    safety = manifest.get("safety") or {}
    patterns = list(safety.get("requires_permit") or [])
    for cap in manifest.get("capabilities") or []:
        if cap.get("requires_permit"):
            patterns.append(str(cap.get("capability_id")))
    return patterns


def _pattern_matches(pattern: str, capability_id: str) -> bool:
    if pattern.endswith(".*"):
        return capability_id.startswith(pattern[:-1])
    if pattern.endswith(".v1") or "." in pattern:
        return pattern == capability_id
    return capability_id.startswith(pattern + ".") or pattern == capability_id


class MHSHost:
    """Discovery, sessions, permits and evidence for a set of MHS endpoints."""

    def __init__(
        self,
        config: MHSConfig | None = None,
        approval_provider: ApprovalProvider | None = None,
        sdk_connect: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config or MHSConfig.load()
        self.approval_provider = approval_provider or _auto_approve_simulated
        self._connect_impl = sdk_connect
        self._clients: dict[str, Any] = {}
        self._manifests: dict[str, dict] = {}
        self._sessions: dict[tuple[str, str, str], str] = {}
        self._ledger: list[dict] = []
        self._closed = False

    # ------------------------------------------------------------------ SDK
    def _connect(self, spec: EndpointSpec):
        if self._connect_impl is not None:
            return self._connect_impl(spec.to_mhs_target())
        try:
            from mhs import connect  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on install
            raise MHSHostError(
                "MHS.HOST.SDK_MISSING",
                "the mhs SDK is not importable; run with PYTHONPATH=MHS/sdk/src "
                "or pip install openmhs",
                details={"cause": str(exc)},
            ) from exc
        return connect(spec.to_mhs_target())

    def _client(self, endpoint_id: str | None):
        spec = self.config.endpoint(endpoint_id)
        if spec.id not in self._clients:
            self._clients[spec.id] = self._connect(spec)
        return spec, self._clients[spec.id]

    # ------------------------------------------------------------ discovery
    def endpoints(self) -> list[dict]:
        return [ep.public() for ep in self.config.endpoints]

    def devices(self, endpoint_id: str | None = None) -> list[dict]:
        """List devices across one or all endpoints, with mode and fidelity."""
        out: list[dict] = []
        for spec in self.config.endpoints:
            if endpoint_id is not None and spec.id != endpoint_id:
                continue
            try:
                client = self._client_for_spec(spec)
                hello = client.hello()
                manifests = self._load_manifests(spec, client)
                for device_id, manifest in manifests.items():
                    out.append(_device_summary(spec, hello, manifest))
            except Exception as exc:  # a dead endpoint must not hide the live ones
                out.append(
                    {
                        "endpoint_id": spec.id,
                        "error": str(exc),
                        "mhs_code": getattr(exc, "code", "MHS.HOST.ENDPOINT_UNAVAILABLE"),
                    }
                )
        return out

    def _client_for_spec(self, spec: EndpointSpec):
        if spec.id not in self._clients:
            self._clients[spec.id] = self._connect(spec)
        return self._clients[spec.id]

    def _load_manifests(self, spec: EndpointSpec, client) -> dict[str, dict]:
        if spec.id in self._manifests:
            return self._manifests[spec.id]
        manifests: dict[str, dict] = {}
        listing = client.devices()
        for item in listing:
            device_id = item.get("device_id") if isinstance(item, dict) else None
            if not device_id:
                continue
            if item.get("capabilities") and item.get("safety"):
                manifests[device_id] = item
            else:
                manifests[device_id] = client.inspect(device_id)
        self._manifests[spec.id] = manifests
        return manifests

    def _resolve_device(self, device_id: str, endpoint_id: str | None):
        """Return (spec, client, manifest) for a device id or short name."""
        candidates: list[tuple[EndpointSpec, Any, dict]] = []
        for spec in self.config.endpoints:
            if endpoint_id is not None and spec.id != endpoint_id:
                continue
            try:
                client = self._client_for_spec(spec)
                for did, manifest in self._load_manifests(spec, client).items():
                    if did == device_id or did.rsplit("/", 1)[-1] == device_id:
                        candidates.append((spec, client, manifest))
            except Exception:
                continue
        if not candidates:
            raise MHSHostError(
                "MHS.HOST.DEVICE_NOT_FOUND",
                f"no device {device_id!r} found on "
                + (endpoint_id or "any configured endpoint"),
            )
        if len(candidates) > 1:
            raise MHSHostError(
                "MHS.HOST.DEVICE_AMBIGUOUS",
                f"device {device_id!r} exists on several endpoints; pass endpoint_id",
                details={"matches": [c[0].id for c in candidates]},
            )
        return candidates[0]

    # ------------------------------------------------------------- sessions
    def _hardware_gate(self, manifest: dict) -> None:
        mode = manifest.get("mode")
        if mode == "hardware" and not self.config.allow_hardware:
            raise MHSHostError(
                "MHS.HOST.HARDWARE_GATED",
                "refusing to open a session on a hardware device: "
                "allow_hardware is false in the MHS host configuration",
                details={"device_id": manifest.get("device_id")},
            )

    def _session(self, spec: EndpointSpec, client, manifest: dict, capability_id: str) -> str:
        device_id = str(manifest.get("device_id"))
        key = (spec.id, device_id, capability_id)
        session_id = self._sessions.get(key)
        if session_id:
            return session_id
        self._hardware_gate(manifest)
        mode = manifest.get("mode")
        opened = client.open_session(
            device_ids=[device_id],
            capabilities=[capability_id],
            mode=mode,
            ttl_s=self.config.session_ttl_s,
        )
        session_id = str(opened.get("session_id") or "")
        if not session_id:
            raise MHSHostError(
                "MHS.HOST.SESSION_FAILED",
                "endpoint did not return a session id",
                details={"device_id": device_id, "capability_id": capability_id},
            )
        self._sessions[key] = session_id
        return session_id

    def _needs_permit(self, manifest: dict, capability_id: str) -> bool:
        for pattern in _capability_patterns(manifest):
            if _pattern_matches(str(pattern), capability_id):
                return True
        return False

    def _permit(
        self,
        spec: EndpointSpec,
        client,
        manifest: dict,
        capability_id: str,
        payload: dict,
        session_id: str,
    ) -> str | None:
        try:
            from mhs.canonical import digest as _digest  # type: ignore
        except Exception:  # pragma: no cover - SDK always ships it
            _digest = None
        request = {
            "endpoint_id": spec.id,
            "device_id": manifest.get("device_id"),
            "capability_id": capability_id,
            "mode": manifest.get("mode"),
            "risk_class": (manifest.get("safety") or {}).get("risk_class"),
            "input": payload,
            "summary": _describe_action(manifest, capability_id, payload),
        }
        decision = self.approval_provider(request) or {}
        if not decision.get("approved"):
            raise MHSHostError(
                "MHS.SAFETY.APPROVAL_REQUIRED",
                "action requires approval and none was granted: "
                + str(decision.get("reason") or "denied"),
                details={"capability_id": capability_id, "device_id": manifest.get("device_id")},
            )
        input_digest = decision.get("input_digest")
        if not input_digest and _digest is not None:
            input_digest = _digest(payload or {})
        approvals = [
            {
                "principal": decision.get("principal") or "openai4s:approval",
                "method": decision.get("method") or "policy_rule",
            }
        ]
        issued = client.permit(
            capability_id,
            input_digest,
            ttl_s=int(decision.get("ttl_s", 60)),
            approvals=approvals,
            session_id=session_id,
        )
        permit_id = issued.get("permit_id") if isinstance(issued, dict) else None
        if not permit_id:
            raise MHSHostError(
                "MHS.SAFETY.PERMIT_INVALID",
                "endpoint refused to issue a permit",
                details={"capability_id": capability_id},
            )
        return str(permit_id)

    # --------------------------------------------------------------- reading
    def inspect(self, device_id: str, endpoint_id: str | None = None) -> dict:
        spec, _client, manifest = self._resolve_device(device_id, endpoint_id)
        return {"endpoint_id": spec.id, "device": manifest}

    def read(
        self,
        device_id: str,
        resource_id: str | None = None,
        endpoint_id: str | None = None,
    ) -> dict:
        spec, client, manifest = self._resolve_device(device_id, endpoint_id)
        resource = resource_id or _first_resource(manifest)
        capability_id = _read_capability(manifest, resource)
        session_id = self._session(spec, client, manifest, capability_id)
        state = client.read(resource, device_id=str(manifest.get("device_id")), session_id=session_id)
        return {"endpoint_id": spec.id, "device_id": manifest.get("device_id"), **state}

    # ---------------------------------------------------------- actuation
    def command(
        self,
        device_id: str,
        capability_id: str,
        payload: dict | None = None,
        resource_id: str | None = None,
        endpoint_id: str | None = None,
        expected_revision: int | None = None,
        deadline_ms: int | None = None,
    ) -> dict:
        spec, client, manifest = self._resolve_device(device_id, endpoint_id)
        payload = dict(payload or {})
        session_id = self._session(spec, client, manifest, capability_id)
        permit_id = None
        if self._needs_permit(manifest, capability_id):
            permit_id = self._permit(
                spec, client, manifest, capability_id, payload, session_id
            )
        receipt = client.invoke(
            capability_id,
            payload,
            device_id=str(manifest.get("device_id")),
            resource=resource_id,
            expected_revision=expected_revision,
            deadline_ms=deadline_ms or self.config.command_timeout_ms,
            permit_id=permit_id,
            session_id=session_id,
        )
        self._record(spec, manifest, capability_id, receipt)
        return {"endpoint_id": spec.id, **receipt}

    def operations(self, device_id: str | None = None, endpoint_id: str | None = None) -> dict:
        spec, client = self._client(endpoint_id)
        return client.operations(device_id=device_id)

    def cancel(self, operation_id: str, endpoint_id: str | None = None) -> dict:
        spec, client = self._client(endpoint_id)
        receipt = client.cancel(operation_id)
        return {"endpoint_id": spec.id, **receipt}

    # -------------------------------------------------------------- safety
    def safety_status(self, device_id: str, endpoint_id: str | None = None) -> dict:
        spec, client, manifest = self._resolve_device(device_id, endpoint_id)
        status = client.safety_status(device_id=str(manifest.get("device_id")))
        return {
            "endpoint_id": spec.id,
            "device_id": manifest.get("device_id"),
            "risk_class": (manifest.get("safety") or {}).get("risk_class"),
            "safe_state": (manifest.get("safety") or {}).get("safe_state"),
            **status,
        }

    def estop(self, device_id: str, reason: str = "host requested", endpoint_id: str | None = None) -> dict:
        spec, client, manifest = self._resolve_device(device_id, endpoint_id)
        session_id = self._session(spec, client, manifest, _estop_capability(manifest))
        receipt = client.estop(reason, device_id=str(manifest.get("device_id")))
        self._record(spec, manifest, "cap.device.estop.v1", receipt)
        return {"endpoint_id": spec.id, **receipt}

    def reset(self, device_id: str, endpoint_id: str | None = None) -> dict:
        """Operator-side host code (the demo, scripts): never exposed to the model.

        The native ``mhs_safety`` tool refuses ``reset``; an OpenAI4S host resets
        through :mod:`openai4s_mhs.operator_route`.
        """
        spec, client, manifest = self._resolve_device(device_id, endpoint_id)
        receipt = client.reset(device_id=str(manifest.get("device_id")))
        self._record(spec, manifest, "cap.device.reset.v1", receipt)
        return {"endpoint_id": spec.id, **receipt}

    # ------------------------------------------------------------ evidence
    def evidence_export(self, endpoint_id: str | None = None) -> dict:
        spec, client = self._client(endpoint_id)
        bundle = client.export_evidence()
        return {"endpoint_id": spec.id, **bundle}

    def evidence_verify(self, bundle: dict | None = None, endpoint_id: str | None = None) -> dict:
        if bundle is None:
            bundle = self.evidence_export(endpoint_id)
        try:
            from mhs.evidence import verify_bundle  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise MHSHostError("MHS.HOST.SDK_MISSING", str(exc)) from exc
        result = verify_bundle(bundle)
        return {"endpoint_id": bundle.get("endpoint_id"), **result}

    def ledger(self, limit: int = 100) -> list[dict]:
        return self._ledger[-limit:]

    def _record(self, spec: EndpointSpec, manifest: dict, capability_id: str, receipt: dict) -> None:
        entry = {
            "ts": _now(),
            "endpoint_id": spec.id,
            "device_id": manifest.get("device_id"),
            "capability_id": capability_id,
            "receipt_id": receipt.get("receipt_id"),
            "command_id": receipt.get("command_id"),
            "status": receipt.get("status"),
            "state_hash_after": receipt.get("state_hash_after"),
            "evidence_digest": (receipt.get("evidence") or {}).get("digest"),
            "mode": manifest.get("mode"),
        }
        self._ledger.append(entry)
        if len(self._ledger) > 5000:
            del self._ledger[:1000]
        try:
            path = self.config.evidence_path
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")
        except OSError:
            pass

    # ----------------------------------------------------------------- close
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for client in self._clients.values():
            try:
                for (spec_id, _device, _cap), session_id in list(self._sessions.items()):
                    if spec_id:
                        try:
                            client.close_session(session_id)
                        except Exception:
                            pass
                client.close()
            except Exception:
                pass
        self._clients.clear()
        self._sessions.clear()

    def __enter__(self) -> "MHSHost":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ----------------------------------------------------------------- helpers
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _first_resource(manifest: dict) -> str:
    resources = manifest.get("resources") or []
    if not resources:
        raise MHSHostError("MHS.HOST.NO_RESOURCES", "device declares no resources")
    return str(resources[0].get("resource_id"))


def _capabilities(manifest: dict) -> list[dict]:
    return list(manifest.get("capabilities") or [])


def _read_capability(manifest: dict, resource_id: str) -> str:
    for cap in _capabilities(manifest):
        cid = str(cap.get("capability_id") or "")
        if cap.get("resource") == resource_id and cid.startswith(("cap.world.state", "cap.world.snapshot", "cap.sensing.read", "cap.device.describe")):
            return cid
    for cap in _capabilities(manifest):
        cid = str(cap.get("capability_id") or "")
        if cid.startswith(("cap.world.state", "cap.sensing.read", "cap.device.describe")):
            return cid
    raise MHSHostError(
        "MHS.HOST.NO_READ_CAPABILITY",
        "device exposes no readable state capability",
        details={"device_id": manifest.get("device_id")},
    )


def _estop_capability(manifest: dict) -> str:
    for cap in _capabilities(manifest):
        cid = str(cap.get("capability_id") or "")
        if "estop" in cid or "stop" in cid:
            return cid
    return _read_capability(manifest, _first_resource(manifest))


def _describe_action(manifest: dict, capability_id: str, payload: dict) -> str:
    """One human sentence for the approval card."""
    device = manifest.get("display_name") or manifest.get("device_id")
    for cap in _capabilities(manifest):
        if str(cap.get("capability_id")) == capability_id:
            title = cap.get("title") or capability_id
            return f"{title} on {device}: {json.dumps(payload, sort_keys=True)}"
    return f"{capability_id} on {device}: {json.dumps(payload, sort_keys=True)}"


def _device_summary(spec: EndpointSpec, hello: dict, manifest: dict) -> dict:
    safety = manifest.get("safety") or {}
    fidelity = manifest.get("fidelity") or {}
    return {
        "endpoint_id": spec.id,
        "device_id": manifest.get("device_id"),
        "display_name": manifest.get("display_name"),
        "mode": manifest.get("mode"),
        "risk_class": safety.get("risk_class"),
        "models": manifest.get("models") or [],
        "capabilities": [
            {
                "capability_id": cap.get("capability_id"),
                "title": cap.get("title"),
                "resource": cap.get("resource"),
                "requires_permit": bool(cap.get("requires_permit")),
            }
            for cap in _capabilities(manifest)
        ],
        "fidelity": {
            "level": fidelity.get("fidelity_level"),
            "determinism": (fidelity.get("determinism") or {}).get("kind"),
            "gaps": fidelity.get("gaps") or [],
        }
        if fidelity
        else None,
        "profile_summary": (manifest.get("profile") or {}).get("summary"),
        "mhs_version": hello.get("mhs_version"),
        "endpoint_conformance": hello.get("conformance"),
    }
