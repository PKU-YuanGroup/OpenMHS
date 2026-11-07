"""MCP projection of an MHS endpoint (MHS-000 section 5.4; MHS-008 section 5).

A stdlib-only stdio MCP server that fronts one MHS endpoint so any MCP host
(Claude Code, Cursor, an agent framework, OpenAI4S's ``MCPManager``) can drive
MHS capabilities.  The model sees tools; the projection owns everything the
model must not control:

* ``initialize`` answers with the client's protocol version when supported,
  otherwise the latest supported one (``SUPPORTED_PROTOCOL_VERSIONS``), and
  reports ``serverInfo.name = "mhs-mcp:<endpoint_id>"``;
* one tool per bound capability named ``mhs__<device_slug>__<capability_slug>``
  (MHS-008 TPT-030 slug rules, <= 63 chars, collisions fail closed; names are
  stable across releases).  The description (<= 2048 bytes) states mode, risk,
  the limits the endpoint enforces, the interlocks the call needs and the
  device facts, all from the device's reference file (``mhs.devices.get``).
  ``annotations`` carry ``readOnlyHint`` (read verbs), ``destructiveHint``
  (non-read calls on R2+ or physical devices), ``idempotentHint`` and
  ``openWorldHint``; ``x-mhs`` and ``_meta["openmhs/capability"]`` carry the
  machine-readable identity;
* ``tools/call`` maps to exactly one ``mhs.command``.  The receipt is returned
  as ``content`` text plus ``structuredContent.receipt`` with ``isError:
  false`` even for rejected/failed/unknown receipts (TPT-038).  ``isError:
  true`` means no receipt exists: a policy refusal, an input that does not
  match the capability schema (text ``MHS.CAPABILITY.INPUT_INVALID: <field
  reasons>``; bounds the endpoint enforces as limits are left to the endpoint,
  which refuses them with a receipt), a lapsed session, or a transport failure;
* sessions are the projection's own: opened per (device, capability) for
  commands and per device for reads, with principal
  ``{"kind": "agent", "id": "agent:mcp/<clientInfo.name>"}``,
  renewed by a heartbeat when less than a third of the TTL is left, and
  reopened after ``MHS.SESSION.EXPIRED``/``UNKNOWN``/``CLOSED`` (that call returns
  ``isError`` asking the model to re-read state; it is never retried
  automatically).  A ``session_id`` argument the projection did not open is
  refused with ``MHS.SESSION.UNKNOWN`` unless the policy sets
  ``allow_external_sessions``;
* ``_meta.retryToken`` and a ``command_id`` that is not a ULID become a
  deterministic ULID (:func:`retry_command_id`), so the same token replays
  the same receipt instead of acting twice;
* discovery tools ``mhs__devices`` (compact summary), ``mhs__inspect``,
  ``mhs__read``, ``mhs__safety``, ``mhs__operations`` (list, get with
  ``wait_ms``, cancel), ``mhs__evidence`` (count, head digest, validity and the
  last receipts; the full bundle is the resource ``mhs://<endpoint>/evidence``)
  and ``mhs__estop``.  ``mhs__reset`` and ``mhs__permit`` are operator tools:
  hidden unless the policy sets ``operator_tools`` (a reset and a permit
  approval are human decisions);
* ``resources/list``/``resources/read`` expose ``mhs://<endpoint>/devices``,
  per-device manifests and reference files, per-resource state and the
  evidence bundle;
* the stdio loop serves ``mhs__estop``, ``ping`` and ``notifications/cancelled``
  on a priority path while a ``tools/call`` is in flight; cancellation of an
  in-flight call is forwarded to ``mhs.operations.cancel``, and a call
  cancelled while still queued is never sent to the endpoint (no response);
* newline-delimited JSON-RPC on stdin/stdout (one object per line, <= 4 MiB),
  diagnostics on stderr only.

Host policy (HOST-001/HOST-068)
-------------------------------
``--config`` points at the host's policy document, a JSON object (the
OpenAI4S reference host in ``integration/openai4s`` passes its settings file).
Every flag defaults to the safe value:

===========================  ====================================================
``enabled``                  false: every ``tools/call`` is refused with
                             ``MHS.AUTH.FORBIDDEN``, ``tools/list`` is empty and
                             ``resources/read`` is refused; no endpoint call is
                             made.  The default whenever ``--config`` is given.
``allow_hardware``           false: capability tools, ``mhs__read`` and
                             ``mhs__operations`` of ``mode: "hardware"`` devices
                             refuse with ``MHS.AUTH.HARDWARE_DISABLED``;
                             discovery, safety status, ``mhs__estop`` and
                             ``mhs__evidence`` stay available.
``operator_tools``           false: ``mhs__reset`` and ``mhs__permit`` are not
                             listed and refuse with ``MHS.AUTH.FORBIDDEN``.  Set
                             it only for a connector a human operator drives.
``allow_external_sessions``  false: a ``session_id`` the projection did not open
                             is refused with ``MHS.SESSION.UNKNOWN``.
===========================  ====================================================

Without ``--config`` the projection is enabled with every other flag false.
``--operator-tools`` and ``--allow-external-sessions`` set the flag on the
command line (they can only enable).

Launch with a running HTTP endpoint, a child command, or a built-in reference
endpoint::

    python3 -m mhs.mcp --endpoint http://127.0.0.1:7400 --config ~/.openai4s/mhs.json
    python3 -m mhs.mcp --command "python3 -m mhs.reference conveyor --stdio"
    python3 -m mhs.mcp --reference conveyor --test-profile
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import queue
import re
import shlex
import sys
import threading
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Mapping

from . import _ids

__all__ = [
    "LATEST_PROTOCOL_VERSION",
    "MAX_FRAME_BYTES",
    "MCPPolicy",
    "MCPProjection",
    "OPERATOR_TOOLS",
    "PROTOCOL_VERSION",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "TOOL_DESCRIPTION_LIMIT",
    "agent_principal",
    "main",
    "projection_tool_name",
    "retry_command_id",
    "serve_stdio",
]

#: The oldest supported MCP revision (the version the projection was first written for).
PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
#: Answered when the client asks for a version the projection does not support.
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]
MAX_FRAME_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_RESPONSE_BYTES = 24 * 1024 * 1024


class _ArtifactResourceResult(dict):
    """Internal response-only budget; never serialized as an MCP field."""
    def __init__(self, contents: list[dict[str, Any]], frame_limit: int):
        super().__init__(contents=contents)
        self.frame_limit = frame_limit

SERVER_VERSION = _ids.SDK_VERSION
RESOURCE_PAGE_SIZE = 100
#: TTL of the projection's own sessions; renewed when less than a third is left.
SESSION_TTL_S = 3600
#: Hard bound on a tool description, in UTF-8 bytes.
TOOL_DESCRIPTION_LIMIT = 2048
EVIDENCE_LAST_N = 10
EVIDENCE_MAX_N = 50
OPERATIONS_WAIT_MAX_MS = 60_000
#: ``_meta`` key of the machine-readable capability identity.
META_KEY = f"{_ids.DIST_NAME}/capability"
#: Tools a model never sees unless the host policy sets ``operator_tools``.
OPERATOR_TOOLS = frozenset({"mhs__reset", "mhs__permit"})
_CAP_PREFIXES = ("x-cap.", "cap.")
_TOOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
_INTERNAL_CAPABILITY_RE = re.compile(r"^cap\.internal\.")
_DISCOVERY_TOOLS = (
    "mhs__devices", "mhs__inspect", "mhs__read", "mhs__safety",
    "mhs__operations", "mhs__evidence", "mhs__estop", "mhs__reset", "mhs__permit",
)
#: Tools that remain usable on a hardware device while ``allow_hardware`` is
#: false: observation and the software safety envelope are not actuation.
_SAFETY_ALLOWED_TOOLS = frozenset(
    {"mhs__devices", "mhs__inspect", "mhs__safety", "mhs__estop", "mhs__reset", "mhs__evidence"}
)
#: Control arguments of a capability tool (never capability input).
_CONTROL_PROPERTIES = ("session_id", "command_id", "expected_revision", "permit_id", "deadline_ms")
_RESERVED_ARGUMENTS = frozenset(_CONTROL_PROPERTIES) | {"retryToken", "retry_token"}
_SESSION_LAPSED = frozenset({"MHS.SESSION.EXPIRED", "MHS.SESSION.UNKNOWN", "MHS.SESSION.CLOSED"})
#: a tools/call whose request was cancelled before anything was sent to the endpoint (no response is written)
_CANCELLED = object()
_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_NOT_CERTIFIED = "Not a safety-rated channel (MHS.SAFETY.NOT_CERTIFIED); a hardware e-stop remains mandatory."


# ---------------------------------------------------------------------------
# deployment policy (HOST-001)
# ---------------------------------------------------------------------------


class MCPPolicy:
    """The host policy ``mhs.mcp`` enforces before it touches an endpoint.

    The document is the integration settings JSON: ``enabled``,
    ``allow_hardware``, ``operator_tools`` and ``allow_external_sessions`` are
    read with secure defaults (false).  A projection constructed without an
    explicit policy remains enabled for direct SDK launches; every other flag
    stays false.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        allow_hardware: bool,
        path: str | None = None,
        configured: bool = True,
        operator_tools: bool = False,
        allow_external_sessions: bool = False,
    ) -> None:
        self.enabled = bool(enabled)
        self.allow_hardware = bool(allow_hardware)
        self.path = path
        self.configured = bool(configured)
        self.operator_tools = bool(operator_tools)
        self.allow_external_sessions = bool(allow_external_sessions)

    @classmethod
    def direct_launch(cls, *, operator_tools: bool = False, allow_external_sessions: bool = False) -> "MCPPolicy":
        """Policy for an explicit human/SDK launch without ``--config``."""
        return cls(enabled=True, allow_hardware=False, path=None, configured=False,
                   operator_tools=operator_tools, allow_external_sessions=allow_external_sessions)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None) -> "MCPPolicy":
        """Load the integration settings document.

        A missing/unreadable document is *not* an error: it means the feature
        has never been configured, so every default is fail-closed.  Malformed
        JSON is an error (the caller exits before serving).
        """
        if path is None:
            return cls.direct_launch()
        target = Path(path).expanduser()
        raw: dict[str, Any] = {}
        if target.exists():
            with open(target, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                raise ValueError(f"MHS policy document {str(target)!r} must be a JSON object")
            raw = loaded
        enabled = raw.get("enabled", False) is True  # only a JSON true enables ("false" is a string, not false)
        # MHS_ENABLED is the documented one-process override; it is explicit.
        override = _env_enabled()
        if override is not None:
            enabled = override
        return cls(
            enabled=enabled,
            allow_hardware=raw.get("allow_hardware", False) is True,
            path=str(target),
            configured=True,
            operator_tools=raw.get("operator_tools", False) is True,
            allow_external_sessions=raw.get("allow_external_sessions", False) is True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "path": self.path,
            "enabled": self.enabled,
            "allow_hardware": self.allow_hardware,
            "operator_tools": self.operator_tools,
            "allow_external_sessions": self.allow_external_sessions,
        }


def _env_enabled() -> bool | None:
    raw = os.environ.get("MHS_ENABLED")
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if value in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return None


class _PolicyDenied(Exception):
    """A coded host-policy refusal (never a transport error)."""

    def __init__(self, code: str, message: str, data: Mapping[str, Any] | None = None):
        self.code = code
        self.message = message
        self.data = dict(data or {})
        super().__init__(message)


class _SessionLapsed(Exception):
    """A projection-owned session the endpoint no longer knows (expired, unknown, closed)."""

    def __init__(self, code: str, session_id: str, device_id: str, capability_id: str | None):
        self.code = code
        self.session_id = session_id
        self.device_id = device_id
        self.capability_id = capability_id
        super().__init__(code)


# ---------------------------------------------------------------------------
# naming (MHS-008 TPT-030), identity and retry tokens
# ---------------------------------------------------------------------------


def _slug(text: str, limit: int) -> tuple[str, bool]:
    body = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    truncated = len(body) > limit
    return (body[:limit].strip("_") or "x", truncated)


def _digest6(text: str) -> str:
    from mhs import canonical

    return canonical.digest(str(text))[len("sha256:") :][:6]


def _device_slug(device_id: str) -> str:
    """Last two non-empty URI path segments, lowercased with ``_`` separators."""

    path = str(device_id).split("://", 1)[-1]
    parts = [part for part in path.split("?")[0].split("/") if part]
    path_parts = parts[1:] if len(parts) > 1 else parts
    if len(path_parts) >= 2:
        body = "_".join(path_parts[-2:])
    else:
        body = (path_parts[-1] if path_parts else "device") + "_" + _digest6(device_id)[:4]
    slug, truncated = _slug(body, 24)
    if truncated:
        slug = f"{slug}_{_digest6(device_id)}"
    return slug


def _capability_slug(capability_id: str) -> str:
    text = str(capability_id)
    for prefix in _CAP_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = re.sub(r"\.v[0-9]+$", "", text)
    body = text.replace(".", "_")
    slug, truncated = _slug(body, 20)
    if truncated:
        slug = f"{slug}_{_digest6(capability_id)}"
    return slug


def projection_tool_name(device_id: str, capability_id: str) -> str:
    """Return the stable MCP tool name for one bound capability."""

    device = _device_slug(device_id)
    capability = _capability_slug(capability_id)
    name = f"mhs__{device}__{capability}"
    if len(name) > 63:
        device = device[:12].strip("_")
        capability = capability[:12].strip("_")
        name = f"mhs__{device}__{capability}_{_digest6(device_id + '|' + capability_id)}"
        if len(name) > 63:
            name = name[:63].rstrip("_")
    return name


def retry_command_id(token: str, tool_name: str) -> str:
    """The deterministic ULID an MCP retry token (or non-ULID ``command_id``) maps to.

    The 128 bits are the first 16 bytes of ``sha256(tool_name + "\\n" + token)``,
    so the same token on the same tool always names the same MHS command and
    the endpoint replays its retained receipt instead of acting twice.
    """
    value = int.from_bytes(hashlib.sha256(f"{tool_name}\n{token}".encode("utf-8")).digest()[:16], "big")
    chars = []
    for _ in range(26):
        chars.append(_ULID_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def agent_principal(client_info: Mapping[str, Any] | None) -> dict[str, Any]:
    """The principal the projection opens sessions as: ``agent:mcp/<clientInfo.name>``."""
    name = str((client_info or {}).get("name") or "unknown")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")[:64] or "unknown"
    return {"id": f"agent:mcp/{name}", "kind": "agent"}


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------


def _result(mid: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": int(code), "message": str(message)}
    if data is not None:
        payload["data"] = data
    return {"jsonrpc": "2.0", "id": mid, "error": payload}


def _error_payload(exc: BaseException) -> dict[str, Any]:
    code = getattr(exc, "code", None) or "MHS.INTERNAL.ERROR"
    message = getattr(exc, "message", None) or str(exc) or code
    data = getattr(exc, "data", None)
    payload: dict[str, Any] = {"mhs_code": code, "message": message}
    if isinstance(data, Mapping):
        payload.update({str(key): value for key, value in data.items() if key != "message"})
    return payload


def _tool_error(code: str, message: str, **details: Any) -> dict[str, Any]:
    """An ``isError: true`` tool result: no MHS receipt exists (TPT-039)."""
    payload: dict[str, Any] = {"mhs_code": code, "message": message}
    payload.update({str(key): value for key, value in details.items() if value is not None})
    return {
        "content": [{"type": "text", "text": f"{code}: {message}"}],
        "structuredContent": {"receipt": None, "mhs_error": payload},
        "isError": True,
    }


class _ProjectionError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = int(code)
        self.message = str(message)
        self.data = data
        super().__init__(self.message)


class _OwnedSession:
    """One session the projection opened (and therefore may renew and accept)."""

    __slots__ = ("session_id", "device_id", "capability_id", "ttl_s", "renew_at")

    def __init__(self, session_id: str, device_id: str, capability_id: str | None, ttl_s: int):
        self.session_id = session_id
        self.device_id = device_id
        self.capability_id = capability_id
        self.ttl_s = int(ttl_s)
        self.renew_at = time.monotonic() + self.ttl_s * 2.0 / 3.0


# ---------------------------------------------------------------------------
# projection
# ---------------------------------------------------------------------------


class MCPProjection:
    """Translate MCP requests into MHS client calls (transport-agnostic).

    ``describe_inputs=True`` (what ``python3 -m mhs.mcp`` serves) gives every
    input property a description with its type, unit and enforced limit when
    the driver wrote none, and appends the unit and limit to the ones it did
    write.  The default ``False`` keeps the input schema as authored, which is
    what the driver gate (G8) lints.
    """

    def __init__(self, client: Any, *, endpoint: str | None = None, policy: MCPPolicy | None = None,
                 describe_inputs: bool = False):
        self.client = client
        self.endpoint = endpoint
        self.policy = policy or MCPPolicy.direct_launch()
        self.describe_inputs = bool(describe_inputs)
        self.endpoint_id: str | None = None
        self.server_name = "mhs-mcp"
        self.protocol_version = PROTOCOL_VERSION
        self.initialized = False
        self.client_info: dict[str, Any] = {}
        self.principal: dict[str, Any] = agent_principal(None)
        self.devices: list[dict[str, Any]] = []
        self._details: dict[str, dict[str, Any]] = {}
        self._sessions: dict[tuple[str, str], _OwnedSession] = {}
        self._tools: dict[str, dict[str, Any]] = {}
        self._resources: list[dict[str, Any]] = []
        self._resource_routes: dict[str, tuple[str, str, str]] = {}
        self._artifact_routes: dict[str, dict[str, Any]] = {}
        self._resource_devices: dict[str, list[str]] = {}
        self._loaded = False
        self._lock = threading.RLock()
        self._load_lock = threading.Lock()
        self._inflight: dict[Any, dict[str, Any]] = {}
        # request ids cancelled before their tools/call was dispatched (bounded; MCP ids are unique per session)
        self._cancelled: dict[Any, bool] = {}
        self.pending_notifications: list[dict[str, Any]] = []

    # -- discovery ---------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:
                return
            if not self.policy.enabled:
                # No endpoint discovery is performed while the integration is off.
                self.devices = []
                self._tools = {}
                self._resources = []
                self._resource_routes = {}
                self._resource_devices = {}
                self._loaded = True
                return
            devices = self.client.devices()
            if not devices:
                raise RuntimeError("MHS endpoint exposes no devices")
            self.devices = [dict(item) for item in devices if isinstance(item, Mapping)]
            details: dict[str, dict[str, Any]] = {}
            inspect = getattr(self.client, "inspect", None)
            for device in self.devices:
                device_id = str(device.get("device_id") or "")
                detail: Any = None
                if callable(inspect):
                    try:
                        # devices.get adds the reference file and x-mhs-effective-limits.
                        detail = inspect(device_id)
                    except Exception:  # noqa: BLE001 - descriptions degrade to the manifest
                        detail = None
                details[device_id] = dict(detail) if isinstance(detail, Mapping) else {}
            self._details = details
            self._build_tools()
            self._build_resources()
            self._loaded = True

    def _build_tools(self) -> None:
        tools: dict[str, dict[str, Any]] = {}
        origin: dict[str, tuple[str, str]] = {}
        collisions: list[str] = []
        for device in self.devices:
            device_id = str(device.get("device_id") or "")
            detail = self._details.get(device_id) or {}
            reference = detail.get("reference") if isinstance(detail.get("reference"), Mapping) else {}
            for capability in device.get("capabilities") or []:
                if not isinstance(capability, Mapping):
                    continue
                capability_id = str(capability.get("capability_id") or "")
                if not capability_id or _INTERNAL_CAPABILITY_RE.match(capability_id):
                    continue
                name = projection_tool_name(device_id, capability_id)
                if not _TOOL_NAME_RE.fullmatch(name):
                    raise RuntimeError(f"MCP tool name {name!r} is not a legal MCP tool name")
                if name in tools:
                    previous = origin[name]
                    if previous != (device_id, capability_id):
                        collisions.append(f"{name}: {previous} vs {(device_id, capability_id)}")
                    continue
                detail_capability = _capability_detail(detail, capability)
                limits = _effective_limits(capability, detail_capability)
                ref_kind, ref_entry = _reference_entry(reference, capability_id, capability.get("resource"))
                entry = {
                    "name": name,
                    "device_id": device_id,
                    "capability_id": capability_id,
                    "capability": dict(capability),
                    "device": device,
                    "reference": reference,
                    "limits": limits,
                    "verb": _capability_verb(capability, ref_kind, ref_entry),
                    "ref_entry": ref_entry,
                    "validation_schema": _validation_schema(capability, limits),
                }
                entry["tool"] = self._capability_tool(name, entry)
                tools[name] = entry
                origin[name] = (device_id, capability_id)
        if collisions:
            raise RuntimeError("MCP tool-name collision (fail-closed, TPT-032): " + "; ".join(collisions[:4]))
        self._tools = tools

    def _endpoint_authority(self) -> str:
        source = self.endpoint_id or (str(self.devices[0].get("device_id", "")) if self.devices else "")
        return source.split("://", 1)[-1] if "://" in source else source

    def _build_resources(self) -> None:
        authority = self._endpoint_authority()
        resources: list[dict[str, Any]] = []
        routes: dict[str, tuple[str, str, str]] = {}
        resource_devices: dict[str, list[str]] = {}
        devices_uri = f"mhs://{authority}/devices"
        routes[devices_uri] = ("devices", "", "")
        resources.append(
            {
                "uri": devices_uri,
                "name": "MHS devices",
                "description": "Device summaries discovered over mhs.devices.list.",
                "mimeType": "application/json",
            }
        )
        evidence_uri = f"mhs://{authority}/evidence"
        routes[evidence_uri] = ("evidence", "", "")
        resources.append(
            {
                "uri": evidence_uri,
                "name": "MHS evidence bundle",
                "description": "The endpoint's full hash-chained evidence bundle (mhs.evidence.export); "
                               "mhs__evidence returns a bounded summary.",
                "mimeType": "application/json",
            }
        )
        for device in self.devices:
            device_id = str(device.get("device_id") or "")
            path = device_id.split("://", 1)[-1].split("/", 1)[-1] if "://" in device_id else device_id
            path = path or _device_slug(device_id)
            manifest_uri = f"mhs://{authority}/devices/{path}"
            routes[manifest_uri] = ("manifest", device_id, "")
            resources.append(
                {
                    "uri": manifest_uri,
                    "name": f"{device.get('display_name') or device_id} manifest",
                    "description": f"Full MHS device manifest (mode={device.get('mode')}).",
                    "mimeType": "application/json",
                }
            )
            if (self._details.get(device_id) or {}).get("reference"):
                reference_uri = f"{manifest_uri}/reference"
                routes[reference_uri] = ("reference", device_id, "")
                resources.append(
                    {
                        "uri": reference_uri,
                        "name": f"{device.get('display_name') or device_id} reference file",
                        "description": "What the device measures and adjusts, its actions, the limits the "
                                       "endpoint enforces, its safety declaration and facts.",
                        "mimeType": "application/json",
                    }
                )
            for resource in device.get("resources") or []:
                if not isinstance(resource, Mapping):
                    continue
                resource_id = str(resource.get("resource_id") or "")
                if not resource_id:
                    continue
                uri = f"{manifest_uri}/resources/{resource_id}"
                routes[uri] = ("resource", device_id, resource_id)
                resource_devices.setdefault(resource_id, []).append(device_id)
                resources.append(
                    {
                        "uri": uri,
                        "name": f"{device.get('display_name') or device_id} / {resource_id}",
                        "description": (
                            f"MHS resource {resource_id!r} (kind={resource.get('kind')}); "
                            "read-only current state via mhs.resource.read."
                        ),
                        "mimeType": "application/json",
                    }
                )
        resources.sort(key=lambda item: item["uri"])
        self._resources = resources
        self._resource_routes = routes
        self._resource_devices = resource_devices

    # -- sessions ----------------------------------------------------------
    def _device_mode(self, device_id: str | None) -> str | None:
        if not device_id:
            return None
        for device in self.devices:
            if str(device.get("device_id")) == str(device_id):
                return str(device.get("mode"))
        return None

    def _is_hardware(self, device_id: str | None) -> bool:
        return self._device_mode(device_id) == "hardware"

    def _assert_device_allowed(self, device_id: str, *, safety: bool = False) -> None:
        """Refuse a session on a hardware device unless policy authorizes it.

        ``safety=True`` is used by ``mhs__reset``: the software safety
        envelope stays reachable for an authorized connector even when
        actuation is disabled (HOST-001 matrix / HOST-046).
        """
        if self.policy.allow_hardware or safety:
            return
        if self._is_hardware(device_id):
            raise _PolicyDenied(
                "MHS.AUTH.HARDWARE_DISABLED",
                "refusing a hardware-device session: allow_hardware is false in "
                "the MHS host policy (the connector is enabled; authorization is not)",
                {"device_id": device_id, "policy": "allow_hardware=false"},
            )

    def _owned(self, session_id: Any) -> _OwnedSession | None:
        if not isinstance(session_id, str):
            return None
        with self._lock:
            for entry in self._sessions.values():
                if entry.session_id == session_id:
                    return entry
        return None

    def _owned_for_device(self, device_id: str | None) -> list[_OwnedSession]:
        with self._lock:
            return [entry for entry in self._sessions.values()
                    if device_id is None or entry.device_id == device_id]

    def _drop(self, session_id: str) -> None:
        with self._lock:
            for key, entry in list(self._sessions.items()):
                if entry.session_id == session_id:
                    del self._sessions[key]
            for uri, route in list(self._artifact_routes.items()):
                if route["session_id"] == session_id:
                    del self._artifact_routes[uri]

    def _touch(self, entry: _OwnedSession) -> None:
        """Heartbeat ``entry`` when less than a third of its TTL is left (raises :class:`_SessionLapsed`)."""
        if time.monotonic() < entry.renew_at:
            return
        heartbeat = getattr(self.client, "heartbeat", None)
        if callable(heartbeat):
            try:
                heartbeat(entry.session_id)
            except Exception as exc:  # noqa: BLE001 - classified below
                code = str(getattr(exc, "code", "") or "")
                if code in _SESSION_LAPSED:
                    self._drop(entry.session_id)
                    raise _SessionLapsed(code, entry.session_id, entry.device_id, entry.capability_id) from exc
                return  # a transient heartbeat failure: the call itself will tell
        entry.renew_at = time.monotonic() + entry.ttl_s * 2.0 / 3.0

    def _session_for_device(
        self, device_id: str, capability_id: str | None = None, *, safety: bool = False
    ) -> str:
        key = (device_id, capability_id or "")
        with self._lock:
            cached = self._sessions.get(key)
        if cached is not None:
            self._touch(cached)
            return cached.session_id
        self._assert_device_allowed(device_id, safety=safety)
        capabilities = [capability_id] if capability_id else None
        session = self.client.open_session(device_ids=[device_id], capabilities=capabilities, mode=None,
                                           ttl_s=SESSION_TTL_S, principal=dict(self.principal))
        session_id = session.get("session_id") if isinstance(session, Mapping) else None
        if not session_id:
            raise RuntimeError("MHS session.open returned no session_id")
        limits = session.get("limits") if isinstance(session, Mapping) else None
        ttl = limits.get("ttl_s") if isinstance(limits, Mapping) else None
        ttl_s = int(ttl) if isinstance(ttl, int) and not isinstance(ttl, bool) and ttl > 0 else SESSION_TTL_S
        with self._lock:
            self._sessions[key] = _OwnedSession(str(session_id), device_id, capability_id, ttl_s)
        return str(session_id)

    def _reopen(self, lapse: _SessionLapsed) -> bool:
        """Open a fresh session after a lapse (best effort; the next call retries anyway)."""
        self._drop(lapse.session_id)
        try:
            self._session_for_device(lapse.device_id, lapse.capability_id, safety=True)
            return True
        except Exception:  # noqa: BLE001 - reported by the next call
            return False

    def _session_renewed(self, lapse: _SessionLapsed, *, tool: str) -> dict[str, Any]:
        renewed = self._reopen(lapse)
        return _tool_error(
            lapse.code,
            "the connector's MHS session for this device lapsed"
            + (" and a new one is open" if renewed else "")
            + "; this call was NOT executed.  When a session expires the endpoint may move the device to its "
            "safe state: re-read its state (mhs__read, mhs__safety) before deciding to call again.",
            session_renewed=renewed,
            retryable=True,
            device_id=lapse.device_id,
            capability_id=lapse.capability_id,
            tool=tool,
        )

    def _with_read_session(self, device_id: str, call: Callable[[str], Any]) -> Any:
        """Run a read with the device session; a lapsed session is reopened and the read retried once."""
        for attempt in range(2):
            try:
                session_id = self._session_for_device(device_id)
            except _SessionLapsed:
                continue
            try:
                return call(session_id)
            except Exception as exc:  # noqa: BLE001 - classified below
                if attempt == 0 and str(getattr(exc, "code", "") or "") in _SESSION_LAPSED:
                    self._drop(session_id)
                    continue
                raise
        return call(self._session_for_device(device_id))

    # -- tool catalog ------------------------------------------------------
    def _tool_descriptions(self) -> list[dict[str, Any]]:
        tools = [tool for tool in self._discovery_tools()
                 if self.policy.operator_tools or tool["name"] not in OPERATOR_TOOLS]
        for name in sorted(self._tools):
            tools.append(copy.deepcopy(self._tools[name]["tool"]))
        return tools

    def _discovery_tools(self) -> list[dict[str, Any]]:
        device_id = {"type": "string", "description": "MHS device id as listed by mhs__devices."}
        return [
            {
                "name": "mhs__devices",
                "title": "List MHS devices",
                "description": "List the devices of this MHS endpoint: id, name, mode, risk class, resources and the "
                               "names of each device's capability tools (read-only).  mhs__inspect gives one "
                               "device's full manifest and reference file.",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": _discovery_annotations("List MHS devices", read_only=True),
            },
            {
                "name": "mhs__inspect",
                "title": "Inspect one MHS device",
                "description": "Read one device's full manifest and its reference file: what it measures and "
                               "adjusts, its actions, the limits the endpoint enforces, interlocks, e-stop, safe "
                               "state, facts and fidelity (read-only).",
                "inputSchema": {"type": "object", "properties": {"device_id": dict(device_id)},
                                "required": ["device_id"]},
                "annotations": _discovery_annotations("Inspect one MHS device", read_only=True),
            },
            {
                "name": "mhs__read",
                "title": "Read MHS resource state",
                "description": "Read the current state document of one MHS resource without changing it "
                               "(read-only).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string",
                                      "description": "MHS device id; optional when the resource id is unique."},
                        "resource_id": {"type": "string",
                                        "description": "Resource id from the device manifest (for example "
                                                       "'workcell')."},
                        "fields": {"type": "array", "items": {"type": "string"},
                                   "description": "Optional top-level state fields to return; omit for the "
                                                  "whole state."},
                    },
                    "required": ["resource_id"],
                },
                "annotations": _discovery_annotations("Read MHS resource state", read_only=True),
            },
            {
                "name": "mhs__safety",
                "title": "Read MHS safety status",
                "description": "Read one device's safety status: risk class, e-stop latch, interlocks, permits and "
                               "the declared safe state (read-only).",
                "inputSchema": {"type": "object", "properties": {"device_id": dict(device_id)},
                                "required": ["device_id"]},
                "annotations": _discovery_annotations("Read MHS safety status", read_only=True),
            },
            {
                "name": "mhs__operations",
                "title": "MHS operations",
                "description": "List the operations this connector started; read one (operation_id, optionally "
                               "waiting up to wait_ms for its final receipt); or cancel one (cancel_operation_id). "
                               "Use it for a receipt with status 'running' or 'unknown'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Only operations of this MHS device."},
                        "operation_id": {"type": "string",
                                         "description": "Return the current receipt of this operation."},
                        "wait_ms": {"type": "integer", "minimum": 0, "maximum": OPERATIONS_WAIT_MAX_MS,
                                    "x-mhs-unit": "ms",
                                    "description": "With operation_id: wait up to this long for a final receipt "
                                                   f"(completed, failed, rejected, cancelled). Unit: ms; at most "
                                                   f"{OPERATIONS_WAIT_MAX_MS}."},
                        "cancel_operation_id": {"type": "string",
                                                "description": "Cancel this operation (mhs.operations.cancel)."},
                    },
                },
                "annotations": _discovery_annotations("MHS operations", read_only=False, destructive=False,
                                                      idempotent=False),
            },
            {
                "name": "mhs__evidence",
                "title": "MHS evidence summary",
                "description": "Summarise the endpoint's hash-chained evidence log: receipt count, head digest, "
                               "whether the chain verifies, and the last receipts (last_n) or the receipts of one "
                               "command_id.  The full bundle is the resource mhs://<endpoint>/evidence "
                               "(read-only).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "last_n": {"type": "integer", "minimum": 0, "maximum": EVIDENCE_MAX_N, "x-mhs-unit": "1",
                                   "description": f"Number of most recent receipts to include (default "
                                                  f"{EVIDENCE_LAST_N}, at most {EVIDENCE_MAX_N}). Unit: 1 (a "
                                                  "count of receipts)."},
                        "command_id": {"type": "string",
                                       "description": "Return only the receipts of this command id."},
                        # include_bundle (a host-only argument for routes without resources/read) is accepted but
                        # not listed, so the model sees a bounded summary tool
                    },
                },
                "annotations": _discovery_annotations("MHS evidence summary", read_only=True),
            },
            {
                "name": "mhs__estop",
                "title": "Emergency stop",
                "description": "Engage the endpoint's emergency stop for one device: it latches before anything "
                               "else, cancels running operations and stops the device; no session or approval is "
                               "needed.  Returns a receipt.  Only a human operator can reset the latch.  This is "
                               "the MHS software safety envelope, not a replacement for a hardware e-stop.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device_id": dict(device_id),
                        "reason": {"type": "string", "description": "Why the stop is needed (recorded in the "
                                                                    "receipt)."},
                    },
                    "required": ["device_id"],
                },
                "annotations": _discovery_annotations("Emergency stop", read_only=False, destructive=False,
                                                      idempotent=True),
            },
            {
                "name": "mhs__reset",
                "title": "Reset the e-stop latch (operator)",
                "description": "Operator tool: reset the safety latch after an e-stop, once every interlock reads "
                               "closed.  A reset is a human decision; it never restarts equipment.",
                "inputSchema": {"type": "object", "properties": {"device_id": dict(device_id)},
                                "required": ["device_id"]},
                "annotations": _discovery_annotations("Reset the e-stop latch", read_only=False, destructive=True,
                                                      idempotent=False),
            },
            {
                "name": "mhs__permit",
                "title": "Issue an MHS permit (operator)",
                "description": "Operator tool: request a single-use permit for a capability that requires "
                               "approval.  The permit is bound to the capability and the exact input; pass it as "
                               "permit_id on the capability tool.  The host must collect the human approval first.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device_id": dict(device_id),
                        "capability_id": {"type": "string", "description": "Capability id the permit is for."},
                        "input": {"type": "object", "description": "The exact capability input the permit "
                                                                   "authorizes."},
                        "resource": {"type": "string", "description": "Resource the capability is bound to "
                                                                      "(defaults to its binding)."},
                        "input_digest": {"type": "string", "description": "sha256: action digest, when input is "
                                                                          "not given."},
                        "ttl_s": {"type": "integer", "minimum": 1, "x-mhs-unit": "s",
                                  "description": "Permit lifetime. Unit: s."},
                        "approvals": {"type": "array", "items": {"type": "object"},
                                      "description": "Approval records collected by the host's operator UI."},
                    },
                    "required": ["capability_id"],
                },
                "annotations": _discovery_annotations("Issue an MHS permit", read_only=False, destructive=False,
                                                      idempotent=False),
            },
        ]

    def _capability_tool(self, name: str, entry: Mapping[str, Any]) -> dict[str, Any]:
        capability = entry["capability"]
        device = entry["device"]
        safety = device.get("safety") if isinstance(device.get("safety"), Mapping) else {}
        fidelity = device.get("fidelity") if isinstance(device.get("fidelity"), Mapping) else {}
        determinism = fidelity.get("determinism") if isinstance(fidelity.get("determinism"), Mapping) else {}
        hardware_disabled = self._is_hardware(device.get("device_id")) and not self.policy.allow_hardware
        title = str(capability.get("title") or entry["ref_entry"].get("name") or capability.get("capability_id"))
        tool: dict[str, Any] = {
            "name": name,
            "title": title[:120],
            "description": _capability_description(entry, hardware_disabled=hardware_disabled,
                                                   operator_tools=self.policy.operator_tools),
            "inputSchema": _tool_input_schema(
                capability, describe=self.describe_inputs, limits=entry["limits"],
                external_sessions=self.policy.allow_external_sessions,
                operator_tools=self.policy.operator_tools,
            ),
            "annotations": _capability_annotations(title, entry["verb"], safety.get("risk_class"),
                                                   device.get("mode")),
        }
        x_mhs: dict[str, Any] = {
            "capability_id": capability.get("capability_id"),
            "device_id": device.get("device_id"),
            "resource": capability.get("resource"),
            "verb": entry["verb"],
            "risk_class": safety.get("risk_class"),
            "mode": device.get("mode"),
            "determinism": determinism.get("kind"),
            "requires_permit": bool(capability.get("requires_permit")),
            "mhs_version": _ids.WIRE_VERSION,
        }
        if hardware_disabled:
            x_mhs["hardware_disabled"] = True
        tool["x-mhs"] = x_mhs
        tool["_meta"] = {META_KEY: dict(x_mhs)}
        return tool

    # -- dispatch ----------------------------------------------------------
    def priority(self, message: Any) -> str | None:
        """How the stdio loop serves ``message`` while a call is in flight.

        ``"inline"`` (answered on the reader thread at once): ``ping`` and
        ``tools/call mhs__estop`` after ``initialize``.  ``"thread"``:
        ``notifications/cancelled`` (its cancel may wait for a receipt).
        ``None``: in order on the worker.
        """
        if not isinstance(message, Mapping):
            return None
        method = message.get("method")
        if method == "ping":
            return "inline"
        if method == "notifications/cancelled":
            return "thread"
        if method == "tools/call" and self.initialized:
            params = message.get("params")
            if isinstance(params, Mapping) and params.get("name") == "mhs__estop":
                return "inline"
        return None

    def handle_message(self, message: Any) -> dict[str, Any] | None:
        if isinstance(message, list):
            return _error(None, -32600, "MCP stdio does not accept JSON-RPC batches")
        if not isinstance(message, Mapping):
            return _error(None, -32600, "Request must be a JSON object")
        mid = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(method, str) or not method:
            return _error(mid, -32600, "Request is missing a method")
        is_notification = "id" not in message
        if not isinstance(params, Mapping):
            if method.startswith("notifications/"):
                return None
            return _error(mid, -32602, "params must be an object")
        try:
            if method == "initialize":
                return _result(mid, self._initialize(params))
            if method == "ping":
                return _result(mid, {})
            if method.startswith("notifications/"):
                self._handle_notification(method, params)
                return None
            if not self.initialized:
                return _error(mid, -32002, "Server not initialized: send initialize first")
            if method == "tools/list":
                self._ensure_loaded()
                if not self.policy.enabled:
                    return _result(mid, {"tools": []})
                return _result(mid, {"tools": self._tool_descriptions()})
            if method == "tools/call":
                if self._take_cancelled(mid):
                    return None  # cancelled while queued: never dispatched, and MCP sends no response
                result = self._tools_call(mid, params)
                return None if result is _CANCELLED else _result(mid, result)
            if method == "resources/list":
                return _result(mid, self._resources_list(params))
            if method == "resources/read":
                return _result(mid, self._resources_read(params))
            if method == "resources/templates/list":
                return _result(mid, {"resourceTemplates": []})
            if method == "prompts/list":
                return _result(mid, {"prompts": []})
            if method == "logging/setLevel":
                return _result(mid, {})
            return _error(mid, -32601, f"Method not found: {method}")
        except _ProjectionError as exc:
            return None if is_notification else _error(mid, exc.code, exc.message, exc.data)
        except Exception as exc:  # noqa: BLE001 - every failure becomes a JSON-RPC error
            if is_notification:
                return None
            payload = _error_payload(exc)
            return _error(mid, -32603, payload.get("message") or "internal error", payload)

    def _handle_notification(self, method: str, params: Mapping[str, Any]) -> None:
        if method != "notifications/cancelled":
            return
        request_id = params.get("requestId")
        if request_id is None:
            return
        with self._lock:
            if request_id not in self._inflight:
                # not dispatched yet (queued behind another call): the worker skips it, so a user-aborted
                # actuation never reaches the endpoint
                self._cancelled[request_id] = True
                while len(self._cancelled) > 256:  # bounded: oldest first
                    self._cancelled.pop(next(iter(self._cancelled)))
                return
        self._cancel_inflight(request_id, str(params.get("reason") or ""))

    def _take_cancelled(self, request_id: Any) -> bool:
        """True (and forgotten) when ``notifications/cancelled`` named ``request_id`` before its dispatch."""
        if request_id is None:
            return False
        with self._lock:
            return self._cancelled.pop(request_id, None) is not None

    def _cancel_inflight(self, request_id: Any, reason: str = "") -> None:
        """Forward an MCP cancellation to ``mhs.operations.cancel`` (best effort, TPT-040/041).

        A call still in flight has no operation id in hand yet: it is looked up
        by the call's ``command_id`` in its session's operations.
        """
        text = ("MCP client cancelled the tool call" + (f": {reason}" if reason else ""))[:200]
        for attempt in range(5):
            with self._lock:
                inflight = dict(self._inflight.get(request_id) or {})
            if not inflight:
                return
            operation_id = inflight.get("operation_id")
            session_id = inflight.get("session_id")
            try:
                if not operation_id and session_id:
                    listed = self.client.operations(inflight.get("device_id"), session_id=session_id)
                    for item in (listed or {}).get("operations") or []:
                        if isinstance(item, Mapping) and item.get("command_id") == inflight.get("command_id"):
                            operation_id = item.get("operation_id")
                            break
                if operation_id:
                    kwargs: dict[str, Any] = {"reason": text}
                    if session_id:
                        kwargs["session_id"] = session_id
                    self.client.cancel(operation_id, **kwargs)
                    return
            except Exception:  # noqa: BLE001 - cancellation is best effort
                return
            time.sleep(0.05 * (attempt + 1))  # the operation may not be registered yet

    # -- initialize --------------------------------------------------------
    def _initialize(self, params: Mapping[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION
        self.protocol_version = str(version)
        self.client_info = dict(params.get("clientInfo") or {}) if isinstance(params.get("clientInfo"), Mapping) else {}
        self.principal = agent_principal(self.client_info)
        if self.policy.enabled:
            try:
                hello = self.client.hello()
                endpoint_id = hello.get("endpoint_id") if isinstance(hello, Mapping) else None
                if isinstance(endpoint_id, str) and endpoint_id:
                    self.endpoint_id = endpoint_id
            except Exception:  # noqa: BLE001 - handshake may fail; tools/list will surface it
                pass
        self.server_name = f"mhs-mcp:{self.endpoint_id}" if self.endpoint_id else "mhs-mcp"
        self.initialized = True
        sys.stderr.write(
            f"[mhs.mcp] initialized for {self.client_info.get('name', 'unknown client')} "
            f"({self.server_name}, MCP {self.protocol_version}); policy enabled={int(self.policy.enabled)} "
            f"allow_hardware={int(self.policy.allow_hardware)} operator_tools={int(self.policy.operator_tools)} "
            f"allow_external_sessions={int(self.policy.allow_external_sessions)} "
            f"config={self.policy.path or '(direct launch)'}; principal={self.principal['id']}; "
            "MHS is not a safety-rated channel (MHS.SAFETY.NOT_CERTIFIED)\n"
        )
        sys.stderr.flush()
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": {"name": self.server_name, "version": SERVER_VERSION},
            "instructions": (
                "MHS projection: each capability tool (mhs__<device>__<capability>) sends one mhs.command; its "
                "description lists the limits the endpoint enforces, the interlocks it needs and device facts. "
                "A receipt, including a rejected or unknown outcome, is a successful tool call; isError=true means "
                "no receipt exists. To retry a call, reuse its command_id (or _meta.retryToken): the endpoint "
                "returns the first receipt instead of acting twice; never retry an 'unknown' outcome before "
                "checking mhs__operations or mhs__read. Sessions are managed by this connector: omit session_id. "
                "Discovery: mhs__devices, mhs__inspect, mhs__read, mhs__safety, mhs__operations, mhs__evidence. "
                "mhs__estop stops a device at once; resets and permit approvals are operator decisions. "
                "MHS never replaces a hardware e-stop (MHS.SAFETY.NOT_CERTIFIED)."
            ),
        }

    # -- tools/call --------------------------------------------------------
    def _policy_error(self, code: str, message: str, **details: Any) -> dict[str, Any]:
        return _tool_error(code, message, **details)

    def _policy_refusal(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any] | None:
        """Return a coded refusal when host policy forbids this tool call."""
        if not self.policy.enabled:
            return self._policy_error(
                "MHS.AUTH.FORBIDDEN",
                "the MHS integration is disabled (enabled=false in the host policy); "
                "no endpoint call was made",
                policy="enabled=false",
                tool=name,
            )
        if name in OPERATOR_TOOLS and not self.policy.operator_tools:
            return self._policy_error(
                "MHS.AUTH.FORBIDDEN",
                f"{name} is an operator tool and this connector does not expose it (operator_tools=false in "
                "the host policy): resetting an e-stop and approving a permit are human decisions made in the "
                "operator console or CLI; no endpoint call was made",
                policy="operator_tools=false",
                reason="operator_tool",
                tool=name,
            )
        if self.policy.allow_hardware:
            return None
        if name not in _DISCOVERY_TOOLS:
            self._ensure_loaded()
            entry = self._tools.get(name)
            if entry is not None and self._is_hardware(entry["device_id"]):
                return self._policy_error(
                    "MHS.AUTH.HARDWARE_DISABLED",
                    "refusing a hardware capability call: allow_hardware is false in "
                    "the MHS host policy",
                    device_id=entry["device_id"],
                    capability_id=entry["capability_id"],
                    policy="allow_hardware=false",
                )
            return None
        if name in _SAFETY_ALLOWED_TOOLS:
            return None
        if name == "mhs__read":
            device_id = arguments.get("device_id")
            self._ensure_loaded()
            if isinstance(device_id, str) and device_id:
                hardware = self._is_hardware(device_id)
            else:
                resource_id = arguments.get("resource_id")
                mapped = self._resource_devices.get(str(resource_id), []) if isinstance(resource_id, str) else []
                hardware = any(self._is_hardware(item) for item in mapped)
            if hardware:
                return self._policy_error(
                    "MHS.AUTH.HARDWARE_DISABLED",
                    "refusing to read a hardware device while allow_hardware is false; "
                    "mhs__safety and mhs__inspect remain available",
                    device_id=device_id,
                    policy="allow_hardware=false",
                )
            return None
        if name == "mhs__operations":
            self._ensure_loaded()
            device_id = arguments.get("device_id")
            if isinstance(device_id, str) and device_id:
                hardware = self._is_hardware(device_id)
            else:
                # Listing/cancelling without a device would span hardware devices
                # on this endpoint; refuse rather than silently mix scopes.
                hardware = any(str(item.get("mode")) == "hardware" for item in self.devices)
            if hardware:
                return self._policy_error(
                    "MHS.AUTH.HARDWARE_DISABLED",
                    "refusing MHS operations for a hardware device while "
                    "allow_hardware is false",
                    device_id=device_id,
                    policy="allow_hardware=false",
                )
            return None
        if name == "mhs__permit":
            self._ensure_loaded()
            capability_id = arguments.get("capability_id")
            device_id = arguments.get("device_id")
            if not isinstance(device_id, str) or not device_id:
                for entry in self._tools.values():
                    if str(entry["capability"].get("capability_id")) == str(capability_id):
                        device_id = str(entry["device"].get("device_id"))
                        break
            if self._is_hardware(device_id if isinstance(device_id, str) else None):
                return self._policy_error(
                    "MHS.AUTH.HARDWARE_DISABLED",
                    "refusing to issue a hardware permit while allow_hardware is false",
                    device_id=device_id,
                    capability_id=capability_id,
                    policy="allow_hardware=false",
                )
            return None
        return None

    def _tools_call(self, mid: Any, params: Mapping[str, Any]) -> Any:
        name = params.get("name")
        if not isinstance(name, str):
            raise _ProjectionError(-32602, "tools/call name must be a string")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            raise _ProjectionError(-32602, "tools/call arguments must be an object")
        refusal = self._policy_refusal(name, arguments)
        if refusal is not None:
            return refusal
        meta = params.get("_meta") if isinstance(params.get("_meta"), Mapping) else {}
        if name in _DISCOVERY_TOOLS:
            return self._discovery_call(name, arguments)
        return self._capability_call(mid, name, arguments, meta)

    def _command_id(self, name: str, arguments: Mapping[str, Any], meta: Mapping[str, Any]) -> str | None:
        for raw in (arguments.get("command_id"), meta.get("command_id"), meta.get("retryToken"),
                    meta.get("retry_token")):
            if raw is None:
                continue
            if not isinstance(raw, str) or not raw:
                raise _ProjectionError(-32602, "command_id and _meta.retryToken must be non-empty strings")
            return raw if _ULID_RE.match(raw) else retry_command_id(raw, name)
        return None

    def _capability_call(self, mid: Any, name: str, arguments: Mapping[str, Any],
                         meta: Mapping[str, Any]) -> dict[str, Any]:
        self._ensure_loaded()
        entry = self._tools.get(name)
        if entry is None:
            raise _ProjectionError(-32602, f"unknown tool {name!r}")
        # Reserved control arguments are not capability input: the capability
        # schema validates only the physical arguments, while command_id is the
        # MHS idempotency key and permit_id authorises the call.
        payload = {
            str(key): copy.deepcopy(value)
            for key, value in arguments.items()
            if key not in _RESERVED_ARGUMENTS
        }
        session_arg = arguments.get("session_id")
        if session_arg is not None and not isinstance(session_arg, str):
            raise _ProjectionError(-32602, "session_id must be a string")
        errors = _validate_input(entry.get("validation_schema"), payload)
        if errors:
            return _tool_error(
                "MHS.CAPABILITY.INPUT_INVALID",
                "; ".join(errors[:8]) + " (nothing was sent to the device; fix the arguments and call again)",
                details={"errors": errors[:16]},
                tool=name,
                capability_id=entry["capability_id"],
            )
        command_id = self._command_id(name, arguments, meta)
        owned: _OwnedSession | None = None
        try:
            if session_arg is not None:
                owned = self._owned(session_arg)
                if owned is None and not self.policy.allow_external_sessions:
                    return _tool_error(
                        "MHS.SESSION.UNKNOWN",
                        "this connector did not open that session_id and does not accept other sessions; omit "
                        "session_id (the connector opens, renews and closes its own sessions)",
                        tool=name,
                        policy="allow_external_sessions=false",
                    )
                if owned is not None:
                    self._touch(owned)
                session_id = session_arg
            else:
                session_id = self._session_for_device(entry["device_id"], entry["capability_id"])
        except _SessionLapsed as lapse:
            return self._session_renewed(lapse, tool=name)
        kwargs: dict[str, Any] = {"session_id": session_id, "device_id": entry["device_id"]}
        if command_id:
            kwargs["command_id"] = command_id
        else:
            from mhs import canonical

            command_id = canonical.ulid()
            kwargs["command_id"] = command_id
        expected_revision = arguments.get("expected_revision")
        if isinstance(expected_revision, int) and not isinstance(expected_revision, bool):
            kwargs["expected_revision"] = expected_revision
        deadline_ms = arguments.get("deadline_ms", meta.get("deadline_ms"))
        if isinstance(deadline_ms, int) and not isinstance(deadline_ms, bool) and deadline_ms > 0:
            kwargs["deadline_ms"] = deadline_ms
        permit_id = arguments.get("permit_id")
        if isinstance(permit_id, str) and permit_id:
            kwargs["permit_id"] = permit_id
        with self._lock:
            if mid is not None and self._cancelled.pop(mid, None) is not None:
                return _CANCELLED  # cancelled while this call was being prepared: nothing was sent
            # In flight: notifications/cancelled finds the operation by this command_id.
            self._inflight[mid] = {"command_id": command_id, "device_id": entry["device_id"],
                                   "session_id": session_id, "operation_id": None}
        try:
            receipt = self.client.invoke(entry["capability_id"], payload, **kwargs)
        except Exception as exc:  # noqa: BLE001 - no MHS receipt exists: a tool malfunction
            code = str(getattr(exc, "code", "") or "")
            if code in _SESSION_LAPSED and (owned is not None or session_arg is None):
                return self._session_renewed(
                    _SessionLapsed(code, session_id, entry["device_id"], entry["capability_id"]), tool=name)
            payload_error = _error_payload(exc)
            payload_error.setdefault("command_id", command_id)
            return {
                "content": [{"type": "text", "text": f"{payload_error.get('mhs_code')}: {payload_error.get('message')}"
                             f" (command_id {command_id}: retry only with this command_id after checking state)"}],
                "structuredContent": {"receipt": None, "mhs_error": payload_error},
                "isError": True,
            }
        finally:
            with self._lock:
                current = self._inflight.get(mid)
                if current is not None and current.get("command_id") == command_id:
                    self._inflight.pop(mid, None)
        receipt = dict(receipt or {})
        error = receipt.get("error") if isinstance(receipt.get("error"), Mapping) else None
        operation_id = receipt.get("operation_id")
        structured: dict[str, Any] = {"receipt": receipt, "mhs_error": dict(error) if error else None}
        status = receipt.get("status")
        if isinstance(operation_id, str) and status in ("accepted", "running", "unknown"):
            vendor = receipt.get("x-vendor") if isinstance(receipt.get("x-vendor"), Mapping) else {}
            handle = {"operation_id": operation_id, "status": status, "device_id": entry["device_id"]}
            for key in ("long_running", "deadline_ms", "max_duration_ms", "unknown_receipt_id"):
                if key in vendor:
                    handle[key] = vendor[key]
            structured["operation"] = handle
            with self._lock:
                self._inflight[mid] = {"command_id": command_id, "device_id": entry["device_id"],
                                       "session_id": session_id, "operation_id": operation_id}
                while len(self._inflight) > 256:  # bounded: oldest first
                    self._inflight.pop(next(iter(self._inflight)))
        progress_token = meta.get("progressToken")
        if progress_token is not None and isinstance(operation_id, str):
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progressToken": progress_token,
                    "progress": int((receipt.get("progress") or {}).get("percent") or 0),
                    "total": 100,
                    "message": f"MHS operation {operation_id} {status}",
                },
            }
            with self._lock:
                self.pending_notifications.append(notification)
        return {
            "content": [{"type": "text", "text": _receipt_text(receipt)}, *self._register_artifacts(receipt)],
            "structuredContent": structured,
            "isError": False,
        }

    def _discovery_call(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            if name == "mhs__devices":
                self._ensure_loaded()
                result: Any = [self._device_summary(device) for device in self.devices]
            elif name == "mhs__inspect":
                result = self.client.inspect(_required(arguments, "device_id"))
            elif name == "mhs__read":
                result = self._read(arguments)
            elif name == "mhs__safety":
                result = self.client.safety_status(_required(arguments, "device_id"))
            elif name == "mhs__operations":
                result = self._operations(arguments)
            elif name == "mhs__evidence":
                result = self._evidence(arguments)
            elif name == "mhs__estop":
                device_id = _required(arguments, "device_id")
                # Never wait for a session: an existing one only attributes the stop.
                owned = self._owned_for_device(device_id)
                result = self.client.estop(
                    str(arguments.get("reason") or "MCP host requested emergency stop"),
                    device_id=device_id,
                    session_id=owned[0].session_id if owned else None,
                )
            elif name == "mhs__reset":
                device_id = _required(arguments, "device_id")
                result = self.client.reset(device_id=device_id,
                                           session_id=self._session_for_device(device_id, safety=True))
            elif name == "mhs__permit":
                result = self._permit(arguments)
            else:  # pragma: no cover - defensive
                raise _ProjectionError(-32601, f"unknown discovery tool {name!r}")
        except _ProjectionError as exc:
            return _tool_error("MHS.PROTOCOL.INVALID_PARAMS", exc.message, tool=name)
        except _PolicyDenied as exc:
            return _tool_error(exc.code, exc.message, **exc.data)
        except _SessionLapsed as lapse:
            return self._session_renewed(lapse, tool=name)
        except Exception as exc:  # noqa: BLE001 - no MHS receipt exists
            payload = _error_payload(exc)
            return {
                "content": [{"type": "text", "text": f"{payload.get('mhs_code')}: {payload.get('message')}"}],
                "structuredContent": {"receipt": None, "mhs_error": payload},
                "isError": True,
            }
        links = self._register_artifacts(result) if name == "mhs__operations" else []
        return {
            "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}, *links],
            "structuredContent": {name.replace("mhs__", ""): result},
            "isError": False,
        }

    def _device_summary(self, device: Mapping[str, Any]) -> dict[str, Any]:
        device_id = str(device.get("device_id") or "")
        safety = device.get("safety") if isinstance(device.get("safety"), Mapping) else {}
        summary: dict[str, Any] = {
            "device_id": device_id,
            "name": device.get("display_name"),
            "mode": device.get("mode"),
            "risk_class": safety.get("risk_class"),
            "resources": [str(item.get("resource_id")) for item in device.get("resources") or []
                          if isinstance(item, Mapping) and item.get("resource_id")],
            "tools": sorted(name for name, entry in self._tools.items() if entry["device_id"] == device_id),
        }
        if self._is_hardware(device_id) and not self.policy.allow_hardware:
            summary["hardware_disabled"] = True
        return summary

    def _read(self, arguments: Mapping[str, Any]) -> Any:
        resource_id = _required(arguments, "resource_id")
        device_id = arguments.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            self._ensure_loaded()
            candidates = self._resource_devices.get(resource_id, [])
            if len(candidates) != 1:
                raise _ProjectionError(
                    -32602,
                    f"resource {resource_id!r} is on {len(candidates)} devices; pass device_id" if candidates
                    else f"unknown resource_id {resource_id!r}; see mhs__devices",
                )
            device_id = candidates[0]
        fields = arguments.get("fields")
        return self._with_read_session(device_id, lambda session_id: self.client.read(
            resource_id, device_id=device_id, fields=fields, session_id=session_id))

    def _operations(self, arguments: Mapping[str, Any]) -> Any:
        device_id = arguments.get("device_id") if isinstance(arguments.get("device_id"), str) else None
        cancel_id = arguments.get("cancel_operation_id")
        operation_id = arguments.get("operation_id")
        owned = self._owned_for_device(device_id) or self._owned_for_device(None)
        if isinstance(cancel_id, str) and cancel_id:
            if not owned:
                raise _ProjectionError(-32602, "this connector has started no operation to cancel")
            return self.client.cancel(cancel_id, session_id=owned[0].session_id,
                                      reason="cancelled through mhs__operations")
        if isinstance(operation_id, str) and operation_id:
            if not owned:
                raise _ProjectionError(-32602, "this connector has started no operation")
            wait_ms = arguments.get("wait_ms")
            wait_ms = int(wait_ms) if isinstance(wait_ms, int) and not isinstance(wait_ms, bool) else 0
            deadline = time.monotonic() + max(0, min(wait_ms, OPERATIONS_WAIT_MAX_MS)) / 1000.0
            delay = 0.05
            while True:
                receipt = self.client.get_operation(operation_id, session_id=owned[0].session_id)
                status = (receipt or {}).get("status")
                if status in ("completed", "failed", "rejected", "cancelled") or time.monotonic() >= deadline:
                    return receipt
                time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
                delay = min(delay * 1.5, 1.0)
        items: dict[str, Any] = {}
        for session in self._owned_for_device(device_id):
            try:
                listed = self.client.operations(device_id, session_id=session.session_id)
            except Exception as exc:  # noqa: BLE001 - a lapsed session lists nothing
                if str(getattr(exc, "code", "") or "") in _SESSION_LAPSED:
                    continue
                raise
            for item in (listed or {}).get("operations") or []:
                if isinstance(item, Mapping) and item.get("operation_id"):
                    items[str(item["operation_id"])] = dict(item)
        operations = sorted(items.values(), key=lambda item: str(item.get("operation_id")))
        return {"operations": operations, "count": len(operations)}

    def _evidence(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        last_n = arguments.get("last_n", EVIDENCE_LAST_N)
        if not isinstance(last_n, int) or isinstance(last_n, bool) or last_n < 0:
            raise _ProjectionError(-32602, "last_n must be a non-negative integer")
        last_n = min(last_n, EVIDENCE_MAX_N)
        command_id = arguments.get("command_id")
        bundle = self.client.export_evidence()
        verify = self.client.verify_evidence(bundle)
        receipts = [item for item in (bundle or {}).get("receipts") or [] if isinstance(item, Mapping)]
        if isinstance(command_id, str) and command_id:
            selected = [item for item in receipts if item.get("command_id") == command_id][-EVIDENCE_MAX_N:]
        else:
            selected = receipts[-last_n:] if last_n else []
        verify = dict(verify or {})
        if isinstance(verify.get("errors"), list):
            verify["errors"] = verify["errors"][:5]
        result = {
            "count": len(receipts),
            "head_digest": (bundle or {}).get("head_digest"),
            "valid": bool(verify.get("valid")),
            "verify": verify,
            "receipts": selected,
            "uri": f"mhs://{self._endpoint_authority()}/evidence",
        }
        if arguments.get("include_bundle") is True:
            # For hosts whose MCP route has no resources/read; bounded only by the frame. The argument is not in
            # the tool's inputSchema, so a model is never offered the unbounded bundle.
            result["bundle"] = bundle
        return result

    def _permit(self, arguments: Mapping[str, Any]) -> Any:
        capability_id = _required(arguments, "capability_id")
        input_payload = arguments.get("input")
        input_digest = arguments.get("input_digest")
        resource = arguments.get("resource")
        device_id = arguments.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            self._ensure_loaded()
            for entry in self._tools.values():
                if str(entry["capability"].get("capability_id")) == capability_id:
                    device_id = str(entry["device"].get("device_id"))
                    if not isinstance(resource, str):
                        resource = entry["capability"].get("resource")
                    break
        if not isinstance(device_id, str) or not device_id:
            raise _ProjectionError(-32602, "device_id is required when the capability is unknown")
        session_id = self._session_for_device(device_id, capability_id)
        ttl_s = arguments.get("ttl_s")
        kwargs: dict[str, Any] = {
            "ttl_s": int(ttl_s) if isinstance(ttl_s, int) and not isinstance(ttl_s, bool) and ttl_s > 0 else 60,
            "approvals": list(arguments.get("approvals") or []),
            "session_id": session_id,
            "device_id": device_id,
        }
        if isinstance(input_payload, Mapping):
            # PROTO-036: the client binds the permit to the action digest.
            return self.client.permit(capability_id, input_payload, resource=resource, **kwargs)
        if not isinstance(input_digest, str) or not input_digest.startswith("sha256:"):
            raise _ProjectionError(-32602, "provide input (preferred) or a sha256: input_digest")
        return self.client.permit(capability_id, input_digest=input_digest, resource=resource, **kwargs)

    def _register_artifacts(self, receipt: Any) -> list[dict[str, Any]]:
        # Only command/operation results reach here, never arbitrary driver
        # strings or evidence exports. Remote MHS transports have no blob API.
        if (getattr(self.client, "supports_local_artifacts", False) is not True
                or not isinstance(receipt, Mapping) or receipt.get("status") != "completed"):
            return []
        owned = self._owned(receipt.get("session_id"))
        if (owned is None or owned.device_id != receipt.get("device_id")
                or owned.capability_id != receipt.get("capability_id")):
            return []  # external sessions do not grant this projection image access
        items = receipt.get("artifacts")
        if not isinstance(receipt.get("output"), Mapping) or not isinstance(items, list) or len(items) > 1:
            return []
        links = []
        with self._lock:
            for uri, route in list(self._artifact_routes.items()):
                if route["expires"] <= time.time():
                    del self._artifact_routes[uri]
            for descriptor in items:
                if not isinstance(descriptor, Mapping):
                    continue
                uri = descriptor.get("uri")
                size = descriptor.get("size_bytes")
                media = descriptor.get("media_type")
                output = receipt["output"]
                references = [name for name in ("image_ref", "artifact_ref") if output.get(name) == uri]
                if (not isinstance(uri, str) or len(uri) > 512
                        or not re.fullmatch(r"mhs\+artifact://[A-Za-z0-9._:-]+/[0-9A-HJKMNP-TV-Z]{26}", uri)
                        or type(size) is not int or not 0 < size <= getattr(self.client, "local_artifact_max_bytes", 0)
                        or not isinstance(media, str) or len(media) > 127
                        or re.fullmatch(r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*", media) is None
                        or len(references) != 1):
                    continue
                try:
                    expires = datetime.fromisoformat(str(descriptor["expires_at"]).replace("Z", "+00:00")).timestamp()
                except (ValueError, KeyError, OverflowError):
                    continue
                if expires <= time.time() or (len(self._artifact_routes) >= 4096 and uri not in self._artifact_routes):
                    continue
                label = "Captured image" if references == ["image_ref"] else "Command artifact"
                self._artifact_routes[uri] = {"session_id": owned.session_id, "device_id": owned.device_id, "name": label,
                                              "descriptor": copy.deepcopy(dict(descriptor)), "expires": expires}
                if self.protocol_version >= "2025-06-18":
                    links.append({"type": "resource_link", "uri": uri, "name": label,
                                  "mimeType": media, "size": size})
        return links

    def _read_artifact_resource(self, uri: str, route: Mapping[str, Any]) -> dict[str, Any]:
        if self._owned(route["session_id"]) is None or route["expires"] <= time.time():
            raise _ProjectionError(-32602, "artifact session or grant is no longer available")
        try:
            self._assert_device_allowed(route["device_id"])
        except _PolicyDenied as exc:
            raise _ProjectionError(-32010, exc.message, {"mhs_code": exc.code, **exc.data}) from exc
        # Deliberately do not renew/reopen here: the original session owns this
        # image. Endpoint auth, expiry and exact scope are checked on every read.
        result = self.client.read_artifact(uri, session_id=route["session_id"])
        descriptor, data = result["descriptor"], result["data"]
        if (descriptor != route["descriptor"] or not isinstance(data, bytes)
                or len(data) != descriptor["size_bytes"]
                or "sha256:" + hashlib.sha256(data).hexdigest() != descriptor["digest"]):
            raise _ProjectionError(-32603, "artifact integrity check failed")
        # Only this authenticated registered-resource response can exceed the
        # ordinary frame ceiling, and only within the local store's explicit
        # size setting. Requests/tools/notifications retain their normal bound.
        configured = getattr(self.client, "local_artifact_max_bytes", 0)
        if type(configured) is not int or not 0 < len(data) <= configured <= 16 * 1024 * 1024:
            raise _ProjectionError(-32603, "artifact exceeds configured local size limit")
        frame_limit = min(MAX_ARTIFACT_RESPONSE_BYTES, max(MAX_FRAME_BYTES, 4 * ((configured + 2) // 3) + 2048))
        response = _ArtifactResourceResult([{"uri": uri, "mimeType": descriptor["media_type"],
                                            "blob": base64.b64encode(data).decode("ascii")}], frame_limit)
        if len(json.dumps(response).encode("utf-8")) + 1024 > frame_limit:
            raise _ProjectionError(-32603, "artifact response exceeds the MCP frame limit")
        return response

    # -- resources ---------------------------------------------------------
    def _resources_list(self, params: Mapping[str, Any]) -> dict[str, Any]:
        if not self.policy.enabled:
            return {"resources": []}
        self._ensure_loaded()
        cursor = params.get("cursor")
        offset = 0
        if isinstance(cursor, str) and cursor:
            try:
                offset = max(0, int(cursor))
            except ValueError as exc:
                raise _ProjectionError(-32602, "invalid pagination cursor") from exc
        with self._lock:
            artifacts = [{"uri": uri, "name": route["name"], "mimeType": route["descriptor"]["media_type"],
                          "size": route["descriptor"]["size_bytes"]}
                         for uri, route in self._artifact_routes.items()
                         if route["expires"] > time.time() and self._owned(route["session_id"]) is not None
                         and (self.policy.allow_hardware or not self._is_hardware(route["device_id"]))]
        resources = self._resources + artifacts
        page = resources[offset : offset + RESOURCE_PAGE_SIZE]
        result: dict[str, Any] = {"resources": list(page)}
        if offset + RESOURCE_PAGE_SIZE < len(resources):
            result["nextCursor"] = str(offset + RESOURCE_PAGE_SIZE)
        return result

    def _resources_read(self, params: Mapping[str, Any]) -> dict[str, Any]:
        if not self.policy.enabled:
            raise _ProjectionError(
                -32002,
                "the MHS integration is disabled (enabled=false in the host policy)",
                {"mhs_code": "MHS.AUTH.FORBIDDEN", "policy": "enabled=false"},
            )
        # Discover first: a fresh connection may read a URI it learnt elsewhere.
        self._ensure_loaded()
        uri = params.get("uri")
        if isinstance(uri, str):
            with self._lock:
                artifact = self._artifact_routes.get(uri)
            if artifact is not None:
                return self._read_artifact_resource(uri, artifact)
        if not isinstance(uri, str) or uri not in self._resource_routes:
            raise _ProjectionError(-32602, f"unknown resource uri {uri!r}")
        kind, device_id, resource_id = self._resource_routes[uri]
        if kind == "resource" and self._is_hardware(device_id) and not self.policy.allow_hardware:
            raise _ProjectionError(
                -32010,
                "refusing to read a hardware device while allow_hardware is false",
                {
                    "mhs_code": "MHS.AUTH.HARDWARE_DISABLED",
                    "device_id": device_id,
                    "policy": "allow_hardware=false",
                },
            )
        if kind == "devices":
            payload: Any = [self._device_summary(device) for device in self.devices]
        elif kind == "manifest":
            payload = self.client.inspect(device_id)
        elif kind == "reference":
            payload = (self.client.inspect(device_id) or {}).get("reference")
        elif kind == "evidence":
            payload = self.client.export_evidence()
        else:
            try:
                payload = self._with_read_session(
                    device_id, lambda session_id: self.client.read(resource_id, device_id=device_id,
                                                                   session_id=session_id))
            except _SessionLapsed as lapse:
                raise _ProjectionError(-32603, f"{lapse.code}: the session lapsed; read again") from lapse
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(payload, sort_keys=True)}]}

    # -- lifecycle ---------------------------------------------------------
    def drain_notifications(self) -> list[dict[str, Any]]:
        with self._lock:
            pending = self.pending_notifications
            self.pending_notifications = []
        return pending

    def close(self) -> None:
        close_session = getattr(self.client, "close_session", None)
        with self._lock:
            owned = [entry.session_id for entry in self._sessions.values()]
            self._sessions.clear()
            self._artifact_routes.clear()
        for session_id in owned:
            if callable(close_session):
                try:
                    close_session(session_id)
                except Exception:  # noqa: BLE001
                    pass
        close = getattr(self.client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# reference / limits / description helpers
# ---------------------------------------------------------------------------


def _required(arguments: Mapping[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise _ProjectionError(-32602, f"{key} is required")
    return value


def _capability_detail(detail: Mapping[str, Any], capability: Mapping[str, Any]) -> Mapping[str, Any]:
    """The ``devices.get`` entry of ``capability`` (same id and resource)."""
    items = [item for item in detail.get("capabilities") or [] if isinstance(item, Mapping)]
    for item in items:
        if (item.get("capability_id") == capability.get("capability_id")
                and item.get("resource") == capability.get("resource")):
            return item
    for item in items:
        if item.get("capability_id") == capability.get("capability_id"):
            return item
    return {}


def _effective_limits(capability: Mapping[str, Any], detail: Mapping[str, Any]) -> dict[str, Any]:
    value = detail.get("x-mhs-effective-limits") or capability.get("x-mhs-effective-limits")
    return dict(value) if isinstance(value, Mapping) else {}


def _reference_entry(reference: Mapping[str, Any], capability_id: str,
                     resource: Any) -> tuple[str | None, dict[str, Any]]:
    for kind, key in (("action", "actions"), ("measure", "measures")):
        candidates = [item for item in reference.get(key) or []
                      if isinstance(item, Mapping) and item.get("cap_id") == capability_id]
        for item in candidates:
            if resource is None or item.get("resource") in (None, resource):
                return kind, dict(item)
        if candidates:
            return kind, dict(candidates[0])
    return None, {}


def _capability_verb(capability: Mapping[str, Any], ref_kind: str | None, ref_entry: Mapping[str, Any]) -> str:
    verb = capability.get("verb")
    if verb in ("read", "write", "invoke"):
        return str(verb)
    if ref_kind == "measure":
        return "read"
    if ref_kind == "action" and ref_entry.get("verb") in ("read", "write", "invoke"):
        return str(ref_entry["verb"])
    try:
        from . import catalog

        spec = catalog.get(str(capability.get("capability_id")))
        if isinstance(spec, Mapping) and spec.get("verb") in ("read", "write", "invoke"):
            return str(spec["verb"])
    except Exception:  # noqa: BLE001 - an unloadable catalogue is not a read
        pass
    return "invoke"


def _validation_schema(capability: Mapping[str, Any], limits: Mapping[str, Any]) -> dict[str, Any] | None:
    """The capability input schema the projection pre-validates against.

    Bounds the endpoint enforces as limits (``x-mhs-effective-limits``) are
    removed: the endpoint checks limits before the remaining schema bounds and
    refuses an out-of-range value with an ``MHS.SAFETY.ENVELOPE_VIOLATION``
    receipt, which the evidence log keeps (plan 3.5).
    """
    schema = capability.get("input_schema")
    if not isinstance(schema, Mapping):
        return None
    rules = limits.get("limits") if isinstance(limits.get("limits"), Mapping) else None
    if not rules:
        return dict(schema)
    try:
        from . import limits as _limits

        cleaned: dict[str, Any] = {}
        for path, rule in rules.items():
            if isinstance(rule, Mapping):
                cleaned[str(path)] = {key: value for key, value in rule.items() if key in _limits.RULE_KEYS}
            elif rule == _limits.OPERATOR_REQUIRED:
                cleaned[str(path)] = rule
        effective = _limits.compile_limits(schema, [_limits.LimitSource("effective", cleaned, partial=True)])
        return _limits.strip_bound_keywords(effective, schema)
    except Exception:  # noqa: BLE001 - fall back to the full schema
        return dict(schema)


def _validate_input(schema: Any, payload: Mapping[str, Any]) -> list[str]:
    if not isinstance(schema, Mapping):
        return []
    try:
        from mhs.schema import validate

        return [str(item) for item in validate(payload, schema)]
    except Exception:  # noqa: BLE001 - validator absence must not break the projection
        return []


def _clip(text: Any, limit: int) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[: max(0, limit - 3)].rstrip() + "..."


def _number(value: Any) -> str:
    # A whole float prints as an integer, but not one so large that its digits would fill a tool description.
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e16:
        return str(int(value))
    return str(value)


_UNSET_TEXT = "no limit set yet (refused with MHS.SAFETY.LIMITS_UNSET until the operator sets one)"
#: A limit path that names one element of a named array (``action.ctrl[7]``).
_ELEMENT_PATH = re.compile(r"(?P<base>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\[(?P<index>[0-9]+)\]")


def _index_set(indices: Any, size: int | None = None) -> str:
    """``0-3,7,9-10``: element indices as ranges; ``*`` when they are every element of an array of ``size``."""
    ordered = sorted(set(int(index) for index in indices))
    if not ordered:
        return ""
    if size is not None and ordered == list(range(size)):
        return "*"
    parts: list[str] = []
    start = previous = ordered[0]
    for index in ordered[1:] + [None]:
        if index is not None and index == previous + 1:
            previous = index
            continue
        parts.append(str(start) if start == previous else f"{start}-{previous}")
        if index is not None:
            start = previous = index
    return ",".join(parts)


def _bounds_text(path: str, rule: Mapping[str, Any]) -> str | None:
    """``path`` and the bounds of ``rule`` without its reason; ``None`` for a reason-only rule.

    Per-element bounds are listed by position (``path [-1..1, -2..2] rad``)
    or, when that is shorter, by value with the indices that share it
    (``path[0-3,7] -87..87 Nm, [4-6] -12..12 Nm``; ``path[*] -1..1`` when
    every element has the same bounds): the description of a 100-actuator
    model stays within the tool size bound.  In the grouped form every group
    carries the unit, as the merged element rules do (:func:`_element_texts`).
    """
    unit = rule.get("unit")
    suffix = f" {unit}" if isinstance(unit, str) and unit and unit != "1" else ""
    low, high = rule.get("min"), rule.get("max")
    if low is not None or high is not None:
        if isinstance(low, list) and isinstance(high, list) and len(low) == len(high):
            pairs = [f"{_number(a)}..{_number(b)}" for a, b in zip(low, high)]
            positional = f"{path} [" + ", ".join(pairs) + "]" + suffix
            groups: dict[str, list[int]] = {}
            for index, pair in enumerate(pairs):
                groups.setdefault(pair, []).append(index)
            grouped = path + ", ".join(f"[{_index_set(indices, len(pairs))}] {pair}{suffix}"
                                       for pair, indices in groups.items())
            return grouped if pairs and len(grouped) < len(positional) else positional
        if low is not None and high is not None:
            text = f"{_render(low)}..{_render(high)}"
        elif low is not None:
            text = f">= {_render(low)}"
        else:
            text = f"<= {_render(high)}"
        return f"{path} {text}{suffix}"
    if isinstance(rule.get("allowed"), list):
        return f"{path} one of " + ", ".join(_render(item) for item in rule["allowed"][:12])
    return None


def _rule_text(path: str, rule: Any, *, with_reason: bool = True) -> str | None:
    """One limit as prose: ``ticks 1..10000 ms (reason)``; ``None`` for a reason-only rule."""
    if rule == "operator_required":
        return f"{path}: {_UNSET_TEXT}"
    if not isinstance(rule, Mapping):
        return None
    text = _bounds_text(path, rule)
    if text is None:
        return None
    reason = rule.get("reason")
    if with_reason and isinstance(reason, str) and reason:
        text += f" ({_clip(reason, 60)})"
    return text


def _element_texts(base: str, members: Any) -> list[str]:
    """The rules on single elements of the array ``base``, ``(index, rule)``, merged by reason and bounds.

    ``base[0-3,22-25] -87..87, [21] 0..255 (reason)`` per reason and
    ``base[7-20]: no limit set yet (...)`` for the ``operator_required``
    elements, ordered by their first index.  ``base`` may be empty (an input
    property's own description).
    """
    by_reason: dict[str, dict[str, list[int]]] = {}
    unset: list[int] = []
    for index, rule in sorted(members, key=lambda item: item[0]):
        if rule == "operator_required":
            unset.append(index)
            continue
        if not isinstance(rule, Mapping):
            continue
        bounds = _bounds_text("", rule)
        if bounds is None:
            continue
        reason = rule.get("reason")
        key = _clip(reason, 60) if isinstance(reason, str) and reason else ""
        by_reason.setdefault(key, {}).setdefault(bounds.strip(), []).append(index)
    entries: list[tuple[int, str]] = []
    for reason, bodies in by_reason.items():
        text = base + ", ".join(f"[{_index_set(indices)}] {bounds}" for bounds, indices in bodies.items())
        entries.append((min(min(indices) for indices in bodies.values()), text + (f" ({reason})" if reason else "")))
    if unset:
        entries.append((min(unset), f"{base}[{_index_set(unset)}]: {_UNSET_TEXT}"))
    return [text for _first, text in sorted(entries, key=lambda entry: entry[0])]


def _limit_texts(rule_map: Mapping[str, Any], unset: Any) -> list[str]:
    """The entries of a tool's "Enforced limits" sentence, in limit-path order.

    Rules on single elements of one array (``action.ctrl[7]``: a MuJoCo model
    that states a control range for some actuators only publishes one rule
    per actuator) are merged into one entry per array (:func:`_element_texts`)
    when that is shorter than one entry per rule.
    """
    rules = {str(path): rule for path, rule in rule_map.items()}
    plain = [text for text in (_rule_text(path, rule) for path, rule in sorted(rules.items())) if text]
    extra = [str(path) for path in unset or [] if str(path) not in rules]
    plain.extend(_rule_text(path, "operator_required") or "" for path in extra)
    items = dict(rules, **{path: "operator_required" for path in extra})
    elements: dict[str, list[tuple[int, Any]]] = {}
    for path, rule in items.items():
        match = _ELEMENT_PATH.fullmatch(path)
        if match is not None:
            elements.setdefault(match.group("base"), []).append((int(match.group("index")), rule))
    if not elements:
        return plain
    merged: list[str] = []
    for path in sorted(items):
        match = _ELEMENT_PATH.fullmatch(path)
        if match is None:
            text = _rule_text(path, items[path])
            if text:
                merged.append(text)
        elif match.group("base") in elements:
            merged.extend(_element_texts(match.group("base"), elements.pop(match.group("base"))))
    return merged if len("; ".join(merged)) < len("; ".join(plain)) else plain


def _render(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_render(item) for item in value) + "]"
    if isinstance(value, str):
        return value
    return _number(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else json.dumps(value)


def _matching_interlocks(reference: Mapping[str, Any], device: Mapping[str, Any],
                         capability_id: str) -> list[Mapping[str, Any]]:
    from . import limits as _limits

    safety = reference.get("safety") if isinstance(reference.get("safety"), Mapping) else None
    if safety is None:
        safety = device.get("safety") if isinstance(device.get("safety"), Mapping) else {}
    out = []
    for item in safety.get("interlocks") or []:
        if not isinstance(item, Mapping):
            continue
        patterns = item.get("required_for")
        if isinstance(patterns, list) and any(_limits.pattern_matches(str(p), capability_id) for p in patterns):
            out.append(item)
    return out


def _fit_bytes(text: str, limit: int) -> str:
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    return data[: max(0, limit - 3)].decode("utf-8", "ignore").rstrip() + "..."


def _capability_description(entry: Mapping[str, Any], *, hardware_disabled: bool, operator_tools: bool) -> str:
    """The tool description: what it does, what the endpoint enforces, and the device facts (<= 2 KB)."""
    capability = entry["capability"]
    device = entry["device"]
    reference = entry["reference"] if isinstance(entry["reference"], Mapping) else {}
    limits = entry["limits"] if isinstance(entry["limits"], Mapping) else {}
    capability_id = str(capability.get("capability_id"))
    semantics = capability.get("semantics") if isinstance(capability.get("semantics"), Mapping) else {}
    safety = device.get("safety") if isinstance(device.get("safety"), Mapping) else {}
    fidelity = device.get("fidelity") if isinstance(device.get("fidelity"), Mapping) else {}
    determinism = fidelity.get("determinism") if isinstance(fidelity.get("determinism"), Mapping) else {}
    title = str(capability.get("title") or entry["ref_entry"].get("name") or capability_id)
    summary = str(semantics.get("summary") or entry["ref_entry"].get("description") or "")
    head = _clip(title, 120) + "." + (f" {_clip(summary, 300)}" if summary and summary != title else "")
    facts_line = f"Mode: {device.get('mode')}. Risk: {safety.get('risk_class')}."
    if device.get("mode") in ("simulated", "replay", "hybrid"):
        gaps = fidelity.get("gaps") or []
        facts_line += (f" Determinism: {determinism.get('kind') or 'none'}. Fidelity gaps: "
                       + ("; ".join(_clip(gap, 80) for gap in gaps[:2]) if gaps else "none declared") + ".")
    segments: list[tuple[int, str]] = [(0, head), (0, facts_line)]
    rule_map = limits.get("limits") if isinstance(limits.get("limits"), Mapping) else {}
    rules = _limit_texts(rule_map, limits.get("operator_required") or [])
    if rules:
        segments.append((1, "Enforced limits (the endpoint refuses anything outside them with "
                            "MHS.SAFETY.ENVELOPE_VIOLATION and a receipt): " + "; ".join(rules) + "."))
    interlocks = _matching_interlocks(reference, device, capability_id)
    if interlocks:
        segments.append((2, "Interlocks that must read closed: " + "; ".join(
            f"{item.get('id')} ({_clip(item.get('description') or '', 60)})" for item in interlocks[:6]) + "."))
    if capability.get("requires_permit"):
        segments.append((1, "Requires an approved MHS permit (permit_id); "
                            + ("mhs__permit issues one after the human approval." if operator_tools
                               else "only the operator can issue one.")))
    constraints = capability.get("constraints") if isinstance(capability.get("constraints"), Mapping) else {}
    if constraints.get("long_running") or entry["ref_entry"].get("long_running"):
        segments.append((1, "Long-running: the receipt can be 'running' with an operation_id; "
                            "mhs__operations {operation_id, wait_ms} returns the final receipt."))
    if hardware_disabled:
        segments.append((0, "Hardware access is disabled by host policy (allow_hardware=false); calls are refused "
                            "until the operator authorizes hardware."))
    facts = [item for item in reference.get("facts") or [] if isinstance(item, Mapping) and item.get("text")]
    if facts:
        segments.append((3, "Facts: " + " ".join(
            f"{_clip(item.get('text'), 160)} [{item.get('source') or 'unsourced'}"
            + (f" {item.get('ref')}" if item.get("ref") else "") + "]." for item in facts[:6])))
    segments.append((0, _NOT_CERTIFIED))
    segments.append((0, f"MHS capability {capability_id} on device {device.get('device_id')}."))
    order = [segment for segment in segments]
    text = " ".join(item for _, item in order)
    # Over budget: shorten the least important segments first, then cut.
    for level in (3, 2, 1):
        if len(text.encode("utf-8")) <= TOOL_DESCRIPTION_LIMIT:
            break
        excess = len(text.encode("utf-8")) - TOOL_DESCRIPTION_LIMIT
        order = [(priority, _fit_bytes(item, max(40, len(item.encode("utf-8")) - excess - 1))
                  if priority == level else item) for priority, item in order]
        text = " ".join(item for _, item in order)
    return _fit_bytes(text, TOOL_DESCRIPTION_LIMIT)


def _capability_annotations(title: str, verb: str, risk: Any, mode: Any) -> dict[str, Any]:
    """MCP tool annotations derived from the verb, the risk class and the device mode."""
    read_only = verb == "read"
    physical = mode in ("hardware", "hybrid")
    return {
        "title": _clip(title, 120),
        "readOnlyHint": read_only,
        "destructiveHint": (not read_only) and (risk in ("R2", "R3") or physical),
        "idempotentHint": verb in ("read", "write"),
        "openWorldHint": physical,
    }


def _discovery_annotations(title: str, *, read_only: bool, destructive: bool = False,
                           idempotent: bool = True) -> dict[str, Any]:
    return {"title": title, "readOnlyHint": read_only, "destructiveHint": destructive,
            "idempotentHint": idempotent, "openWorldHint": False}


# ---------------------------------------------------------------------------
# schema / text helpers
# ---------------------------------------------------------------------------


def _schema_types(schema: Mapping[str, Any]) -> list[str]:
    kinds = schema.get("type")
    return [kinds] if isinstance(kinds, str) else [str(kind) for kind in kinds or [] if isinstance(kind, str)]


def _type_text(schema: Mapping[str, Any]) -> str:
    kinds = [kind for kind in _schema_types(schema) if kind != "null"]
    if "array" in kinds and isinstance(schema.get("items"), Mapping):
        inner = [kind for kind in _schema_types(schema["items"]) if kind != "null"]
        return "array of " + ("/".join(inner) or "values")
    return "/".join(kinds) or "value"


def _is_numeric(schema: Mapping[str, Any]) -> bool:
    kinds = _schema_types(schema)
    if "array" in kinds and isinstance(schema.get("items"), Mapping):
        return _is_numeric(schema["items"])
    return any(kind in ("number", "integer") for kind in kinds)


def _schema_unit(schema: Mapping[str, Any]) -> str | None:
    unit = schema.get("x-mhs-unit")
    if not unit and isinstance(schema.get("items"), Mapping):
        unit = schema["items"].get("x-mhs-unit")
    return str(unit) if isinstance(unit, str) and unit else None


def _describe_property(path: str, schema: dict[str, Any], *, required: bool, rules: Mapping[str, Any],
                       unset: set[str], depth: int = 0) -> None:
    """Give ``schema`` (one input property, edited in place) a description with type, unit and limit."""
    existing = str(schema.get("description") or "").strip()
    parts = [existing if existing.endswith((".", "!", "?")) else existing + "."] if existing else [
        f"{_type_text(schema).capitalize()}, {'required' if required else 'optional'}."]
    unit = _schema_unit(schema)
    rule = rules.get(path) if path in rules else rules.get(f"{path}[*]")
    if not unit and isinstance(rule, Mapping) and isinstance(rule.get("unit"), str) and rule["unit"]:
        unit = rule["unit"]  # the schema declares none, but the enforced limit states the unit it is checked in
    if _is_numeric(schema):
        if unit and unit.lower() not in existing.lower():
            parts.append(f"Unit: {unit}.")
        elif not unit:
            parts.append("Unit: none declared.")
    # Rules on single elements of this array (path[3]); unset ones are listed in the rule map as well.
    elements = [(int(match.group("index")), value) for key, value in rules.items()
                if (match := _ELEMENT_PATH.fullmatch(str(key))) is not None and match.group("base") == path]
    elements += [(int(match.group("index")), "operator_required") for key in unset
                 if (match := _ELEMENT_PATH.fullmatch(str(key))) is not None and match.group("base") == path
                 and key not in rules]
    if path in unset or f"{path}[*]" in unset:
        parts.append("No limit set yet: refused with MHS.SAFETY.LIMITS_UNSET until the operator sets one.")
    elif rule is not None:
        text = _rule_text("", rule)
        if text:
            parts.append(f"Endpoint-enforced limit: {text.strip()}.")
    elif elements:
        parts.append("Endpoint-enforced limits by element: " + "; ".join(_element_texts("", elements)) + ".")
    elif isinstance(schema.get("enum"), list) and "one of" not in existing.lower():
        parts.append("One of: " + ", ".join(_render(item) for item in schema["enum"][:12]) + ".")
    schema["description"] = " ".join(part for part in parts if part)
    if depth >= 3:
        return
    target = schema
    prefix = path
    if "array" in _schema_types(schema) and isinstance(schema.get("items"), Mapping):
        target = schema["items"]
        prefix = f"{path}[*]"
    properties = target.get("properties") if isinstance(target.get("properties"), dict) else None
    if properties:
        required_set = set(target.get("required") or [])
        for key, sub in properties.items():
            if isinstance(sub, dict):
                _describe_property(f"{prefix}.{key}", sub, required=key in required_set, rules=rules,
                                   unset=unset, depth=depth + 1)


def _tool_input_schema(capability: Mapping[str, Any], *, describe: bool = False,
                       limits: Mapping[str, Any] | None = None, external_sessions: bool = False,
                       operator_tools: bool = False) -> dict[str, Any]:
    schema = capability.get("input_schema")
    if not isinstance(schema, Mapping):
        schema = {"type": "object", "properties": {}}
    result = copy.deepcopy(dict(schema))
    result.setdefault("type", "object")
    properties = result.get("properties")
    if not isinstance(properties, dict):
        properties = {}
        result["properties"] = properties
    if describe:
        limits = limits or {}
        rules = limits.get("limits") if isinstance(limits.get("limits"), Mapping) else {}
        unset = {str(path) for path in limits.get("operator_required") or []}
        required = set(result.get("required") or [])
        for key, sub in properties.items():
            if isinstance(sub, dict) and key not in _CONTROL_PROPERTIES:
                _describe_property(str(key), sub, required=key in required, rules=rules, unset=unset)
    properties["session_id"] = {
        "type": "string",
        "description": (
            "Optional; leave it out: the connector opens, renews and closes MHS sessions itself."
            + (" Another session id is passed through." if external_sessions
               else " A session this connector did not open is refused (MHS.SESSION.UNKNOWN).")
        ),
    }
    properties["command_id"] = {
        "type": "string",
        "description": (
            "Optional idempotency key: reuse the same value to retry this exact call and the endpoint "
            "returns the first receipt instead of acting twice. Any string; a value that is not a ULID is "
            "mapped to a deterministic ULID for this tool."
        ),
    }
    properties["expected_revision"] = {
        "type": "integer",
        "minimum": 0,
        "x-mhs-unit": "1",
        "description": "Optional resource revision (a count, unit 1) the call expects; a different current "
                       "revision refuses the call without effect.",
    }
    properties["permit_id"] = {
        "type": "string",
        "description": "Optional permit id for a capability that requires approval"
                       + ("; mhs__permit issues one after the human approval." if operator_tools
                          else "; only the operator can issue one."),
    }
    properties["deadline_ms"] = {
        "type": "integer",
        "minimum": 1,
        "x-mhs-unit": "ms",
        "description": "Optional time to wait for the receipt. Unit: ms. It bounds the wait only; it never "
                       "cancels the command.",
    }
    return result


def _receipt_text(receipt: Mapping[str, Any]) -> str:
    status = receipt.get("status")
    capability_id = receipt.get("capability_id")
    revision = receipt.get("state_revision_after")
    summary = f"MHS {capability_id} {status} at revision {revision} (receipt {receipt.get('receipt_id')})"
    error = receipt.get("error")
    if isinstance(error, Mapping):
        summary += f"; {error.get('mhs_code')}: {error.get('message')}"
    operation_id = receipt.get("operation_id")
    if status in ("accepted", "running") and operation_id:
        summary += (f"; operation {operation_id} is still running: mhs__operations with operation_id "
                    f"{operation_id} (and wait_ms) returns the final receipt")
    elif status == "unknown":
        summary += ("; the outcome is not known yet: do not repeat the command before mhs__operations"
                    + (f" (operation_id {operation_id})" if operation_id else "") + " or mhs__read shows it")
    return summary + "\n" + json.dumps(receipt, sort_keys=True)


# ---------------------------------------------------------------------------
# stdio loop / CLI
# ---------------------------------------------------------------------------


def _make_client(args: argparse.Namespace, token: str | None = None) -> Any:
    from mhs import connect

    if args.command:
        return connect(shlex.split(args.command))
    if args.reference:
        argv = [sys.executable, "-m", "mhs.reference", args.reference, "--stdio", "--quiet"]
        if args.test_profile:
            argv.append("--test-profile")
        if args.noise:
            argv += ["--noise", "--seed", str(args.seed)]
        return connect(argv)
    if token:
        return connect(args.endpoint, token=token)
    return connect(args.endpoint)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mhs.mcp",
        description=f"MCP stdio projection of an MHS endpoint ({_ids.PROJECT_NAME} {_ids.SDK_VERSION}).",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--endpoint", help="HTTP endpoint URL, e.g. http://127.0.0.1:7400")
    target.add_argument("--command", help="stdio endpoint command line")
    target.add_argument("--reference", choices=("conveyor", "lab", "arm", "replay"), help="launch a built-in reference endpoint")
    parser.add_argument("--test-profile", action="store_true", help="reference endpoints: test-profile capabilities")
    parser.add_argument("--noise", action="store_true", help="arm reference endpoint: seeded noise")
    parser.add_argument("--seed", type=int, default=0, help="arm reference endpoint: seed")
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help=(
            "host policy / integration settings JSON (enabled, allow_hardware, operator_tools, "
            "allow_external_sessions). Omit only for an explicit diagnostic launch; the projection is then "
            "enabled and every other flag is false."
        ),
    )
    parser.add_argument("--operator-tools", action="store_true",
                        help="list mhs__reset and mhs__permit (only for a connector a human operator drives)")
    parser.add_argument("--allow-external-sessions", action="store_true",
                        help="accept a session_id this projection did not open")
    parser.add_argument("--token-file", default=None, metavar="PATH",
                        help="file holding the bearer token for --endpoint (the endpoint binds the principal to it)")
    return parser


def serve_stdio(projection: MCPProjection, *, stdin: Any = None, stdout: Any = None) -> int:
    """Serve ``projection`` over newline-delimited JSON-RPC.

    The reader thread answers ``ping`` and ``mhs__estop`` itself and hands
    ``notifications/cancelled`` to a short-lived thread, so neither waits
    behind a ``tools/call`` in flight; every other message is served in order
    by one worker.  At end of input the queued requests are finished first.
    """
    input_stream = stdin if stdin is not None else sys.stdin.buffer
    output_stream = stdout if stdout is not None else sys.stdout.buffer
    write_lock = threading.Lock()

    def write(message: Mapping[str, Any]) -> None:
        data = json.dumps(message, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
        result = message.get("result")
        limit = MAX_FRAME_BYTES
        if isinstance(result, _ArtifactResourceResult):
            limit = min(MAX_ARTIFACT_RESPONSE_BYTES, max(MAX_FRAME_BYTES, result.frame_limit))
        if len(data) > limit:
            data = json.dumps(_error(message.get("id"), -32603, "response exceeds MCP frame limit")).encode() + b"\n"
        with write_lock:
            output_stream.write(data)
            output_stream.flush()

    def respond(message: Any) -> None:
        try:
            response = projection.handle_message(message)
        except Exception as exc:  # noqa: BLE001 - last-resort guard
            sys.stderr.write(f"[mhs.mcp] unhandled error: {exc}\n{traceback.format_exc()}\n")
            response = _error(
                message.get("id") if isinstance(message, Mapping) else None, -32603, "internal error"
            )
        for notification in projection.drain_notifications():
            write(notification)
        if response is not None:
            write(response)

    work: "queue.Queue[Any]" = queue.Queue()
    stop = object()

    def worker() -> None:
        while True:
            item = work.get()
            if item is stop:
                return
            respond(item)

    thread = threading.Thread(target=worker, name="mhs-mcp-worker", daemon=True)
    thread.start()
    try:
        while True:
            raw = input_stream.readline(MAX_FRAME_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_FRAME_BYTES:
                while raw and not raw.endswith(b"\n"):  # discard the rest of the oversized line
                    raw = input_stream.readline(MAX_FRAME_BYTES + 1)
                write(_error(None, -32700, "JSON-RPC frame exceeds 4 MiB"))
                continue
            line = raw.strip()
            if not line:
                continue
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                write(_error(None, -32700, "Parse error"))
                continue
            lane = projection.priority(message)
            if lane == "inline":
                respond(message)
            elif lane == "thread":
                threading.Thread(target=respond, args=(message,), name="mhs-mcp-cancel", daemon=True).start()
            else:
                work.put(message)
    finally:
        work.put(stop)
        thread.join()
        projection.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy = MCPPolicy.load(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[mhs.mcp] cannot load host policy {args.config!r}: {exc}\n")
        return 2
    policy.operator_tools = policy.operator_tools or bool(args.operator_tools)
    policy.allow_external_sessions = policy.allow_external_sessions or bool(args.allow_external_sessions)
    token = None
    if args.token_file:
        try:
            token = Path(args.token_file).expanduser().read_text(encoding="utf-8").strip()
        except OSError as exc:
            sys.stderr.write(f"[mhs.mcp] cannot read --token-file {args.token_file!r}: {exc}\n")
            return 2
        if not token:
            sys.stderr.write(f"[mhs.mcp] --token-file {args.token_file!r} is empty\n")
            return 2
    try:
        client = _make_client(args, token)
    except Exception as exc:  # noqa: BLE001 - connecting failed before the MCP handshake
        sys.stderr.write(f"[mhs.mcp] cannot connect to MHS endpoint: {exc}\n")
        return 1
    projection = MCPProjection(client, endpoint=args.endpoint or args.reference, policy=policy,
                               describe_inputs=True)
    return serve_stdio(projection)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
