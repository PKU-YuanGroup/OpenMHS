"""MHS endpoint runtime: sessions, commands, safety, receipts and evidence.

The server implements the contract plane of MHS-000 §5 and §6: it owns sessions,
grants, revisions, idempotency, safety-envelope enforcement, permits, receipts,
operations, subscriptions and the hash-chained evidence log.  A *bridge* owns
only the device-specific translation and state; it never advances a revision and
never makes a receipt (see :class:`mhs.bridge.base.Bridge`).

Deliberate simplifications for the reference implementation, each documented in
the spec as a permitted implementation choice:

* receipts, the idempotency store and the e-stop latch are kept in memory
  unless ``MHSServer(state_dir=...)`` names a directory, which then holds the
  evidence chain, the latch file and the idempotency journal across restarts
  (:mod:`mhs._server.state`); sessions, permits and operations never survive
  a restart (the safe direction: a restarted endpoint grants nothing);
* every command runs as a registered operation in its own worker; the caller
  waits for it at most until its deadline;
* HTTP serving uses ``http.server`` in threads (Host/Origin allowlist, exact
  ``Content-Type``, optional bearer tokens, session-scoped SSE); stdio uses one
  reader thread that handles e-stops itself, cancellations on a priority
  thread and everything else on one FIFO lane per device, plus a write lock so
  notifications can be emitted from operation workers.

``MHSServer(strict=True)`` / ``Device(strict=True)`` resolve every binding
against the capability catalogue and enable the strict-only runtime rules
(:mod:`mhs._server.strict`); the 0.9 default (``strict=None``) is a
compatibility mode that reports the same findings as :class:`MHSStrictWarning`.

Nothing here is a safety-rated channel.  The endpoint enforces the declared
envelope; it cannot replace a hardware emergency stop (MHS-000 §6.3).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
from contextlib import ExitStack
import copy
import hmac
import inspect
import ipaddress
import json
import logging
import math
import os
import re
import secrets
import select
import socket
import sys
import threading
import time
import traceback
import warnings
import weakref
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse

from . import _ids, canonical, protocol
from . import catalog as _catalog
from . import limits as _limits
from . import reference_file as _reference_file
from ._server import limits_plan as _limits_plan
from ._server import state as _state
from ._server import strict as _strict
from ._server.state import StateDirError
from ._server.strict import MHSStrictError, MHSStrictWarning
from .errors import MHSError
from .evidence import EvidenceLog
from .protocol import Method
from .schema import resolve_pointer as _resolve_pointer
from .schema import validate as schema_validate
from . import signals as _signals
from .signals import Cancelled as _Cancelled
from .bridge import simulation_timing as _sim_timing
from . import artifacts as _artifacts

MHS_VERSION = protocol.MHS_VERSION
SERVER_NAME = "mhs-reference-server"
SERVER_VERSION = _ids.SDK_VERSION

_log = logging.getLogger("mhs.server")

_RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
_CAPABILITY_ID_RE = re.compile(r"^(?:cap|x-cap)\.[a-z0-9_.-]+\.v[0-9]+$")

#: Methods that carry a required ``deadline_ms`` (MHS-002 §3 flag **D**).
_BLOCKING_METHODS = frozenset(
    {
        "mhs.resource.read",
        "mhs.resource.write",
        "mhs.command",
        "mhs.operations.get",
        "mhs.operations.cancel",
        "mhs.subscribe",
        "mhs.snapshot",
        "mhs.restore",
        "mhs.safety.status",
        "mhs.safety.estop",
        "mhs.safety.reset",
    }
)

#: Maximum command deadline accepted by this endpoint (matches hello limits).
_MAX_DEADLINE_MS = 600_000

#: Blocking methods that already manage their own bounded operation.  The
#: e-stop bounds only its native stop path: the latch is set before any bridge
#: I/O and the caller always gets a receipt (SAFE-040).
_SELF_BOUNDED_METHODS = frozenset(
    {"mhs.command", "mhs.operations.cancel", "mhs.safety.estop"}
)
#: Blocking methods that can have a physical/state effect if they time out.
_BOUNDED_MUTATING_METHODS = frozenset(
    {"mhs.restore", "mhs.safety.reset", "mhs.resource.write"}
)
#: Methods with an effect whose outcome only a response can report (PROTO-005).
#: Sent as a JSON-RPC notification they are dropped and logged, never run.  An
#: e-stop (also ``mhs.command`` on ``cap.motion.estop.v1``) is still engaged:
#: dropping a stop is never the safe direction.
_EFFECTFUL_METHODS = frozenset(
    {
        "mhs.command",
        "mhs.resource.write",
        "mhs.restore",
        "mhs.safety.reset",
        "mhs.safety.permit",
        "mhs.composition.run",
    }
)

#: Default receipt retention (EVID-018: at least 30 days).  Advertised in
#: ``hello.limits``; nothing is pruned: in memory receipts last until the
#: process exits, under ``MHSServer(state_dir=...)`` they outlive it.
_DEFAULT_RECEIPT_RETENTION_S = 30 * 86_400

#: HTTP: hosts that are always accepted in the ``Host`` header and as the
#: origin of a same-origin request.  Others must be configured
#: (``MHSServer(allowed_hosts=...)``).
_LOOPBACK_HOST_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
#: HTTP: socket timeout of every connection (seconds); a stalled client is
#: disconnected instead of holding a handler thread for ever.
_HTTP_TIMEOUT_S = 30.0
#: HTTP: concurrent SSE streams one principal may hold (429 beyond).
_MAX_SSE_STREAMS_PER_PRINCIPAL = 4
#: HTTP: SSE keepalive comment period (TPT-016: 15-30 s).
_SSE_KEEPALIVE_S = 15.0

#: Upper bound on one wait of the session-expiry timer (seconds).
_REAPER_MAX_WAIT_S = 1.0

#: Capability classes that stop motion.  Like every ``safe_state.achieved_by``
#: action they are always callable: exempt from the e-stop latch, permits,
#: cumulative budgets and the exclusive device lease (SAFE-029/040).
_STOP_CLASSES = frozenset({"cap.motion.stop.v1", "cap.motion.estop.v1"})
#: ``concurrency`` values, weakest first (ADPT-025: a binding may only be as strict or stricter than its class).
_CONCURRENCY_RANK = {"shared": 0, "serialized": 1, "exclusive": 2}
#: The catalogue e-stop class; ``mhs.command`` routes it to the e-stop latch.
_MOTION_ESTOP = "cap.motion.estop.v1"
#: The write primitive: ``mhs.resource.write`` is a command of this class's
#: binding on the target resource (plan 3.2; its receipts carry this id).
_CONFIGURE = _catalog.CONFIGURE_CLASS
#: Strict-mode finding rules the runtime enforces in compatibility mode too.
_ENFORCED_IN_BOTH_MODES = frozenset({"operator-required-unset"})
#: Native e-stop budget when ``safety.estop.latency_ms`` is not declared.
_DEFAULT_ESTOP_BUDGET_MS = 1000
#: ``_receipt(resource_state=...)``: no state was read yet (read it to hash it).
_NO_STATE = object()
#: Background retry back-off for an unconfirmed e-stop (seconds).
_ESTOP_RETRY_INITIAL_S = 0.25
_ESTOP_RETRY_MAX_S = 5.0
#: Upper bound on the state read that hashes an e-stop receipt (seconds); it
#: is also never allowed past the caller's deadline.
_ESTOP_READ_BOUND_S = 0.1
#: Upper bound on each device-state read the revision rule makes around a
#: command (seconds; plan 3.7).  A read that has not answered by then is an
#: unknown change -- the revision advances -- and never holds the command.
#: The read before the native call also takes at most half of what is left of
#: the caller's budget.
_REVISION_READ_BOUND_S = 1.0
#: Execution bound of a ``long_running`` binding that declares no
#: ``max_duration_ms`` and whose class declares none either (plan 3.7): the
#: longest command deadline.  Strict mode refuses such a binding.
_LONG_RUNNING_DEFAULT_MAX_MS = _MAX_DEADLINE_MS
#: How long the execution-bound timer waits for a cancellable operation to
#: acknowledge its cancellation before it records ``unknown`` (seconds).
_MAX_DURATION_GRACE_S = 0.25
#: Upper bound on the state read of a receipt written because the response
#: deadline passed (seconds): the answer never waits for a slow device.
_DEADLINE_RECEIPT_READ_BOUND_S = 0.1
#: How long the response path waits for a worker that is already recording
#: the final receipt (its state read is bounded by _REVISION_READ_BOUND_S).
_FINAL_RECEIPT_WAIT_S = _REVISION_READ_BOUND_S + 0.5
#: How long a worker waits for a claimed ``unknown`` receipt to be recorded
#: before its final receipt (that receipt's state read is bounded too).
_UNKNOWN_RECORD_WAIT_S = 2.0

#: Monotonic time at which the endpoint received the request being handled
#: (self-bounded methods only): ``deadline_ms`` counts from there (PROTO-011).
_REQUEST_INGRESS: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "mhs_request_ingress", default=None
)

#: The principal a transport authenticated for the request being handled (a
#: bearer token of ``MHSServer(auth_tokens=...)``), or None.  Set by
#: :meth:`MHSServer._handle_message` and copied into the bounded-dispatch
#: worker, so every handler sees the caller it serves.
_REQUEST_PRINCIPAL: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "mhs_request_principal", default=None
)

#: Supported cumulative-limit windows (SAFE-016) -> seconds.
_CUMULATIVE_WINDOWS = {
    "rolling_1h": 3600.0,
    "rolling_24h": 86400.0,
    "rolling_7d": 604800.0,
    "session": None,  # session-independent within endpoint retention
}


def action_digest(capability_id: str, resource: str | None, payload: dict[str, Any]) -> str:
    """The one action digest used by receipts, permits and idempotency (PROTO-036)."""
    return canonical.digest(
        {"capability_id": str(capability_id), "resource": resource, "input": payload or {}}
    )


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SafetyEnvelope:
    """Declared safety envelope for one device (manifest ``safety`` object).

    ``envelope`` maps a capability id or pattern (``cap.<class>.*``) to a limit
    map ``{limit path: rule | "operator_required"}``.  The runtime never merges
    these maps itself: :mod:`mhs.limits` intersects them with the class and
    binding limits and the operator overlay (``MHSServer(site_limits=...)``).
    """

    risk_class: str = "R0"
    envelope: dict[str, Any] = field(default_factory=dict)
    interlocks: list[dict[str, Any]] = field(default_factory=list)
    requires_permit: list[str] = field(default_factory=list)
    estop: dict[str, Any] = field(default_factory=lambda: {"kind": "software", "latching": True})
    safe_state: dict[str, Any] = field(
        default_factory=lambda: {"description": "no declared safe state", "achieved_by": []}
    )
    max_cumulative: dict[str, Any] = field(default_factory=dict)

    def permits_required_for(self, capability_id: str) -> bool:
        for pattern in self.requires_permit or []:
            if _pattern_matches(str(pattern), capability_id):
                return True
        return False

    def required_interlocks_for(self, capability_id: str) -> list[dict[str, Any]]:
        required = []
        for entry in self.interlocks or []:
            wanted = entry.get("required_for") or []
            if not wanted:
                continue
            for pattern in wanted:
                if _pattern_matches(str(pattern), capability_id):
                    required.append(entry)
                    break
        return required


@dataclass
class Resource:
    """A stateful thing inside a device."""

    resource_id: str
    kind: str = "generic"
    title: str | None = None
    state_schema: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    revision: int = 0
    sampling: dict[str, Any] | None = None
    hash_exclusions: list[str] | None = None

    def manifest(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "state_schema": self.state_schema or {"type": "object"},
        }
        if self.title:
            out["title"] = self.title
        if self.state is not None:
            out["state"] = self.state
        out["revision"] = self.revision
        if self.sampling:
            out["sampling"] = self.sampling
        if self.hash_exclusions:
            out["hash_exclusions"] = self.hash_exclusions
        return out


@dataclass
class Capability:
    """One capability bound to one resource of one device.

    ``verb`` may be omitted: compatibility mode then uses ``invoke`` (as
    before 0.9) and strict mode the class verb from the catalogue.  A declared
    verb that differs from the class verb is drift (strict mode refuses it).
    """

    capability_id: str
    resource: str
    title: str | None = None
    verb: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    semantics: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None
    limits: dict[str, Any] | None = None
    determinism: str | None = None
    exclusive: bool = False
    requires_permit: bool = False
    native: str | None = None

    def __post_init__(self) -> None:
        #: The verb the binding declared; None means "take it from the class"
        #: (strict mode) or ``invoke`` (compatibility mode).
        self.declared_verb: str | None = self.verb or None
        self.verb = self.verb or "invoke"
        #: Set by strict mode: the manifest then states the (class) verb.
        self.publish_verb = False

    @property
    def cancellable(self) -> bool:
        return bool((self.constraints or {}).get("cancellable", False))

    @property
    def long_running(self) -> bool:
        """``constraints.long_running`` of the binding (the runtime also honours the class flag)."""
        return (self.constraints or {}).get("long_running") is True

    def published_constraints(self, concurrency: str | None = None) -> dict[str, Any]:
        """``constraints`` as published: the declared ones, with ``concurrency`` set to what the runtime applies.

        ``concurrency`` is the effective value on a hardware or hybrid device
        (:meth:`MHSServer._effective_concurrency`); without it an ``exclusive``
        binding says ``exclusive`` and nothing else is invented.  Before
        RESIDUAL-B a binding without constraints published
        ``{"concurrency": "shared"}``: wrong on hardware, where it takes the
        device lock, and -- read back from the manifest -- the very value that
        opts a binding out of that lock.
        """
        out = dict(self.constraints or {})
        if concurrency is not None:
            out["concurrency"] = concurrency
        elif self.exclusive:
            out["concurrency"] = "exclusive"
        return out

    def manifest(self, *, concurrency: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "capability_id": self.capability_id,
            "resource": self.resource,
            "input_schema": self.input_schema or {"type": "object", "properties": {}},
            "output_schema": self.output_schema or {"type": "object"},
            "constraints": self.published_constraints(concurrency),
        }
        if getattr(self, "publish_verb", False) and self.verb in ("read", "write", "invoke"):
            out["verb"] = self.verb
        if self.title:
            out["title"] = self.title
        if self.semantics:
            out["semantics"] = self.semantics
        if self.limits:
            out["limits"] = self.limits
        if self.determinism:
            out["determinism"] = self.determinism
        if self.exclusive:
            out["exclusive"] = True
        if self.requires_permit:
            out["requires_permit"] = True
        if self.native:
            out["native"] = self.native
        return out


@dataclass
class Device:
    """A logical machine exposed by an endpoint.

    ``strict`` (default None: compatibility mode in 0.9; see
    :mod:`mhs._server.strict`): with ``strict=True`` the device is resolved
    against the capability catalogue at construction and refused with
    :class:`MHSStrictError` on any finding; it then serves the class verb and
    the binding ∩ class schemas.  A device is strict when either it or its
    :class:`MHSServer` says ``strict=True``.
    """

    device_id: str
    display_name: str | None = None
    mode: str = "simulated"
    resources: list[Resource] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    safety: SafetyEnvelope = field(default_factory=SafetyEnvelope)
    fidelity: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    instance_id: str | None = None
    models: list[str] | None = None
    vendor: dict[str, Any] | None = None
    model: str | None = None
    firmware: str | None = None
    serial: str | None = None
    conformance: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    signatures: list[dict[str, Any]] | None = None
    bridge: Any = None
    strict: bool | None = None

    def __post_init__(self) -> None:
        self.resources = [r if isinstance(r, Resource) else Resource(**r) for r in self.resources]
        self.capabilities = [
            c if isinstance(c, Capability) else Capability(**c) for c in self.capabilities
        ]
        if isinstance(self.safety, Mapping):
            self.safety = SafetyEnvelope(**self.safety)
        if not self.instance_id:
            self.instance_id = canonical.ulid()
        # Bindings are keyed by (capability_id, resource) (plan 3.6 step 3):
        # one class may be bound to several resources (two pipettes, two
        # grippers), each with its own schema, limits and grants.  The same
        # pair twice is refused in every mode -- only one of them could ever
        # be served, so the other's schema and limits would be silently lost.
        by_binding, duplicates = self._index_bindings()
        if duplicates:
            raise MHSStrictError(self.duplicate_findings(duplicates))
        self._binding_index = by_binding
        self._duplicate_bindings: tuple[tuple[str, str], ...] = ()
        self._indexed: tuple[Capability, ...] = tuple(self.capabilities)
        #: Legacy single-binding view (capability id -> its first binding),
        #: rebuilt with :attr:`_by_binding`.  The runtime never decides with it:
        #: it resolves bindings with :meth:`binding` / :meth:`bindings_of` /
        #: :attr:`_by_binding`, which follow :attr:`capabilities` as it is now.
        self._by_capability: dict[str, Capability] = self._first_bindings(by_binding)
        self._by_resource = {r.resource_id: r for r in self.resources}
        #: The strict resolution, once this device was checked and applied in
        #: strict mode (here or by the server).
        self._strict_resolution: "_strict.DeviceResolution | None" = None
        if self.strict is True:
            resolution = _strict.resolve_device(self)
            if resolution.refused:
                raise MHSStrictError(resolution.refused)
            _strict.apply_strict(self, resolution)
            self._strict_resolution = resolution

    # -- lookups -------------------------------------------------------
    def _index_bindings(self) -> tuple[dict[tuple[str, str], Capability], list[tuple[str, str]]]:
        """``(capability_id, resource)`` -> binding (the first wins), and the pairs bound more than once."""
        index: dict[tuple[str, str], Capability] = {}
        duplicates: list[tuple[str, str]] = []
        for capability in self.capabilities:
            key = (capability.capability_id, capability.resource)
            if key in index:
                if key not in duplicates:
                    duplicates.append(key)
                continue
            index[key] = capability
        return index, duplicates

    @staticmethod
    def _first_bindings(index: Mapping[tuple[str, str], Capability]) -> dict[str, Capability]:
        """Capability id -> its first binding (the legacy :attr:`_by_capability` view)."""
        first: dict[str, Capability] = {}
        for (capability_id, _resource), capability in index.items():
            first.setdefault(capability_id, capability)
        return first

    def duplicate_findings(self, duplicates: Sequence[tuple[str, str]] | None = None) -> list["_strict.Finding"]:
        """One ``capability-duplicate`` finding per pair bound more than once (default: now)."""
        pairs = self._index_bindings()[1] if duplicates is None else list(duplicates)
        return [_strict.Finding(
            "capability-duplicate", "MHS.ADAPTER.MANIFEST_INVALID", str(self.device_id),
            f"is bound to resource {resource!r} more than once; a binding is identified by "
            "(capability_id, resource)", capability_id=capability_id, path=f"capabilities[{resource}]")
            for capability_id, resource in pairs]

    @property
    def _by_binding(self) -> dict[tuple[str, str], Capability]:
        """The bindings by ``(capability_id, resource)``, re-indexed when :attr:`capabilities` changed.

        A binding replaced, added or removed after construction is the one
        served (its own schema and limits, never a stale object's); the legacy
        :attr:`_by_capability` view is rebuilt with it.  A pair
        bound twice after construction keeps its first binding here and is
        listed in :attr:`_duplicate_bindings`; the server then refuses the
        device's commands, stops excepted (``MHS.ADAPTER.MANIFEST_INVALID``,
        ``capability-duplicate``).
        """
        current = self.capabilities
        indexed = self._indexed
        if len(current) != len(indexed) or any(a is not b for a, b in zip(current, indexed)):
            index, duplicates = self._index_bindings()
            self._binding_index, self._duplicate_bindings = index, tuple(duplicates)
            self._by_capability = self._first_bindings(index)
            self._indexed = tuple(current)
        return self._binding_index

    def duplicate_pairs(self) -> tuple[tuple[str, str], ...]:
        """The ``(capability_id, resource)`` pairs bound more than once now (empty after construction)."""
        self._by_binding  # noqa: B018 - re-index when the bindings changed
        return self._duplicate_bindings

    def bindings_of(self, capability_id: str) -> list[Capability]:
        """Every binding of ``capability_id``, in declaration order."""
        return [cap for (cid, _resource), cap in self._by_binding.items() if cid == capability_id]

    def binding(self, capability_id: str, resource: str | None = None) -> Capability:
        """The binding ``(capability_id, resource)``; ``resource`` may be omitted when it is unique.

        Raises ``MHS.CAPABILITY.UNKNOWN`` when the device binds no such class,
        ``MHS.PROTOCOL.INVALID_PARAMS`` (``details.reason: "resource_required"``)
        when ``resource`` is omitted and the class is bound to several
        resources, and ``MHS.CAPABILITY.NOT_BOUND`` when it is not bound to
        ``resource`` (also a resource the device does not have).
        """
        bindings = self.bindings_of(capability_id)
        if not bindings:
            raise MHSError(
                "MHS.CAPABILITY.UNKNOWN",
                f"device does not expose capability {capability_id!r}",
                {"device_id": self.device_id, "capability_id": capability_id, "retryable": False},
            )
        resources = [cap.resource for cap in bindings]
        if resource is None:
            if len(bindings) == 1:
                return bindings[0]
            data: dict[str, Any] = {
                "retryable": False,
                "details": {"reason": "resource_required", "device_id": self.device_id,
                            "capability_id": capability_id, "resources": resources}}
            if capability_id in _STOP_CLASSES:
                data["remediation"] = ("Send one command per resource, or mhs.safety.estop, which stops "
                                       "every binding of the device.")
            raise MHSError(
                "MHS.PROTOCOL.INVALID_PARAMS",
                f"{capability_id} is bound to several resources ({', '.join(resources)}); name one in 'resource'",
                data,
            )
        found = self._by_binding.get((capability_id, str(resource)))
        if found is None:
            raise MHSError(
                "MHS.CAPABILITY.NOT_BOUND",
                f"{capability_id} is not bound to resource {resource!r} of this device "
                f"(bound: {', '.join(resources)})",
                {"retryable": False,
                 "details": {"device_id": self.device_id, "capability_id": capability_id,
                             "resource": resource, "bound_resources": resources,
                             "resource_exists": str(resource) in self._by_resource}},
            )
        return found

    def capability(self, capability_id: str, resource: str | None = None) -> Capability:
        """:meth:`binding`; kept for callers written before bindings were keyed by resource."""
        return self.binding(capability_id, resource)

    def resource(self, resource_id: str) -> Resource:
        res = self._by_resource.get(resource_id)
        if res is None:
            raise MHSError(
                "MHS.RESOURCE.UNKNOWN",
                f"device has no resource {resource_id!r}",
                {"device_id": self.device_id, "resource_id": resource_id},
            )
        return res

    @property
    def primary_resource(self) -> Resource:
        return self.resources[0]

    # -- manifest ------------------------------------------------------
    def manifest(self, *, include_state: bool = True,
                 concurrency: Callable[["Capability"], str | None] | None = None) -> dict[str, Any]:
        """The device manifest; ``concurrency`` gives each binding's effective concurrency (the server's rule)."""
        out: dict[str, Any] = {
            "mhs_version": MHS_VERSION,
            "device_id": self.device_id,
            "instance_id": self.instance_id or canonical.ulid(),
            "display_name": self.display_name or self.device_id,
            "mode": self.mode,
            "resources": [
                r.manifest() if include_state else _resource_manifest_without_state(r)
                for r in self.resources
            ],
            "capabilities": [c.manifest(concurrency=concurrency(c) if concurrency is not None else None)
                             for c in self.capabilities],
            "safety": self.safety_object(),
        }
        if self.models:
            out["models"] = list(self.models)
        if self.vendor:
            out["vendor"] = dict(self.vendor)
        if self.model:
            out["model"] = self.model
        if self.firmware:
            out["firmware"] = self.firmware
        if self.serial:
            out["serial"] = self.serial
        if self.profile:
            out["profile"] = dict(self.profile)
        if self.fidelity:
            out["fidelity"] = dict(self.fidelity)
        if self.conformance:
            out["conformance"] = dict(self.conformance)
        if self.provenance:
            out["provenance"] = dict(self.provenance)
        if self.signatures:
            out["signatures"] = list(self.signatures)
        return out

    def safety_object(self) -> dict[str, Any]:
        safety: dict[str, Any] = {
            "risk_class": self.safety.risk_class,
            "interlocks": list(self.safety.interlocks or []),
            "estop": dict(self.safety.estop or {"kind": "software", "latching": True}),
            "safe_state": dict(
                self.safety.safe_state
                or {"description": "no declared safe state", "achieved_by": []}
            ),
        }
        if self.safety.envelope:
            safety["envelope"] = dict(self.safety.envelope)
        if self.safety.requires_permit:
            safety["requires_permit"] = list(self.safety.requires_permit)
        if self.safety.max_cumulative:
            safety["max_cumulative"] = dict(self.safety.max_cumulative)
        return safety

    def summary(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "instance_id": self.instance_id,
            "display_name": self.display_name or self.device_id,
            "mode": self.mode,
            "risk_class": self.safety.risk_class,
            "capabilities": [
                {
                    "capability_id": c.capability_id,
                    "title": c.title,
                    "resource": c.resource,
                    "verb": c.verb,
                    "requires_permit": bool(c.requires_permit),
                    "determinism": c.determinism,
                    "exclusive": bool(c.exclusive),
                }
                for c in self.capabilities
            ],
            "capability_ids": [c.capability_id for c in self.capabilities],
            "resources": [r.resource_id for r in self.resources],
            "fidelity": _fidelity_summary(self.fidelity),
            "profile": self.profile,
        }


def _resource_manifest_without_state(res: Resource) -> dict[str, Any]:
    out: dict[str, Any] = {
        "resource_id": res.resource_id,
        "kind": res.kind,
        "state_schema": res.state_schema or {"type": "object"},
        "revision": res.revision,
    }
    if res.title:
        out["title"] = res.title
    if res.sampling:
        out["sampling"] = res.sampling
    if res.hash_exclusions:
        out["hash_exclusions"] = res.hash_exclusions
    return out


def _fidelity_summary(fidelity: dict[str, Any] | None) -> dict[str, Any] | None:
    if not fidelity:
        return None
    summary = dict(fidelity)
    determinism = summary.get("determinism")
    if not isinstance(determinism, Mapping):
        summary["determinism"] = {"kind": str(determinism or "none")}
    summary["gaps"] = list(summary.get("gaps") or [])
    return summary


# ---------------------------------------------------------------------------
# Session, permit, operation records
# ---------------------------------------------------------------------------


@dataclass
class Session:
    session_id: str
    principal: dict[str, Any]
    device_ids: list[str]
    mode: str
    granted: dict[str, list[str]]
    ttl_s: int
    created_at: float
    expires_at: float
    approvals: list[dict[str, Any]] = field(default_factory=list)
    #: True once the endpoint released the session's operations, permits and
    #: subscriptions (expiry timer or close); the record may stay so a later
    #: call still gets ``MHS.SESSION.EXPIRED``.
    released: bool = False
    #: The kind the endpoint authorizes the session as: ``operator``,
    #: ``human``, ``agent`` or ``service`` (``principal`` is its wire form,
    #: where an operator is ``kind: "human"`` with ``x-meta.role``).  None:
    #: the principal's own kind.
    authority: str | None = None
    #: True when the principal comes from a bearer token (``auth_tokens``);
    #: such a session is usable only by requests with the same principal.
    authenticated: bool = False
    #: device_id -> capability_id -> the granted resources (plan 3.6 step 2:
    #: a grant is a binding, ``(capability_id, resource)``).  None: the
    #: capability grants of ``granted`` cover every resource they are bound to.
    granted_resources: dict[str, dict[str, list[str]]] | None = None

    @property
    def kind(self) -> str:
        """The kind the session is authorized as (see ``authority``)."""
        return str(self.authority or (self.principal or {}).get("kind") or "agent")

    def expired(self, now: float | None = None) -> bool:
        return (now or time.time()) > self.expires_at

    def allows(self, device_id: str, capability_id: str, resource: str | None = None) -> bool:
        """True when the session is granted ``capability_id`` (on ``resource``, when named)."""
        if capability_id not in self.granted.get(device_id, []):
            return False
        if resource is None or self.granted_resources is None:
            return True
        return resource in (self.granted_resources.get(device_id) or {}).get(capability_id, [])


@dataclass
class Permit:
    permit_id: str
    capability_id: str
    input_digest: str
    principal: str
    approvals: list[dict[str, Any]]
    expires_at: float
    used: bool = False
    session_id: str | None = None
    device_id: str | None = None
    resource: str | None = None


@dataclass
class Operation:
    operation_id: str
    device_id: str
    capability_id: str
    command_id: str
    session_id: str
    receipt: dict[str, Any]
    cancel_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    state: str = "running"
    final_receipt: dict[str, Any] | None = None
    cancel_reason: str | None = None
    #: Set by the worker once ``final_receipt`` is recorded (or it gave up).
    done: threading.Event = field(default_factory=threading.Event)
    #: ``(principal id, authorized kind, authenticated)`` of the session that
    #: started it (strict mode: only sessions with the same triple may get or
    #: cancel it, so a self-declared namesake of a token principal cannot).
    owner: tuple[str, str, bool] | None = None
    #: The resource of the binding it runs (bindings are keyed by
    #: ``(capability_id, resource)``).
    resource: str | None = None
    #: The binding is ``long_running`` (plan 3.7): past the response deadline
    #: its caller got a ``running`` receipt, never ``unknown``.
    long_running: bool = False
    #: Explicit cancellation authority of the admitted binding. Capture it
    #: once: another resource or later metadata must not grant cancellation.
    cancellable: bool = False
    #: Serialises the receipt written when the response deadline (or the
    #: execution bound) passed with the worker's final receipt, so a command
    #: has exactly one final receipt and an ``unknown`` one always precedes it.
    outcome_lock: threading.Lock = field(default_factory=threading.Lock)
    #: An ``unknown`` receipt was claimed for it (deadline or execution bound).
    unknown_claimed: bool = False
    #: Set once the claimed ``unknown`` receipt is recorded (or recording failed).
    unknown_recorded: threading.Event = field(default_factory=threading.Event)
    #: The recorded ``unknown`` receipt; the final receipt reconciles it.
    unknown_receipt: dict[str, Any] | None = None
    #: The worker is recording the final receipt (no ``unknown`` may follow).
    finishing: bool = False
    #: Timer of the execution bound (``max_duration_ms``), once the caller was answered.
    bound_timer: threading.Timer | None = None
    simulation_timing: _sim_timing.SimulationTimingReport | None = None


class _EstopAttempt:
    """One run of a device's stop path: native e-stop, then every safe-state action.

    The safe-state actions do not wait past the e-stop budget for a native
    stop that hangs (:meth:`MHSServer._run_estop_attempt`).
    Filled in by a daemon worker; ``done`` is set when the worker has finished,
    however long the native call took.  ``ok`` is true only when every step that
    ran succeeded and the device has a stop path (SAFE-040: a stop that cannot be
    confirmed is reported as SAFE_STATE_UNREACHED).
    """

    __slots__ = ("done", "ok", "native", "native_error", "failed_actions", "shared_stops", "bridge_safe_state",
                 "reason", "started", "ended", "thread", "awaiting", "resent", "sensed")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.ok = False
        #: "engaged" (native stop returned), "software_only" (no native stop),
        #: "failed" (native stop raised) or "pending" (still running).
        self.native = "pending"
        self.native_error: dict[str, Any] | None = None
        self.failed_actions: list[dict[str, Any]] = []
        #: safe-state actions the bridge answered from the identical upstream stop request this e-stop already sent
        #: and saw confirmed (``{capability_id, same_request_as}``; ``"native"`` or the action that sent it)
        self.shared_stops: list[dict[str, Any]] = []
        #: the bridge's own ``safety_status().safe_state.achieved`` (None when unknown)
        self.bridge_safe_state: bool | None = None
        #: why ``ok`` is false: native_failed, action_failed, no_stop_path, bridge_reports_unsafe
        self.reason: str | None = None
        self.started = time.monotonic()
        self.ended: float | None = None
        self.thread: threading.Thread | None = None
        #: on a device that declares a re-enable, the operation ids of the commands
        #: that were in flight when the attempt started (CORE-086): the attempt is
        #: done only once they have settled and the stop path ran again after them.
        self.awaiting: list[str] = []
        #: the stop path ran again after the commands in flight settled
        self.resent = False
        #: the SDK ROS bridge's report of a sensed-confirmation stop (SAFE-049, CORE-088), or None
        self.sensed: dict[str, Any] | None = None


class _StateRead:
    """One read of every resource of a device for the revision rule (plan 3.7).

    Filled in by a daemon worker (:meth:`MHSServer._start_state_read`);
    ``done`` is set when it returned, however long the bridge took.
    ``fallback`` is the declared state of each resource (the receipt's
    ``state_hash_after`` fallback, never compared).
    """

    __slots__ = ("done", "fallback", "states", "complete", "thread")

    def __init__(self, fallback: dict[str, Any]) -> None:
        self.done = threading.Event()
        self.fallback = fallback
        #: resource id -> the state read (None until the read returned)
        self.states: dict[str, Any] | None = None
        #: every resource was read without an error
        self.complete = False
        self.thread: threading.Thread | None = None


class _Context:
    """What a bridge is allowed to know about one call.

    ``extra["deadline_at"]`` is the call's monotonic deadline (seconds, the
    clock of :func:`time.monotonic`), so :meth:`remaining_ms` here and in
    :class:`mhs.bridge.base.BridgeContext` report the budget that is really
    left, not the full ``deadline_ms``.
    """

    __slots__ = (
        "command_id",
        "session_id",
        "device_id",
        "resource",
        "operation_id",
        "deadline_ms",
        "expected_revision",
        "permit_id",
        "revision",
        "mode",
        "cancel_event",
        "extra",
    )

    def __init__(self, **kwargs: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, kwargs.get(name))
        self.extra = dict(kwargs.get("extra") or {})
        if self.extra.get("deadline_at") is None and self.deadline_ms:
            self.extra["deadline_at"] = time.monotonic() + int(self.deadline_ms) / 1000.0

    def cancelled(self) -> bool:
        event = self.cancel_event
        if event is None:
            return False
        is_set = getattr(event, "is_set", None)
        return bool(is_set()) if callable(is_set) else bool(event)

    def remaining_ms(self) -> int:
        deadline_at = self.extra.get("deadline_at")
        if deadline_at is not None:
            return max(0, int((float(deadline_at) - time.monotonic()) * 1000.0))
        deadline = self.deadline_ms
        return int(deadline) if deadline else 30_000


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


class MHSServer:
    """One MHS endpoint.

    HTTP options (plan 3.6, unconditional): ``allowed_hosts`` extends the
    ``Host`` allowlist beyond ``localhost``, ``127.0.0.1`` and ``[::1]``;
    ``allowed_origins`` lists browser origins (``scheme://host[:port]``) that may
    call the endpoint besides its own loopback origin; ``auth_tokens`` maps
    bearer tokens to principals (``{token: {"id": ..., "kind": ...}}``) and,
    when set, every HTTP route except ``/.well-known/mhs.json`` needs one;
    ``insecure_dev=True`` allows a non-loopback bind without tokens (development
    only, warned); ``http_timeout_s`` is the per-connection socket timeout.

    Principals (plan 3.6 step 1): a request that presents a bearer token
    (``Authorization`` over HTTP, :meth:`handle` ``auth_token`` in process,
    :meth:`run_stdio` ``auth_token`` for the pipe) is that token's principal;
    ``session.open`` then ignores ``params.principal`` (kept as
    ``x-meta.claimed_principal``) and the session is usable only by requests
    with the same principal.  A token principal's ``kind`` is ``human``,
    ``agent``, ``service`` or ``operator``.

    ``strict`` (default None: compatibility mode in 0.9; :mod:`mhs._server.strict`):
    ``True`` resolves every device against the capability catalogue and
    refuses findings with :class:`MHSStrictError`, and enables the strict
    runtime rules: class verb, binding ∩ class schemas and class permit
    flags; outputs validated against ``output_schema`` (a failed receipt
    ``MHS.CAPABILITY.OUTPUT_INVALID``); a self-declared ``human`` or
    ``operator`` without a token is recorded as ``claimed_principal`` and
    treated as an ``agent``; permits on hardware at R2 or above need the
    ``approval_verifier`` (fail closed); only an ``operator`` principal may
    reset a hardware or hybrid device; operations are visible to their own
    principal only.  Compatibility mode reports each finding as an
    :class:`MHSStrictWarning` (see :attr:`strict_findings`), raises a risk
    class below the class floor to the floor and otherwise keeps the 0.9
    behaviour.

    ``armed``: hardware actuation (a non-read, non-stop command on a
    ``hardware`` device) needs the device to be armed, otherwise it is
    refused with ``MHS.AUTH.HARDWARE_DISABLED``.  ``True`` arms every device,
    a collection of device ids arms those, ``False`` arms none.  None (the
    default) arms none in strict mode and every device in compatibility mode
    (warned).

    Limits (plan 3.5, both modes): every binding's limits are the
    intersection of its class limits, its own ``limits``, the device envelope
    and ``site_limits`` -- the operator overlay (a ``site-limits.json``
    document or a path to one), which may only narrow them and fills
    ``operator_required`` bounds.  A limit that cannot be enforced as written
    (a path that does not resolve, an unknown rule member, a widening overlay,
    a unit mismatch...) refuses the endpoint at construction with
    :class:`mhs.limits.LimitConfigError` (strict mode: a ``limits-invalid``
    finding of :class:`MHSStrictError`).  Commands are checked in the order of
    plan 3.6: structure (the schema without the bounds of limited fields),
    then every limited array element and nested leaf
    (``MHS.SAFETY.ENVELOPE_VIOLATION`` with ``{path, bound, value, unit,
    source}``, before any native call), then the remaining schema bounds.  An
    ``operator_required`` bound no overlay filled refuses a call that sets the
    field with ``MHS.SAFETY.LIMITS_UNSET``; strict mode also refuses hardware
    and hybrid write/invoke calls at R1 or above that set a numeric input no
    limit covers.  ``mhs.devices.get`` publishes each binding's effective
    limits (``x-mhs-effective-limits``) and the device's ``reference`` file.

    Persistence (``state_dir``, unconditional when given; layout in
    :mod:`mhs._server.state`): the evidence chain is
    ``EvidenceLog(path=<state_dir>/evidence.jsonl)``; the e-stop latch of
    every device is rewritten atomically to ``latch.json`` under the global
    lock, before any bridge I/O, by every e-stop and every completed reset;
    the idempotency index, the write-ahead records of commands between their
    reservation and their final receipt and the cumulative budget draws go to
    ``journal.jsonl``.  On start an existing latch keeps its device latched
    (``safety.status`` ``estop.restored``; the stop path is unconfirmed until
    the next e-stop, or a replay of the latching e-stop's ``command_id``,
    runs it again); so does an e-stop receipt in the verified evidence with
    no later completed reset, whatever ``latch.json`` says (warned).  A latch
    file that exists but cannot be read, or is missing although the evidence
    holds receipts, starts every device latched (warned; an unreadable file
    is kept as ``latch.json.unreadable-*``).
    A retried ``command_id`` replays its retained receipt; a command that was
    in flight when the process died gets an ``unknown`` receipt
    (``MHS.OUTCOME.UNKNOWN``, ``details.reason: endpoint_restarted``) instead
    of running again.  An effectful command whose write-ahead record cannot
    be written is refused before any bridge I/O (``MHS.INTERNAL.ERROR``,
    ``details.reason: journal_write_failed``); reads, stop classes and
    safe-state actions are not.  Revisions continue above the last one reached, so a
    pre-restart revision is never current again.  A state directory that is
    in use, belongs to another endpoint, or whose evidence or journal cannot
    be trusted refuses the start (:class:`StateDirError`).  ``fsync=True``
    also fsyncs every evidence and journal append (the latch file is always
    fsynced).  :meth:`close` releases the directory.
    """

    def __init__(
        self,
        endpoint_id: str,
        devices: Sequence[Device] | None = None,
        *,
        features: Sequence[str] | None = None,
        log_ready: bool = True,
        receipt_retention_s: int = _DEFAULT_RECEIPT_RETENTION_S,
        approval_verifier: Callable[..., Any] | None = None,
        auth_tokens: Mapping[str, Mapping[str, Any]] | None = None,
        allowed_hosts: Sequence[str] = (),
        allowed_origins: Sequence[str] = (),
        insecure_dev: bool = False,
        http_timeout_s: float = _HTTP_TIMEOUT_S,
        strict: bool | None = None,
        armed: bool | Sequence[str] | None = None,
        site_limits: Mapping[str, Any] | str | os.PathLike[str] | None = None,
        state_dir: str | os.PathLike[str] | None = None,
        fsync: bool = False,
        artifact_store: _artifacts.LocalArtifactStore | None = None,
    ) -> None:
        if artifact_store is not None and not isinstance(artifact_store, _artifacts.LocalArtifactStore):
            raise TypeError("artifact_store must be a LocalArtifactStore or None")
        self._artifact_store = artifact_store
        self._artifact_publication_lock = threading.RLock()
        if artifact_store is not None:
            artifact_store.bind(endpoint_id)
        if strict not in (None, True, False):
            raise TypeError("strict must be None, True or False")
        #: The operator overlay (site-limits.json) and its digest (plan 3.5).
        self.site_limits, self._site_limits_digest = _limits_plan.load_site_limits(site_limits)
        self.endpoint_id = endpoint_id
        #: None / False: compatibility mode; True: strict mode (see the class docstring).
        self.strict = strict
        self.devices: dict[str, Device] = {}
        for device in devices or []:
            self.devices[device.device_id] = device
        self.features = list(
            features
            or [
                "MHS.SAFETY.NOT_CERTIFIED",
                "mhs.subscribe",
                "mhs.operations",
                "mhs.evidence",
            ]
        )
        for feature in ("MHS.SAFETY.NOT_CERTIFIED", "batch", "sse"):
            if feature not in self.features:
                self.features.append(feature)
        self.log_ready = log_ready
        self.receipt_retention_s = int(receipt_retention_s)
        if self.receipt_retention_s < 1:
            raise ValueError("receipt_retention_s must be a positive number of seconds")
        if auth_tokens is not None and not isinstance(auth_tokens, Mapping):
            raise TypeError("auth_tokens must map bearer tokens to principals")
        for token in auth_tokens or {}:
            if not isinstance(token, str) or len(token) < 1:
                raise ValueError("auth_tokens keys must be non-empty strings")
        #: bearer token -> principal ``{id, kind[, display_name, contact]}``;
        #: None means no token authentication.
        self._auth_tokens: dict[str, dict[str, Any]] | None = None
        if auth_tokens:
            self._auth_tokens = {}
            for index, (token, principal) in enumerate(auth_tokens.items()):
                normalised, problems = _strict.normalise_token_principal(principal, index=index)
                if problems and strict is True:
                    raise ValueError("; ".join(problems))
                for problem in problems:
                    warnings.warn(MHSStrictWarning(
                        f"{problem}; using {normalised} (strict=True refuses it)"), stacklevel=2)
                self._auth_tokens[str(token)] = normalised
        if armed is not None and not isinstance(armed, bool):
            if isinstance(armed, str) or not all(isinstance(item, str) for item in armed):
                raise TypeError("armed must be None, a bool or a collection of device ids")
        #: See the class docstring; :meth:`_is_armed`.
        self.armed: bool | frozenset[str] | None = (
            armed if armed is None or isinstance(armed, bool) else frozenset(armed)
        )
        self.allowed_hosts = [str(host).strip().lower() for host in allowed_hosts if str(host).strip()]
        self.allowed_origins = [str(origin).strip().rstrip("/").lower()
                                for origin in allowed_origins if str(origin).strip()]
        self.insecure_dev = bool(insecure_dev)
        self.http_timeout_s = float(http_timeout_s)
        self._lock = threading.RLock()
        self._device_locks: dict[str, threading.Lock] = {
            did: threading.Lock() for did in self.devices
        }
        self._revisions: dict[str, int] = {did: 0 for did in self.devices}
        self._sessions: dict[str, Session] = {}
        self._permits: dict[str, Permit] = {}
        self._receipts: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
        self._receipts_by_id: dict[str, dict[str, Any]] = {}
        self._initialized = False
        self._negotiated_version: str | None = None
        #: Callable that authenticates human approvals for R3 hardware
        #: (SAFE-033/034).  None means "no trusted approval authority": R3
        #: hardware sessions and permits fail closed.
        self._approval_verifier = approval_verifier
        #: rolling cumulative-limit usage: (device_id, rule_key) -> [{t, amount, id}]
        self._cumulative_usage: dict[tuple[str, str], list[dict[str, Any]]] = {}
        #: cumulative accounting is a process-shared transaction (RE-SAFE-002).
        self._cumulative_lock = threading.RLock()
        #: single-use permits are reserved/consumed atomically (RE-SAFE-001).
        self._permit_lock = threading.Lock()
        #: (device_id, command_id) -> in-flight reservation (RE-PROTO-002).
        self._inflight: dict[tuple[str, str], dict[str, Any]] = {}
        # FID-030/FID-031: a hybrid device must declare authority as an object
        # covering exactly its resources, with a truth side for each.
        for device in self.devices.values():
            if device.mode != "hybrid":
                continue
            authority = (device.fidelity or {}).get("authority")
            resources = {resource.resource_id for resource in device.resources}
            if not isinstance(authority, Mapping):
                raise ValueError(
                    f"hybrid device {device.device_id} must declare fidelity.authority as an object"
                )
            if set(map(str, authority)) != resources:
                raise ValueError(
                    f"hybrid device {device.device_id}: authority keys {sorted(authority)} "
                    f"do not match resources {sorted(resources)}"
                )
            for resource_id, side in authority.items():
                if side not in ("hardware", "model"):
                    raise ValueError(
                        f"hybrid device {device.device_id}: authority[{resource_id!r}] "
                        f"must be 'hardware' or 'model', got {side!r}"
                    )
        # Cumulative windows this endpoint cannot enforce (SAFE-016) fail
        # closed at start-up with every other limit defect: mhs.limits refuses
        # an unknown ``per`` (limit-rule-invalid) in binding, envelope and
        # overlay rules alike (_resolve_strict).
        # SAFE-029: every safe-state action must be a capability bound on the
        # device; a typo used to be skipped silently on every e-stop.  A
        # hardware or hybrid device with an unbound action is refused.  On a
        # simulated or replay device it is a strict-mode finding (refused in
        # strict mode, an MHSStrictWarning in compatibility mode, below) and
        # every e-stop reports the action as failed, so the receipt says
        # SAFE_STATE_UNREACHED.
        #: device_id -> achieved_by ids that are not bound on the device
        self._unbound_safe_state: dict[str, list[str]] = {}
        for device in self.devices.values():
            achieved_by = (device.safety.safe_state or {}).get("achieved_by") or []
            if not isinstance(achieved_by, (list, tuple)):
                raise ValueError(
                    f"device {device.device_id}: safe_state.achieved_by must be a list of capability ids"
                )
            bound_classes = {capability_id for capability_id, _resource in device._by_binding}
            unknown = [str(item) for item in achieved_by if str(item) not in bound_classes]
            if not unknown:
                continue
            message = (
                f"device {device.device_id}: safe_state.achieved_by names {unknown}, "
                f"which {'is' if len(unknown) == 1 else 'are'} not bound on the device "
                f"(bound: {sorted(bound_classes)})"
            )
            if device.mode in ("hardware", "hybrid") and not _strict.resolve_flag(
                    strict, getattr(device, "strict", None)):
                raise ValueError(message)  # strict mode refuses it below, with every finding
            self._unbound_safe_state[device.device_id] = unknown
        # CORE-086/CORE-087: a declared recovery after an e-stop (an explicit
        # re-enable, or a terminal stop that no reset undoes) must be well
        # formed in every mode; a malformed one is refused at start-up.
        for device in self.devices.values():
            recovery = _estop_recovery_problems(device)
            if recovery:
                raise ValueError("; ".join(recovery))
            # SAFE-049 / CORE-088: a sensed-confirmation stop on a device of another mode is refused, in every mode.
            sensed = _sensed_stop_problems(device)
            if sensed:
                raise MHSError("MHS.ADAPTER.MANIFEST_INVALID", "; ".join(sensed),
                               {"device_id": device.device_id, "retryable": False,
                                "details": {"reason": "sensed_stop_not_simulated"}})
            # Verification F3: what this endpoint serves (the manifest's mode), not a constructor argument, lets the
            # SDK ROS bridge's sensed confirmation stand for a stop.
            _bind_sensed_route(device)
        #: device_id -> the Device object whose declared recovery was checked
        #: (construction, or :meth:`_check_late_recovery` on first use).
        self._recovery_checked: dict[str, Device] = dict(self.devices)
        #: device ids served in strict mode (the server's or the device's flag).
        self._strict_devices: set[str] = set()
        #: device_id -> its strict resolution (:func:`mhs._server.strict.resolve_device`).
        self._resolutions: dict[str, _strict.DeviceResolution] = {}
        #: (device_id, capability_id, resource) -> resolved contract (mhs.catalog.Effective).
        self._effective: dict[tuple[str, str, str], Any] = {}
        #: every strict-mode finding of this endpoint (see :attr:`strict_findings`).
        self._strict_findings: list[dict[str, Any]] = []
        #: compatibility-mode runtime warnings already emitted (one per key).
        self._compat_warned: set[tuple[Any, ...]] = set()
        #: device_id -> the Device object resolved for it (:meth:`_adopt_late_device`).
        self._adopted: dict[str, Device] = {}
        #: device_id -> (Device, resolution) of a late device strict mode refused.
        self._late_refused: dict[str, tuple[Device, _strict.DeviceResolution]] = {}
        self._adopt_lock = threading.Lock()
        #: (device_id, capability_id, resource) -> its limit plan
        #: (:mod:`mhs._server.limits_plan`), recompiled when what it was
        #: compiled from changes (:meth:`_limit_plan`).
        self._limit_plans: dict[tuple[str, str, str], _limits_plan.BindingPlan] = {}
        self._limit_lock = threading.Lock()
        #: device_id -> (key, reference file or None, problem or None) for devices.get.
        self._reference_cache: dict[str, tuple[Any, Any, Any]] = {}
        self._resolve_strict(stacklevel=3)
        self._operations: dict[str, Operation] = {}
        # Per-device restore ownership spans user-controlled preparation,
        # native effects, verification, rollback and receipt retention.
        self._restore_admissions: dict[str, int] = {}
        self._subscriptions: dict[str, dict[str, Any]] = {}
        #: Push-mode events (stdio) in seq order, appended under ``self._lock``
        #: and written by :meth:`_flush_outbox` outside it, exactly once.
        self._outbox: deque[Any] = deque()
        #: principal id -> open SSE streams (HTTP).
        self._sse_streams: dict[str, int] = {}
        #: The last report stored by :meth:`record_conformance_report`.
        self._conformance_report: dict[str, Any] | None = None
        #: Session-expiry timer (:func:`_session_reaper_loop`).
        self._reaper_thread: threading.Thread | None = None
        self._reaper_wake = threading.Event()
        #: Software e-stop latch per device.  Set under ``self._lock`` before any
        #: bridge I/O; cleared only by an accepted mhs.safety.reset.
        self._latched: dict[str, bool] = {did: False for did in self.devices}
        #: Per-device e-stop bookkeeping: ``generation`` (bumped by every reset;
        #: a background retry stops when it changes), ``seq`` (bumped by every
        #: engaged e-stop; a reset that saw it change while it ran keeps the
        #: latch), ``reason`` (of the last e-stop), ``attempt`` (the current
        #: :class:`_EstopAttempt`), ``confirmed`` (None when not latched, False
        #: while the stop path is unconfirmed, True once it succeeded),
        #: ``attempts``, ``unconfirmed`` (command ids of failed e-stop receipts),
        #: ``supervisor`` (the background retry thread) and the
        #: ``supervisor_generation`` it serves, ``resetting`` (number of resets
        #: inside ``bridge.reset()``; the retry waits while it is > 0),
        #: ``reset_hold_until`` (monotonic deadline of that wait), ``reset_seq``
        #: (``seq`` when the last reset entered ``bridge.reset()``; an e-stop
        #: engaged since then lifts the wait) and ``pending_attempts`` (every
        #: attempt whose native stop may still be running).
        self._estop_state: dict[str, dict[str, Any]] = {
            did: _fresh_estop_state() for did in self.devices
        }
        #: Per-thread dispatch context: ``abandoned`` is the event
        #: :meth:`_dispatch_bounded` sets when the caller has been answered
        #: with ``MHS.OUTCOME.TIMEOUT`` (a reset that has not reached
        #: ``bridge.reset()`` yet is then not performed).
        self._dispatch_local = threading.local()
        #: capability id -> catalogue verb (None: not catalogued), see
        #: :meth:`_is_read_capability`.
        self._class_verbs: dict[str, str | None] = {}
        #: capability id -> catalogue ``constraints`` ({} when not catalogued),
        #: see :meth:`_execution_bounds`.
        self._class_constraints: dict[str, dict[str, Any]] = {}
        #: capability id -> catalogue ``concurrency`` (None: not catalogued or
        #: not declared), see :meth:`_effective_concurrency`.
        self._class_concurrencies: dict[str, str | None] = {}
        #: Persistence (WP-04 step 4f; see the class docstring).  None: in memory.
        self.state_dir: Path | None = Path(state_dir).expanduser() if state_dir is not None else None
        self._state: _state.StateDir | None = None
        #: device_id -> its entry in ``latch.json`` (devices not served now included).
        self._latch_entries: dict[str, dict[str, Any]] = {}
        self._closed = False
        if self.state_dir is None:
            self._evidence = EvidenceLog(
                endpoint_id, server={"name": SERVER_NAME, "version": SERVER_VERSION}
            )
        else:
            self._open_state_dir(fsync=bool(fsync))
        self._emit: Callable[[dict[str, Any]], None] | None = None
        self._emit_lock = threading.Lock()
        self._started_at = canonical.now_rfc3339()
        self._http_handle: "_HTTPHandle | None" = None

    # -- persistence (state_dir, WP-04 step 4f) -------------------------
    def _open_state_dir(self, *, fsync: bool) -> None:
        """Load ``state_dir`` and adopt its latch, index, revisions and budgets.

        No bridge I/O.  Order: take the directory lock; load and verify the
        evidence chain (it must be this endpoint's); read the latch file and
        derive the latch from the evidence too (:meth:`_adopt_latches`);
        rebuild the journal against the evidence; record an ``unknown``
        receipt for every command that was in flight when the previous
        process stopped; then rewrite the journal (compacted) and the latch
        file atomically.  Any failure releases the directory and refuses the
        start (an ``OSError`` of the final writes as :class:`StateDirError`).
        """
        assert self.state_dir is not None
        store = _state.StateDir(self.state_dir, self.endpoint_id, fsync=fsync)
        try:
            try:
                evidence = EvidenceLog(
                    self.endpoint_id, path=store.evidence_path,
                    server={"name": SERVER_NAME, "version": SERVER_VERSION}, fsync=fsync,
                    recover_torn_tail=True,
                )
            except MHSError as exc:
                raise StateDirError(
                    f"state_dir {store.path}: {_state.EVIDENCE_FILE} cannot be trusted "
                    f"({exc.code}: {exc.message}); the endpoint does not start on a broken chain"
                ) from exc
            if evidence.recovered_tail and evidence.recovered_tail.get("kept_as"):
                warnings.warn(RuntimeWarning(
                    f"state_dir {store.path}: the last line of {_state.EVIDENCE_FILE} was torn by a crash "
                    f"during an append ({evidence.recovered_tail['bytes']} bytes, kept as "
                    f"{Path(evidence.recovered_tail['kept_as']).name}); a command it belonged to is "
                    "recorded as unknown"), stacklevel=3)
            owner = (evidence.genesis or {}).get("endpoint_id")
            if owner != self.endpoint_id:
                raise StateDirError(
                    f"state_dir {store.path}: {_state.EVIDENCE_FILE} belongs to endpoint "
                    f"{owner!r}, not {self.endpoint_id!r}"
                )
            records = evidence.records()
            latches = store.load_latches()
            if latches.absent and _state.holds_receipts(records):
                # The endpoint writes latch.json at every start, before any
                # receipt: a missing one is lost state, never a fresh directory.
                latches.unreadable = f"missing, although {_state.EVIDENCE_FILE} holds receipts"
            journal = store.load_journal(records)
            self._evidence = evidence
            self._state = store
            self._adopt_latches(latches, records)
            for key, begin in sorted(journal.pending.items(), key=lambda item: str(item[1].get("accepted_at"))):
                recorded = self._record_receipt(self._restart_unknown_receipt(begin))
                journal.index[key] = (str(recorded.get("input_digest")), recorded)
            journal.pending = {}
            for key, (digest, receipt) in journal.index.items():
                self._receipts[key] = (digest, receipt)
                if isinstance(receipt.get("receipt_id"), str):
                    self._receipts_by_id[receipt["receipt_id"]] = receipt
            # A restart may have changed the device without the endpoint
            # seeing it: continue above the last revision reached, so no
            # pre-restart revision (expected_revision) is ever current again.
            for did, revision in journal.revisions.items():
                self._revisions[did] = int(revision) + 1
                device = self.devices.get(did)
                if device is not None:
                    device.primary_resource.revision = self._revisions[did]
            journal.revisions = {did: self._revisions[did] for did in journal.revisions}
            journal.draws = self._adopt_draws(journal.draws)
            try:
                store.compact(journal)
            except OSError as exc:
                raise StateDirError(
                    f"state_dir {store.path}: cannot rewrite {_state.JOURNAL_FILE} "
                    f"({type(exc).__name__}: {exc})") from exc
            if latches.unreadable is not None:
                # Only now, with everything else loaded: a start refused
                # earlier leaves the unreadable file in place (it fails
                # latched again), and latch.json is only ever replaced
                # atomically, never removed.
                kept = store.preserve_unreadable_latch(latches)
                problem = ("is missing, although its evidence holds receipts (lost state)" if latches.absent
                           else f"is unreadable ({latches.unreadable})")
                warnings.warn(RuntimeWarning(
                    f"state_dir {store.path}: {_state.LATCH_FILE} {problem}; "
                    "every device starts latched (reset each one through mhs.safety.reset)"
                    + (f"; the file was kept as {kept.name}" if kept is not None else "")
                ), stacklevel=3)
            try:
                store.write_latches(self._latch_entries)
            except OSError as exc:
                raise StateDirError(
                    f"state_dir {store.path}: cannot write {_state.LATCH_FILE} ({type(exc).__name__}: {exc}); "
                    "the endpoint does not start without its latch file") from exc
        except BaseException:
            self._state = None
            store.close()
            raise

    def _adopt_latches(self, latches: _state.LatchState, records: list[dict[str, Any]]) -> None:
        """Apply ``latch.json`` and the latch the evidence derives (fail latched).

        A device is latched when ``latch.json`` says so, or when the verified
        evidence holds an e-stop receipt with no later completed reset
        (:func:`mhs._server.state.derive_latches`: a deleted or hand-edited
        latch file, or an e-stop whose latch write failed, never comes back
        unlatched).  An unreadable (or lost) latch file latches every device
        served now and every device the evidence holds a receipt for.
        """
        now = canonical.now_rfc3339()
        entries: dict[str, dict[str, Any]] = {}
        if latches.unreadable is not None:
            # Fail latched: every device served now and every device this
            # state directory has a receipt for (it may be served later).
            known = set(self.devices) | {
                str(record["device_id"]) for record in records if isinstance(record.get("device_id"), str)
            }
            reason = (f"latch file missing at start-up, although {_state.EVIDENCE_FILE} holds receipts"
                      if latches.absent else f"latch file unreadable at start-up: {latches.unreadable}")
            entries = {did: {"latched": True, "reason": reason, "since": now} for did in sorted(known)}
        else:
            entries = {did: dict(entry) for did, entry in latches.entries.items()}
        disagreements: list[str] = []
        for did, record in sorted(_state.derive_latches(records).items()):
            if entries.get(did, {}).get("latched"):
                continue
            receipt_id = record.get("receipt_id")
            entries[did] = {
                "latched": True,
                "reason": f"e-stop receipt {receipt_id} in {_state.EVIDENCE_FILE} has no later reset",
                "since": record.get("ended_at") if isinstance(record.get("ended_at"), str) else now,
            }
            disagreements.append(f"{did} (e-stop receipt {receipt_id})")
        if disagreements:
            warnings.warn(RuntimeWarning(
                f"state_dir {self.state_dir}: {_state.LATCH_FILE} does not hold the latch of "
                + ", ".join(disagreements)
                + f", but {_state.EVIDENCE_FILE} records that e-stop and no later reset; "
                "the device starts latched (reset it through mhs.safety.reset)"), stacklevel=4)
        for did in self.devices:
            entries.setdefault(did, {"latched": False, "reason": None, "since": None})
        self._latch_entries = entries
        for did, entry in entries.items():
            if not entry.get("latched"):
                continue
            self._latched[did] = True
            state = self._estop_state.setdefault(did, _fresh_estop_state())
            state["reason"] = entry.get("reason")
            # Nothing has confirmed the stop path since the restart.
            state["confirmed"] = False
            state["restored"] = True
            state["persisted"] = True

    def _adopt_draws(self, draws: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Load the cumulative draws still inside their window (SAFE-016)."""
        now = time.time()
        live: list[dict[str, Any]] = []
        with self._cumulative_lock:
            for draw in draws:
                window = str(draw["window"])
                window_s = _CUMULATIVE_WINDOWS.get(window)
                horizon = window_s if window_s is not None else max(3600.0, float(self.receipt_retention_s))
                if now - float(draw["t"]) > horizon:
                    continue
                self._cumulative_usage.setdefault((str(draw["key"]), window), []).append(
                    {"t": float(draw["t"]), "amount": float(draw["amount"]), "id": str(draw["id"])})
                live.append(draw)
        return live

    def _restart_unknown_receipt(self, begin: Mapping[str, Any]) -> dict[str, Any]:
        """The ``unknown`` receipt of a command the previous process never finished.

        Built from the journal's ``begin`` entry (no bridge I/O): the command
        passed every pre-check and may have acted, so it is never run again
        and its outcome is ``unknown`` (``retryable: false``).
        """
        now = canonical.now_rfc3339()
        did = str(begin.get("device_id"))
        device = self.devices.get(did)
        capability_id = str(begin.get("capability_id") or "cap.internal.unknown.v1")
        resource = begin.get("resource") if isinstance(begin.get("resource"), str) else None
        session_id = begin.get("session_id")
        if not isinstance(session_id, str) or not re.match(r"^mhs_s_[A-Za-z0-9]+$", session_id):
            session_id = f"mhs_s_{canonical.ulid()}"
        principal = begin.get("principal")
        if not isinstance(principal, Mapping) or not isinstance(principal.get("id"), str):
            principal = {"id": "unknown", "kind": "agent"}
        mode = begin.get("mode")
        if mode not in ("simulated", "hardware", "hybrid", "replay"):
            mode = device.mode if device is not None else "simulated"
        accepted_at = begin.get("accepted_at") if isinstance(begin.get("accepted_at"), str) else now
        details: dict[str, Any] = {"reason": "endpoint_restarted", "accepted_at": accepted_at,
                                   "evidence_seq": begin.get("evidence_seq")}
        message = "the endpoint stopped while this command was in flight; it may have acted and is not run again"
        if isinstance(begin.get("lost_receipt_id"), str):
            # The journal retained a receipt the evidence lost (its tail was not
            # on disk): the command ran, its recorded outcome is gone.
            details["lost_receipt_id"] = begin["lost_receipt_id"]
            message = ("the endpoint stopped after this command ended, but its receipt was lost from the "
                       "evidence log; its outcome is unknown and it is not run again")
        if device is not None:
            effects = self._sanitize_effects(
                self._effects_for(device, capability_id, "unknown", resource), device, "unknown")
        else:
            risk = begin.get("risk") if begin.get("risk") in _RISK_ORDER else "R3"
            effects = [{"kind": "capability.invoke", "summary": f"{capability_id} (unknown)",
                        "reversible": False, "severity": risk}]
        return {
            "receipt_id": canonical.ulid(),
            "command_id": str(begin.get("command_id")),
            "session_id": session_id,
            "endpoint_id": self.endpoint_id,
            "device_id": did,
            "capability_id": capability_id,
            "resource_ids": [resource] if resource else [],
            "input_digest": str(begin.get("input_digest")),
            "status": "unknown",
            "mode": mode,
            "principal": _plain(dict(principal)),
            "accepted_at": accepted_at,
            "started_at": accepted_at,
            "ended_at": now,
            "output": None,
            "effects": effects,
            "replayed": False,
            "error": {
                "mhs_code": "MHS.OUTCOME.UNKNOWN",
                "message": message,
                "retryable": False,
                "details": details,
            },
            "x-vendor": {"restart_reconciled": True},
        }

    def _journal(self, entry: Mapping[str, Any]) -> None:
        """Append one journal line; a write failure is logged, never raised.

        Called under ``self._lock`` (or the cumulative lock) so the lines of
        one key are in the order the server applied them.
        """
        store = self._state
        if store is None:
            return
        try:
            store.append(entry)
        except (OSError, TypeError, ValueError) as exc:
            if not store.closed:
                _log.error("state_dir %s: journal append failed (%s: %s)",
                           self.state_dir, type(exc).__name__, exc)

    def _retain_receipt(self, key: tuple[str, str], digest: str, receipt: dict[str, Any], *,
                        deferred: bool = False) -> Any:
        """Retain an outcome, or prepare its artifact-only no-I/O publication.

        Deferred preparation happens before evidence recording; no receipt is
        exposed yet. Its returned closure only inserts already-built objects.
        The artifact transaction activates grants before invoking that closure.
        """
        if deferred:
            if not isinstance(receipt.get("receipt_id"), str):
                raise ValueError("a staged receipt needs an identifier")
            def publish(recorded: dict[str, Any]) -> None:
                with self._lock:
                    self._receipts[key] = (digest, recorded)
                    self._receipts_by_id[recorded["receipt_id"]] = recorded
            return publish
        self._receipts[key] = (digest, receipt)
        if isinstance(receipt.get("receipt_id"), str):
            self._receipts_by_id[receipt["receipt_id"]] = receipt
        self._journal_retained_receipt(key, digest, receipt)

    def _journal_retained_receipt(self, key: tuple[str, str], digest: str, receipt: dict[str, Any]) -> None:
        if self._state is not None:
            evidence = receipt.get("evidence")
            self._journal({"op": "put", "device_id": key[0], "command_id": key[1], "input_digest": digest,
                           "receipt_id": receipt.get("receipt_id"),
                           "seq": evidence.get("seq") if isinstance(evidence, Mapping) else None})

    def _forget_receipt(self, key: tuple[str, str], receipt_id: Any) -> None:
        """Free a command id whose retained receipt was ``receipt_id`` (caller holds ``self._lock``)."""
        stored = self._receipts.get(key)
        if stored is None or stored[1].get("receipt_id") != receipt_id:
            return
        self._receipts.pop(key, None)
        self._journal({"op": "drop", "device_id": key[0], "command_id": key[1], "receipt_id": receipt_id})

    def close(self) -> None:
        """Stop recording: close the evidence log and release ``state_dir`` (idempotent).

        A closed endpoint keeps its in-memory latch, but nothing it does is
        recorded any more; construct a new :class:`MHSServer` on the same
        ``state_dir`` to continue.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            store, self._state = self._state, None
        try:
            self._evidence.close()
        finally:
            if self._artifact_store is not None:
                self._artifact_store.close()
            if store is not None:
                store.close()

    def read_artifact(self, uri: str, *, session_id: str, auth_token: str | None = None) -> dict[str, Any]:
        """Local transport API only: authenticated, original-session artifact read.

        This is deliberately absent from JSON-RPC dispatch. It never dereferences
        a file/network URL. The returned bytes are bounded by the local store.
        """
        principal = self._principal_for_token(auth_token)
        if (auth_token is not None or self._auth_tokens) and principal is None:
            raise MHSError("MHS.AUTH.UNAUTHENTICATED", "a valid endpoint token is required")
        token = _REQUEST_PRINCIPAL.set(principal)
        try:
            with self._lock:
                if self._closed or self._artifact_store is None:
                    raise MHSError("MHS.PROTOCOL.UNSUPPORTED_FEATURE", "local artifacts are unavailable")
                session = self._session(session_id)
            def authorize(scope: _artifacts.ArtifactScope) -> None:
                with self._lock:
                    live = self._session(session_id)
                    if live is not session or not session.allows(scope.device_id, scope.capability_id, scope.resource):
                        raise MHSError("MHS.SESSION.CAPABILITY_NOT_GRANTED", "session does not cover this artifact")
            result = self._artifact_store.read(uri, session_id, authorize)
            with self._lock:
                if self._closed or self._session(session_id) is not session:
                    raise MHSError("MHS.SESSION.UNKNOWN", "artifact session is no longer active")
            return result
        finally:
            _REQUEST_PRINCIPAL.reset(token)

    # -- public: transports -------------------------------------------
    def run_stdio(self, *, auth_token: str | None = None) -> None:
        """Serve JSON-RPC over stdin/stdout (NDJSON, T1) until stdin closes.

        ``auth_token`` authenticates the pipe: every request is that
        ``auth_tokens`` principal (the process that holds the pipe started the
        endpoint with it).  An unknown token raises ``MHS.AUTH.UNAUTHENTICATED``
        before anything is served.

        The reader thread (the caller) never waits behind a device: an
        ``mhs.safety.estop`` (or ``mhs.command`` on ``cap.motion.estop.v1``) is
        handled by the reader itself, so the latch is engaged before the next
        line is read; ``mhs.operations.cancel`` runs on its own priority
        thread; every other request goes to the FIFO lane of the device it
        targets (one worker per lane), so a blocking command delays only later
        requests for the same device.  Responses are written as they complete
        and are correlated by ``id``.  At end of input the lanes are drained
        before returning.
        """
        pipe_principal = None
        if auth_token is not None:
            pipe_principal = self._principal_for_token(auth_token)
            if pipe_principal is None:
                raise MHSError("MHS.AUTH.UNAUTHENTICATED", "the bearer token is not known to this endpoint")
        stdin = sys.stdin.buffer
        stdout = sys.stdout.buffer
        write_lock = threading.Lock()
        max_request_bytes = 1024 * 1024

        def write(message: Any) -> None:
            data = protocol.encode_json(message) + b"\n"
            with write_lock:
                stdout.write(data)
                stdout.flush()

        def emit(message: Any) -> None:
            try:
                write(message)
            except (TypeError, ValueError) as exc:
                # A non-JSON value (NaN, an object) must not kill the transport.
                request_id = getattr(message, "id", None)
                if request_id is None and isinstance(message, Mapping):
                    request_id = message.get("id")
                write(protocol.make_error(request_id, MHSError(
                    "MHS.INTERNAL.ERROR", "response is not JSON-encodable",
                    {"detail": type(exc).__name__})))

        dispatcher = _StdioDispatcher(self, emit, auth=pipe_principal)
        self._emit = emit
        if self.log_ready:
            ready = {
                "mhs_ready": True,
                "endpoint_id": self.endpoint_id,
                "transport": "stdio",
                "devices": [d.device_id for d in self.devices.values()],
            }
            sys.stderr.write(json.dumps(ready) + "\n")
            sys.stderr.flush()

        stop = threading.Event()

        def flush_notifications() -> None:
            # Backstop for events queued while a caller held ``self._lock``;
            # every event is written exactly once (the outbox is popped).
            while not stop.is_set():
                try:
                    self._flush_outbox()
                except (BrokenPipeError, OSError):
                    return
                stop.wait(0.05)

        flusher = threading.Thread(target=flush_notifications, name="mhs-stdio-events", daemon=True)
        flusher.start()
        interrupted = False
        try:
            while True:
                # A blocking readline: select() on the descriptor would miss
                # lines that are already in the reader's buffer (pipelined
                # requests arrive in one read).
                try:
                    raw = stdin.readline(max_request_bytes + 1)
                except (OSError, ValueError):
                    break
                if not raw:
                    break
                if len(raw) > max_request_bytes and not raw.endswith(b"\n"):
                    emit(protocol.make_error(None, MHSError("MHS.LIMIT.PAYLOAD_TOO_LARGE")))
                    while raw and not raw.endswith(b"\n"):  # discard the rest of that line
                        raw = stdin.readline(max_request_bytes + 1)
                    continue
                line = raw.strip()
                if not line:
                    continue
                try:
                    message = _decode_wire(line)
                except Exception:  # noqa: BLE001 - MHSError or any decoder failure: the reader never dies
                    emit(protocol.make_error(None, MHSError("MHS.PROTOCOL.PARSE_ERROR")))
                    continue
                dispatcher.submit(message)
        except BrokenPipeError:
            pass
        except KeyboardInterrupt:
            interrupted = True
        finally:
            # End of input: answer every request already read (each is bounded
            # by its deadline).  An interrupt does not wait for them.
            dispatcher.close(timeout=0.5 if interrupted else _MAX_DEADLINE_MS / 1000.0 + 5.0)
            try:
                self._flush_outbox()
            except (BrokenPipeError, OSError):
                pass
            stop.set()
            flusher.join(timeout=0.5)
            self._emit = None

    def run_http(self, host: str = "127.0.0.1", port: int = 7400, *,
                 insecure_dev: bool | None = None) -> None:
        handle = self.start_http(host, port, insecure_dev=insecure_dev)
        try:
            while True:
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            handle.shutdown()

    def _check_bind_host(self, host: str, *, insecure_dev: bool | None) -> None:
        """Refuse a non-loopback bind unless tokens or ``insecure_dev`` (SAFE-060).

        ``0.0.0.0``, ``::``, the empty host, any other address and any name but
        ``localhost`` count as non-loopback.  With ``auth_tokens`` the bind is
        allowed (TLS is the deployment's job, TPT-013); with ``insecure_dev``
        it is allowed with a warning.
        """
        if _is_loopback_host(host):
            return
        if self._auth_tokens:
            return
        if insecure_dev if insecure_dev is not None else self.insecure_dev:
            warnings.warn(
                f"MHS endpoint bound to non-loopback address {host!r} without authentication "
                "(insecure_dev=True): any host on the network can drive these devices",
                RuntimeWarning, stacklevel=3,
            )
            return
        raise MHSError(
            "MHS.AUTH.TRANSPORT_INSECURE",
            f"refusing to serve HTTP on non-loopback address {host!r} without auth_tokens; "
            "bind 127.0.0.1, configure MHSServer(auth_tokens=...) (behind TLS), or pass "
            "insecure_dev=True for a development network",
            {"retryable": False, "details": {"host": host}},
        )

    def start_http(self, host: str = "127.0.0.1", port: int = 7400, *,
                   insecure_dev: bool | None = None) -> "_HTTPHandle":
        """Serve HTTP (T2) in a background thread and return its handle.

        Refuses a non-loopback ``host`` without ``auth_tokens`` unless
        ``insecure_dev`` (here or on the server) is true.
        """
        self._check_bind_host(host, insecure_dev=insecure_dev)
        closing = threading.Event()
        server = ThreadingHTTPServer((host, int(port)),
                                     _make_handler(self, bind_host=host, closing=closing))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, name="mhs-http", daemon=True)
        thread.start()
        actual = server.server_address[1]
        handle = _HTTPHandle(server, thread, host, actual, closing)
        self._http_handle = handle
        if self.log_ready:
            print(
                json.dumps(
                    {
                        "mhs_ready": True,
                        "endpoint_id": self.endpoint_id,
                        "transport": "http",
                        "url": handle.url,
                    }
                ),
                flush=True,
            )
        return handle

    # -- public: dispatch ---------------------------------------------
    def handle(self, request: Mapping[str, Any], *, auth_token: str | None = None) -> dict[str, Any] | None:
        """Handle one decoded JSON-RPC message in process.

        ``auth_token`` authenticates the caller as the principal of that
        ``auth_tokens`` entry (compared in constant time), exactly like an
        HTTP ``Authorization: Bearer`` header; an unknown token is
        ``MHS.AUTH.UNAUTHENTICATED``.  Without it the caller is
        unauthenticated (its ``session.open`` principal is self-declared).
        """
        principal = None
        if auth_token is not None:
            principal = self._principal_for_token(auth_token)
            if principal is None:
                request_id = request.get("id") if isinstance(request, Mapping) else None
                return protocol.make_error(request_id, MHSError(
                    "MHS.AUTH.UNAUTHENTICATED", "the bearer token is not known to this endpoint"))
        # Decoded in-process replies cross the same ownership boundary as JSON
        # sent over a socket. Retained receipts/operations must never share
        # mutable nested objects with the caller's returned document.
        return copy.deepcopy(self._handle_message(request, auth=principal))

    def take_notifications(self) -> list[dict[str, Any]]:
        """Drain every buffered ``mhs.event`` notification of every session.

        For in-process callers and tests only: a transport delivers one
        session's events (:meth:`take_notifications_for_session`).
        """
        with self._lock:
            pending: list[dict[str, Any]] = []
            for subscription in self._subscriptions.values():
                pending.extend(_drain_subscription(subscription))
        return pending

    def take_notifications_for(self, subscription_id: str) -> list[dict[str, Any]]:
        """Drain one subscription's buffered notifications."""
        with self._lock:
            subscription = self._subscriptions.get(str(subscription_id))
            if subscription is None:
                return []
            return _drain_subscription(subscription)

    def take_notifications_for_session(
        self, session_id: str, subscription_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Drain the buffered notifications of one session's subscriptions (SSE).

        With ``subscription_id`` only that subscription is drained, and only
        when it belongs to ``session_id`` (TPT-017: never another principal's
        events).
        """
        with self._lock:
            pending: list[dict[str, Any]] = []
            for sid, subscription in self._subscriptions.items():
                if subscription.get("session_id") != session_id:
                    continue
                if subscription_id is not None and sid != subscription_id:
                    continue
                pending.extend(_drain_subscription(subscription))
        return pending

    def record_conformance_report(self, report: Mapping[str, Any]) -> None:
        """Store an executed conformance report for ``mhs.conformance.report``.

        ``report`` is the output of :func:`mhs.conformance.run_suite` (or a
        saved copy) for this endpoint: its ``report_digest`` must recompute
        and ``subject.id`` must name this endpoint or one of its devices.
        The method then returns it verbatim until another report is stored.
        """
        if not isinstance(report, Mapping):
            raise TypeError("a conformance report must be an object")
        document = copy.deepcopy(_plain(dict(report)))
        digest = document.get("report_digest")
        if not isinstance(digest, str) or digest != _conformance_report_digest(document):
            raise ValueError("conformance report_digest does not match the report")
        subject = document.get("subject") if isinstance(document.get("subject"), Mapping) else {}
        if subject.get("id") not in {self.endpoint_id, *self.devices}:
            raise ValueError(
                f"conformance report is about {subject.get('id')!r}, not this endpoint "
                f"({self.endpoint_id!r})"
            )
        with self._lock:
            self._conformance_report = document

    def export_evidence(self) -> dict[str, Any]:
        return self._export_bundle()

    # -- strict mode ---------------------------------------------------
    @property
    def strict_findings(self) -> list[dict[str, Any]]:
        """Every strict-mode finding of this endpoint (``mode``: ``strict`` or ``compat``).

        In compatibility mode each was also emitted as an
        :class:`MHSStrictWarning`; ``refuse`` says whether strict mode refuses
        the device (True) or enforces the rule at runtime (False).
        """
        with self._lock:
            return [dict(item) for item in self._strict_findings]

    def _resolve_strict(self, *, stacklevel: int) -> None:
        """Resolve every device against the catalogue at construction (WP-04 4b).

        Strict devices are refused on any ``refuse`` finding and then serve
        their resolved contract (:func:`mhs._server.strict.apply_strict`).
        Compatibility devices get one :class:`MHSStrictWarning` per finding and
        a risk class raised to the class floor.
        """
        refused: list[_strict.Finding] = []
        compat: list[tuple[Device, _strict.DeviceResolution]] = []
        limit_errors: list[_limits.LimitConfigError] = []
        plans: dict[str, dict[tuple[str, str], _limits_plan.BindingPlan]] = {}
        for device in self.devices.values():
            device_strict = _strict.resolve_flag(self.strict, getattr(device, "strict", None))
            resolution = getattr(device, "_strict_resolution", None) if device_strict else None
            if resolution is None:
                resolution = self._resolve_device(device)
            self._resolutions[device.device_id] = resolution
            self._adopted[device.device_id] = device
            for (capability_id, resource), resolved in resolution.effective.items():
                self._effective[(device.device_id, capability_id, resource)] = resolved
            # Plan 3.5: the limits of every binding are compiled at start-up,
            # in both modes; a limit that cannot be enforced as written
            # refuses the endpoint (strict: a finding of MHSStrictError).
            plans[device.device_id], limit_error = self._compile_device_plans(
                device, resolution, strict=device_strict)
            # A pair bound twice -- appended to Device.capabilities after
            # construction -- is refused in every mode, as Device(...) refuses
            # it (4d verifier p3: the wider duplicate was served).  A strict
            # device's own resolution predates the append (4d r2 q8), so the
            # pairs are counted again here (once: a fresh strict resolution
            # already refuses them).
            if not (device_strict and any(item.rule == "capability-duplicate" for item in resolution.refused)):
                refused.extend(device.duplicate_findings())
            if device_strict:
                self._strict_devices.add(device.device_id)
                refused.extend(resolution.refused)
                if limit_error is not None and not any(
                        item.rule == "limits-invalid" for item in resolution.findings):
                    refused.append(self._limit_error_finding(device, limit_error))
            else:
                compat.append((device, resolution))
                if limit_error is not None:
                    limit_errors.append(limit_error)
        if refused:
            raise MHSStrictError(refused)
        if limit_errors:
            raise limit_errors[0]
        self._warn_unknown_overlay_devices(stacklevel=stacklevel)
        for did in sorted(self._strict_devices):
            device = self.devices[did]
            resolution = self._resolutions[did]
            if getattr(device, "_strict_resolution", None) is None:
                _strict.apply_strict(device, resolution)
                device._strict_resolution = resolution
            self._store_plans(device, plans[did])
            self._strict_findings.extend(
                {**finding.to_json(), "mode": "strict"}
                for finding in [*resolution.findings, *self._deployment_findings(device),
                                *self._limit_findings(device)]
            )
        for device, resolution in compat:
            raised = _strict.apply_compat(device, resolution)
            self._store_plans(device, plans[device.device_id])
            for finding in [*resolution.findings, *self._deployment_findings(device),
                            *self._limit_findings(device)]:
                if finding.rule == "risk-floor" and raised:
                    note = f"compatibility mode: risk_class raised to {raised}; strict=True refuses the device"
                elif finding.rule in _ENFORCED_IN_BOTH_MODES:
                    note = "enforced in every mode"
                elif finding.refuse:
                    note = "compatibility mode: served anyway; strict=True refuses the device"
                else:
                    note = "compatibility mode: not enforced; strict=True enforces it"
                self._strict_findings.append({**finding.to_json(), "mode": "compat"})
                warnings.warn(MHSStrictWarning(f"{finding.text()} -- {note}"), stacklevel=stacklevel)

    # -- limits (plan 3.5) ----------------------------------------------
    def _compile_device_plans(
        self, device: Device, resolution: "_strict.DeviceResolution | None", *, strict: bool
    ) -> tuple[dict[tuple[str, str], _limits_plan.BindingPlan], _limits.LimitConfigError | None]:
        """Compile the limit plan of every binding of ``device`` (no server state is changed).

        Strict devices are compiled against the schema they will serve (the
        resolved binding ∩ class one).  Returns the plans and the first
        load-time defect (:class:`mhs.limits.LimitConfigError`, its message
        naming the device and capability), or None.
        """
        out: dict[tuple[str, str], _limits_plan.BindingPlan] = {}
        first: _limits.LimitConfigError | None = None
        effective_map = resolution.effective if resolution is not None else {}
        for capability in device.capabilities:
            effective = effective_map.get((capability.capability_id, capability.resource))
            served = effective.input_schema if strict and effective is not None else _limits_plan.SERVED
            plan = _limits_plan.compile_binding(
                device, capability, overlay=self.site_limits, overlay_digest=self._site_limits_digest,
                effective=effective, served_schema=served)
            out[(capability.capability_id, capability.resource)] = plan
            if plan.error is not None and first is None:
                first = _limits_plan.located_error(device.device_id, capability.capability_id, plan.error)
        if first is None:
            try:
                # Strict mode reports an unbound envelope key as its own
                # refusing finding (envelope-unbound, _strict.resolve_device).
                _limits_plan.check_device_targets(device, out, self.site_limits, refuse_unbound=not strict)
            except _limits.LimitConfigError as exc:
                first = _limits_plan.located_error(device.device_id, None, exc)
        return out, first

    def _store_plans(self, device: Device, plans: Mapping[tuple[str, str], _limits_plan.BindingPlan]) -> None:
        """Cache compiled plans, keyed by what the device serves now (after strict/compat apply)."""
        bindings = _limits_plan.device_bindings(device)
        with self._limit_lock:
            for key in [key for key in self._limit_plans if key[0] == device.device_id]:
                del self._limit_plans[key]
            for capability in device.capabilities:
                plan = plans.get((capability.capability_id, capability.resource))
                if plan is None:
                    continue
                plan.key = _limits_plan.fingerprint(device, capability, self._site_limits_digest)
                plan.bindings = bindings
                self._limit_plans[(device.device_id, capability.capability_id, capability.resource)] = plan

    def _limit_plan(self, device: Device, capability: Capability) -> _limits_plan.BindingPlan:
        """The binding's limit plan, recompiled when what it was compiled from changed.

        The cached plan is used while the binding's :func:`fingerprint
        <mhs._server.limits_plan.fingerprint>` (schema, limits, envelope,
        overlay, device object) and the device's bindings are unchanged.
        Otherwise -- a device put in :attr:`devices` after construction, or an
        envelope, schema or binding changed after start-up -- every binding of
        the device is compiled again together with the device-level load-time
        rules (:meth:`_recompile_device_limits`), so a declaration
        construction would refuse is never served with its limit dropped.
        """
        cache_key = (device.device_id, capability.capability_id, capability.resource)
        key = _limits_plan.fingerprint(device, capability, self._site_limits_digest)
        bindings = _limits_plan.device_bindings(device)
        with self._limit_lock:
            plan = self._limit_plans.get(cache_key)
        if plan is not None and plan.key == key and plan.bindings == bindings:
            return plan
        plans, device_error = self._recompile_device_limits(device)
        plan = plans.get((capability.capability_id, capability.resource))
        if plan is not None and plan.key == key:
            return plan
        # Not one of device.capabilities (or changed while compiling): this binding alone.
        effective = (self._effective.get((device.device_id, capability.capability_id, capability.resource))
                     if device.device_id in self._strict_devices else None)
        plan = _limits_plan.compile_binding(
            device, capability, overlay=self.site_limits, overlay_digest=self._site_limits_digest,
            effective=effective, key=key)
        if device_error is not None and plan.error is None and capability.capability_id not in _STOP_CLASSES:
            plan.error = device_error
        return plan

    def _recompile_device_limits(
        self, device: Device
    ) -> tuple[dict[tuple[str, str], _limits_plan.BindingPlan], _limits.LimitConfigError | None]:
        """Compile every binding of ``device`` and run the device-level rules again; cache the plans.

        A binding whose own limits cannot be enforced keeps its error
        (:attr:`BindingPlan.error <mhs._server.limits_plan.BindingPlan.error>`).
        A device-level defect (:func:`mhs._server.limits_plan.check_device_targets`:
        an envelope key that is no capability id or pattern, or that matches no
        bound capability; a pattern path that resolves in no binding it
        matches; an overlay naming an unbound capability or a non-writable
        parameter) -- refused at construction -- is stored on every binding but
        the stop classes, so ``_check_input`` refuses them with
        ``MHS.ADAPTER.MANIFEST_INVALID`` (``limits_invalid``) before any bridge
        call.  Refusing a stop is never the safer outcome.  Returns the plans
        and the device-level defect (or None).
        """
        did = device.device_id
        strict = did in self._strict_devices
        plans: dict[tuple[str, str], _limits_plan.BindingPlan] = {}
        for capability in device.capabilities:
            effective = self._effective.get((did, capability.capability_id, capability.resource)) if strict else None
            plans[(capability.capability_id, capability.resource)] = _limits_plan.compile_binding(
                device, capability, overlay=self.site_limits, overlay_digest=self._site_limits_digest,
                effective=effective)
        device_error: _limits.LimitConfigError | None = None
        duplicates = device.duplicate_pairs() if isinstance(device, Device) else ()
        if duplicates:
            # A pair bound twice after construction (Device(...) and the server
            # start refuse it in every mode): which binding's schema and limits
            # apply is ambiguous, so nothing but a stop is served.
            capability_id, resource = duplicates[0]
            device_error = _limits_plan.located_error(did, capability_id, _limits.LimitConfigError(
                f"is bound to resource {resource!r} more than once; a binding is identified by "
                "(capability_id, resource)", rule="capability-duplicate", path=f"capabilities[{resource}]"))
        try:
            _limits_plan.check_device_targets(device, plans, self.site_limits)
        except _limits.LimitConfigError as exc:
            device_error = device_error or _limits_plan.located_error(did, None, exc)
        except Exception as exc:  # noqa: BLE001 - a defect of the declaration fails closed
            device_error = device_error or _limits_plan.located_error(did, None, _limits.LimitConfigError(
                f"the device limits cannot be checked: {type(exc).__name__}: {exc}"))
        bindings = _limits_plan.device_bindings(device)
        for (capability_id, _resource), plan in plans.items():
            plan.bindings = bindings
            if device_error is not None and plan.error is None and capability_id not in _STOP_CLASSES:
                plan.error = device_error
        with self._limit_lock:
            for key in [key for key in self._limit_plans if key[0] == did]:
                del self._limit_plans[key]
            for (capability_id, resource), plan in plans.items():
                self._limit_plans[(did, capability_id, resource)] = plan
        return plans, device_error

    @staticmethod
    def _limit_error_finding(device: Device, error: _limits.LimitConfigError) -> _strict.Finding:
        return _strict.Finding(
            "limits-invalid", "MHS.ADAPTER.MANIFEST_INVALID", device.device_id,
            f"{error} ({error.rule})", capability_id=getattr(error, "capability_id", None),
            path=error.path)

    def _limit_findings(self, device: Device) -> list[_strict.Finding]:
        """Findings about inputs without an enforceable limit (enforced at runtime, never refusals).

        ``operator-required-unset`` (every mode): a bound declared
        ``operator_required`` that no overlay filled; a call that sets the
        field is ``MHS.SAFETY.LIMITS_UNSET``.  ``limits-unset`` (strict mode
        enforces it): a hardware or hybrid write/invoke at R1 or above with
        numeric inputs no limit covers.
        """
        out: list[_strict.Finding] = []
        did = device.device_id
        for capability in device.capabilities:
            with self._limit_lock:
                plan = self._limit_plans.get((did, capability.capability_id, capability.resource))
            if plan is None or plan.limits is None:
                continue
            if plan.unset:
                out.append(_strict.Finding(
                    "operator-required-unset", "MHS.SAFETY.LIMITS_UNSET", did,
                    f"limits declared operator_required are not filled by site_limits: {list(plan.unset)}; "
                    "a call that sets them is refused", capability_id=capability.capability_id, refuse=False))
            if self._limits_unset_applies(device, capability, plan) and plan.unlimited:
                out.append(_strict.Finding(
                    "limits-unset", "MHS.SAFETY.LIMITS_UNSET", did,
                    f"numeric inputs without a limit: {list(plan.unlimited)} (declare a sourced limit or "
                    "operator_required)", capability_id=capability.capability_id, refuse=False))
        return out

    @staticmethod
    def _limits_unset_applies(device: Device, capability: Capability, plan: _limits_plan.BindingPlan) -> bool:
        """Plan 3.5: hardware or hybrid, risk R1 or above, a write or invoke, not a stop class.

        The verb is the catalogue's.  An extension's (or an uncatalogued id's)
        declared verb is not trusted, as for the latch and arming
        (:meth:`_is_read_capability`): only a catalogued read class is exempt.
        """
        return (device.mode in ("hardware", "hybrid")
                and _RISK_ORDER.get(plan.risk, 0) >= 1
                and (plan.verb in ("write", "invoke") or not plan.catalogued)
                and capability.capability_id not in _STOP_CLASSES)

    def _warn_unknown_overlay_devices(self, *, stacklevel: int) -> None:
        unknown = [did for did in _limits_plan.overlay_device_ids(self.site_limits) if did not in self.devices]
        if unknown:
            warnings.warn(RuntimeWarning(
                f"site_limits names devices this endpoint does not serve: {unknown[:8]}; their entries apply "
                "only if such a device is added later (check the device ids for typos)"), stacklevel=stacklevel)

    def _deployment_findings(self, device: Device) -> list[_strict.Finding]:
        """Endpoint-configuration findings for one device (not refusals).

        Strict mode enforces each at runtime (fail closed): an unarmed
        hardware device refuses actuation, R2+ hardware permits need the
        approval verifier, and only an operator principal (a token) may reset
        a hardware or hybrid device.
        """
        did = device.device_id
        strict = did in self._strict_devices
        out: list[_strict.Finding] = []
        if device.mode == "hardware" and self.armed is None and not strict:
            out.append(_strict.Finding(
                "hardware-armed-implicitly", "MHS.AUTH.HARDWARE_DISABLED", did,
                "hardware actuation is armed implicitly; strict mode refuses it unless "
                "MHSServer(armed=True or [device ids])", refuse=False))
        if device.mode in ("hardware", "hybrid"):
            if (_RISK_ORDER.get(device.safety.risk_class, 0) >= 2
                    and self._approval_verifier is None):
                out.append(_strict.Finding(
                    "approval-verifier-missing", "MHS.SAFETY.APPROVAL_REQUIRED", did,
                    f"no approval_verifier: permits on this {device.safety.risk_class} "
                    f"{device.mode} device are refused in strict mode (fail closed)", refuse=False))
            if not any(principal.get("kind") == "operator"
                       for principal in (self._auth_tokens or {}).values()):
                out.append(_strict.Finding(
                    "operator-token-missing", "MHS.AUTH.FORBIDDEN", did,
                    "no auth_tokens principal of kind 'operator': in strict mode nobody can "
                    f"reset this {device.mode} device", refuse=False))
        return out

    def _is_strict(self, device: Device | None) -> bool:
        """Whether ``device`` is served in strict mode.

        Every device of a strict server is, including one put in
        :attr:`devices` after construction (:meth:`_adopt_late_device`), and
        so is a ``Device(strict=True)`` on any server.
        """
        if self.strict is True:
            return True
        return device is not None and (device.device_id in self._strict_devices
                                       or getattr(device, "strict", None) is True)

    def _served_devices(self) -> list[Device]:
        """The devices this endpoint serves: :attr:`devices` without the late
        ones strict mode refuses (:meth:`_adopt_late_device`).  Used by hello,
        the well-known descriptor, conformance claims and the default device
        list of ``mhs.session.open``; the e-stop still reaches every device."""
        served = []
        for device in list(self.devices.values()):
            try:
                self._adopt_late_device(device)
            except MHSError:
                continue
            served.append(device)
        return served

    def _check_late_recovery(self, device: Device) -> None:
        """CORE-086/CORE-087 for a device put in :attr:`devices` after construction, in every mode.

        Construction refuses a malformed declared recovery (a re-enable or a
        terminal e-stop); a device added or replaced later is checked once per
        object on first use, and a malformed declaration gives
        ``MHS.ADAPTER.MANIFEST_INVALID`` (``details.reason``
        ``estop_recovery_invalid``) before any bridge call.  The e-stop still
        reaches the device (:meth:`_device` with ``adopt=False``).
        """
        did = device.device_id
        if self._recovery_checked.get(did) is device:
            return
        sensed = _sensed_stop_problems(device)
        if sensed:
            raise MHSError(
                "MHS.ADAPTER.MANIFEST_INVALID",
                f"device {did} was added after the endpoint started and declares a sensed-confirmation stop although "
                "it is not simulated",
                {"device_id": did, "retryable": False,
                 "details": {"reason": "sensed_stop_not_simulated", "problems": sensed[:16]},
                 "remediation": "Serve the sensed-confirmation stop on a simulated device only (SAFE-049)."},
            )
        problems = _estop_recovery_problems(device)
        if problems:
            raise MHSError(
                "MHS.ADAPTER.MANIFEST_INVALID",
                f"device {did} was added after the endpoint started and its declared e-stop recovery is malformed",
                {"device_id": did, "retryable": False,
                 "details": {"reason": "estop_recovery_invalid", "problems": problems[:16]},
                 "remediation": "Fix safety.estop.reenable or safety.estop.terminal, or pass the device to "
                                "MHSServer(...) to see the problems at start-up."},
            )
        _bind_sensed_route(device)  # verification F3: bound from the served manifest, as at start-up
        self._recovery_checked[did] = device

    def _adopt_late_device(self, device: Device) -> Device:
        """Resolve a strict device put in :attr:`devices` after construction, on first use.

        Construction resolves the devices it is given (:meth:`_resolve_strict`).
        A device added to the public ``devices`` dict later (or replaced
        there) is resolved here once per object when it is served in strict
        mode: strict resolution refusing it gives ``MHS.ADAPTER.MANIFEST_INVALID``
        with the findings (the e-stop still reaches it); otherwise it serves
        its resolved contract under the strict runtime rules (arming, operator
        reset, verified permits).  A compatibility server serves late devices
        as before; their limits (binding and device-level rules alike) are
        compiled on first use by :meth:`_limit_plan`, and a declaration
        construction would refuse gives ``MHS.ADAPTER.MANIFEST_INVALID``
        (``limits_invalid``) before any bridge call.
        """
        did = device.device_id
        self._check_late_recovery(device)
        if self._adopted.get(did) is device or not self._is_strict(device):
            return device
        # Resolve under a lock of its own (never under self._lock: an e-stop
        # must not wait for it), then register under self._lock.  Both steps
        # are idempotent, so a racing first use only repeats them.
        with self._adopt_lock:
            resolution = getattr(device, "_strict_resolution", None)
            refused = self._late_refused.get(did)
            if resolution is None and refused is not None and refused[0] is device:
                resolution = refused[1]
            if resolution is None:
                resolution = self._resolve_device(device)
            plans, limit_error = self._compile_device_plans(device, resolution, strict=True)
            refusals = list(resolution.refused)
            if isinstance(device, Device) and not any(item.rule == "capability-duplicate" for item in refusals):
                refusals.extend(device.duplicate_findings())  # appended after the device's resolution
            if limit_error is not None and not any(item.rule == "limits-invalid" for item in resolution.findings):
                refusals.append(self._limit_error_finding(device, limit_error))
            if refusals:
                self._late_refused[did] = (device, resolution)
                raise MHSError(
                    "MHS.ADAPTER.MANIFEST_INVALID",
                    f"device {did} was added after the strict endpoint started and strict mode refuses it",
                    {"device_id": did, "retryable": False,
                     "details": {"reason": "strict_refused",
                                 "findings": [finding.to_json() for finding in refusals][:32]},
                     "remediation": "Fix the findings, or pass the device to MHSServer(...) "
                                    "to see them at start-up."},
                )
            if getattr(device, "_strict_resolution", None) is None:
                _strict.apply_strict(device, resolution)
                device._strict_resolution = resolution
            self._store_plans(device, plans)
        with self._lock:
            if self._adopted.get(did) is device:
                return device
            self._late_refused.pop(did, None)
            self._resolutions[did] = resolution
            for key in [key for key in self._effective if key[0] == did]:
                del self._effective[key]
            for (capability_id, resource), resolved in resolution.effective.items():
                self._effective[(did, capability_id, resource)] = resolved
            self._strict_devices.add(did)
            self._strict_findings = [item for item in self._strict_findings if item.get("device_id") != did]
            self._strict_findings.extend(
                {**finding.to_json(), "mode": "strict"}
                for finding in [*resolution.findings, *self._deployment_findings(device),
                                *self._limit_findings(device)]
            )
            self._revisions.setdefault(did, 0)
            self._device_locks.setdefault(did, threading.Lock())
            self._latched.setdefault(did, False)
            self._adopted[did] = device
        return device

    @staticmethod
    def _resolve_device(device: Device) -> _strict.DeviceResolution:
        """:func:`mhs._server.strict.resolve_device`; a resolver defect is a refusing finding."""
        try:
            return _strict.resolve_device(device)
        except Exception as exc:  # noqa: BLE001 - a resolver defect must not hide the device
            return _strict.DeviceResolution(device.device_id, [_strict.Finding(
                "resolution-failed", "MHS.ADAPTER.MANIFEST_INVALID", device.device_id,
                f"the device could not be resolved ({type(exc).__name__}: {exc})")],
                {}, "R0", str(device.safety.risk_class))

    def _is_armed(self, device: Device) -> bool:
        """Whether hardware actuation on ``device`` is armed (``MHSServer(armed=...)``)."""
        armed = self.armed
        if armed is True or armed is False:
            return armed
        if isinstance(armed, frozenset):
            return device.device_id in armed
        return not self._is_strict(device)

    def _hardware_effect(self, device: Device, resource_id: str | None) -> bool:
        """True when an action on ``resource_id`` reaches real hardware."""
        if device.mode == "hardware":
            return True
        if device.mode == "hybrid":
            authority = (device.fidelity or {}).get("authority") or {}
            return authority.get(resource_id or device.primary_resource.resource_id) == "hardware"
        return False

    def _compat_warn(self, key: tuple[Any, ...], message: str) -> None:
        """One :class:`MHSStrictWarning` per ``key`` for a compatibility-mode runtime finding."""
        with self._lock:
            if key in self._compat_warned:
                return
            self._compat_warned.add(key)
        warnings.warn(MHSStrictWarning(message), stacklevel=3)

    # -- principals ------------------------------------------------------
    def _principal_for_token(self, token: Any) -> dict[str, Any] | None:
        """The principal of a bearer token (constant-time compare), or None."""
        tokens = self._auth_tokens
        if not tokens or not isinstance(token, str) or not token:
            return None
        candidate = token.encode("utf-8")
        matched: dict[str, Any] | None = None
        for known, principal in tokens.items():
            # Every token is compared (no early exit), each in constant time.
            if hmac.compare_digest(known.encode("utf-8"), candidate):
                matched = principal
        return dict(matched) if matched is not None else None

    @staticmethod
    def _request_principal() -> dict[str, Any] | None:
        """The token principal of the request being handled (None: unauthenticated)."""
        principal = _REQUEST_PRINCIPAL.get()
        return dict(principal) if isinstance(principal, Mapping) else None

    def _owns_session(self, session: Session) -> bool:
        """A token-bound session is usable only by requests with its principal."""
        if not session.authenticated:
            return True
        caller = self._request_principal()
        return (caller is not None and caller.get("id") == (session.principal or {}).get("id")
                and caller.get("kind") == session.kind)

    # -- bounded dispatch / in-flight identity -------------------------
    def _dispatch_bounded(
        self,
        handler: Callable[["MHSServer", dict[str, Any]], Any],
        params: dict[str, Any],
        deadline_ms: int,
        method: str,
        ingress: float,
    ) -> Any:
        """Run a blocking handler with one monotonic budget (RE-PROTO-004).

        The handler runs in a daemon worker so a slow bridge cannot outlive the
        caller's deadline.  On expiry the caller gets a structured
        ``MHS.OUTCOME.TIMEOUT``; for effectful methods the response says that
        the effect may have occurred and carries the pre-assigned command id so
        the operation can be reconciled instead of blindly retried.
        """
        budget = max(0.0, float(deadline_ms) / 1000.0 - (time.monotonic() - ingress))
        may_have_effect = method in _BOUNDED_MUTATING_METHODS
        if may_have_effect and not params.get("command_id"):
            params["command_id"] = canonical.ulid()
        holder: dict[str, Any] = {}
        abandoned = threading.Event()

        def run() -> None:
            # A handler can ask whether its caller already got the timeout
            # (mhs.safety.reset must not release the latch after that).
            self._dispatch_local.abandoned = abandoned
            try:
                holder["result"] = handler(self, params)
            except BaseException as exc:  # noqa: BLE001 - relayed to the caller
                holder["error"] = exc

        # The worker sees the caller's authenticated principal (_REQUEST_PRINCIPAL).
        context = contextvars.copy_context()
        thread = threading.Thread(target=context.run, args=(run,), name=f"mhs-bounded-{method}",
                                  daemon=True)
        thread.start()
        thread.join(budget)
        if thread.is_alive():
            abandoned.set()
            raise MHSError(
                "MHS.OUTCOME.TIMEOUT",
                f"{method} exceeded its {deadline_ms} ms deadline",
                {
                    "retryable": False,
                    "details": {
                        "method": method,
                        "deadline_ms": deadline_ms,
                        "may_have_effect": may_have_effect,
                        "command_id": params.get("command_id"),
                        "reconcile": (
                            "read state / safety.status and retain the command id; "
                            "do not retry a mutation blindly"
                        ),
                    },
                },
            )
        if "error" in holder:
            raise holder["error"]
        return holder.get("result")

    def _peek_inflight(
        self, device_id: str, command_id: str, digest: str
    ) -> tuple[str, dict[str, Any] | None]:
        """Return ('none'|'inflight'|'conflict', reservation)."""
        key = (device_id, command_id)
        with self._lock:
            entry = self._inflight.get(key)
            if entry is None:
                return "none", None
            if entry.get("digest") != digest:
                return "conflict", entry
            return "inflight", entry

    def _begin_inflight(
        self, device_id: str, command_id: str, digest: str, *,
        session: Session | None = None, capability_id: str | None = None, resource: str | None = None,
        write_ahead: bool = False,
    ) -> tuple[str, dict[str, Any] | None]:
        """Reserve ``(device_id, command_id)`` before any effect (RE-PROTO-002).

        Returns ``('new'|'replay'|'conflict'|'inflight'|'journal_failed',
        reservation)``.  The reservation belongs to the caller that got
        ``'new'``: only it releases it (:meth:`_finish_inflight`).

        Under ``state_dir`` a new reservation is also a journal ``begin``
        line (write-ahead): if the process dies before the final receipt, the
        restarted endpoint records the command as ``unknown`` instead of
        running it again.  ``write_ahead``: the ``begin`` line is the
        command's only crash protection (an effectful command), so when it
        cannot be written the reservation is withdrawn and
        ``'journal_failed'`` returned -- the caller refuses the command before
        any bridge I/O.  Otherwise (reads, stop classes and safe-state
        actions) a failed write is logged and the command runs.
        """
        key = (device_id, command_id)
        with self._lock:
            if key in self._receipts:
                return "replay", None
            entry = self._inflight.get(key)
            if entry is not None:
                if entry.get("digest") != digest:
                    return "conflict", entry
                return "inflight", entry
            entry = {
                "digest": digest,
                "operation": None,
                "event": threading.Event(),
                "started_at": time.time(),
            }
            self._inflight[key] = entry
            store = self._state
            if store is not None:
                device = self.devices.get(device_id)
                begin = {
                    "op": "begin", "device_id": device_id, "command_id": command_id,
                    "input_digest": digest, "capability_id": capability_id, "resource": resource,
                    "session_id": session.session_id if session is not None else None,
                    "principal": _plain(dict(session.principal)) if session is not None else None,
                    "mode": device.mode if device is not None else None,
                    "risk": device.safety.risk_class if device is not None else None,
                    "accepted_at": canonical.now_rfc3339(),
                    "evidence_seq": self._evidence.seq,
                }
                try:
                    store.append(begin)
                except (OSError, TypeError, ValueError) as exc:
                    if not store.closed:
                        _log.error("state_dir %s: the write-ahead begin of command %s on %s was not "
                                   "written (%s: %s)%s", self.state_dir, command_id, device_id,
                                   type(exc).__name__, exc,
                                   "; the command is refused" if write_ahead else "")
                    if write_ahead:
                        self._inflight.pop(key, None)
                        return "journal_failed", None
                else:
                    entry["journaled"] = True
            return "new", entry

    def _finish_inflight(self, device_id: str, command_id: str, digest: str | None = None) -> None:
        """Release the reservation of ``(device_id, command_id)`` (journal ``end``).

        Only the request that made the reservation may release it.  With
        ``digest`` (:meth:`_finish_command`) a reservation for another input
        -- the command a refused duplicate collided with -- is left alone.
        """
        with self._lock:
            key = (device_id, command_id)
            entry = self._inflight.get(key)
            if entry is None or (digest is not None and entry.get("digest") != digest):
                return
            self._inflight.pop(key, None)
            if entry.get("journaled"):
                self._journal({"op": "end", "device_id": device_id, "command_id": command_id})

    def _wait_inflight(self, entry: Mapping[str, Any], timeout_s: float) -> dict[str, Any] | None:
        event = entry.get("event")
        if isinstance(event, threading.Event):
            event.wait(timeout=max(0.0, float(timeout_s)))
        operation = entry.get("operation")
        if operation is not None:
            receipt = operation.final_receipt or operation.receipt
            if isinstance(receipt, Mapping):
                replay = dict(receipt)
                replay["replayed"] = True
                return replay
        return None

    def _consume_permit(
        self,
        session: Session,
        device: Device,
        capability: Capability,
        payload: dict[str, Any],
        input_digest: str,
        permit_id: str,
        *,
        resource_id: str | None,
    ) -> None:
        """Atomically re-check and consume a single-use permit (RE-SAFE-001)."""
        with self._permit_lock:
            self._check_permit(
                session, device, capability, payload, input_digest, permit_id,
                consume=False, resource_id=resource_id,
            )
            permit = self._permits.get(permit_id)
            if permit is None:
                raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit does not exist",
                               {"permit_id": permit_id})
            permit.used = True

    def _return_permit(self, device: Device, permit_id: str | None) -> None:
        """Give back a permit consumed for a command that was then not started.

        Only for a refusal at operation registration (the revision moved,
        plan 3.6 step 12): nothing ran, so the single-use permit is not spent.
        Never after an e-stop of the device, which revokes its permits
        (SAFE-036), nor for an expired permit.
        """
        if not permit_id:
            return
        with self._lock:
            if self._latched.get(device.device_id):
                return
            with self._permit_lock:
                permit = self._permits.get(permit_id)
                if permit is not None and permit.expires_at >= time.time():
                    permit.used = False

    # -- protocol dispatch --------------------------------------------
    def _dispatch_gate_error(self, method: str, params: Mapping[str, Any]) -> MHSError | None:
        """The generic pre-dispatch refusal for ``method``, if any.

        ``mhs.hello`` must come first, and blocking methods carry an integer
        ``deadline_ms`` in ``[1, max_command_deadline_ms]`` (MHS-002 §3 flag D).
        """
        if method != "mhs.hello" and not self._initialized:
            return MHSError("MHS.PROTOCOL.INVALID_REQUEST", "send mhs.hello before other methods")
        if method in _BLOCKING_METHODS:
            deadline = params.get("deadline_ms")
            if not isinstance(deadline, int) or isinstance(deadline, bool) or deadline < 1:
                return MHSError(
                    "MHS.PROTOCOL.DEADLINE_INVALID",
                    "blocking methods require an integer deadline_ms >= 1",
                    {"details": {"method": method}},
                )
            if deadline > _MAX_DEADLINE_MS:
                return MHSError(
                    "MHS.PROTOCOL.DEADLINE_INVALID",
                    f"deadline_ms exceeds max_command_deadline_ms ({_MAX_DEADLINE_MS})",
                    {"details": {"method": method, "max_command_deadline_ms": _MAX_DEADLINE_MS}},
                )
        return None

    def _handle_message(self, message: Any, *, auth: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        """Dispatch one message; ``auth`` is the principal its transport authenticated.

        Without ``auth`` the principal already in effect (an enclosing batch)
        is kept.
        """
        if auth is None:
            return self._dispatch_message(message)
        token = _REQUEST_PRINCIPAL.set(dict(auth))
        try:
            return self._dispatch_message(message)
        finally:
            _REQUEST_PRINCIPAL.reset(token)

    def _dispatch_message(self, message: Any) -> dict[str, Any] | None:
        if isinstance(message, list):
            if not message:
                return protocol.make_error(None, MHSError("MHS.PROTOCOL.INVALID_REQUEST"))
            if len(message) > 64:
                return protocol.make_error(None, MHSError("MHS.PROTOCOL.BATCH_TOO_LARGE"))
            responses = []
            for item in message:
                response = self._handle_message(item)
                if response is not None:
                    responses.append(response.to_dict() if hasattr(response, "to_dict") else response)
            return responses or None
        if not isinstance(message, Mapping):
            return protocol.make_error(None, MHSError("MHS.PROTOCOL.INVALID_REQUEST"))
        ingress = time.monotonic()
        has_id = "id" in message
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}

        def _fail(error: MHSError) -> dict[str, Any] | None:
            # PROTO-005: no response is ever sent to a notification, including
            # when validation fails.
            return None if not has_id else protocol.make_error(request_id, error)

        defect = _envelope_defect(message)
        if defect is not None and _recognisably_estop(method, params):
            # Plan 3.6: an e-stop is never refused before it latched, and a request is an e-stop by what it asks for,
            # not by how well its envelope is written (CORE-076).
            return self._serve_defective_estop(message, defect)
        if message.get("jsonrpc") != "2.0":
            return _fail(MHSError("MHS.PROTOCOL.INVALID_REQUEST", "jsonrpc must be exactly '2.0'"))
        if has_id and (
            not isinstance(request_id, (str, int)) or isinstance(request_id, bool)
        ):
            return protocol.make_error(None, MHSError("MHS.PROTOCOL.INVALID_REQUEST", "id must be a string or integer"))
        if not isinstance(method, str) or not method:
            return _fail(MHSError("MHS.PROTOCOL.INVALID_REQUEST", "method must be a non-empty string"))
        if not isinstance(params, Mapping):
            return _fail(MHSError("MHS.PROTOCOL.INVALID_PARAMS"))
        estop = _is_estop_request(method, params)
        if _has_non_finite(params):
            if not estop:
                # NaN / Infinity are not JSON (RFC 8259); the wire decoders
                # refuse them too (protocol.loads_strict, _decode_wire).  Never
                # reaches a device.
                return _fail(MHSError(
                    "MHS.PROTOCOL.PARSE_ERROR",
                    "NaN and Infinity are not valid JSON numbers",
                    {"details": {"method": method}},
                ))
            # Plan 3.6: an e-stop is never refused before it latched.  Its
            # non-finite values (a 1e999 deadline overflows to inf) become null;
            # the handler then falls back to the device's e-stop budget.
            _log.warning("e-stop %s carried NaN/Infinity values; they were replaced by null", method)
            params = _without_non_finite(params)
        if not has_id and method in _EFFECTFUL_METHODS and not estop:
            # PROTO-005: an effectful method sent as a notification could never
            # be receipted to its caller, so it is not executed.
            _log.warning(
                "dropped JSON-RPC notification for effectful method %s "
                "(send it as a request with an id)", method,
            )
            return None
        # Plan 3.6: an e-stop is never refused by a generic gate before it has
        # latched; the handler sanitises its own deadline (_estop_deadline_ms).
        if not estop:
            gate = self._dispatch_gate_error(method, params)
            if gate is not None:
                return _fail(gate)
        handler = self._METHODS.get(method)
        if handler is None:
            return _fail(
                MHSError("MHS.PROTOCOL.METHOD_NOT_FOUND", f"unknown method {method!r}", {"method": method})
            )
        # A self-bounded method counts its deadline from here, like the
        # bounded dispatcher does (PROTO-011; plan 3.7).
        ingress_token = _REQUEST_INGRESS.set(ingress) if method in _SELF_BOUNDED_METHODS else None
        try:
            if method in _BLOCKING_METHODS and method not in _SELF_BOUNDED_METHODS:
                result = self._dispatch_bounded(handler, dict(params), int(params["deadline_ms"]), method, ingress)
            else:
                result = handler(self, dict(params))
        except MHSError as exc:
            return _fail(exc)
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the wire
            error = MHSError(
                "MHS.INTERNAL.ERROR",
                f"internal error: {type(exc).__name__}",
                {"detail": str(exc)},
                cause=exc,
            )
            if os.environ.get("MHS_DEBUG"):
                error.data["traceback"] = traceback.format_exc()
            return _fail(error)
        finally:
            if ingress_token is not None:
                _REQUEST_INGRESS.reset(ingress_token)
        if not has_id:
            return None
        return protocol.make_result(request_id, result)

    # -- hello / discovery -------------------------------------------
    def _m_hello(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocol_versions")
        if requested is not None:
            if not isinstance(requested, list) or not requested:
                raise MHSError(
                    "MHS.PROTOCOL.VERSION_UNSUPPORTED",
                    "protocol_versions must be a non-empty array of version strings",
                    {"details": {"supported": [MHS_VERSION]}},
                )
            supported = {MHS_VERSION}
            common = [str(v) for v in requested if str(v) in supported]
            if not common:
                raise MHSError(
                    "MHS.PROTOCOL.VERSION_UNSUPPORTED",
                    "no mutually supported protocol version",
                    {"details": {"client": [str(v) for v in requested], "supported": [MHS_VERSION]}},
                )
            self._negotiated_version = common[0]
        else:
            self._negotiated_version = MHS_VERSION
        self._initialized = True
        served = self._served_devices()
        retention_s = self.receipt_retention_s
        retention_days: int | float = (
            retention_s // 86_400 if retention_s % 86_400 == 0 else round(retention_s / 86_400, 6)
        )
        return {
            "server": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "implementation": {"name": _ids.DIST_NAME, "version": _ids.SDK_VERSION},
            "spec_version": _ids.SPEC_VERSION,
            "mhs_version": MHS_VERSION,
            "protocol_versions": [MHS_VERSION],
            "endpoint_id": self.endpoint_id,
            "time": {"now": canonical.now_rfc3339(),
                     "mono_ms": int(time.monotonic() * 1000)},
            "started_at": self._started_at,
            "features": list(self.features)
            + (["replay.seek"] if any(d.mode == "replay" for d in served) else []),
            "limits": {
                "max_request_bytes": 1024 * 1024,
                "max_batch": 64,
                "max_subscriptions": 64,
                "max_rate_per_s": 50,
                "session_max_ttl_s": 86_400,
                # The same retention in two units (EVID-018).  None is pruned
                # before that.  "memory": receipts, the idempotency store and
                # the latch are lost on restart; "state_dir": they survive it
                # (MHSServer(state_dir=...), WP-04 step 4f).
                "receipt_retention_days": retention_days,
                "max_receipt_retention_s": retention_s,
                "receipt_store": "memory" if self.state_dir is None else "state_dir",
                "max_command_deadline_ms": _MAX_DEADLINE_MS,
            },
            # Only claims a device makes (backed by a published report); never a
            # default level for a device that claims nothing.
            "conformance": self._conformance_claims(served),
            "devices": [self._device_summary(d) for d in served],
            "safety": {"certified": False, "notice": "MHS.SAFETY.NOT_CERTIFIED"},
        }

    def _conformance_claims(self, served: Sequence[Device] | None = None) -> list[dict[str, Any]]:
        """The served devices' own conformance claims, de-duplicated (hello, well-known).

        A device without ``conformance.level`` claims nothing and contributes
        nothing: the list is empty rather than a default level.
        """
        claims: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for device in (self._served_devices() if served is None else served):
            claim = device.conformance if isinstance(device.conformance, Mapping) else {}
            level = claim.get("level")
            if not isinstance(level, str) or not level:
                continue
            profile = str(claim.get("profile") or "MHS-Sim")
            digest = claim.get("report_digest")
            key = (profile, level, str(digest or ""))
            if key in seen:
                continue
            seen.add(key)
            entry: dict[str, Any] = {"profile": profile, "level": level}
            if isinstance(digest, str) and digest:
                entry["report_digest"] = digest
            claims.append(entry)
        return claims

    def _m_devices_list(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = params.get("detail")
        full = detail is True or (isinstance(detail, str) and detail == "full")
        device_id = params.get("device_id")
        filters = params.get("filter") if isinstance(params.get("filter"), Mapping) else {}
        devices = []
        for device in list(self.devices.values()):
            if device_id is not None and device.device_id != device_id:
                continue
            try:
                self._adopt_late_device(device)
            except MHSError:
                continue  # a late device strict mode refuses is not served
            if filters.get("mode") and device.mode != filters["mode"]:
                continue
            if filters.get("risk_class") and device.safety.risk_class != filters["risk_class"]:
                continue
            if filters.get("capability") and not any(
                _pattern_matches(str(filters["capability"]), cap.capability_id)
                for cap in device.capabilities
            ):
                continue
            if filters.get("tag"):
                tags = (device.profile or {}).get("tags") or []
                if filters["tag"] not in tags:
                    continue
            devices.append(self._device_manifest(device) if full else self._device_summary(device))
        return {"devices": devices, "count": len(devices)}

    def _m_devices_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """The device manifest, its effective limits and its reference file (plan 3.3 / 3.5).

        Each binding carries ``x-mhs-effective-limits``: the intersected
        limits the runtime enforces (``limits``), cumulative budgets,
        ``operator_required`` bounds still unset, numeric inputs no limit
        covers and what the overlay narrowed.  ``reference`` is the device's
        reference file rendered by :func:`mhs.reference_file.render` with the
        operator overlay (``x-mhs-reference-error`` says why when it cannot be
        rendered, e.g. an uncatalogued capability id).
        """
        device = self._device(params.get("device_id"))
        include_state = params.get("include_state", True) is not False
        out = self._device_manifest(device, include_state=include_state)
        for entry, capability in zip(out.get("capabilities") or [], device.capabilities):
            entry["x-mhs-effective-limits"] = _plain(self._limit_plan(device, capability).to_json())
        reference, problem = self._reference_for(device)
        if reference is not None:
            out["reference"] = reference
        elif problem:
            out["x-mhs-reference-error"] = problem
        return out

    def _reference_for(self, device: Device) -> tuple[dict[str, Any] | None, str | None]:
        """The rendered reference file of ``device`` (cached per manifest and overlay), or the reason."""
        manifest = self._device_manifest(device, include_state=False)
        manifest.pop("instance_id", None)  # a reference file describes the device, not this process
        for resource in manifest.get("resources") or []:
            if isinstance(resource, dict):
                resource.pop("revision", None)
        # safety.estop.native: the manifest's when it states one, otherwise the
        # stop path the runtime calls (None: a software-only latch).
        estop = (manifest.get("safety") or {}).get("estop")
        options: dict[str, Any] = {}
        if not (isinstance(estop, Mapping) and "native" in estop):
            path = self._native_estop_path(device)
            options["estop_native"] = (f"{type(device.bridge).__name__}.estop" if path == "bridge"
                                       else _MOTION_ESTOP if path == "capability" else None)
        # The overlay is recorded only when it has an entry for this device (a
        # site file that names other devices narrows nothing here).
        named = device.device_id in _limits_plan.overlay_device_ids(self.site_limits)
        overlay = self.site_limits if named else None
        try:
            key: Any = canonical.digest({"manifest": manifest, "options": options,
                                         "overlay": self._site_limits_digest if named else None})
        except Exception:  # noqa: BLE001 - not canonical JSON: never cached
            key = None
        cached = self._reference_cache.get(device.device_id)
        if key is not None and cached is not None and cached[0] == key:
            return copy.deepcopy(cached[1]), cached[2]
        reference: dict[str, Any] | None = None
        problem: str | None = None
        try:
            reference = _reference_file.render(manifest, overlay=overlay, **options)
        except Exception as exc:  # noqa: BLE001 - devices.get never fails for the reference
            problem = f"the reference file cannot be rendered: {type(exc).__name__}: {exc}"[:500]
        if key is not None:
            self._reference_cache[device.device_id] = (key, reference, problem)
        return (copy.deepcopy(reference) if reference is not None else None), problem

    def _m_schema_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return a bound capability's schema or a shipped schema document.

        A ``ref`` that is not a bound capability id is resolved only through
        :meth:`mhs.schema.SchemaStore.resolve_public` on a fresh store: a bare
        shipped file name or a known ``$id``.  Paths (``/``, ``\\``, ``..``,
        ``~``, drives, URLs of other hosts) are refused, and a document some
        local caller indexed by path in a long-lived store is never served
        (finding SDK-05).
        """
        ref = params.get("ref")
        ref = ref if isinstance(ref, str) else ""
        if not ref:
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "ref is required", {"details": {"ref": ref}})
        # Optional selectors: a class bound to several resources (or devices)
        # serves the schema of the named binding (bindings are keyed by
        # (capability_id, resource)); without them the first binding's.
        wanted_device = params.get("device_id")
        wanted_resource = params.get("resource")
        for device in self.devices.values():
            if isinstance(wanted_device, str) and wanted_device and wanted_device not in (
                    device.device_id, device.device_id.rsplit("/", 1)[-1]):
                continue
            for cap in device.capabilities:
                if cap.capability_id == ref and (not isinstance(wanted_resource, str)
                                                 or cap.resource == wanted_resource):
                    semantics = dict(cap.semantics or {})
                    resource = device._by_resource.get(cap.resource)
                    schema = {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "capability_id": ref,
                        "title": (cap.title or ref)[:120],
                        "verb": cap.verb if cap.verb in ("read", "write", "invoke", "subscribe", "compose") else "invoke",
                        "resource_kinds": [resource.kind if resource is not None else "generic"],
                        "input_schema": cap.input_schema or {"type": "object"},
                        "output_schema": cap.output_schema or {"type": "object"},
                        "summary": str(semantics.get("summary") or cap.title or f"Capability {ref}"),
                        "tags": list(semantics.get("tags") or ["capability"]),
                    }
                    # MHS-1.0 capability classes are FLAT: never reintroduce the
                    # legacy nested `semantics` object on the wire (SPEC-002).
                    for key in (
                        "units", "effects", "hazards", "preconditions",
                        "postconditions", "determinism", "notes",
                    ):
                        if key in semantics:
                            schema[key] = semantics[key]
                    if cap.determinism:
                        schema.setdefault("determinism", cap.determinism)
                    constraints = cap.published_constraints(self._published_concurrency(device, cap))
                    if constraints:
                        schema["constraints"] = constraints
                        if isinstance(constraints.get("concurrency"), str):
                            schema["concurrency"] = constraints["concurrency"]
                    schema["risk_class"] = device.safety.risk_class
                    if cap.limits:
                        schema["limits"] = dict(cap.limits)
                    return {
                        "ref": ref,
                        "capability_id": ref,
                        "schema": schema,
                        "digest": canonical.digest(schema),
                        "media_type": "application/schema+json",
                    }
        try:
            from .schema import SchemaStore

            document, _base = SchemaStore(autoload=False).resolve_public(ref)
        except Exception as exc:  # noqa: BLE001 - unknown ref is an invalid parameter
            raise MHSError(
                "MHS.PROTOCOL.INVALID_PARAMS",
                "schema ref is not a bound capability id or a shipped schema",
                {"details": {"ref": ref[:200], "error": type(exc).__name__}, "retryable": False},
            ) from exc
        return {
            "ref": ref,
            "schema": document,
            "digest": canonical.digest(document),
            "media_type": "application/schema+json",
        }

    # -- sessions ----------------------------------------------------
    def _session_principal(
        self, auth: Mapping[str, Any] | None, claimed: Any, *, strict: bool
    ) -> tuple[dict[str, Any], str | None, bool]:
        """``(wire principal, authority, authenticated)`` of a new session (plan 3.6 step 1).

        A token principal wins over ``params.principal`` (a different claim is
        kept as ``x-meta.claimed_principal``).  Without a token, a
        self-declared ``human`` or ``operator`` is trusted as declared in
        compatibility mode (warned) and, in strict mode, recorded as
        ``x-meta.claimed_principal`` and authorized as an ``agent``.

        ``x-meta.authenticated``, ``role`` and ``claimed_principal`` are the
        endpoint's (:data:`mhs._server.strict.RESERVED_X_META`): a caller's
        own are dropped, and an unauthenticated principal that carries an
        ``x-meta`` says ``authenticated: false`` (without one, absence means
        unauthenticated).  Only a token principal says ``true``.
        """
        if auth is not None:
            meta: dict[str, Any] = {"authenticated": True}
            if (isinstance(claimed, Mapping) and claimed.get("id")
                    and (str(claimed.get("id")), claimed.get("kind")) != (auth.get("id"), auth.get("kind"))):
                meta["claimed_principal"] = _strict.claimed_summary(claimed)
            return _strict.wire_principal(auth, x_meta=meta), str(auth.get("kind")), True
        claimed = _strict.untrusted_principal(claimed, strict=strict)
        kind = claimed.get("kind")
        if kind in _strict.PRIVILEGED_KINDS:
            if strict:
                wire = {"id": str(claimed.get("id"))[:200], "kind": "agent",
                        "x-meta": {"claimed_principal": _strict.claimed_summary(claimed),
                                   "authenticated": False}}
                return wire, "agent", False
            self._compat_warn(
                ("claimed-principal", str(claimed.get("id")), kind),
                f"{self.endpoint_id}: session.open: self-declared {kind} principal "
                f"{str(claimed.get('id'))!r} without a bearer token -- compatibility mode: trusted as "
                "declared; strict=True records it as claimed_principal and treats it as an agent",
            )
        wire = _strict.wire_principal(claimed)
        if strict and wire.get("kind") not in ("human", "agent", "service"):
            wire["kind"] = "agent"
        if isinstance(wire.get("x-meta"), Mapping):
            wire["x-meta"] = {**wire["x-meta"], "authenticated": False}
        authority = kind if kind in _strict.PRINCIPAL_KINDS else None
        return wire, (authority if not strict or kind in ("agent", "service") else "agent"), False

    def _m_session_open(self, params: dict[str, Any]) -> dict[str, Any]:
        auth = self._request_principal()
        principal = params.get("principal")
        if auth is None:
            principal = principal or {"id": "anonymous", "kind": "service"}
            if not isinstance(principal, Mapping) or not principal.get("id"):
                raise MHSError("MHS.AUTH.PRINCIPAL_REQUIRED", "principal.id is required")
        requested_devices = params.get("device_ids") or [d.device_id for d in self._served_devices()]
        if isinstance(requested_devices, str):
            requested_devices = [requested_devices]
        mode = params.get("mode")
        requested_caps = params.get("capabilities") or []
        if isinstance(requested_caps, str):
            requested_caps = [requested_caps]
        ttl_s = int(params.get("ttl_s") or 600)
        if ttl_s <= 0 or ttl_s > 86_400:
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "ttl_s must be 1..86400")
        granted: dict[str, list[str]] = {}
        #: device_id -> capability_id -> granted resources (a grant is a binding)
        granted_resources: dict[str, dict[str, list[str]]] = {}
        resolved_mode = None
        for requested_device in requested_devices:
            device = self._device(requested_device)
            device_id = device.device_id
            if device.mode == "hardware" and mode == "simulated":
                raise MHSError("MHS.SESSION.MODE_MISMATCH", "cannot request simulated mode on a hardware device")
            if mode is not None and mode != device.mode:
                raise MHSError(
                    "MHS.SESSION.MODE_MISMATCH",
                    f"session mode {mode!r} does not match device mode {device.mode!r}",
                    {"device_id": device_id, "current_revision": self._current_revision(device)},
                )
            resolved_mode = device.mode
            pairs = self._requested_bindings(device, requested_caps)
            granted[device_id] = sorted({capability_id for capability_id, _resource in pairs})
            scoped: dict[str, list[str]] = {}
            for capability_id, resource in pairs:
                scoped.setdefault(capability_id, [])
                if resource not in scoped[capability_id]:
                    scoped[capability_id].append(resource)
            granted_resources[device_id] = scoped
        principal, authority, authenticated = self._session_principal(
            auth, principal,
            strict=self.strict is True or any(self._is_strict(self.devices.get(did)) for did in granted),
        )
        verified_session_approvals: list[dict[str, Any]] = []
        raw_session_approvals = list(params.get("approvals") or [])
        for device_id in granted:
            device = self.devices[device_id]
            if device.mode == "hardware" and device.safety.risk_class == "R3":
                verified_session_approvals.extend(
                    self._verify_approvals(
                        device=device,
                        capability_id="mhs.session.open",
                        resource=device.primary_resource.resource_id,
                        input_digest=action_digest(
                            "mhs.session.open",
                            device.primary_resource.resource_id,
                            {"device_id": device_id, "capabilities": granted[device_id]},
                        ),
                        principal=str(principal.get("id")),
                        approvals=raw_session_approvals,
                    )
                )
        session_id = _new_session_id()
        now = time.time()
        session = Session(
            session_id=session_id,
            principal=dict(principal),
            device_ids=list(granted),
            mode=resolved_mode or "simulated",
            granted=granted,
            ttl_s=ttl_s,
            created_at=now,
            expires_at=now + ttl_s,
            approvals=verified_session_approvals or raw_session_approvals,
            authority=authority,
            authenticated=authenticated,
            granted_resources=granted_resources,
        )
        with self._lock:
            self._sessions[session_id] = session
        self._prune_sessions(now)
        self._ensure_session_reaper()
        return {
            "session_id": session_id,
            # One entry per granted binding (02 §5.1 granted[{device_id, capability_id, resource}]).
            "granted": [
                {"device_id": device_id, "capability_id": capability_id, "resource": resource}
                for device_id, capabilities in granted.items()
                for capability_id in capabilities
                for resource in granted_resources[device_id].get(capability_id, [])
            ],
            "grants": [{"device_id": d, "capabilities": c} for d, c in granted.items()],
            "expires_at": canonical.rfc3339_from_ms(int(session.expires_at * 1000)),
            "mode": session.mode,
            "safety_context": self._safety_context(session),
            "limits": {
                "max_open_operations": 16,
                "max_subscriptions": 64,
                "max_rate_per_s": 50,
                "ttl_s": ttl_s,
            },
        }

    @staticmethod
    def _requested_bindings(device: Device, requested: Sequence[Any]) -> list[tuple[str, str]]:
        """The bindings ``mhs.session.open`` grants on ``device`` (plan 3.6 step 2).

        An item of ``capabilities[]`` is a capability id, a pattern
        (``cap.world.*``) or an object ``{capability_id, resource?}`` naming
        one binding (every binding of the id or pattern when ``resource`` is
        omitted).  An empty request grants every binding.  An unknown id or a
        pattern that matches nothing is ``MHS.CAPABILITY.UNKNOWN``; a resource
        the id is not bound to is ``MHS.CAPABILITY.NOT_BOUND``.
        """
        bindings = list(device._by_binding)
        if not requested:
            return bindings
        out: list[tuple[str, str]] = []
        for item in requested:
            resource: Any = None
            if isinstance(item, Mapping):
                capability_id = item.get("capability_id")
                resource = item.get("resource")
                if not isinstance(capability_id, str) or not capability_id or not (
                        resource is None or isinstance(resource, str)):
                    raise MHSError(
                        "MHS.PROTOCOL.INVALID_PARAMS",
                        "a capabilities[] object needs a string capability_id and an optional string resource",
                        {"retryable": False, "details": {"reason": "capability_request_invalid"}},
                    )
            else:
                capability_id = str(item)
            if "*" in capability_id:
                matches = [pair for pair in bindings if _pattern_prefix_match(capability_id, pair[0])]
                if not matches:
                    raise MHSError(
                        "MHS.CAPABILITY.UNKNOWN",
                        f"capability pattern {capability_id!r} matched nothing",
                        {"device_id": device.device_id, "capability_id": capability_id},
                    )
            else:
                matches = [pair for pair in bindings if pair[0] == capability_id]
                if not matches:
                    device.binding(capability_id)  # raises MHS.CAPABILITY.UNKNOWN
            if resource is not None:
                scoped = [pair for pair in matches if pair[1] == resource]
                if not scoped:
                    raise MHSError(
                        "MHS.CAPABILITY.NOT_BOUND",
                        f"{capability_id} is not bound to resource {resource!r} of {device.device_id}",
                        {"retryable": False,
                         "details": {"device_id": device.device_id, "capability_id": capability_id,
                                     "resource": resource,
                                     "bound_resources": sorted({pair[1] for pair in matches})}},
                    )
                matches = scoped
            out.extend(matches)
        return list(dict.fromkeys(out))

    def _current_revision(self, device: Device) -> int:
        """The device's true current revision (a replay device: the recorded revision it is at)."""
        if device.mode == "replay":
            try:
                recorded = getattr(device.bridge, "current_revision", None)
            except Exception:  # noqa: BLE001 - a closed recording: the endpoint's own count
                recorded = None
            if isinstance(recorded, int) and not isinstance(recorded, bool):
                return recorded
        return int(self._revisions.get(device.device_id, 0))

    def _m_session_heartbeat(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        with self._lock:
            # The expiry timer may have released the session since _session()
            # looked: a heartbeat never revives it.
            lapsed = session.released or session.expired()
            if not lapsed:
                session.expires_at = time.time() + session.ttl_s
        if lapsed:
            if not session.released:
                self._expire_session(session, pop=True)
            raise MHSError("MHS.SESSION.EXPIRED", "session has expired",
                           {"session_id": session.session_id})
        return {
            "session_id": session.session_id,
            "expires_at": canonical.rfc3339_from_ms(int(session.expires_at * 1000)),
            "safety_context": self._safety_context(session),
        }

    def _m_session_close(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        cancelled_operations: list[str] = []
        with self._lock:
            self._sessions.pop(session.session_id, None)
            session.released = True
            for subscription_id, subscription in list(self._subscriptions.items()):
                if subscription.get("session_id") == session.session_id:
                    self._subscriptions.pop(subscription_id, None)
            operations = [
                operation for operation in self._operations.values()
                if operation.session_id == session.session_id and operation.final_receipt is None
            ]
            for permit in self._permits.values():
                if permit.session_id == session.session_id:
                    permit.used = True
        for operation in operations:
            operation.cancel_event.set()
            operation.cancel_reason = "session closed"
            cancelled_operations.append(operation.operation_id)
        receipts = [
            receipt for _digest, receipt in self._receipts.values()
            if receipt.get("session_id") == session.session_id
        ]
        return {
            "session_id": session.session_id,
            "closed_at": canonical.now_rfc3339(),
            "summary": {
                "commands": len(receipts),
                "completed": sum(1 for item in receipts if item.get("status") == "completed"),
                "rejected": sum(1 for item in receipts if item.get("status") == "rejected"),
                "failed": sum(1 for item in receipts if item.get("status") == "failed"),
                "cancelled": sum(1 for item in receipts if item.get("status") == "cancelled"),
                "receipts_head": self._evidence.head_digest,
                "cancellation_pending": bool(cancelled_operations),
                "operation_ids": cancelled_operations,
            },
            "receipts_head": self._evidence.head_digest,
        }

    # -- reads -------------------------------------------------------
    def _m_resource_read(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        device, resource_id = self._locate(session, params.get("device_id"), params.get("resource_id"))
        if not session.granted.get(device.device_id):
            raise MHSError("MHS.SESSION.CAPABILITY_NOT_GRANTED", "session may not read this device")
        if device.mode != "replay":
            return self._read_resource_result(device, resource_id, params)
        # Seeking changes the shared replay cursor. Own the same lane as a
        # snapshot until state and revision have both been captured, so a
        # competing client cannot relabel another frame's state.
        device_lock = self._device_locks.setdefault(device.device_id, threading.Lock())
        if not device_lock.acquire(blocking=False):
            raise MHSError("MHS.DEVICE.BUSY", "replay read requires an idle replay cursor",
                           {"retryable": True})
        try:
            return self._read_resource_result(device, resource_id, params)
        finally:
            device_lock.release()

    def _read_resource_result(
        self, device: Device, resource_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        bridge = self._bridge(device)
        revision_override = None
        filters = params.get("filter") if isinstance(params.get("filter"), Mapping) else {}
        if filters.get("revision") is not None:
            if device.mode != "replay":
                raise MHSError(
                    "MHS.PROTOCOL.INVALID_PARAMS",
                    "filter.revision is only valid on a replay device",
                    {"details": {"mode": device.mode}},
                )
            seek = getattr(bridge, "seek", None)
            if not callable(seek):
                raise MHSError(
                    "MHS.PROTOCOL.UNSUPPORTED_FEATURE",
                    "endpoint does not advertise replay.seek",
                    {"details": {"device_id": device.device_id}},
                )
            revision_override = int(filters["revision"])
            try:
                seek(revision_override)
            except MHSError as exc:
                raise MHSError(
                    "MHS.RESOURCE.UNKNOWN",
                    f"recorded revision {revision_override} is not available",
                    {"details": {"requested_revision": revision_override,
                                 "recorded_revisions": list(getattr(bridge, "revisions", []) or []),
                                 "cause": exc.code},
                     "retryable": False},
                ) from exc
        state = self._read_state(device, resource_id, params.get("fields"))
        resource = device._by_resource.get(resource_id)
        exclusions = list((resource.hash_exclusions if resource else None) or [])
        if params.get("fields"):
            # A partial read hashes the returned subset; the revision still proves
            # the underlying state did not change.
            exclusions = []
        current_revision = self._revisions.get(device.device_id, 0)
        if device.mode == "replay" and getattr(bridge, "current_revision", None) is not None:
            current_revision = int(bridge.current_revision)
        return {
            "device_id": device.device_id,
            "resource_id": resource_id,
            "revision": revision_override if revision_override is not None else current_revision,
            "state": state,
            "state_hash": canonical.state_hash(_plain(state), exclusions),
            "sampled_at": canonical.now_rfc3339(),
        }

    def _m_resource_write(self, params: dict[str, Any]) -> dict[str, Any]:
        """``mhs.resource.write``: a command of the resource's ``cap.device.configure.v1`` binding.

        The write primitive (plan 3.2/3.3): the patch *is* the input of the
        configure binding of the target resource -- its keys are properties
        of the resource's ``state_schema`` (``MHS.RESOURCE.FIELD_UNKNOWN``
        otherwise), ``readOnly`` properties are ``MHS.RESOURCE.NOT_WRITABLE``,
        limits are keyed by state paths, and every rule of ``mhs.command``
        applies in the plan 3.6 order (grant on the binding, latch, arming,
        limits, permit, interlocks, ``expected_revision``).  The receipt
        carries the configure class id and the class output
        ``{applied, revision}``.  A resource without a configure binding is
        ``MHS.RESOURCE.NOT_WRITABLE``: the patch is never passed as the input
        of another class, whose limits are keyed by its own input names
        (fit-lab-instruments ``v_write_coupling``, driver-authoring).
        """
        session = self._session(params.get("session_id"))
        device, resource_id = self._locate(session, params.get("device_id"), params.get("resource_id"))
        supplied_command_id = params.get("command_id")
        if supplied_command_id is not None and not canonical.is_ulid(str(supplied_command_id)):
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "command_id must be a ULID")
        command_id = str(supplied_command_id or canonical.ulid())
        patch = params.get("patch")
        payload = dict(patch) if isinstance(patch, Mapping) else {}
        not_canonical = _non_canonical_input(payload, "patch")
        if not_canonical is not None:
            raise not_canonical
        resource = device._by_resource.get(resource_id)
        deadline_ms = int(params.get("deadline_ms") or 30_000)

        def _reject(error: MHSError) -> dict[str, Any]:
            return self._finish_command(
                session=session,
                device=device,
                capability=None,
                capability_id=_CONFIGURE,
                resource_id=resource_id,
                command_id=command_id,
                input_payload=payload,
                input_digest=action_digest(_CONFIGURE, resource_id, payload),
                status="rejected",
                output=None,
                started=time.time(),
                deadline_ms=deadline_ms,
                permit_id=params.get("permit_id"),
                error=error,
                bump=False,
            )

        if device.mode == "replay":
            return _reject(MHSError("MHS.MODE.READ_ONLY", "replay devices are read-only",
                                    {"retryable": False}))
        if resource is None:
            return _reject(MHSError("MHS.RESOURCE.UNKNOWN",
                                    f"device has no resource {resource_id!r}", {"retryable": False}))
        if not isinstance(patch, Mapping):
            return _reject(MHSError("MHS.CAPABILITY.INPUT_INVALID", "patch must be an object",
                                    {"retryable": False}))
        explicit = params.get("capability_id")
        binding = device._by_binding.get((_CONFIGURE, resource_id))
        if binding is None or (explicit is not None and explicit != _CONFIGURE):
            # SAFE-001 / PROTO-025a: never a generic mutation escape hatch.
            others = [cap.capability_id for cap in device.capabilities
                      if cap.resource == resource_id and cap.verb == "write" and cap.capability_id != _CONFIGURE]
            reason = "configure_unbound" if binding is None else "write_class_not_configure"
            raise MHSError(
                "MHS.RESOURCE.NOT_WRITABLE",
                (f"resource {resource_id!r} has no {_CONFIGURE} binding" if binding is None else
                 f"mhs.resource.write is served by {_CONFIGURE}, not {explicit!r}")
                + (f"; invoke {', '.join(others)} with mhs.command and its class input" if others else ""),
                {"resource_id": resource_id, "retryable": False,
                 "details": {"reason": reason, "write_class": _CONFIGURE, "resource_id": resource_id,
                             "write_capabilities": others},
                 "remediation": f"Bind {_CONFIGURE} to the resource (its writable state_schema properties "
                                "are the parameters), or invoke a write class with mhs.command."},
            )
        return self._run_command(
            session=session,
            device=device,
            capability_id=_CONFIGURE,
            resource_id=resource_id,
            command_id=command_id,
            input_payload=payload,
            expected_revision=params.get("expected_revision"),
            deadline_ms=deadline_ms,
            permit_id=params.get("permit_id"),
        )

    def _m_snapshot(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        device = self._device_from_session(session, params.get("device_id"))
        if device.mode not in ("simulated", "hybrid", "replay"):
            raise MHSError("MHS.PROTOCOL.UNSUPPORTED_FEATURE", "snapshots are only defined for simulated/replay devices",
                           {"retryable": False, "details": {"mode": device.mode}})
        if device.mode == "simulated" and not (device.fidelity or {}).get("snapshot_restore"):
            raise MHSError("MHS.PROTOCOL.UNSUPPORTED_FEATURE", "device declares fidelity.snapshot_restore=false",
                           {"retryable": False})
        device_lock = self._device_locks.setdefault(device.device_id, threading.Lock())
        if not device_lock.acquire(blocking=False):
            raise MHSError("MHS.DEVICE.BUSY", "snapshot requires an idle mutation lane", {"retryable": True})
        try:
            bridge = self._bridge(device)
            raw = _plain(bridge.snapshot(device.device_id))
            state = self._validate_snapshot_state(device, raw)
            revision = self._revisions.get(device.device_id, 0)
            if device.mode == "replay" and getattr(bridge, "current_revision", None) is not None:
                revision = int(bridge.current_revision)
            return {
                "device_id": device.device_id,
                "instance_id": device.instance_id,
                "mode": device.mode,
                "revision": revision,
                # For a single-resource device this is exactly the hash returned by
                # resource.read and carried in receipts, so a snapshot can be
                # compared with a live read.
                "state_hash": self._state_document_hash(device, state),
                "state": state,
                # Backwards-compatible alias used by earlier SDK builds.
                "snapshot": state,
                "snapshot_digest": canonical.digest(state),
                "fidelity_digest": canonical.digest(device.fidelity or {}),
                "created_at": canonical.now_rfc3339(),
            }
        finally:
            device_lock.release()

    def _m_restore(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        device = self._device_from_session(session, params.get("device_id"))
        if params.get("command_id") is not None and not canonical.is_ulid(params["command_id"]):
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "command_id must be a ULID")
        command_id = str(params.get("command_id") or canonical.ulid())
        deadline_ms = int(params.get("deadline_ms") or 30_000)
        started = time.time()
        primary = device.primary_resource.resource_id
        bridge = self._bridge(device)

        def _reject(
            error: MHSError,
            *,
            digest: str | None = None,
            input_payload: dict[str, Any] | None = None,
            bump: bool = False,
            status: str = "rejected",
            revision_before: int | None = None,
            output: Any = None,
        ) -> dict[str, Any]:
            payload = dict(input_payload or {})
            return self._finish_command(
                session=session,
                device=device,
                capability=None,
                capability_id="cap.internal.restore.v1",
                command_id=command_id,
                input_payload=payload,
                input_digest=digest or action_digest("cap.internal.restore.v1", primary, payload),
                status=status,
                output=output,
                started=started,
                deadline_ms=deadline_ms,
                permit_id=None,
                error=error,
                bump=bump,
            )

        if device.mode == "replay":
            return _reject(MHSError(
                "MHS.MODE.READ_ONLY",
                "replay endpoints are read-only; select a recorded revision with "
                "mhs.resource.read filter.revision and hello feature replay.seek",
                {"retryable": False, "details": {"mode": "replay",
                                                  "alternative": "mhs.resource.read filter.revision"}},
            ))
        if device.mode not in ("simulated", "hybrid"):
            return _reject(MHSError("MHS.PROTOCOL.UNSUPPORTED_FEATURE",
                                    "restore is only permitted in simulated or hybrid mode",
                                    {"retryable": False, "details": {"mode": device.mode}}))
        snapshot = params.get("snapshot")
        if not isinstance(snapshot, Mapping):
            return _reject(MHSError("MHS.RESOURCE.STATE_INVALID", "snapshot must be an object",
                                    {"retryable": False}))

        if device.mode == "simulated" and not (device.fidelity or {}).get("snapshot_restore"):
            return _reject(MHSError("MHS.PROTOCOL.UNSUPPORTED_FEATURE",
                                    "device declares fidelity.snapshot_restore=false", {"retryable": False}))
        from .schema import default_store
        defects = default_store().validate(snapshot, "snapshot.schema.json")
        if defects:
            return _reject(MHSError("MHS.CONFLICT.SNAPSHOT_MISMATCH", "invalid snapshot envelope",
                                    {"retryable": False, "details": {"errors": defects[:10]}}))
        if "state" in snapshot and "snapshot" in snapshot:
            if canonical.jcs(snapshot["state"]) != canonical.jcs(snapshot["snapshot"]):
                return _reject(MHSError("MHS.CONFLICT.SNAPSHOT_MISMATCH", "snapshot aliases differ",
                                        {"retryable": False}))
        submitted = snapshot.get("state", snapshot.get("snapshot"))
        if (set(submitted) != {resource.resource_id for resource in device.resources}
                or any(not isinstance(value, Mapping) for value in submitted.values())):
            return _reject(MHSError("MHS.CONFLICT.SNAPSHOT_MISMATCH", "snapshot resource set differs",
                                    {"retryable": False}))
        if snapshot["snapshot_digest"] != canonical.digest(submitted):
            return _reject(MHSError("MHS.CONFLICT.STATE_HASH", "snapshot_digest does not recompute",
                                    {"retryable": False}))

        # LEAD-FID-004: the snapshot identity/fidelity metadata is mandatory;
        # omitting a field must not silently weaken configuration isolation.
        required = ("device_id", "instance_id", "mode", "state_hash", "fidelity_digest")
        missing = [name for name in required if not isinstance(snapshot.get(name), str)]
        if missing:
            return _reject(MHSError(
                "MHS.CONFLICT.SNAPSHOT_MISMATCH",
                "snapshot is missing required identity/fidelity metadata",
                {"retryable": False, "details": {"missing": missing}},
            ))
        if snapshot.get("device_id") != device.device_id:
            return _reject(MHSError("MHS.CONFLICT.SNAPSHOT_MISMATCH",
                                    "snapshot belongs to a different device",
                                    {"retryable": False}))
        if snapshot.get("instance_id") != device.instance_id:
            return _reject(MHSError("MHS.CONFLICT.SNAPSHOT_MISMATCH",
                                    "snapshot belongs to another instance",
                                    {"retryable": False}))
        if snapshot.get("mode") != device.mode:
            return _reject(MHSError("MHS.CONFLICT.SNAPSHOT_MISMATCH",
                                    "snapshot mode does not match the target mode",
                                    {"retryable": False}))
        if snapshot.get("mode") == "hardware":
            return _reject(MHSError("MHS.CONFLICT.SNAPSHOT_MISMATCH",
                                    "hardware snapshots cannot be restored",
                                    {"retryable": False}))
        current_fidelity_digest = canonical.digest(device.fidelity or {})
        if snapshot.get("fidelity_digest") != current_fidelity_digest:
            return _reject(MHSError(
                "MHS.CONFLICT.SNAPSHOT_MISMATCH",
                "snapshot belongs to a different fidelity configuration",
                {"retryable": False,
                 "details": {"snapshot_fidelity_digest": snapshot.get("fidelity_digest"),
                             "current_fidelity_digest": current_fidelity_digest}},
            ))

        try:
            state = self._validate_snapshot_state(device, submitted)
        except MHSError as exc:
            return _reject(exc)
        claimed_hash = str(snapshot["state_hash"])
        if claimed_hash != self._state_document_hash(device, state):
            return _reject(MHSError(
                "MHS.CONFLICT.STATE_HASH",
                "snapshot state_hash does not recompute from its state",
                {"retryable": False, "details": {"expected": claimed_hash}},
            ))

        digest = action_digest("cap.internal.restore.v1", primary, {"snapshot": state})
        retained = self._receipts.get((device.device_id, command_id))
        if retained is not None:
            stored_digest, stored_receipt = retained
            if stored_digest == digest:
                replay = dict(stored_receipt)
                replay["replayed"] = True
                return replay
            return _reject(MHSError("MHS.CONFLICT.COMMAND_ID_REUSE",
                                    "command_id was already used with different input",
                                    {"retryable": False}),
                           digest=digest, input_payload={"snapshot": state})

        peek_state, peek_entry = self._peek_inflight(device.device_id, command_id, digest)
        if peek_state == "conflict":
            return _reject(MHSError("MHS.CONFLICT.COMMAND_ID_REUSE",
                                    "command_id is in flight for a different action",
                                    {"retryable": False}),
                           digest=digest, input_payload={"snapshot": state})
        if peek_state == "inflight" and peek_entry is not None:
            replay = self._wait_inflight(peek_entry, min(1.0, deadline_ms / 1000.0))
            if replay is not None:
                return replay
            raise MHSError("MHS.OUTCOME.TIMEOUT",
                           "an identical restore is already in flight",
                           {"retryable": False,
                            "details": {"command_id": command_id, "may_have_effect": True}})

        device_lock = self._device_locks.setdefault(device.device_id, threading.Lock())
        if not device_lock.acquire(blocking=False):
            return _reject(MHSError("MHS.DEVICE.BUSY", "restore requires an idle mutation lane",
                                    {"retryable": True}), digest=digest, input_payload={"snapshot": state})
        try:
            with self._lock:
                admission_epoch = int((self._estop_state.get(device.device_id) or {}).get("seq", 0))
                self._restore_admissions[device.device_id] = admission_epoch
            with ExitStack() as bridge_admission:
                expected = params.get("expected_revision")
                current_revision = self._revisions.get(device.device_id, 0)
                if expected is not None:
                    try:
                        if type(expected) is not int:
                            raise TypeError("expected_revision must be an integer")
                        expected_int = int(expected)
                    except (TypeError, ValueError):
                        return _reject(MHSError("MHS.CAPABILITY.INPUT_INVALID",
                                                "expected_revision must be an integer"),
                                       digest=digest, input_payload={"snapshot": state})
                    if expected_int != current_revision:
                        return _reject(MHSError("MHS.CONFLICT.REVISION",
                                                "expected_revision does not match",
                                                {"retryable": False,
                                                 "current_revision": current_revision}),
                                       digest=digest, input_payload={"snapshot": state})
                if self._latched.get(device.device_id):
                    # A restore rewrites device state; it is refused while latched.
                    return _reject(_estop_engaged_error(current_revision),
                                   digest=digest, input_payload={"snapshot": state})

                begin_state, inflight_entry = self._begin_inflight(
                    device.device_id, command_id, digest,
                    session=session, capability_id="cap.internal.restore.v1", resource=primary,
                    write_ahead=True,  # a restore rewrites the device state
                )
                if begin_state == "journal_failed":
                    return _reject(_journal_failed_error(command_id), digest=digest, input_payload={"snapshot": state})
                if begin_state in ("replay", "inflight"):
                    replay = None
                    if begin_state == "inflight" and inflight_entry is not None:
                        replay = self._wait_inflight(inflight_entry, min(1.0, deadline_ms / 1000.0))
                    if replay is None:
                        retained = self._receipts.get((device.device_id, command_id))
                        if retained is not None:
                            replay = dict(retained[1])
                            replay["replayed"] = True
                    if replay is not None:
                        return replay
                    raise MHSError("MHS.OUTCOME.TIMEOUT",
                                   "an identical restore could not be observed",
                                   {"retryable": False,
                                    "details": {"command_id": command_id, "may_have_effect": True}})
                if begin_state == "conflict":
                    return _reject(MHSError("MHS.CONFLICT.COMMAND_ID_REUSE",
                                            "command_id was already used or is in flight for a different action",
                                            {"retryable": False}),
                                   digest=digest, input_payload={"snapshot": state})

                def stopped_since_admission() -> bool:
                    with self._lock:
                        return int((self._estop_state.get(device.device_id) or {}).get("seq", 0)) != admission_epoch

                admission = getattr(bridge, "restore_admission", None)
                if callable(admission):
                    try:
                        bridge_admission.enter_context(admission(stopped_since_admission))
                    except MHSError as exc:
                        self._finish_inflight(device.device_id, command_id, digest)
                        return _reject(exc, digest=digest, input_payload={"snapshot": state})
                validator = getattr(bridge, "validate_restore", None)
                if callable(validator):
                    try:
                        validator(state)
                    except MHSError as exc:
                        self._finish_inflight(device.device_id, command_id, digest)
                        return _reject(exc, digest=digest, input_payload={"snapshot": state})
                previous_state: dict[str, Any] = {}
                previous_hash: str | None = None
                try:
                    raw_previous = _plain(bridge.snapshot(device.device_id))
                    previous_state = self._validate_snapshot_state(device, raw_previous)
                    previous_hash = self._state_document_hash(device, previous_state)
                except Exception:  # noqa: BLE001 - best-effort rollback point
                    previous_state = {}
                    previous_hash = None

                revision_before = current_revision
                with self._lock:
                    # Re-checked after the (possibly slow) rollback read, right before
                    # the state is rewritten: an e-stop meanwhile refuses the restore.
                    latched_now = bool(self._latched.get(device.device_id))
                    estop_seq = admission_epoch
                    stopped_since_admission = int((self._estop_state.get(device.device_id) or {}).get("seq", 0)) != estop_seq
                if latched_now or stopped_since_admission:
                    self._finish_inflight(device.device_id, command_id, digest)
                    return _reject(_estop_engaged_error(current_revision),
                                   digest=digest, input_payload={"snapshot": state})
                if bool(getattr(self._dispatch_local, "abandoned", None) and self._dispatch_local.abandoned.is_set()):
                    self._finish_inflight(device.device_id, command_id, digest)
                    return _reject(MHSError("MHS.OUTCOME.TIMEOUT", "restore deadline expired before native setter",
                                           {"retryable": False, "details": {"may_have_effect": False}}),
                                   digest=digest, input_payload={"snapshot": state})
                try:
                    return self._restore_and_receipt(
                        device=device, bridge=bridge, state=state, command_id=command_id,
                        claimed_hash=claimed_hash, previous_state=previous_state,
                        previous_hash=previous_hash, revision_before=revision_before,
                        digest=digest, reject=_reject, session=session, primary=primary, estop_seq=estop_seq,
                    )
                finally:
                    with self._lock:
                        estop_during_restore = int(
                            (self._estop_state.get(device.device_id) or {}).get("seq", 0)) != estop_seq
                    if estop_during_restore:
                        # bridge.restore() may have rewritten the state the e-stop's
                        # stop path had just reached: run the stop path again (not
                        # waited for here; retried in the background until confirmed).
                        self._reassert_estop(device, session, 0.0)
        finally:
            with self._lock:
                self._restore_admissions.pop(device.device_id, None)
            device_lock.release()

    def _restore_and_receipt(
        self,
        *,
        device: Device,
        bridge: Any,
        state: dict[str, Any],
        command_id: str,
        claimed_hash: str,
        previous_state: dict[str, Any],
        previous_hash: str | None,
        revision_before: int,
        digest: str,
        reject: Callable[..., dict[str, Any]],
        session: Session,
        primary: str,
        estop_seq: int,
    ) -> dict[str, Any]:
        """``bridge.restore(state)`` and the restore receipt (the tail of :meth:`_m_restore`)."""
        _reject = reject
        failure: Exception | None = None
        actual_hash: str | None = None
        try:
            bridge.restore(state)
            self._sync_device_state(device)
            actual_document = {
                resource.resource_id: self._read_state(device, resource.resource_id)
                for resource in device.resources
            }
            actual_hash = self._state_document_hash(device, actual_document)
        except Exception as exc:  # a setter/read may have changed state before failing
            failure = exc
        with self._lock:
            interrupted = int((self._estop_state.get(device.device_id) or {}).get("seq", 0)) != estop_seq
        if failure is not None or interrupted or actual_hash != claimed_hash:
            # The bridge did not reach the declared checkpoint.  Never report
            # completed; try to roll back, and report truthfully if we cannot.
            rolled_back = False
            try:
                if previous_state and not interrupted:
                    bridge.restore(previous_state)
                    self._sync_device_state(device)
                    rolled_back = previous_hash is not None and (
                        self._state_document_hash(device, {
                            resource.resource_id: self._read_state(device, resource.resource_id)
                            for resource in device.resources
                        }) == previous_hash
                    )
            except Exception:  # noqa: BLE001 - unknown post-state
                rolled_back = False
            self._finish_inflight(device.device_id, command_id, digest)
            if rolled_back:
                return _reject(MHSError(
                    "MHS.CONFLICT.STATE_HASH",
                    "restore did not reproduce the snapshot state; changes were rolled back",
                    {"retryable": False,
                     "details": {"expected_state_hash": claimed_hash,
                                 "actual_state_hash": actual_hash,
                                 "rolled_back": True}},
                ), digest=digest, input_payload={"snapshot": state}, status="failed",
                   revision_before=revision_before)
            return _reject(MHSError(
                "MHS.OUTCOME.UNKNOWN",
                "restore outcome could not be verified and rollback is not provable",
                {"retryable": False,
                 "details": {"expected_state_hash": claimed_hash,
                             "actual_state_hash": actual_hash,
                             "rolled_back": False}},
            ), digest=digest, input_payload={"snapshot": state}, status="unknown",
               bump=True, revision_before=revision_before)

        self._bump_revision(device, session)
        receipt = self._receipt(
            session=session,
            device=device,
            capability_id="cap.internal.restore.v1",
            resource_ids=[primary],
            command_id=command_id,
            input_payload={"snapshot": state},
            input_digest=digest,
            status="completed",
            output={"restored": True, "state": _plain(state), "state_hash": claimed_hash},
            effects=[{"kind": "simulation.restore", "summary": "state restored from snapshot",
                      "reversible": True, "severity": "R0"}],
            revision_before=revision_before,
        )
        with self._lock:
            self._retain_receipt((device.device_id, command_id), digest, receipt)
        self._finish_inflight(device.device_id, command_id, digest)
        return receipt

    def _validate_snapshot_state(self, device: Device, state: Any) -> dict[str, Any]:
        """A checkpoint is the exact declared resource document, not native-only data."""
        if (not isinstance(state, Mapping)
                or set(state) != {resource.resource_id for resource in device.resources}):
            raise MHSError("MHS.RESOURCE.STATE_INVALID", "snapshot resource set differs from the device",
                           {"retryable": False})
        for resource in device.resources:
            value = state[resource.resource_id]
            if not isinstance(value, Mapping):
                raise MHSError("MHS.RESOURCE.STATE_INVALID", "snapshot resource state must be an object",
                               {"retryable": False})
            errors = schema_validate(value, resource.state_schema or {"type": "object"})
            if errors:
                raise MHSError("MHS.RESOURCE.STATE_INVALID", "snapshot does not match served resource state_schema",
                               {"retryable": False, "details": {"resource_id": resource.resource_id,
                                                                "errors": errors[:10]}})
        return copy.deepcopy(dict(state))

    def _state_from_snapshot(self, device: Device, snapshot: Any) -> dict[str, Any]:
        """Normalise a snapshot payload to a ``{resource_id: state}`` document."""
        raw = snapshot
        if isinstance(raw, Mapping) and "state" in raw and isinstance(raw["state"], Mapping):
            raw = raw["state"]
        elif isinstance(raw, Mapping) and "snapshot" in raw and isinstance(raw["snapshot"], Mapping):
            raw = raw["snapshot"]
        if not isinstance(raw, Mapping):
            return {}
        resource_ids = {resource.resource_id for resource in device.resources}
        if resource_ids.intersection(raw):
            return {str(key): _plain(value) for key, value in raw.items() if key in resource_ids}
        return {device.primary_resource.resource_id: _plain(raw)}

    def _sync_device_state(self, device: Device, state: Mapping[str, Any] | None = None) -> None:
        """Refresh ``Resource.state`` from ``state`` or from the bridge."""
        if state is not None:
            for resource in device.resources:
                if resource.resource_id in state:
                    resource.state = _plain(state[resource.resource_id])
            return
        bridge = device.bridge
        if bridge is None:
            return
        for resource in device.resources:
            try:
                fresh = bridge.read(resource.resource_id)
                if isinstance(fresh, Mapping) and resource.resource_id in fresh and isinstance(
                    fresh[resource.resource_id], Mapping
                ):
                    fresh = fresh[resource.resource_id]
                if isinstance(fresh, Mapping):
                    resource.state = _plain(fresh)
            except Exception:  # noqa: BLE001 - keep the last known state
                continue

    def _state_document_hash(self, device: Device, state: Mapping[str, Any]) -> str:
        """Hash a ``{resource_id: state}`` document with one consistent scope."""
        if len(device.resources) == 1:
            resource = device.primary_resource
            document = state.get(resource.resource_id)
            if isinstance(document, Mapping):
                return canonical.state_hash(_plain(document), resource.hash_exclusions or [])
            return canonical.state_hash(_plain(document or {}), resource.hash_exclusions or [])
        return self._device_state_hash(device, state)

    def _device_state_hash(self, device: Device, state: Mapping[str, Any]) -> str:
        pointers: list[str] = []
        for resource in device.resources:
            if resource.resource_id not in state:
                continue
            for pointer in resource.hash_exclusions or []:
                if isinstance(pointer, str) and pointer.startswith("/"):
                    pointers.append(f"/{resource.resource_id}{pointer}")
        return canonical.state_hash(_plain(state), pointers)

    # -- command -----------------------------------------------------
    def _m_command(self, params: dict[str, Any]) -> dict[str, Any]:
        if params.get("capability_id") == _MOTION_ESTOP:
            # SAFE-040: the catalogue e-stop class latches before the session,
            # mode, command-id and deadline checks of an ordinary command.
            routed = self._command_estop(params)
            if routed is not None:
                return routed
            # Not bound on the target device: an ordinary command after all,
            # so the generic gates _handle_message skipped apply here.
            gate = self._dispatch_gate_error("mhs.command", params)
            if gate is not None:
                raise gate
        session = self._session(params.get("session_id"))
        device = self._device_from_session(session, params.get("device_id"))
        if session.mode != device.mode:
            raise MHSError(
                "MHS.SESSION.MODE_MISMATCH",
                f"session mode {session.mode!r} does not match device mode {device.mode!r}",
                {"device_id": device.device_id, "retryable": False},
            )
        capability_id = params.get("capability_id")
        if not isinstance(capability_id, str) or not capability_id:
            raise MHSError("MHS.CAPABILITY.INPUT_INVALID", "capability_id is required")
        if not _CAPABILITY_ID_RE.match(capability_id):
            raise MHSError(
                "MHS.PROTOCOL.INVALID_PARAMS",
                f"capability_id {capability_id!r} is not a well-formed MHS capability id",
                {"details": {"capability_id": capability_id}},
            )
        payload = params.get("input") or {}
        if not isinstance(payload, Mapping):
            raise MHSError("MHS.CAPABILITY.INPUT_INVALID", "input must be a JSON object")
        not_canonical = _non_canonical_input(payload)
        if not_canonical is not None:
            raise not_canonical
        supplied_command_id = params.get("command_id")
        if supplied_command_id is not None and not canonical.is_ulid(str(supplied_command_id)):
            raise MHSError(
                "MHS.PROTOCOL.INVALID_PARAMS",
                "command_id must be a ULID",
                {"details": {"command_id": supplied_command_id}},
            )
        command_id = str(supplied_command_id or canonical.ulid())
        receipt = self._run_command(
            session=session,
            device=device,
            capability_id=capability_id,
            resource_id=params.get("resource"),
            command_id=command_id,
            input_payload=dict(payload),
            expected_revision=params.get("expected_revision"),
            deadline_ms=int(params.get("deadline_ms") or 30_000),
            permit_id=params.get("permit_id"),
        )
        return receipt

    def _visible_operation(self, session: Session, operation_id: Any) -> Operation:
        """The operation ``operation_id`` as seen by ``session``.

        Strict mode: an operation is visible only to sessions of the principal
        that started it (02 §operations: never another principal's), the same
        id, authorized kind and authentication (:meth:`_owner_of`); others
        get ``MHS.OPERATION.UNKNOWN``, exactly like an unknown id.
        """
        operation = self._operations.get(str(operation_id))
        if operation is not None and operation.session_id != session.session_id:
            device = self.devices.get(operation.device_id)
            if (self._is_strict(device) and operation.owner is not None
                    and operation.owner != self._owner_of(session)):
                operation = None
        if operation is None:
            raise MHSError("MHS.OPERATION.UNKNOWN", f"unknown operation {str(operation_id)[:80]!r}")
        return operation

    @staticmethod
    def _owner_of(session: Session) -> tuple[str, str, bool]:
        """``(principal id, authorized kind, authenticated)``: who owns what ``session`` starts."""
        return (str((session.principal or {}).get("id")), session.kind, bool(session.authenticated))

    def _m_operations_get(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        operation = self._visible_operation(session, params.get("operation_id"))
        return operation.final_receipt or operation.receipt

    def _m_operations_list(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        device_id = params.get("device_id")
        state_filter = params.get("state")
        items = []
        for operation in self._operations.values():
            if operation.session_id != session.session_id:
                continue
            if device_id is not None and operation.device_id != device_id:
                continue
            receipt = operation.final_receipt or operation.receipt or {}
            state = receipt.get("status") or operation.state
            if state_filter is not None and state != state_filter:
                continue
            items.append(
                {
                    "operation_id": operation.operation_id,
                    "device_id": operation.device_id,
                    "capability_id": operation.capability_id,
                    "resource": operation.resource,
                    "state": state,
                    "status": state,
                    "command_id": operation.command_id,
                    "progress": receipt.get("progress"),
                    "accepted_at": receipt.get("accepted_at"),
                }
            )
        return {"operations": items, "count": len(items)}

    def _m_operations_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        operation = self._visible_operation(session, params.get("operation_id"))
        if operation.final_receipt is not None:
            retained = operation.final_receipt
            if retained.get("status") == "completed":
                return retained
            return retained
        if not operation.cancellable:
            raise MHSError("MHS.OPERATION.NOT_CANCELLABLE", "the admitted capability binding is not cancellable")
        operation.cancel_reason = str(params.get("reason") or "cancelled by client")
        operation.cancel_event.set()
        operation.done.wait(min(int(params.get("deadline_ms") or 5000) / 1000.0, 5.0))
        if operation.final_receipt is not None:
            return operation.final_receipt
        # PROTO-003: cancellation is best-effort.  Until the worker (or the
        # endpoint's stop path) has acknowledged, report a non-terminal state
        # with safe_state_achieved=false.  Never claim a physical stop that has
        # not been observed.  The snapshot is not evidence: it carries no
        # outcome fields (a recorded unknown receipt stays in the evidence and
        # the final receipt still reconciles it).
        recorded_unknown = operation.unknown_receipt is not None
        receipt = {key: value for key, value in dict(operation.receipt or {}).items()
                   if key not in ("error", "ended_at", "state_revision_after", "state_hash_after",
                                  "output", "effects", "evidence")}
        receipt["status"] = "running"
        receipt["progress"] = ({"percent": 0} if recorded_unknown
                               else receipt.get("progress") or {"percent": 0})
        receipt["cancellation"] = {
            "requested_at": canonical.now_rfc3339(),
            "requested_by": session.principal.get("id"),
            "reason": operation.cancel_reason,
            "safe_state_achieved": False,
        }
        receipt["x-vendor"] = {
            "cancellation_pending": True,
            "safe_state_achieved": False,
            "operation_id": operation.operation_id,
        }
        operation.receipt = receipt
        return receipt

    # -- subscriptions ----------------------------------------------
    def _m_subscribe(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        streams = params.get("streams") or ["state"]
        if isinstance(streams, str):
            streams = [streams]
        if not isinstance(streams, list) or not streams:
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "streams must be a non-empty array")
        allowed = {"state", "telemetry", "events", "log", "progress", "control"}
        for stream in streams:
            name = stream.get("stream") if isinstance(stream, Mapping) else stream
            if name not in allowed:
                raise MHSError("MHS.PROTOCOL.INVALID_PARAMS",
                               f"unknown subscription stream {name!r}",
                               {"details": {"allowed": sorted(allowed)}})
        max_subscriptions = 64
        max_buffer = 256
        device_id = params.get("device_id")
        expires_at = canonical.rfc3339_from_ms(int((time.time() + session.ttl_s) * 1000))
        # RE-PROTO-005: count and insertion are one atomic transaction, so two
        # concurrent subscribes cannot jointly exceed the advertised limit.
        with self._lock:
            existing = sum(
                1 for sub in self._subscriptions.values()
                if sub.get("session_id") == session.session_id
            )
            if existing >= max_subscriptions:
                raise MHSError(
                    "MHS.LIMIT.SUBSCRIPTION_LIMIT",
                    f"session already holds {existing} subscriptions (limit {max_subscriptions})",
                    {"details": {"active": existing, "max_subscriptions": max_subscriptions},
                     "retryable": False},
                )
            # Unguessable (128 random bits): an SSE selector must not be
            # derivable from another client's id (finding SDK-08).
            subscription_id = "sub_" + secrets.token_hex(16)
            while subscription_id in self._subscriptions:  # pragma: no cover - 2**-128
                subscription_id = "sub_" + secrets.token_hex(16)
            self._subscriptions[subscription_id] = {
                "session_id": session.session_id,
                "device_id": device_id,
                "streams": list(streams),
                "seq": 0,
                "events": [],
                "delivered": 0,
                "dropped": 0,
                "max_buffer": max_buffer,
                "created_at": time.time(),
                "expires_at": expires_at,
            }
        return {
            "subscription_id": subscription_id,
            "seq_start": 1,
            "streams": list(streams),
            "expires_at": expires_at,
            "max_buffer": max_buffer,
        }

    def _m_unsubscribe(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        subscription_id = str(params.get("subscription_id"))
        with self._lock:
            sub = self._subscriptions.get(subscription_id)
            # Only the owning session may end a subscription; another
            # session's id is reported exactly like an unknown one.
            if sub is not None and sub.get("session_id") == session.session_id:
                self._subscriptions.pop(subscription_id, None)
            else:
                sub = None
        if sub is None:
            raise MHSError("MHS.SESSION.UNKNOWN",
                           "unknown subscription for this session",
                           {"details": {"subscription_id": subscription_id[:80]}})
        return {
            "subscription_id": subscription_id,
            "seq_end": sub.get("seq", 0),
            "delivered": sub.get("delivered", 0),
            "dropped": sub.get("dropped", 0),
        }

    # -- safety ------------------------------------------------------
    def _m_safety_status(self, params: dict[str, Any]) -> dict[str, Any]:
        device = self._device(params.get("device_id"), adopt=False)  # readable even when refused
        bridge = self._bridge(device)
        interlocks = _plain(bridge.interlocks() or [])
        status = _plain(bridge.safety_status() or {})
        permits = [
            {"permit_id": p.permit_id, "capability_id": p.capability_id, "used": p.used,
             "expires_at": canonical.rfc3339_from_ms(int(p.expires_at * 1000))}
            for p in self._permits.values()
            if not p.used and p.expires_at > time.time()
        ]
        engaged = bool(self._latched.get(device.device_id, False))
        estop_state = self._estop_state.get(device.device_id) or {}
        estop_block = dict(device.safety.estop or {})
        estop_block.setdefault("kind", "software")
        estop_block.setdefault("latching", True)
        estop_block["engaged"] = engaged
        if engaged:
            # False while the native stop path has not confirmed (SAFE-040: the
            # endpoint keeps retrying in the background).
            estop_block["confirmed"] = bool(estop_state.get("confirmed"))
            if estop_state.get("restored"):
                # Latched by a previous run of this endpoint (state_dir).
                estop_block["restored"] = True
            if estop_state.get("terminal"):
                # CORE-087: a declared terminal e-stop ran here; no reset of this endpoint undoes it.
                estop_block["terminated"] = True
        if self.state_dir is not None:
            # Whether latch.json holds the current latch state (state_dir).
            estop_block["persisted"] = estop_state.get("persisted") is not False
        if engaged and not any(str(i.get("id")) == "estop" for i in interlocks):
            interlocks = list(interlocks) + [
                {"id": "estop", "state": "open", "description": "emergency stop latched"}
            ]
        return {
            "device_id": device.device_id,
            "mode": device.mode,
            "risk_class": device.safety.risk_class,
            "certified": False,
            "estop": estop_block,
            "estop_engaged": engaged,
            "interlocks": interlocks,
            "status": status,
            "permits": permits,
            "safe_state": dict(device.safety.safe_state or {}),
        }

    def _m_safety_estop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Engage the e-stop (SAFE-040; plan 3.6 unconditional rules).

        Never refused for want of a session: a live session supplies the
        principal; an expired session keeps its principal for attribution; an
        unknown or missing session is recorded with the endpoint's anonymous
        principal (:meth:`_estop_principal`).  Any device of the endpoint may be
        stopped, whether or not the session covers it.  Nor is it refused for
        want of ``mhs.hello``, a ULID ``command_id`` or a valid ``deadline_ms``
        (:func:`_is_estop_request`, :func:`_estop_deadline_ms`).  A request that
        names no device on an endpoint that serves several stops all of them
        (:meth:`_estop_devices`).
        """
        entered = time.monotonic()
        session = self._estop_known_session(params.get("session_id"))
        devices = self._estop_devices(session, params.get("device_id"))
        reason = str(params.get("reason") or "emergency stop requested")
        input_payload = {"reason": reason}
        input_digest = canonical.digest(
            {"capability_id": "cap.internal.safety_estop.v1", "reason": reason}
        )
        command_id = _estop_command_id(params.get("command_id"))
        jobs = [
            (device, {
                "session": session if session is not None else self._estop_transient_session(device, params),
                "reason": reason,
                "command_id": command_id,
                "input_payload": input_payload,
                "input_digest": input_digest,
                "deadline_ms": _estop_deadline_ms(params.get("deadline_ms"), self._estop_budget_ms(device)),
                "entered": entered,
            })
            for device in devices
        ]
        return self._engage_estops(jobs)

    def _command_estop(self, params: Mapping[str, Any]) -> dict[str, Any] | None:
        """``mhs.command`` on a bound ``cap.motion.estop.v1`` (SAFE-040).

        Engages the same latch, with the same stop path, as
        ``mhs.safety.estop`` and is just as unconditional: no live session,
        grant, matching session mode, well-formed ``command_id``, object
        ``input`` or valid ``deadline_ms`` is needed.  Returns None when the
        target device does not bind the class (an ordinary unknown capability).
        Without a device on an endpoint that serves several, every device that
        binds the class is stopped.
        """
        entered = time.monotonic()
        session = self._estop_known_session(params.get("session_id"))
        devices = self._estop_devices(session, params.get("device_id"))
        raw_input = params.get("input")
        payload = dict(raw_input) if isinstance(raw_input, Mapping) else {}
        command_id = _estop_command_id(params.get("command_id"))
        jobs = []
        for device in devices:
            bindings = device.bindings_of(_MOTION_ESTOP)
            if not bindings:
                continue
            # Never refused for its resource: the latch covers the whole device.
            capability = device._by_binding.get((_MOTION_ESTOP, str(params.get("resource")))) or bindings[0]
            jobs.append((device, {
                "session": session if session is not None else self._estop_transient_session(device, params),
                "reason": str(payload.get("reason") or _MOTION_ESTOP),
                "command_id": command_id,
                "input_payload": payload,
                "input_digest": _estop_action_digest(capability.resource, payload),
                "deadline_ms": _estop_deadline_ms(params.get("deadline_ms"), self._estop_budget_ms(device)),
                "entered": entered,
                "capability": capability,
            }))
        if not jobs:
            return None
        return self._engage_estops(jobs)

    def _engage_estops(self, jobs: Sequence[tuple[Device, dict[str, Any]]]) -> dict[str, Any]:
        """Engage the e-stop of every ``(device, keyword arguments)`` job; the receipt of the one, or of the worst of several.

        One device takes the plain path.  Several are engaged concurrently, so
        that a stop path which hangs on one never delays the latch of another
        (each :meth:`_engage_estop` sets its latch before any bridge I/O).  The
        result is then one receipt: the first that is not ``completed``, else
        the first, with ``x-vendor.estop`` listing what happened to every
        device.  It is ``completed`` only when every stop path succeeded
        (SAFE-002); a device whose engagement raised is reported ``failed``.
        """
        if len(jobs) == 1:
            device, kwargs = jobs[0]
            return self._engage_estop(device=device, **kwargs)
        _log.info("e-stop without a device on an endpoint that serves several: stopping all %d", len(jobs))
        outcomes: list[Any] = [None] * len(jobs)

        def run(index: int, device: Device, kwargs: dict[str, Any]) -> None:
            try:
                outcomes[index] = self._engage_estop(device=device, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - one device's failure never keeps the others from stopping
                outcomes[index] = exc

        threads = [
            threading.Thread(target=run, args=(index, device, kwargs), name=f"mhs-estop-{index}", daemon=True)
            for index, (device, kwargs) in enumerate(jobs)
        ]
        for thread in threads:
            thread.start()
        # Each engagement is bounded by its own deadline; the margin only keeps a stuck thread from holding the caller.
        end = time.monotonic() + max(kwargs["deadline_ms"] for _device, kwargs in jobs) / 1000.0 + 5.0
        for thread in threads:
            thread.join(max(0.0, end - time.monotonic()))
        receipts = [outcome for outcome in outcomes if isinstance(outcome, dict)]
        if not receipts:
            failure = next((outcome for outcome in outcomes if isinstance(outcome, MHSError)), None)
            if failure is not None:
                raise failure
            raise MHSError("MHS.INTERNAL.ERROR", "no e-stop could be engaged on any device")
        entries = []
        for (device, _kwargs), outcome in zip(jobs, outcomes):
            if isinstance(outcome, dict):
                error = outcome.get("error") if isinstance(outcome.get("error"), Mapping) else {}
                entry = {
                    "device_id": device.device_id,
                    "status": outcome.get("status"),
                    "receipt_id": outcome.get("receipt_id"),
                    "safe_state_achieved": (outcome.get("output") or {}).get("safe_state_achieved"),
                }
                if error:
                    entry["error"] = error.get("mhs_code") or (error.get("data") or {}).get("mhs_code")
            else:
                entry = {"device_id": device.device_id, "status": "failed", "receipt_id": None,
                         "safe_state_achieved": None,
                         "error": outcome.code if isinstance(outcome, MHSError) else "MHS.INTERNAL.ERROR"}
            entries.append(entry)
        chosen = next((r for r in receipts if r.get("status") != "completed"), receipts[0])
        result = copy.deepcopy(chosen)
        unengaged = [entry["device_id"] for entry, outcome in zip(entries, outcomes) if not isinstance(outcome, dict)]
        if unengaged and result.get("status") == "completed":
            # A device whose engagement raised or never answered is not stopped as far as this endpoint can tell.
            result["status"] = "failed"
            result["error"] = {
                "mhs_code": "MHS.SAFETY.SAFE_STATE_UNREACHED",
                "message": "the e-stop could not be engaged on: " + ", ".join(unengaged),
                "retryable": False,
                "details": {"reason": "engagement_failed", "devices": unengaged},
                "remediation": "Use the physical e-stop; inspect the devices.",
            }
        vendor = dict(result.get("x-vendor") or {})
        vendor["estop"] = {"scope": "all_devices", "devices": entries}
        result["x-vendor"] = vendor
        return result

    def _estop_devices(self, session: Session | None, device_id: Any) -> list[Device]:
        """The devices an e-stop request stops.

        The one it names; else the single device of its session; else the only
        device of the endpoint; else, on an endpoint that serves several, all of
        them: a stop that names no device is not refused, it stops everything.
        Never refused for strict resolution (adopt=False): any device of the
        endpoint can be stopped.
        """
        if device_id:
            return [self._device(device_id, adopt=False)]
        if session is not None and len(session.device_ids) == 1 and session.device_ids[0] in self.devices:
            return [self.devices[session.device_ids[0]]]
        if len(self.devices) > 1:
            return list(self.devices.values())
        return [self._device(None, adopt=False)]

    def _serve_defective_estop(self, message: Mapping[str, Any], defect: tuple[str, str]) -> dict[str, Any] | None:
        """Serve an e-stop whose JSON-RPC envelope is defective, then answer with the defect (CORE-076).

        ``jsonrpc`` other than ``"2.0"``, an ``id`` that is not a string or an
        integer and ``params`` that are not an object make the request invalid,
        but they never keep it from latching.  Parameters that cannot be used
        (``params`` not an object, a ``device_id`` that names no device) are
        dropped, so the stop covers every device; non-finite values become null.
        The answer is the error of the defect (``id`` null when the id is
        unusable, no answer to a notification) whose ``details`` say whether the
        stop was served and carry its receipt.
        """
        code, text = defect
        method = message["method"]
        raw = message.get("params")
        params = dict(raw) if isinstance(raw, Mapping) else {}
        if _has_non_finite(params):
            _log.warning("e-stop %s carried NaN/Infinity values; they were replaced by null", method)
            params = _without_non_finite(params)
        _log.warning("e-stop request with a defective envelope (%s) is served anyway", text)
        if not self._names_a_device(params.get("device_id")):
            params.pop("device_id", None)  # an unusable selector never narrows a stop that is already irregular
        if method == "mhs.safety.estop":
            params["reason"] = f"{params.get('reason') or 'emergency stop requested'} (request defect: {text})"
        elif isinstance(params.get("input"), Mapping):
            payload = dict(params["input"])
            payload["reason"] = f"{payload.get('reason') or _MOTION_ESTOP} (request defect: {text})"
            params["input"] = payload
        details: dict[str, Any] = {"estop_served": False, "defect": text}
        ingress = _REQUEST_INGRESS.set(time.monotonic())
        try:
            receipt = self._METHODS[method](self, params)
            details.update(estop_served=True, receipt=receipt)
        except MHSError as exc:
            details["estop_error"] = {"mhs_code": exc.code, "message": exc.message}
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the wire
            details["estop_error"] = {"mhs_code": "MHS.INTERNAL.ERROR", "message": f"internal error: {type(exc).__name__}"}
        finally:
            _REQUEST_INGRESS.reset(ingress)
        if "id" not in message:
            return None
        request_id = message.get("id")
        usable = isinstance(request_id, (str, int)) and not isinstance(request_id, bool)
        served = ("the emergency stop was served anyway" if details["estop_served"]
                  else "the emergency stop could NOT be engaged (see details)")
        return protocol.make_error(request_id if usable else None,
                                   MHSError(code, f"{text}; {served}", {"details": details}))

    def _names_a_device(self, device_id: Any) -> bool:
        if not isinstance(device_id, str) or not device_id:
            return False
        try:
            self._lookup_device(device_id)
        except MHSError:
            return False
        return True

    def _estop_known_session(self, session_id: Any) -> Session | None:
        """The session an e-stop names, live or expired (kept for attribution).

        A token-bound session named by another caller is not used: the e-stop
        still latches, attributed to the caller (:meth:`_estop_principal`).
        """
        if isinstance(session_id, str) and session_id:
            session = self._sessions.get(session_id)
            if session is not None and not self._owns_session(session):
                return None
            return session
        return None

    def _estop_transient_session(self, device: Device, params: Mapping[str, Any]) -> Session:
        """A one-off session for an e-stop sent without a known session."""
        now = time.time()
        return Session(
            session_id=_new_session_id(),
            principal=self._estop_principal(params),
            device_ids=[device.device_id],
            mode=device.mode,
            granted={},
            ttl_s=1,
            created_at=now,
            expires_at=now,
        )

    def _estop_principal(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """Principal recorded for an e-stop sent without a usable session.

        The caller's token principal when its transport authenticated one;
        otherwise an anonymous agent (every caller that reached the endpoint
        may stop it, and a self-declared principal is never trusted).
        """
        caller = self._request_principal()
        if caller is not None:
            return _strict.wire_principal(caller, x_meta={"authenticated": True})
        return {"id": "anonymous", "kind": "agent"}

    def _persist_latch(self, device: Device, latched: bool, reason: str | None) -> bool | None:
        """Write the e-stop latch to ``state_dir`` (called under ``self._lock``).

        The whole ``latch.json`` is replaced atomically (temp file, fsync,
        rename), before any bridge I/O of the e-stop, so a restart comes back
        latched.  Returns None without a state directory, otherwise whether
        the write succeeded.  A failed write never stops the latch (it is
        logged and reported: e-stop ``output.latch_persisted``,
        ``safety.status`` ``estop.persisted``); the next latch write rewrites
        the whole file.
        """
        did = device.device_id
        state = self._estop_state.setdefault(did, _fresh_estop_state())
        state.pop("restored", None)
        store = self._state
        if store is None:
            return None
        self._latch_entries[did] = {
            "latched": bool(latched),
            "reason": reason if latched else None,
            "since": canonical.now_rfc3339() if latched else None,
        }
        try:
            store.write_latches(self._latch_entries)
        except (OSError, TypeError, ValueError) as exc:
            state["persisted"] = False
            _log.error("state_dir %s: the e-stop latch of %s (latched=%s) was not persisted (%s: %s)",
                       self.state_dir, did, latched, type(exc).__name__, exc)
            return False
        state["persisted"] = True
        return True

    def _device_reports_latch(self, device: Device, bridge: Any) -> bool:
        """True when the device reports a latch of its own (SAFE-043 context).

        Read from ``bridge.safety_status()`` (``latched: true`` or
        ``estop.engaged: true``) or, for devices that model the latch as state,
        from a boolean ``latched`` property declared in the primary resource's
        ``state_schema``.  Failures to read count as not latched: the reset is
        then refused, which is the safe direction.
        """
        try:
            status = _plain(bridge.safety_status() or {})
        except Exception:  # noqa: BLE001
            status = {}
        if isinstance(status, Mapping):
            if status.get("latched") is True:
                return True
            estop = status.get("estop")
            if isinstance(estop, Mapping) and estop.get("engaged") is True:
                return True
        resource = device.primary_resource
        properties = (resource.state_schema or {}).get("properties")
        declared = properties.get("latched") if isinstance(properties, Mapping) else None
        if not isinstance(declared, Mapping) or declared.get("type") != "boolean":
            return False
        try:
            state = _plain(bridge.read(resource.resource_id))
        except Exception:  # noqa: BLE001
            return False
        return isinstance(state, Mapping) and state.get("latched") is True

    def _estop_budget_ms(self, device: Device) -> int:
        latency = (device.safety.estop or {}).get("latency_ms")
        if isinstance(latency, int) and not isinstance(latency, bool) and latency > 0:
            return latency
        return _DEFAULT_ESTOP_BUDGET_MS

    def _is_safe_state_action(self, device: Device, capability_id: str | None) -> bool:
        """True for stop classes and ``safe_state.achieved_by`` actions (SAFE-029)."""
        if not capability_id:
            return False
        if capability_id in _STOP_CLASSES:
            return True
        achieved_by = (device.safety.safe_state or {}).get("achieved_by") or []
        return capability_id in {str(item) for item in achieved_by}

    @staticmethod
    def _operation_binding(device: Device, operation: Operation) -> Capability | None:
        """The binding an operation runs, ``(capability_id, resource)``."""
        found = device._by_binding.get((operation.capability_id, str(operation.resource)))
        if found is not None or operation.resource is not None:
            return found
        bindings = device.bindings_of(operation.capability_id)
        return bindings[0] if len(bindings) == 1 else None

    def _device_summary(self, device: Device) -> dict[str, Any]:
        """:meth:`Device.summary` with each binding's ``exclusive`` as the runtime applies it.

        On a hardware or hybrid device a non-read binding takes the device
        lock by default (:meth:`_takes_device_lock`), so its summary says
        ``exclusive: true`` although the binding did not declare it; a stop
        class or ``safe_state.achieved_by`` action never takes it (SAFE-029).
        """
        summary = device.summary()
        if device.mode in ("hardware", "hybrid"):
            for entry, capability in zip(summary.get("capabilities") or [], device.capabilities):
                # serialized holds the device lock too (_takes_device_lock)
                entry["exclusive"] = self._published_concurrency(device, capability) != "shared"
        return summary

    def _takes_device_lock(self, device: Device, capability: Capability | None) -> bool:
        """Plan 3.6 step 12: whether a command holds the device lock (runs exclusively).

        A binding declared ``exclusive`` always does.  On a hardware or hybrid
        device every other binding does too unless its
        :meth:`_effective_concurrency` is ``shared`` (RESIDUAL-B, 4d r3: the
        lock was taken only for an explicit ``exclusive``).  A simulated or
        replay device keeps the declared flag.  Safe-state actions and stop
        classes never wait for the lock (SAFE-029); the caller exempts them.
        """
        if capability is None:
            return True
        if capability.exclusive:
            return True
        if device.mode not in ("hardware", "hybrid"):
            return False
        return self._effective_concurrency(device, capability) != "shared"

    def _effective_concurrency(self, device: Device, capability: Capability) -> str:
        """The concurrency a binding of a hardware or hybrid device runs with (plan 3.6 step 12).

        ``exclusive`` for a binding declared ``exclusive``.  A read
        (:meth:`_is_read_capability`: a catalogued read class; an extension's
        own ``verb: read`` is not trusted) is ``shared`` unless the binding
        declares ``exclusive`` or ``serialized`` (CAP-014).  Any other binding
        takes the stricter of its own ``constraints.concurrency`` and its
        class's ``concurrency`` (spec 00 section 6; ADPT-025: a binding is
        never weaker than its class), and ``exclusive`` when neither declares
        one.  ``serialized`` holds the device lock like ``exclusive``.
        """
        if capability.exclusive:
            return "exclusive"
        declared = (capability.constraints or {}).get("concurrency")
        declared = declared if declared in _CONCURRENCY_RANK else None
        if self._is_read_capability(capability):
            return declared if declared in ("exclusive", "serialized") else "shared"
        found = [value for value in (declared, self._class_concurrency_of(capability.capability_id)) if value]
        if not found:
            return "exclusive"
        return max(found, key=lambda value: _CONCURRENCY_RANK[value])

    def _published_concurrency(self, device: Device, capability: Capability) -> str | None:
        """The ``constraints.concurrency`` a manifest publishes for a binding (None: the declared constraints).

        On a hardware or hybrid device: :meth:`_effective_concurrency`, but
        ``shared`` for a stop class or ``safe_state.achieved_by`` action,
        which never takes the device lock (SAFE-029).  A simulated or replay
        device publishes what the binding declares (:meth:`Capability.published_constraints`).
        """
        if device.mode not in ("hardware", "hybrid"):
            return None
        if self._is_safe_state_action(device, capability.capability_id):
            return "shared"
        return self._effective_concurrency(device, capability)

    def _class_concurrency_of(self, capability_id: str) -> str | None:
        """The catalogue ``concurrency`` of a class (None for an extension, an uncatalogued id or no value)."""
        if capability_id in self._class_concurrencies:
            return self._class_concurrencies[capability_id]
        if _catalog.is_extension(capability_id):
            found: str | None = None
        else:
            try:
                entry = _catalog.get(capability_id)
            except Exception:  # noqa: BLE001 - no catalogue: the hardware default applies, retry next time
                return None
            found = None
            if isinstance(entry, Mapping):
                value = entry.get("concurrency")
                if value is None and isinstance(entry.get("constraints"), Mapping):
                    value = entry["constraints"].get("concurrency")
                found = value if value in _CONCURRENCY_RANK else None
        self._class_concurrencies[capability_id] = found
        return found

    def _device_manifest(self, device: Device, **options: Any) -> dict[str, Any]:
        """:meth:`Device.manifest` with each binding's published concurrency (:meth:`_published_concurrency`)."""
        return device.manifest(concurrency=lambda capability: self._published_concurrency(device, capability),
                               **options)

    def _is_read_capability(self, capability: Capability | None) -> bool:
        """True when ``capability`` counts as a read for the e-stop latch and reset.

        A binding's declared verb is not trusted on its own: a mis-declared
        binding must never run while latched.  A ``cap.*`` class is a read only
        when its declared verb and its catalogue verb are both ``read``.  An
        extension id (``x-cap.*``, ``cap.x.*``), whose verb the catalogue cannot
        confirm, is never a read here (fail closed: it is latched like any
        action).  An uncatalogued ``cap.*`` id, or a catalogue that cannot be
        loaded, is not a read either.
        """
        if capability is None or capability.verb != "read":
            return False
        capability_id = capability.capability_id
        if _catalog.is_extension(capability_id):
            return False
        if capability_id not in self._class_verbs:
            try:
                entry = _catalog.get(capability_id)
            except Exception:  # noqa: BLE001 - no catalogue: fail closed, retry next time
                return False
            self._class_verbs[capability_id] = (
                str(entry.get("verb")) if isinstance(entry, Mapping) and entry.get("verb") else None
            )
        return self._class_verbs[capability_id] == "read"

    def _native_estop_path(self, device: Device) -> str | None:
        """'bridge' (Bridge.estop is implemented), 'capability' (a bound
        cap.motion.estop.v1 is the native stop) or None (software latch only).

        Decided on the bindings served now (:meth:`Device.bindings_of`): an
        e-stop binding removed after start-up is no stop path -- a hardware
        device then reports ``SAFE_STATE_UNREACHED`` (``no_stop_path``) instead
        of an e-stop "engaged" that called nothing (4d r2 verifier blocker) --
        and one added after start-up is called.
        """
        bridge = device.bridge
        if bridge is None:
            return None
        if _bridge_overrides_estop(bridge):
            return "bridge"
        if device.bindings_of(_MOTION_ESTOP):
            return "capability"
        return None

    def _engage_estop(
        self,
        *,
        device: Device,
        session: Session,
        reason: str,
        command_id: str,
        input_payload: dict[str, Any],
        input_digest: str,
        deadline_ms: int,
        entered: float,
        capability: Capability | None = None,
    ) -> dict[str, Any]:
        """Latch, cancel, then stop the device within a bounded budget.

        Order (plan 3.6): (1) under the global lock set the latch (and persist
        it: :meth:`_persist_latch`), set ``cancel_event`` on every running
        operation of the device and revoke its permits (SAFE-036); (2) run the
        native e-stop and every ``safe_state.achieved_by`` action in a daemon
        worker (:meth:`_run_estop_attempt`: the actions run once the native
        stop answered, or once the e-stop budget is spent while it is still
        pending); (3) wait at most ``safety.estop.latency_ms`` (default 1000 ms)
        and never past the caller's deadline.  A stop path that did not
        confirm in time, raised anything, or does not exist on a hardware or
        hybrid device gives a ``failed`` receipt with
        ``MHS.SAFETY.SAFE_STATE_UNREACHED``; the latch stays engaged and the
        stop path is retried in the background until it succeeds or the device
        is reset.

        A retried ``command_id`` replays its receipt while the device is
        latched.  When the latch was restored at start-up (``state_dir``) and
        nothing has confirmed its stop path since, the replay also runs the
        stop path again, waits for it like an e-stop and keeps retrying it in
        the background (SAFE-040: the previous run's retry ended with it).
        """
        did = device.device_id
        started = time.time()
        with self._lock:
            retained = self._receipts.get((did, command_id))
            rerun = (self._rerun_restored_stop_path_locked(device)
                     if retained is not None and self._latched.get(did) else None)
        if retained is not None and rerun is not None:
            attempt, generation, rerun_reason = rerun
            self._await_stop_path(device, session, attempt, generation, rerun_reason,
                                  deadline_ms / 1000.0 - (time.monotonic() - entered))
            replay = dict(retained[1])
            replay["replayed"] = True
            return replay
        with self._lock:
            retained = self._receipts.get((did, command_id))
            if retained is not None and self._latched.get(did):
                replay = dict(retained[1])
                replay["replayed"] = True
                return replay
            if retained is not None:
                command_id = canonical.ulid()
            self._latched[did] = True
            latch_persisted = self._persist_latch(device, True, reason)
            state = self._estop_state.setdefault(did, _fresh_estop_state())
            # A reset that is in flight now must not release this e-stop.
            state["seq"] = int(state.get("seq", 0)) + 1
            state["reason"] = reason
            if state.get("confirmed") is not True:
                state["confirmed"] = False
            cancelled: list[str] = []
            for operation in self._operations.values():
                # A running stop / safe-state action is never cancelled by the
                # e-stop it serves.
                if (operation.device_id == did and operation.final_receipt is None
                        and not self._is_safe_state_action(device, operation.capability_id)):
                    operation.cancel_reason = f"emergency stop: {reason}"
                    operation.cancel_event.set()
                    cancelled.append(operation.operation_id)
            # SAFE-036: an e-stop revokes every outstanding permit for the device.
            for permit in self._permits.values():
                if permit.device_id in (None, did):
                    permit.used = True
            attempt = state.get("attempt")
            if attempt is None or attempt.done.is_set():
                attempt = self._start_estop_attempt(device, reason)
                state["attempt"] = attempt
                state["confirmed"] = False
            generation = state.get("generation", 0)
        latch_latency_ms = int((time.monotonic() - entered) * 1000)
        budget_s = min(
            self._estop_budget_ms(device) / 1000.0,
            max(0.0, deadline_ms / 1000.0 - (time.monotonic() - entered)),
        )
        attempt.done.wait(budget_s)
        finished = attempt.done.is_set()
        ok = finished and attempt.ok
        latency_ms = int((time.monotonic() - entered) * 1000)
        native = "timeout" if attempt.native == "pending" else attempt.native
        retrying = not ok and (not finished or attempt.reason not in ("no_stop_path", "safe_state_unbound"))
        with self._lock:
            if ok:
                # Only the current attempt of this latch generation confirms:
                # a newer e-stop that started its own attempt meanwhile (and
                # may have failed) is not overwritten.
                if (not self._closed and self._latched.get(did)
                        and state.get("generation", 0) == generation
                        and state.get("attempt") is attempt):
                    state["confirmed"] = True
            elif retrying:
                state.setdefault("unconfirmed", []).append(command_id)
        error: MHSError | None = None
        if not ok:
            # CORE-086: an attempt that waits for the commands in flight to settle
            # (and then stops again) is not a stop that answered late. The label and
            # the list come from the operations still in flight now (verification
            # F2, review S10-5): once they have settled, a stop that has not
            # answered is a timeout like any other.
            still = self._still_in_flight(attempt.awaiting) if not finished else []
            failure = attempt.reason if finished else ("command_in_flight" if still else "timeout")
            details: dict[str, Any] = {
                "reason": failure,
                "latched": True,
                "native": native,
                "budget_ms": int(round(budget_s * 1000)),
                "retrying": retrying,
            }
            if failure == "command_in_flight":
                details["awaiting_operations"] = still
            if attempt.native_error:
                details["native_error"] = dict(attempt.native_error)
            if attempt.failed_actions:
                details["failed_actions"] = [dict(item) for item in attempt.failed_actions]
            if attempt.bridge_safe_state is False:
                details["bridge_safe_state"] = False
            if finished and attempt.sensed is not None:
                # SAFE-049 / CORE-088: why the sensed confirmation did not confirm (no new CORE-077 reason).
                details["sensed"] = copy.deepcopy(attempt.sensed)
            messages = {
                "timeout": "the device did not confirm the e-stop within its budget",
                "command_in_flight": "a command already sent to the device when the e-stop landed has not "
                                     "settled; the stop is sent again once it has, and only that stop confirms",
                # (once the commands settled, a stop that has not answered is reported as "timeout")
                "native_failed": "the native e-stop failed",
                "action_failed": "a safe-state action failed",
                "no_stop_path": "no native e-stop and no safe-state action: only the software latch is engaged",
                "safe_state_unbound": "safe_state.achieved_by names an action the device does not bind",
                "bridge_reports_unsafe": "the device reports that its safe state was not reached",
            }
            error = MHSError(
                "MHS.SAFETY.SAFE_STATE_UNREACHED",
                messages.get(str(failure), "the e-stop could not be confirmed")
                + "; the latch stays engaged" + ("; retrying in the background" if retrying else ""),
                {"retryable": False, "details": details,
                 "remediation": "Use the physical e-stop; inspect the device."},
            )
        if capability is not None:
            output: dict[str, Any] = {
                "engaged": True,
                "latched": True,
                "latency_ms": latency_ms,
                "safe_state_achieved": bool(ok),
            }
        else:
            output = {
                "estop": native,
                "latched": True,
                "latency_ms": latency_ms,
                "latch_latency_ms": latch_latency_ms,
                "safe_state_achieved": bool(ok),
                "safe_state": dict(device.safety.safe_state or {}),
                "cancelled_operations": cancelled,
            }
        if latch_persisted is not None:  # MHSServer(state_dir=...)
            output["latch_persisted"] = latch_persisted
        # Safe-state commands the ROS bridge answered from a stop request this e-stop already sent and saw
        # confirmed: x-vendor, because cap.motion.estop.v1's output schema is closed.
        vendor = ({"shared_stop_requests": [dict(item) for item in attempt.shared_stops]}
                  if finished and attempt.shared_stops else None)
        if ok and attempt.sensed is not None:
            # SAFE-049 / SAFE-044: the confirmation window that achieved the safe state, and nothing beyond it.
            vendor = dict(vendor or {}, sensed_confirmation=copy.deepcopy(attempt.sensed))
        try:
            receipt = self._finish_command(
                session=session,
                device=device,
                capability=capability,
                capability_id="cap.internal.safety_estop.v1" if capability is None else None,
                command_id=command_id,
                input_payload=input_payload,
                input_digest=input_digest,
                status="completed" if ok else "failed",
                output=output,
                started=started,
                deadline_ms=deadline_ms,
                permit_id=None,
                error=error,
                effects=[{"kind": "safety.estop", "summary": "emergency stop engaged",
                          "reversible": False, "severity": "R0"}],
                # Always bounded: a stop path that answered says nothing about a
                # read that waits on a lock a running call holds.
                read_timeout_s=max(0.002, min(
                    _ESTOP_READ_BOUND_S,
                    deadline_ms / 1000.0 - (time.monotonic() - entered),
                )),
                vendor=vendor,
            )
            self._notify("safety", did, {"estop": "engaged", "latched": True, "reason": reason,
                                         "native": native, "safe_state_achieved": bool(ok)})
            return receipt
        finally:
            # Native stop progress must not depend on successful evidence I/O.
            # Preserve a recording exception for the caller, but still supervise
            # a retryable failed stop (SAFE-040 / CORE-077).
            if retrying:
                self._ensure_estop_supervisor(device, session, reason, generation)

    def _still_in_flight(self, operation_ids: Sequence[str]) -> list[str]:
        """The operations of ``operation_ids`` that have not settled yet (CORE-086; verification F2)."""
        with self._lock:
            return [operation_id for operation_id in operation_ids
                    if (operation := self._operations.get(operation_id)) is not None and not operation.done.is_set()]

    def _start_estop_attempt(self, device: Device, reason: str) -> _EstopAttempt:
        """Run the stop path once in a daemon worker (caller holds ``self._lock``)."""
        attempt = _EstopAttempt()
        state = self._estop_state.setdefault(device.device_id, {})
        if _estop_terminal(device) is not None:
            # CORE-087: once this endpoint starts the stop path of a device
            # whose e-stop is declared terminal, no reset of this endpoint
            # undoes it (set before any bridge I/O of the attempt).
            state["terminal"] = True
        state["attempts"] = int(state.get("attempts", 0)) + 1
        # Every native stop still in flight blocks a reset (_stop_path_pending),
        # not only the current attempt: a re-assert may replace a pending one.
        state["pending_attempts"] = [
            item for item in state.get("pending_attempts") or [] if not item.done.is_set()
        ] + [attempt]
        # CORE-086: on a device that declares a re-enable (its stop leaves it
        # disabled), a command already dispatched when this stop path starts may
        # land after the native stop and leave the device enabled: the re-enable
        # itself, or an upstream cancel path that re-arms the device after its own
        # quick-stop.  The attempt therefore stops at once, waits for every
        # effectful command of the device that is still in flight to settle (stop
        # and safe-state actions are the stop; reads, as the latch counts them,
        # actuate nothing) and runs the stop path again; it is not done, and the
        # stop not confirmed, before that second run.  A device without a declared
        # re-enable keeps the single run.
        settle: list[Operation] = []
        if _estop_reenable(device) is not None:
            settle = [operation for operation in self._operations.values()
                      if operation.device_id == device.device_id and not operation.done.is_set()
                      and not self._is_safe_state_action(device, operation.capability_id)
                      and not self._is_read_capability(self._operation_binding(device, operation))]
        attempt.awaiting = [operation.operation_id for operation in settle]

        def run() -> None:
            try:
                self._run_estop_attempt(device, reason, attempt)
                if settle:
                    for operation in settle:
                        _await_settled(operation)
                    for name in ("native_error", "reason", "bridge_safe_state", "sensed"):
                        setattr(attempt, name, None)
                    attempt.native, attempt.failed_actions, attempt.ok = "pending", [], False
                    # The receipt describes the run that confirms: only the stop requests this run shared
                    # (CORE-074), not those of the run before the commands in flight settled.
                    attempt.shared_stops = []
                    self._run_estop_attempt(device, reason, attempt)
                    attempt.resent = True
            except BaseException as exc:  # noqa: BLE001 - never leave an attempt open
                attempt.ok = False
                attempt.reason = attempt.reason or "native_failed"
                attempt.native_error = attempt.native_error or _describe_exception(exc)
            finally:
                attempt.ended = time.monotonic()
                attempt.done.set()

        thread = threading.Thread(
            target=run, name=f"mhs-estop-{device.device_id.rsplit('/', 1)[-1]}", daemon=True
        )
        attempt.thread = thread
        thread.start()
        return attempt

    def _run_estop_attempt(self, device: Device, reason: str, attempt: _EstopAttempt) -> None:
        """One run of the stop path: the native e-stop, then every safe-state action.

        ``safe_state.achieved_by`` is an independent path to the safe state, so
        a hung native stop must not hold it back: the native call runs in its
        own daemon thread and the actions start as soon as it answered or once
        the device's e-stop budget is spent, whichever comes first.  The
        attempt is finished only when both are done.

        Every action is called.  On an SDK-owned ROS route
        (:func:`_sdk_ros_route`) each call gets ``ctx.extra["estop_shared"]``, a
        report list of that call only: the ROS bridge answers a safe-state
        command whose request (service or action, type, profile, literal
        request, success predicate, timeout) this e-stop already sent and saw
        confirmed successful from that request's response, checks the
        command's own output contract, and reports ``{same_request_as}`` there;
        the attempt lists it in ``shared_stops`` (CORE-074). After any other
        outcome of that request the command sends its own.
        The server never skips an action.  A retry (SAFE-040) is a new attempt
        and sends the stop again.
        """
        bridge = device.bridge
        path = self._native_estop_path(device)
        native_done = threading.Event()
        # Review S10-2: each run (the first, and the run after the commands in flight settled) takes its settle
        # budget from its own start, never from the first run's.
        run_started = time.monotonic()

        def native() -> None:
            try:
                if path == "bridge":
                    _plain(bridge.estop(reason))
                else:
                    # Every binding of the e-stop class (one per arm, say): the
                    # first failure fails the attempt, after all were tried.
                    # No binding left to call is a failure, never "engaged"
                    # (fail closed: the stop path was chosen on a binding).
                    bindings = device.bindings_of(_MOTION_ESTOP)
                    if not bindings:
                        raise RuntimeError(f"no {_MOTION_ESTOP} binding is left to call")
                    failure: BaseException | None = None
                    for capability in bindings:
                        ctx = _Context(device_id=device.device_id, resource=capability.resource,
                                       mode=device.mode, cancel_event=threading.Event(),
                                       deadline_ms=self._estop_budget_ms(device), extra={"estop": True})
                        try:
                            _plain(bridge.call(_MOTION_ESTOP, {"reason": reason}, ctx))
                        except BaseException as exc:  # noqa: BLE001 - stop the others too
                            failure = failure or exc
                    if failure is not None:
                        raise failure
                attempt.native = "engaged"
            except BaseException as exc:  # noqa: BLE001 - any failure is "unreached"
                attempt.native = "failed"
                attempt.native_error = _describe_exception(exc)
            finally:
                native_done.set()

        if path is None:
            attempt.native = "software_only"
            native_done.set()
        else:
            threading.Thread(
                target=native, name=f"mhs-estop-native-{device.device_id.rsplit('/', 1)[-1]}",
                daemon=True,
            ).start()
            native_done.wait(self._estop_budget_ms(device) / 1000.0)
        attempt.failed_actions = self._run_safe_state_actions(
            device, skip=(_MOTION_ESTOP,) if path == "capability" else (), shared=attempt.shared_stops,
        )
        native_done.wait()
        with self._lock:
            restoring = device.device_id in self._restore_admissions
        if not restoring:
            # A simulator bridge (the SDK's own settle_native_work) gets the rest of the budget to let a
            # native step or reset already in flight end; its safety_status then decides. A checkpoint
            # restore is never waited for: it is reported unachieved just below, it refuses itself at its
            # next check, and its end re-asserts the stop path (_reassert_estop) -- a wait would only
            # delay this answer. A restore admitted after the latch is refused before it takes the bridge.
            _settle_native_work(bridge, self._estop_budget_ms(device) / 1000.0 - (time.monotonic() - run_started))
        attempt.bridge_safe_state, attempt.sensed = _bridge_safety_report(bridge)
        with self._lock:
            if restoring or device.device_id in self._restore_admissions:
                # A software latch cannot stop an opaque checkpoint setter that
                # still owns admission. Do not acknowledge achieved safety; a
                # restore seen at the first sample counts even if its admission
                # was dropped before this second one (verification F1).
                attempt.bridge_safe_state = False
        has_stop_path = path is not None or bool(
            (device.safety.safe_state or {}).get("achieved_by") or []
        )
        if attempt.native == "failed":
            attempt.reason = "native_failed"
        elif attempt.failed_actions and all(
            (item.get("error") or {}).get("type") == "NotBound" for item in attempt.failed_actions
        ):
            attempt.reason = "safe_state_unbound"  # a manifest error; retrying cannot fix it
        elif attempt.failed_actions:
            attempt.reason = "action_failed"
        elif not has_stop_path and device.mode in ("hardware", "hybrid"):
            attempt.reason = "no_stop_path"
        elif attempt.bridge_safe_state is False:
            attempt.reason = "bridge_reports_unsafe"
        attempt.ok = attempt.reason is None

    def _run_safe_state_actions(self, device: Device, *, skip: Sequence[str] = (),
                                shared: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Call every ``safe_state.achieved_by`` action; return the failures.

        Deliberately bypasses grants, permits, budgets and the device lease
        (SAFE-029).  Every action is attempted even after one fails.

        With ``shared`` (an e-stop attempt) and an SDK-owned ROS route
        (:func:`_sdk_ros_route`), each call gets ``ctx.extra["estop_shared"]``,
        a report list of that call only; a ``{same_request_as}`` report that
        names ``native`` or another ``achieved_by`` action is appended to
        ``shared``.  Nothing is skipped on a report: it only records that the
        bridge answered the call from an identical request of this e-stop.
        """
        bridge = device.bridge
        failures: list[dict[str, Any]] = []
        achieved_by = [str(item) for item in (device.safety.safe_state or {}).get("achieved_by") or []]
        reporting = shared is not None and _sdk_ros_route(bridge)
        for capability_id in (device.safety.safe_state or {}).get("achieved_by") or []:
            capability_id = str(capability_id)
            if capability_id in skip:
                continue
            bindings = device.bindings_of(capability_id)
            if not bindings or bridge is None:
                failures.append({"capability_id": capability_id,
                                 "error": {"type": "NotBound" if not bindings else "NoBridge"}})
                continue
            # Every binding of the class: a stop bound on two arms stops both
            # (FIT-ROS-03).
            for capability in bindings:
                extra: dict[str, Any] = {"safe_state": True}
                reported: list[Any] = []
                if reporting:
                    extra["estop_shared"] = reported
                ctx = _Context(
                    device_id=device.device_id,
                    resource=capability.resource,
                    mode=device.mode,
                    cancel_event=threading.Event(),
                    deadline_ms=self._estop_budget_ms(device),
                    extra=extra,
                )
                try:
                    _plain(bridge.call(capability.capability_id, {}, ctx))
                except BaseException as exc:  # noqa: BLE001 - try every declared action
                    failure: dict[str, Any] = {"capability_id": capability_id, "error": _describe_exception(exc)}
                    if len(bindings) > 1:
                        failure["resource"] = capability.resource
                    failures.append(failure)
                finally:
                    if reporting and shared is not None:
                        entry = _shared_stop_entry(reported, capability_id, achieved_by)
                        if entry is not None:
                            if len(bindings) > 1:
                                entry["resource"] = capability.resource
                            shared.append(entry)
        return failures

    def _ensure_estop_supervisor(
        self, device: Device, session: Session, reason: str, generation: int
    ) -> None:
        """Make sure a background retry serves ``generation`` of the device's latch.

        A supervisor serves exactly one latch generation (a reset bumps it) and
        ends on its own, within one 50 ms poll, once the generation changed.  A
        live supervisor of an older generation is therefore not a reason to
        skip: a failed e-stop right after a reset gets its own supervisor.
        Nothing is started when ``generation`` itself was already reset.
        """
        did = device.device_id
        with self._lock:
            state = self._estop_state.setdefault(did, {})
            if self._closed or not self._latched.get(did) or state.get("generation", 0) != generation:
                return
            supervisor = state.get("supervisor")
            if (isinstance(supervisor, threading.Thread) and supervisor.is_alive()
                    and state.get("supervisor_generation") == generation):
                return
            thread = threading.Thread(
                target=self._supervise_estop,
                args=(device, session, reason, generation),
                name=f"mhs-estop-retry-{did.rsplit('/', 1)[-1]}",
                daemon=True,
            )
            state["supervisor"] = thread
            state["supervisor_generation"] = generation
        thread.start()

    def _supervise_estop(self, device: Device, session: Session, reason: str, generation: int) -> None:
        """Keep trying the stop path until it succeeds or the device is reset (SAFE-040).

        Serves one latch ``generation`` and always the device's *current*
        attempt: after confirming one it ends only when no newer e-stop has
        started an attempt meanwhile (it deregisters itself under the lock, so
        a later failure starts a new supervisor).  A retry is not started
        while a reset is inside ``bridge.reset()`` (``resetting`` > 0), up to
        that reset's deadline (``reset_hold_until``) and only while no e-stop
        was engaged since the reset entered (``reset_seq``): the reset either
        releases the latch (this supervisor then ends) or fails, and the retry
        follows it.  A ``bridge.reset()`` that outlives its deadline no longer
        holds the retry back; that reset then cannot release the latch while
        the retry runs (``stop_path_pending``).
        """
        did = device.device_id
        delay = _ESTOP_RETRY_INITIAL_S
        me = threading.current_thread()

        def current_locked() -> bool:  # the caller holds self._lock
            state = self._estop_state.get(did) or {}
            return not self._closed and bool(self._latched.get(did)) and state.get("generation", 0) == generation

        def current() -> bool:
            with self._lock:
                if current_locked():
                    return True
                leave_locked()
                return False

        def leave_locked() -> None:  # the caller holds self._lock
            # Deregister before ending, atomically with the decision to end, so
            # an e-stop that fails from now on starts a new supervisor
            # (_ensure_estop_supervisor) instead of relying on this one.
            state = self._estop_state.get(did) or {}
            if state.get("supervisor") is me:
                state["supervisor"] = None

        while True:
            with self._lock:
                if not current_locked():
                    leave_locked()
                    return
                attempt = (self._estop_state.get(did) or {}).get("attempt")
                if attempt is None:
                    leave_locked()
                    return
            while not attempt.done.wait(0.05):
                if not current():
                    return
            if not current():
                return
            if attempt.ok:
                try:
                    self._confirm_estop(device, session, reason, attempt, generation)
                except Exception:  # recording failure must not commit or kill the retry
                    if not current():
                        return
                    _log.exception("background e-stop confirmation could not be recorded for %s", did)
                    # Keep all command ids unconfirmed. The bounded retry below
                    # rechecks the native stop before trying another receipt.
                else:
                    with self._lock:
                        state = self._estop_state.get(did) or {}
                        if not current_locked() or state.get("attempt") is attempt:
                            leave_locked()
                            return
                    # A newer e-stop started its own attempt while this one was
                    # being confirmed: serve it (its receipt says retrying).
                    delay = _ESTOP_RETRY_INITIAL_S
                    continue
            resume_at = time.monotonic() + delay
            delay = min(delay * 2, _ESTOP_RETRY_MAX_S)
            while True:
                with self._lock:
                    if not current_locked():
                        leave_locked()
                        return
                    state = self._estop_state.setdefault(did, {})
                    now = time.monotonic()
                    # A reset inside bridge.reset() holds the retry back -- unless
                    # an e-stop was engaged since it entered (that reset is refused
                    # with estop_during_reset anyway, so the new stop path must
                    # not wait for it).
                    held = (int(state.get("resetting", 0)) > 0
                            and now < float(state.get("reset_hold_until") or 0.0)
                            and int(state.get("seq", 0)) == int(state.get("reset_seq", -1)))
                    if state.get("attempt") is not attempt:
                        break   # a newer e-stop started an attempt: serve that one
                    if now >= resume_at and not held:
                        state["attempt"] = self._start_estop_attempt(device, reason)
                        break
                time.sleep(min(0.05, max(0.005, resume_at - time.monotonic())))

    def _confirm_estop(self, device: Device, session: Session, reason: str, attempt: _EstopAttempt,
                       generation: int | None = None) -> None:
        """Record that a background attempt reached the safe state.

        The confirmation receipt is in the evidence log before
        ``safety.status`` reports ``estop.confirmed``; a reset in between
        (``generation`` changed) leaves the cleared state alone.  Only the
        current attempt confirms: when a newer e-stop started its own attempt
        before the receipt is written nothing is recorded, and when one starts
        while it is written the receipt settles the command ids it names but
        ``confirmed`` stays false (the newer attempt decides, and the
        supervisor serves it).
        """
        did = device.device_id
        with self._lock:
            state = self._estop_state.setdefault(did, {})
            if self._closed or not self._latched.get(did) or (
                generation is not None and state.get("generation", 0) != generation
            ) or state.get("attempt") is not attempt:
                # Reset meanwhile, or a newer e-stop started its own attempt
                # (whose outcome now decides): nothing to confirm.  The
                # command ids stay unconfirmed until that attempt succeeds.
                return
            unconfirmed = list(state.get("unconfirmed") or [])
            attempts = int(state.get("attempts", 0))
        output = {
            "estop": attempt.native,
            "latched": True,
            "safe_state_achieved": True,
            "safe_state": dict(device.safety.safe_state or {}),
            "confirms": unconfirmed[0] if unconfirmed else None,
            "confirms_command_ids": unconfirmed,
            "attempts": attempts,
        }
        self._finish_command(
            session=session,
            device=device,
            capability=None,
            capability_id="cap.internal.safety_estop.v1",
            command_id=canonical.ulid(),
            input_payload={"reason": reason},
            input_digest=canonical.digest(
                {"capability_id": "cap.internal.safety_estop.v1", "reason": reason}
            ),
            status="completed",
            output=output,
            started=time.time(),
            deadline_ms=self._estop_budget_ms(device),
            permit_id=None,
            effects=[{"kind": "safety.estop", "summary": "emergency stop confirmed",
                      "reversible": False, "severity": "R0"}],
            bump=False,
            # Bounded like the e-stop receipt: a read that waits on a lock a
            # running call holds must not delay the confirmation.
            read_timeout_s=_ESTOP_READ_BOUND_S,
            vendor=_confirmation_vendor(attempt),
        )
        # Publish confirmation only after its receipt was recorded successfully.
        # A failed write must retain the original unconfirmed command ids.
        confirmed = False
        with self._lock:
            state = self._estop_state.setdefault(did, {})
            if not self._closed and self._latched.get(did) and (
                generation is None or state.get("generation", 0) == generation
            ):
                state["unconfirmed"] = [
                    command_id for command_id in state.get("unconfirmed") or []
                    if command_id not in unconfirmed
                ]
                # A newer e-stop keeps its own unconfirmed state even when
                # this receipt settled the earlier command ids.
                if state.get("attempt") is attempt:
                    state["confirmed"] = True
                    confirmed = True
        if confirmed:
            self._notify("safety", did, {"estop": "engaged", "latched": True, "confirmed": True,
                                         "safe_state_achieved": True})

    def _reassert_estop(self, device: Device, session: Session, wait_s: float) -> bool:
        """Run the stop path again (the latch is already engaged).

        Used when an e-stop landed while ``bridge.reset()`` ran.  Waits at most
        the device's e-stop budget and ``wait_s``; an unconfirmed attempt is
        retried in the background like any failed e-stop.  Returns whether the
        stop path confirmed in time.  An older attempt that is still running
        stays tracked (``pending_attempts``), so no reset passes while its native
        e-stop may still land.

        An already-admitted reset may return after endpoint close and undo a
        concurrent stop. Its final protective reassertion still runs, even then;
        close prevents further background retries and confirmation publication,
        not this compensating stop. It does not reopen evidence or the endpoint.
        """
        did = device.device_id
        with self._lock:
            state = self._estop_state.setdefault(did, {})
            reason = str(state.get("reason") or "emergency stop requested")
            attempt = self._start_estop_attempt(device, reason)
            state["attempt"] = attempt
            state["confirmed"] = False
            generation = state.get("generation", 0)
        return self._await_stop_path(device, session, attempt, generation, reason, wait_s)

    def _await_stop_path(self, device: Device, session: Session, attempt: _EstopAttempt,
                         generation: int, reason: str, wait_s: float) -> bool:
        """Wait (at most the e-stop budget and ``wait_s``) for a re-run of the stop path.

        On an open endpoint, a successful current attempt of the same latch
        generation confirms the native stop (CORE-077 / CORE-171). This is not
        a statement that a reset or replay receipt was newly recorded. Close
        prevents publication; unsuccessful attempts are supervised only while
        the endpoint remains open (:meth:`_ensure_estop_supervisor`).
        """
        did = device.device_id
        attempt.done.wait(max(0.0, min(self._estop_budget_ms(device) / 1000.0, wait_s)))
        ok = attempt.done.is_set() and attempt.ok
        if ok:
            with self._lock:
                state = self._estop_state.setdefault(did, {})
                if (not self._closed and self._latched.get(did)
                        and state.get("generation", 0) == generation
                        and state.get("attempt") is attempt):
                    state["confirmed"] = True
        else:
            self._ensure_estop_supervisor(device, session, reason, generation)
        return ok

    def _rerun_restored_stop_path_locked(self, device: Device) -> tuple[_EstopAttempt, int, str] | None:
        """Start the stop path of a restored, unconfirmed latch (caller holds ``self._lock``).

        Returns ``(attempt, generation, reason)``, or None when the latch was
        not restored at start-up, is confirmed, or an attempt is running.
        """
        state = self._estop_state.setdefault(device.device_id, _fresh_estop_state())
        running = state.get("attempt")
        if (not state.get("restored") or state.get("confirmed") is True
                or (isinstance(running, _EstopAttempt) and not running.done.is_set())):
            return None
        reason = str(state.get("reason") or "emergency stop requested")
        attempt = self._start_estop_attempt(device, reason)
        state["attempt"] = attempt
        state["confirmed"] = False
        return attempt, int(state.get("generation", 0)), reason

    def _m_safety_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Release a latched e-stop (SAFE-041/042/043).

        Refused with ``MHS.SAFETY.RESET_REFUSED`` (a ``rejected`` receipt, the
        bridge is not called) when nothing is latched, when an effectful
        operation is still running (it ignored the e-stop's cancellation), when
        the stop path of the last e-stop is still running (``stop_path_pending``:
        the native e-stop has not answered; releasing the latch would let it,
        or its safe-state actions, land on a device that was already reset
        and moving again), or when any declared
        interlock not marked ``reset_exempt`` reads ``open`` or ``unknown``
        (not reported, or unreadable).  "Latched" is the endpoint's e-stop
        latch or a latch the device reports itself (:meth:`_device_reports_latch`,
        for example a guard-door trip).  A reset releases the latch only: it
        never resumes the interrupted motion; a new command is required.

        The latch is released only when no e-stop was engaged while the reset
        ran, including after its caller was answered ``MHS.OUTCOME.TIMEOUT``
        (``RESET_REFUSED`` ``estop_during_reset`` otherwise; the native stop is
        then re-asserted after ``bridge.reset()``).  A refusal decided after
        ``bridge.reset()`` returned (``estop_during_reset``, or
        ``stop_path_pending`` with ``details.bridge_reset: "completed"``) is a
        ``failed`` receipt, still ``RESET_REFUSED`` with ``latched: true``:
        the bridge reset was executed (RESIDUAL-B).  A reset whose caller was
        already answered ``MHS.OUTCOME.TIMEOUT`` before it reached
        ``bridge.reset()`` is not performed (a ``failed`` receipt, reason
        ``deadline_exceeded``); one already inside ``bridge.reset()`` finishes
        and is receipted as usual (RE-PROTO-004: the timeout said
        ``may_have_effect``; reconcile by ``command_id``).
        """
        session = self._session(params.get("session_id"))
        device = self._device_from_session(session, params.get("device_id"))
        bridge = self._bridge(device)
        did = device.device_id
        started = time.time()
        entered = time.monotonic()
        command_id = str(params.get("command_id") or canonical.ulid())
        deadline_ms = int(params.get("deadline_ms") or 5000)
        abandoned = getattr(self._dispatch_local, "abandoned", None)

        def _caller_gone() -> bool:
            return isinstance(abandoned, threading.Event) and abandoned.is_set()

        def _timed_out() -> dict[str, Any]:
            return _finish("failed", error=MHSError(
                "MHS.OUTCOME.TIMEOUT",
                f"the reset outlived its {deadline_ms} ms deadline before reaching the device; "
                "nothing was reset and the latch stays engaged",
                {"retryable": False, "details": {"reason": "deadline_exceeded", "latched": True,
                                                 "bridge_reset": "not_called"}},
            ))

        def _finish(status: str, *, output: Any = None, error: MHSError | None = None,
                    effects: list[dict[str, Any]] | None = None, bump: bool | None = None) -> dict[str, Any]:
            return self._finish_command(
                session=session,
                device=device,
                capability=None,
                capability_id="cap.internal.safety_reset.v1",
                command_id=command_id,
                input_payload={},
                input_digest=canonical.digest({}),
                status=status,
                output=output,
                started=started,
                deadline_ms=deadline_ms,
                permit_id=None,
                error=error,
                effects=effects,
                bump=status == "completed" if bump is None else bump,
            )

        def _refuse(reason: str, message: str, *, interlocks: Any = None,
                    details: Mapping[str, Any] | None = None, after_reset: bool = False,
                    remediation: str | None = None) -> dict[str, Any]:
            data: dict[str, Any] = {"retryable": False, "details": {"reason": reason, **dict(details or {})}}
            if interlocks:
                data["interlocks"] = interlocks
            if remediation:
                data["remediation"] = remediation
            if after_reset:
                # Decided after bridge.reset() returned: the reset was executed,
                # so the receipt is 'failed' (a 'rejected' receipt says nothing
                # was executed, plan 3.7).  The device state may have changed:
                # the revision advances, as for a completed reset.
                return _finish("failed", error=MHSError("MHS.SAFETY.RESET_REFUSED", message, data), bump=True)
            return _finish("rejected", error=MHSError("MHS.SAFETY.RESET_REFUSED", message, data))

        if device.mode in ("hardware", "hybrid") and not (session.kind == "operator" and session.authenticated):
            # Plan 3.6 / SURF-01: resetting a hardware latch is a human
            # operator's decision, never a model's.  Strict mode refuses any
            # other principal (bridge not called, latch kept).
            if self._is_strict(device):
                return _finish("rejected", error=MHSError(
                    "MHS.AUTH.FORBIDDEN",
                    f"only an authenticated operator principal may reset a {device.mode} device",
                    {"retryable": False,
                     "details": {"reason": "operator_required", "mode": device.mode,
                                 "principal_kind": session.kind,
                                 "authenticated": bool(session.authenticated)},
                     "remediation": "Reset from an operator console with an operator bearer token."},
                ))
            self._compat_warn(
                ("reset", did),
                f"{did}: mhs.safety.reset by a {session.kind} principal "
                f"({'token' if session.authenticated else 'self-declared'}) -- compatibility mode: allowed; "
                "strict=True lets only an authenticated operator reset a hardware or hybrid device",
            )

        stop_path_message = ("the stop path of the last e-stop is still running (the native e-stop "
                             "has not answered); wait for it to answer before reset")
        with self._lock:
            restore_pending = did in self._restore_admissions
            latched = bool(self._latched.get(did))
            # Every e-stop bumps seq; one engaged from here on survives the reset.
            estop_seq = int((self._estop_state.get(did) or {}).get("seq", 0))
            pending = _stop_path_pending(self._estop_state.get(did) or {})
            # CORE-087: this endpoint started the stop path of a terminal e-stop.
            terminal_stop = bool((self._estop_state.get(did) or {}).get("terminal"))
            # An effectful operation that ignored its cancellation is still
            # moving the device; releasing the latch now would let it run on.
            # A declared read verb alone is not trusted (_is_read_capability).
            running = [
                operation.operation_id for operation in self._operations.values()
                if operation.device_id == did and operation.final_receipt is None
                and operation.thread is not None and operation.thread.is_alive()
                and not self._is_read_capability(self._operation_binding(device, operation))
            ]
        if restore_pending:
            return _refuse("restore_running", "a checkpoint restore still owns the device; wait for completion",
                           details={"latched": latched})
        if not latched and not self._device_reports_latch(device, bridge):
            return _refuse("not_latched", "the device is not latched; there is nothing to reset")
        def _terminal_refusal(*, after_reset: bool = False) -> dict[str, Any]:
            # A declared terminal e-stop (CORE-087): its native stop ran on this
            # endpoint and no reset of this endpoint can undo it.  The bridge is
            # not called and the latch is kept, for the endpoint's whole life.
            statement = _estop_terminal(device) or "terminal e-stop declared"
            details: dict[str, Any] = {"latched": True, "terminal": statement}
            if after_reset:
                details["bridge_reset"] = "completed"
            return _refuse(
                "terminal_estop",
                "the e-stop of this device is terminal and cannot be reset on this endpoint: " + statement,
                details=details,
                after_reset=after_reset,
                remediation="Serve the device from a new endpoint (a new native session); an operator then "
                            "resets the latch that endpoint restores.",
            )

        if terminal_stop:
            return _terminal_refusal()
        if running:
            return _refuse("operation_running",
                           "an effectful operation is still running on the device; "
                           "wait for it to end before reset",
                           details={"operation_ids": running})
        if pending:
            return _refuse("stop_path_pending", stop_path_message, details={"latched": True})
        declared = [
            entry for entry in device.safety.interlocks or []
            if isinstance(entry, Mapping) and entry.get("id") is not None
        ]
        try:
            live = {
                str(entry.get("id")): str(entry.get("state"))
                for entry in _plain(bridge.interlocks() or [])
                if isinstance(entry, Mapping)
            }
            readable = True
        except Exception:  # noqa: BLE001 - unreadable interlocks are unknown
            live, readable = {}, False
        blocked = [
            {"id": str(entry["id"]), "state": live.get(str(entry["id"]), "unknown")}
            for entry in declared
            if not entry.get("reset_exempt") and live.get(str(entry["id"])) != "closed"
        ]
        if blocked:
            return _refuse(
                "interlock_open",
                "interlock not closed: " + ", ".join(f"{b['id']} ({b['state']})" for b in blocked),
                interlocks=blocked,
                details={} if readable else {"interlocks_readable": False},
            )
        if _caller_gone():
            return _timed_out()
        with self._lock:
            state = self._estop_state.setdefault(did, {})
            # Re-checked atomically with entering bridge.reset(): a background
            # retry started meanwhile must not run alongside the reset, and
            # none starts while ``resetting`` is held.
            pending = _stop_path_pending(state)
            restore_pending = did in self._restore_admissions
            # A terminal e-stop engaged since the first check is never reset either.
            terminal_stop = bool(state.get("terminal"))
            if not pending and not restore_pending and not terminal_stop:
                state["resetting"] = int(state.get("resetting", 0)) + 1
                # The retry waits for the reset at most until the reset's deadline,
                # and only while no e-stop was engaged after it entered.
                state["reset_hold_until"] = max(float(state.get("reset_hold_until") or 0.0),
                                                entered + deadline_ms / 1000.0)
                state["reset_seq"] = int(state.get("seq", 0))
        if terminal_stop:
            return _terminal_refusal()
        if pending:
            return _refuse("stop_path_pending", stop_path_message, details={"latched": True})
        if restore_pending:
            return _refuse("restore_running", "a checkpoint restore still owns the device; wait for completion",
                           details={"latched": True})
        in_reset = True

        def _leave_reset_locked() -> None:  # the caller holds self._lock
            nonlocal in_reset
            if in_reset:
                in_reset = False
                state["resetting"] = max(0, int(state.get("resetting", 0)) - 1)

        try:
            try:
                _plain(bridge.reset())
            except MHSError as exc:
                with self._lock:
                    _leave_reset_locked()
                return _refuse(
                    "bridge_refused",
                    str(exc.message or exc.code),
                    interlocks=(exc.data or {}).get("interlocks"),
                    details={"bridge_code": str(exc.code)},
                )
            except Exception as exc:  # noqa: BLE001 - the latch stays engaged
                with self._lock:
                    _leave_reset_locked()
                return _finish("failed", error=MHSError(
                    "MHS.ADAPTER.SHIM_FAILED",
                    f"bridge reset raised {type(exc).__name__}",
                    {"retryable": False, "details": {"exception_type": type(exc).__name__,
                                                     "latched": True}},
                ))
            with self._lock:
                _leave_reset_locked()
                estop_during_reset = int(state.get("seq", 0)) != estop_seq
                # A retry that started after the reset outlived its deadline:
                # the latch is never released under a running stop path.
                stop_path_running = not estop_during_reset and _stop_path_pending(state)
                restore_pending = did in self._restore_admissions
                # A terminal stop path that started while the bridge reset ran
                # (a replayed e-stop of a restored latch) is never undone either.
                terminal_during_reset = not estop_during_reset and bool(state.get("terminal"))
                if (not estop_during_reset and not stop_path_running and not restore_pending
                        and not terminal_during_reset):
                    self._latched[did] = False
                    state["generation"] = int(state.get("generation", 0)) + 1
                    state["confirmed"] = None
                    state["unconfirmed"] = []
                    self._persist_latch(device, False, None)
        finally:
            if in_reset:  # BaseException out of bridge.reset()
                with self._lock:
                    _leave_reset_locked()
        if estop_during_reset:
            # bridge.reset() may have cleared the device's own latch after the
            # new e-stop's native stop ran: stop the device again.
            remaining_s = deadline_ms / 1000.0 - (time.monotonic() - entered)
            reasserted = self._reassert_estop(device, session, remaining_s)
            return _refuse(
                "estop_during_reset",
                "an emergency stop was engaged while the reset ran; the latch stays engaged",
                details={"latched": True, "bridge_reset": "completed", "stop_reasserted": reasserted},
                after_reset=True,
            )
        if stop_path_running:
            return _refuse("stop_path_pending", stop_path_message,
                           details={"latched": True, "bridge_reset": "completed"}, after_reset=True)
        if restore_pending:
            return _refuse("restore_running", "a checkpoint restore still owns the device; latch retained",
                           details={"latched": True}, after_reset=True)
        if terminal_during_reset:
            return _terminal_refusal(after_reset=True)
        cleared = [
            str(entry["id"]) for entry in declared if live.get(str(entry["id"])) == "closed"
        ] or sorted(key for key, value in live.items() if value == "closed")
        output = {"reset": True, "estop": "released", "latched": False,
                  "cleared_interlocks": cleared, "resumed": False}
        reenable = _estop_reenable(device)
        if reenable is not None:
            # CORE-086: the reset re-armed nothing; this is the new start command
            # the device needs before it moves again (SAFE-042).
            output["reenable"] = reenable
        receipt = _finish(
            "completed",
            output=output,
            effects=[{"kind": "safety.reset", "summary": "safety reset; nothing resumed",
                      "reversible": True, "severity": "R0"}],
        )
        self._notify("safety", did, {"estop": "released", "latched": False})
        return receipt

    def _m_safety_permit(self, params: dict[str, Any]) -> dict[str, Any]:
        session = self._session(params.get("session_id"))
        device = self._device_from_session(session, params.get("device_id"))
        capability_id = str(params.get("capability_id") or "")
        if not capability_id:
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "capability_id is required")
        if not device.bindings_of(capability_id):
            raise MHSError("MHS.CAPABILITY.UNKNOWN",
                           f"device does not expose capability {capability_id!r}",
                           {"retryable": False})
        if not session.allows(device.device_id, capability_id):
            raise MHSError("MHS.SESSION.CAPABILITY_NOT_GRANTED",
                           f"session may not permit {capability_id!r}",
                           {"device_id": device.device_id, "capability_id": capability_id})
        input_digest = params.get("input_digest")
        if not isinstance(input_digest, str) or not canonical.is_digest(input_digest):
            raise MHSError("MHS.SAFETY.PERMIT_INVALID",
                           "input_digest must be a sha256:<64 hex> digest")
        # A permit is for one binding, (capability_id, resource): an omitted
        # resource with several bindings is INVALID_PARAMS resource_required.
        resource = params.get("resource") or None
        if resource is None:
            capability = device.binding(capability_id)
            resource = capability.resource
        else:
            if not isinstance(resource, str) or resource not in device._by_resource:
                raise MHSError("MHS.SAFETY.PERMIT_INVALID",
                               "resource does not exist on this device",
                               {"resource": resource, "retryable": False})
            found = device._by_binding.get((capability_id, resource))
            if found is None:
                bound = [cap.resource for cap in device.bindings_of(capability_id)]
                raise MHSError("MHS.SAFETY.PERMIT_INVALID",
                               "permit resource must be a resource the capability is bound to",
                               {"capability_resource": bound[0], "bound_resources": bound,
                                "requested_resource": resource, "retryable": False})
            capability = found
        if not session.allows(device.device_id, capability_id, resource):
            raise MHSError("MHS.SESSION.CAPABILITY_NOT_GRANTED",
                           f"session may not permit {capability_id!r} on resource {resource!r}",
                           {"device_id": device.device_id, "capability_id": capability_id, "resource": resource})
        if "input" in params and isinstance(params.get("input"), Mapping):
            not_canonical = _non_canonical_input(dict(params["input"]))
            if not_canonical is not None:
                raise not_canonical
            expected_digest = action_digest(capability_id, resource, dict(params["input"]))
            if expected_digest != input_digest:
                raise MHSError("MHS.SAFETY.PERMIT_INVALID",
                               "input_digest does not match the supplied input",
                               {"expected_digest": expected_digest, "retryable": False})
        try:
            ttl_s = int(params.get("ttl_s") or 60)
        except (TypeError, ValueError) as exc:
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "ttl_s must be an integer") from exc
        ttl_s = max(1, min(300, ttl_s))
        raw_approvals = list(params.get("approvals") or [])
        if not raw_approvals:
            raw_approvals = [
                {
                    "principal": str((session.principal or {}).get("id") or "unknown"),
                    "method": "policy_rule",
                }
            ]
        approvals: list[dict[str, Any]] = []
        for approval in raw_approvals:
            if not isinstance(approval, Mapping):
                raise MHSError("MHS.SAFETY.PERMIT_INVALID",
                               "approvals must be objects, not bare strings")
            principal = approval.get("principal")
            if not isinstance(principal, str) or not principal:
                raise MHSError("MHS.SAFETY.PERMIT_INVALID",
                               "each approval needs a principal")
            method = approval.get("method", "auto")
            if method not in ("human_click", "policy_rule", "dual_control", "auto"):
                raise MHSError("MHS.SAFETY.PERMIT_INVALID",
                               f"unknown approval method {method!r}")
            entry: dict[str, Any] = {"principal": principal, "method": method}
            if isinstance(approval.get("approved_at"), str):
                entry["approved_at"] = approval["approved_at"]
            if isinstance(approval.get("evidence_ref"), str):
                entry["evidence_ref"] = approval["evidence_ref"]
            approvals.append(entry)
        approvals = self._verify_approvals(
            device=device,
            capability_id=capability_id,
            resource=resource,
            input_digest=input_digest,
            principal=str((session.principal or {}).get("id")),
            approvals=approvals,
        )
        expires_at = time.time() + ttl_s
        permit = Permit(
            # A full ULID plus 64 random bits: unique and not derivable from
            # another permit's id (pattern ^permit_[A-Za-z0-9_]+$).
            permit_id=f"permit_{canonical.ulid()}_{secrets.token_hex(8)}",
            capability_id=capability_id,
            input_digest=input_digest,
            principal=str((session.principal or {}).get("id")),
            approvals=approvals,
            expires_at=expires_at,
            session_id=session.session_id,
            device_id=device.device_id,
            resource=resource,
        )
        with self._lock:
            self._permits[permit.permit_id] = permit
        scope = {
            "device_id": device.device_id,
            "capability_id": capability_id,
            "resource": resource,
            "input_digest": input_digest,
            "principal": permit.principal,
            "expires_at": canonical.rfc3339_from_ms(int(expires_at * 1000)),
            "single_use": True,
        }
        # SAFE-035: the approval decision is auditable even though the method
        # returns a permit object rather than a command receipt.
        command_id = canonical.ulid()
        audit = self._receipt(
            session=session,
            device=device,
            capability_id="cap.internal.safety_permit.v1",
            resource_ids=[resource],
            command_id=command_id,
            input_payload={"capability_id": capability_id, "resource": resource,
                           "input_digest": input_digest},
            status="completed",
            output={"permit_id": permit.permit_id, "scope": scope},
            effects=[{"kind": "safety.permit", "summary": "approval recorded",
                      "reversible": True, "severity": device.safety.risk_class}],
        )
        with self._lock:
            self._retain_receipt((device.device_id, command_id), audit["input_digest"], audit)
        return {
            "permit_id": permit.permit_id,
            "capability_id": capability_id,
            "resource": resource,
            "input_digest": input_digest,
            "expires_at": canonical.rfc3339_from_ms(int(expires_at * 1000)),
            "single_use": True,
            "scope": scope,
            "approvals": approvals,
            "evidence": audit.get("evidence"),
        }

    # -- evidence ----------------------------------------------------
    def _export_bundle(self) -> dict[str, Any]:
        if self._artifact_store is None:
            return self._export_bundle_unlocked()
        # Evidence transport must not expose a completed artifact receipt in
        # the interval between its append and grant/index publication. Native
        # commands and independent e-stop never acquire this export-only lock.
        with self._artifact_publication_lock:
            return self._export_bundle_unlocked()

    def _export_bundle_unlocked(self) -> dict[str, Any]:
        """Export the evidence bundle.

        A replay endpoint serves the *recorded* source bundle unchanged
        (FID-028); its replay-access audit is kept separately in memory so the
        recording digest is never rewritten.
        """
        for device in self.devices.values():
            if device.mode != "replay":
                continue
            bridge = self._bridge(device)
            source = getattr(bridge, "source_bundle", None)
            if isinstance(source, Mapping):
                import copy as _copy

                return _copy.deepcopy(dict(source))
        # Normal endpoint: export the live chain.
        return self._export_live_bundle()

    def _export_live_bundle(self) -> dict[str, Any]:
        """Export the evidence log with a verifiable ``endpoint_info``.

        ``EvidenceLog.endpoint_info()`` in the foundation can report the current
        chain head as ``genesis_digest``.  Offline verification recomputes the
        genesis document digest, so a verbatim export would not verify.  This
        workaround recomputes the genesis digest for the exported bundle only;
        the hash chain itself is untouched.
        """
        bundle = self._evidence.export()
        try:
            from .evidence import compute_genesis_digest

            genesis = bundle.get("genesis")
            document = genesis.get("genesis_document") if isinstance(genesis, Mapping) else None
            if isinstance(document, Mapping):
                digest = compute_genesis_digest(document)
                info = bundle.setdefault("endpoint_info", {})
                if isinstance(info, dict):
                    info["genesis_digest"] = digest
                bundle.setdefault("genesis_digest", digest)
            info = bundle.get("endpoint_info")
            if isinstance(info, dict):
                info.setdefault("server", {"name": SERVER_NAME, "version": SERVER_VERSION})
                info.setdefault("endpoint_id", self.endpoint_id)
                info.setdefault("mhs_version", MHS_VERSION)
        except Exception:  # noqa: BLE001 - an export must still return the chain
            pass
        return bundle

    def _m_evidence_export(self, params: dict[str, Any]) -> dict[str, Any]:
        self._session(params.get("session_id")) if params.get("session_id") else None
        return self._export_bundle()

    def _m_evidence_verify(self, params: dict[str, Any]) -> dict[str, Any]:
        from .evidence import verify_bundle

        bundle = params.get("bundle")
        if bundle is None:
            bundle = self._export_bundle()
        report = verify_bundle(bundle)
        return report.to_dict() if hasattr(report, "to_dict") else dict(report)

    def _m_conformance_report(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the last stored executed report, or a CL0 report with nothing run.

        The endpoint never asserts a result nobody executed (finding SDK-12):
        it returns the report stored by :meth:`record_conformance_report` (the
        output of :func:`mhs.conformance.run_suite` for this endpoint)
        verbatim.  Without one, every suite test is listed as not run (status
        ``skip``, detail ``not_run: ...``) and ``level_achieved`` is ``CL0``.
        """
        with self._lock:
            stored = copy.deepcopy(self._conformance_report) if self._conformance_report else None
        if stored is not None:
            return stored
        levels = ("CL0", "CL1", "CL2", "CL3", "CL4", "CL5")
        profiles = ("MHS-Device", "MHS-Sim", "MHS-Bridge", "MHS-Host", "MHS-Registry")
        claimed = params.get("level") if params.get("level") in levels else "CL0"
        profile = params.get("profile") if params.get("profile") in profiles else "MHS-Sim"
        detail = ("not_run: no executed conformance report is stored on this endpoint; "
                  "run mhs.conformance.run_suite against it")
        report_version, suite_version = "1.0.0", "1.0.0"
        tests: list[dict[str, Any]] = []
        try:
            from .conformance import report as _report_module
            from .conformance.tests_core import TESTS as _suite_tests

            report_version = str(_report_module.REPORT_VERSION)
            suite_version = str(_report_module.SUITE_VERSION)
            seen: set[str] = set()
            for case in _suite_tests:
                if case.id in seen or (case.profiles and profile not in case.profiles):
                    continue
                seen.add(case.id)
                tests.append({"id": case.id, "name": case.name, "level": case.level,
                              "status": "skip", "detail": detail})
        except Exception:  # noqa: BLE001 - the report must not depend on the suite importing
            tests = []
        if not tests:
            tests = [{"id": "PROTO-013", "name": "mhs.hello negotiates the protocol",
                      "level": "CL1", "status": "skip", "detail": detail}]
        report: dict[str, Any] = {
            "report_version": report_version,
            "suite_version": suite_version,
            "profile": profile,
            "subject": {"kind": "endpoint", "id": self.endpoint_id, "mhs_version": MHS_VERSION},
            "level_claimed": claimed,
            "level_achieved": "CL0",
            "tests": tests,
            "environment": {
                "os": os.uname().sysname if hasattr(os, "uname") else os.name,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "date": canonical.now_rfc3339(),
                "suite": f"{_ids.DIST_NAME} {_ids.SDK_VERSION}",
                "endpoint_ids": list(self.devices),
            },
            "coverage": {"required": len(tests), "passed": 0, "failed": 0, "skipped": len(tests)},
            "issuer": {"kind": "self", "name": SERVER_NAME},
            "limitations": [
                "No conformance run is stored on this endpoint: nothing was executed and "
                "nothing is claimed.",
                "MHS is not a safety-rated channel and does not replace a hardware emergency stop.",
            ],
            "disclaimers": [
                {"id": "not_certified",
                 "text": "A conformance report is a behavioural test result, not a safety certification."},
                {"id": "self_issued", "text": "Issued by the endpoint itself."},
            ],
        }
        report["report_digest"] = _conformance_report_digest(report)
        return report

    # ------------------------------------------------------------------
    # Core command execution
    # ------------------------------------------------------------------
    def _run_command(
        self,
        *,
        session: Session,
        device: Device,
        capability_id: str,
        resource_id: str | None,
        command_id: str,
        input_payload: dict[str, Any],
        expected_revision: Any,
        deadline_ms: int,
        permit_id: str | None,
    ) -> dict[str, Any]:
        """Run one command as a registered operation (plan 3.6 order).

        Every effect is an operation: ``capability_id`` must name a capability
        bound on ``device`` (an unknown id is a rejected receipt).  The caller
        waits until the operation's final receipt or the deadline.

        Pre-effect order (each refusal is a ``rejected`` receipt, no native
        call): grant of the class (2), the binding ``(capability_id,
        resource)`` and the grant of that binding (3; an omitted ``resource``
        with several bindings is ``MHS.PROTOCOL.INVALID_PARAMS``
        ``resource_required``, an unbound one ``MHS.CAPABILITY.NOT_BOUND``),
        ``command_id`` replay / reuse (4), the e-stop latch (5), replay mode,
        hybrid authority of the targeted resource and hardware arming (6),
        structure -- the input schema without the bound keywords of limited
        fields (7), the limits: every array element and nested leaf, then
        ``LIMITS_UNSET`` (8), the remaining schema bounds (9), permit and
        cumulative budgets (10), interlocks (11), the device lock, then
        ``expected_revision`` against the live revision, re-checked with the
        latch when the operation is registered (12).  A
        ``cap.device.configure.v1`` command (also ``mhs.resource.write``)
        takes a patch of the resource's writable state properties.

        Deadlines and long-running work (plan 3.7): ``deadline_ms`` bounds
        only the wait for the response, counted from the request; it never
        cancels the command.  ``max_duration_ms`` (the binding's, else its
        class's) bounds the execution and is the bridge's budget.  Past the
        deadline a ``long_running`` binding answers its non-terminal
        ``running`` receipt; any other command answers ``unknown`` +
        ``MHS.OUTCOME.TIMEOUT`` (``retryable: false``) and keeps running.  At
        the execution bound a cancellable command is asked to stop.  Every
        command ends with exactly one final receipt; one that follows an
        ``unknown`` receipt replaces the stored receipt and names it in
        ``x-vendor.reconciles``.
        """
        started = time.time()
        entered = time.monotonic()
        bindings = device.bindings_of(capability_id)
        capability: Capability | None = None
        target_resource = resource_id if resource_id is not None else (
            bindings[0].resource if len(bindings) == 1 else device.primary_resource.resource_id)
        input_digest = action_digest(capability_id, target_resource, input_payload)

        # Pre-effect refusals are receipts, not protocol errors: the agent must
        # be able to see *why* nothing happened, and the refusal must be chained
        # into the evidence log (MHS-000 SAFE-014/SAFE-030/SAFE-031).
        reservations: list[tuple[tuple[str, str], float, str]] = []
        timing_report = None

        def _refuse(error: MHSError) -> dict[str, Any]:
            self._release_cumulative(reservations)
            data = getattr(error, "data", None)
            if isinstance(data, dict) and "current_revision" in data:
                # The true current revision, not the one read before the slow checks.
                data["current_revision"] = self._current_revision(device)
            return self._finish_command(
                session=session,
                device=device,
                capability=capability,
                capability_id=capability_id,
                resource_id=target_resource,
                command_id=command_id,
                input_payload=input_payload,
                input_digest=input_digest,
                status="rejected",
                output=None,
                started=started,
                deadline_ms=deadline_ms,
                permit_id=permit_id,
                error=error,
                vendor=timing_report.vendor(final=True) if timing_report is not None else None,
                bump=False,
            )

        if not bindings:
            return _refuse(MHSError(
                "MHS.CAPABILITY.UNKNOWN",
                f"device does not expose capability {capability_id!r}",
                {"device_id": device.device_id, "capability_id": capability_id, "retryable": False},
            ))
        if capability_id == _MOTION_ESTOP:
            # SAFE-040: the catalogue e-stop class engages the same latch, with
            # the same stop path, as mhs.safety.estop; it needs no grant and is
            # never refused for its resource (the latch covers the device).
            capability = device._by_binding.get((capability_id, str(resource_id))) or bindings[0]
            return self._engage_estop(
                device=device,
                session=session,
                reason=str(input_payload.get("reason") or "cap.motion.estop.v1"),
                command_id=command_id,
                input_payload=input_payload,
                input_digest=action_digest(capability_id, capability.resource, input_payload),
                deadline_ms=deadline_ms,
                entered=time.monotonic(),
                capability=capability,
            )
        if not session.allows(device.device_id, capability_id):
            raise MHSError(
                "MHS.SESSION.CAPABILITY_NOT_GRANTED",
                f"session may not invoke {capability_id!r}",
                {"device_id": device.device_id, "capability_id": capability_id},
            )
        # Plan 3.6 step 3: the binding is (capability_id, resource).  Never fall
        # back to another binding's schema and limits, nor pass an arbitrary
        # resource through to the bridge (LAB-01, FIT-ROS-03).
        try:
            resolved = device.binding(capability_id, resource_id)
        except MHSError as exc:
            if exc.code != "MHS.CAPABILITY.NOT_BOUND":
                raise  # resource_required: the params do not name one binding
            return _refuse(exc)
        capability = resolved
        target_resource = resolved.resource
        input_digest = action_digest(capability_id, target_resource, input_payload)
        if not session.allows(device.device_id, capability_id, target_resource):
            raise MHSError(
                "MHS.SESSION.CAPABILITY_NOT_GRANTED",
                f"session may not invoke {capability_id!r} on resource {target_resource!r}",
                {"device_id": device.device_id, "capability_id": capability_id,
                 "resource": target_resource},
            )
        strict = self._is_strict(device)
        try:
            timing_report = _sim_timing.report_for_binding(capability, input_payload)
        except _sim_timing.TimingError as exc:
            return _refuse(MHSError("MHS.ADAPTER.MANIFEST_INVALID", str(exc), {"retryable": False}))

        # Idempotency: exact replay returns the retained receipt.  A conflicting
        # reuse is a rejected receipt and never overwrites the retained one.
        retained = self._receipts.get((device.device_id, command_id))
        if retained is not None:
            stored_digest, stored_receipt = retained
            if stored_digest == input_digest:
                replay = dict(self._replay_view(stored_receipt))
                replay["replayed"] = True
                return replay
            return _refuse(
                MHSError(
                    "MHS.CONFLICT.COMMAND_ID_REUSE",
                    "command_id was already used with different input",
                    {"command_id": command_id, "retryable": False},
                )
            )

        peek_state, peek_entry = self._peek_inflight(device.device_id, command_id, input_digest)
        if peek_state == "conflict":
            return _refuse(
                MHSError(
                    "MHS.CONFLICT.COMMAND_ID_REUSE",
                    "command_id is in flight for a different action",
                    {"command_id": command_id, "retryable": False},
                )
            )
        if peek_state == "inflight" and peek_entry is not None:
            receipt = self._wait_inflight(peek_entry, min(0.5, max(0.01, deadline_ms / 1000.0)))
            if receipt is not None:
                return receipt

        current_revision = self._current_revision(device)

        # Plan 3.6 step 5: while latched every effectful command is refused.
        # Reads (by the catalogue verb, not only the declared one), stop
        # classes and safe_state.achieved_by actions stay callable (SAFE-029).
        # The latch is re-checked atomically when the operation is
        # registered, after every slow pre-check.
        safe_state_action = capability is not None and self._is_safe_state_action(
            device, capability.capability_id
        )
        latch_applies = not safe_state_action and not self._is_read_capability(capability)
        if latch_applies and self._latched.get(device.device_id):
            return _refuse(_estop_engaged_error(current_revision))

        # Plan 3.6 step 6, mode: a replay device refuses every command before
        # any bridge call (FID-024), so the receipt is a no-effect `rejected`
        # at the recorded revision (conformance-verify v_replay).
        if device.mode == "replay":
            return _refuse(MHSError(
                "MHS.MODE.READ_ONLY",
                "replay devices are read-only; reads, snapshots and restores are available",
                {"retryable": False, "current_revision": current_revision,
                 "details": {"mode": "replay", "capability_id": capability_id},
                 "remediation": "Use mhs.resource.read (filter.revision) or mhs.snapshot on a replay device."},
            ))

        # Plan 3.6 step 6: on a hybrid device the model may not drive a
        # hardware-authority resource -- the targeted resource of the binding
        # (a binding of the model's arm cannot reach the hardware arm: the
        # pair would be unbound, above).  Strict mode does not trust a
        # declared verb here either: only a catalogued read class may touch it
        # (_is_read_capability); compatibility mode keeps the declared verb.
        if (
            device.mode == "hybrid"
            and (not self._is_read_capability(capability) if strict else capability.verb != "read")
        ):
            authority = (device.fidelity or {}).get("authority") or {}
            if authority.get(target_resource) == "hardware":
                return _refuse(MHSError(
                    "MHS.SAFETY.ENVELOPE_VIOLATION",
                    f"resource {target_resource!r} has hardware authority; "
                    "the model may not drive it on a hybrid device",
                    {"details": {"resource": target_resource, "authority": "hardware"},
                     "retryable": False},
                ))

        # Plan 3.6 step 6: hardware actuation needs an armed device
        # (MHSServer(armed=...)).  Only reads and stop classes are never
        # refused for it: a safe_state.achieved_by action is exempt from the
        # latch (step 5), not from arming, since it may be any actuation class
        # with any input.  The e-stop path runs the safe-state actions itself
        # (_run_safe_state_actions), whatever the arming.
        arming_applies = (
            not (capability is not None and capability.capability_id in _STOP_CLASSES)
            and not self._is_read_capability(capability)
        )
        if arming_applies and device.mode == "hardware" and not self._is_armed(device):
            return _refuse(MHSError(
                "MHS.AUTH.HARDWARE_DISABLED",
                f"hardware actuation on {device.device_id} is not armed",
                {"retryable": False,
                 "details": {"reason": "not_armed", "device_id": device.device_id,
                             "capability_id": capability.capability_id if capability is not None
                             else capability_id},
                 "remediation": "An operator arms the device: MHSServer(armed=True or [device ids])."},
            ))

        # Plan 3.6 steps 7-9: structure first (the schema without the bound
        # keywords of limited fields), then the limits (every array element
        # and nested leaf; LIMITS_UNSET), then the remaining schema bounds.  A
        # limited field out of range is a safety refusal, not INPUT_INVALID.
        plan = self._limit_plan(device, capability)
        refusal = self._check_input(device, capability, plan, input_payload, current_revision,
                                    strict=strict)
        if refusal is not None:
            return _refuse(refusal)

        # Plan 3.6 step 10: permit, then cumulative budgets (reserved
        # atomically; any later refusal releases them).
        try:
            self._check_permit(
                session, device, capability, input_payload, input_digest, permit_id,
                consume=False, resource_id=target_resource,
            )
        except MHSError as exc:
            return _refuse(exc)
        try:
            reservations = self._reserve_cumulative(device, capability, plan, input_payload, current_revision)
        except MHSError as exc:
            return _refuse(exc)
        # Plan 3.6 step 11: interlocks (unknown counts as open).
        try:
            self._check_interlocks(device, capability)
        except MHSError as exc:
            return _refuse(exc)

        expected_int: int | None = None
        if expected_revision is not None:
            try:
                if isinstance(expected_revision, bool):
                    raise TypeError("a boolean is not a revision")
                expected_int = int(expected_revision)
            except (TypeError, ValueError):
                return _refuse(MHSError("MHS.CAPABILITY.INPUT_INVALID", "expected_revision must be an integer"))

        # Plan 3.6 step 12: the device lock (safe-state actions never wait for
        # it: SAFE-029), then expected_revision against the live revision --
        # never the one read before the slow interlock and permit checks
        # (SDK-07, sdk-core e7 a).  It is checked again, with the latch, when
        # the operation is registered.
        exclusive = self._takes_device_lock(device, capability) and not safe_state_action
        device_lock = self._device_locks.setdefault(device.device_id, threading.Lock())
        if exclusive:
            acquired = device_lock.acquire(blocking=False)
            if not acquired:
                return _refuse(MHSError(
                    "MHS.DEVICE.BUSY",
                    "device is executing another exclusive capability",
                    {"device_id": device.device_id, "retryable": True},
                ))
        if expected_int is not None and expected_int != self._current_revision(device):
            if exclusive:
                device_lock.release()
            return _refuse(_revision_conflict_error(expected_int, self._current_revision(device)))

        # Reserve the idempotency identity atomically after every pre-effect
        # check passed but before invoking the bridge (RE-PROTO-002).  Under
        # state_dir an effectful command never reaches the bridge without its
        # write-ahead record; reads, stop classes and safe-state actions do.
        begin_state, inflight_entry = self._begin_inflight(
            device.device_id, command_id, input_digest,
            session=session, capability_id=capability_id, resource=target_resource,
            write_ahead=latch_applies,
        )
        if begin_state == "journal_failed":
            if exclusive:
                device_lock.release()
            return _refuse(_journal_failed_error(command_id))
        if begin_state == "replay":
            if exclusive:
                device_lock.release()
            retained_receipt = self._receipts.get((device.device_id, command_id))
            if retained_receipt is not None:
                replay = dict(self._replay_view(retained_receipt[1]))
                replay["replayed"] = True
                return replay
        if begin_state == "conflict":
            if exclusive:
                device_lock.release()
            return _refuse(MHSError(
                "MHS.CONFLICT.COMMAND_ID_REUSE",
                "command_id was already used or is in flight for a different action",
                {"command_id": command_id, "retryable": False},
            ))
        if begin_state == "inflight" and inflight_entry is not None:
            if exclusive:
                device_lock.release()
            receipt = self._wait_inflight(inflight_entry, min(0.5, max(0.01, deadline_ms / 1000.0)))
            if receipt is not None:
                return receipt
            return _refuse(MHSError(
                "MHS.DEVICE.BUSY",
                "an identical command is already in flight",
                {"command_id": command_id, "retryable": True},
            ))

        # The permit is consumed only after every pre-effect check passed, and
        # atomically with respect to other requests (RE-SAFE-001).
        consumed_permit = False
        if permit_id and capability is not None and self._permit_required(device, capability):
            try:
                self._consume_permit(
                    session, device, capability, input_payload, input_digest, permit_id,
                    resource_id=target_resource,
                )
                consumed_permit = True
            except MHSError as exc:
                self._finish_inflight(device.device_id, command_id, input_digest)
                if exclusive:
                    device_lock.release()
                return _refuse(exc)

        operation: Operation | None = None
        try:
            # Inside the try: a missing bridge or a malformed max_duration_ms
            # must still release the device lock and the in-flight entry
            # (finally below); a malformed constraint is a failed receipt.
            bridge = self._bridge(device)
            # Plan 3.7: deadline_ms bounds only the wait for the response,
            # counted from the request (PROTO-011); max_duration_ms (binding,
            # else class) bounds the execution and is the bridge's budget.
            long_running, bound_ms = self._execution_bounds(capability)
            deadline_int = int(deadline_ms)
            if bound_ms is not None:
                exec_ms = bound_ms
            elif long_running:
                exec_ms = _LONG_RUNNING_DEFAULT_MAX_MS
            else:
                exec_ms = deadline_int  # nothing else bounds it
            ingress = _REQUEST_INGRESS.get()
            reply_by = (ingress if isinstance(ingress, float) else entered) + max(0.001, deadline_int / 1000.0)
            if time.monotonic() >= reply_by:
                # OP-012: the deadline passed in the pre-checks, before the
                # command was accepted.  Nothing was dispatched: refuse it
                # rather than start work its caller no longer waits for.
                self._return_permit(device, permit_id if consumed_permit else None)
                return _refuse(MHSError(
                    "MHS.OUTCOME.TIMEOUT",
                    f"the {deadline_int} ms deadline passed before the command was dispatched; "
                    "nothing was executed",
                    {"retryable": True,
                     "details": {"reason": "deadline_exceeded_before_dispatch", "deadline_ms": deadline_int},
                     "remediation": "Nothing ran: retry, with a longer deadline_ms if the device is slow to check."},
                ))
            # The execution bound counts from dispatch, the deadline from the request.
            exec_at = (time.monotonic() + max(0.001, exec_ms / 1000.0)
                       if bound_ms is not None or long_running else reply_by)
            response_at = min(reply_by, exec_at)
            # The execution bound ends the wait before the deadline does.
            bound_first = bound_ms is not None and exec_at <= reply_by
            cancel_event = threading.Event()
            ctx = _Context(
                command_id=command_id,
                session_id=session.session_id,
                device_id=device.device_id,
                resource=target_resource,
                deadline_ms=exec_ms if (bound_ms is not None or long_running) else deadline_ms,
                expected_revision=expected_revision,
                permit_id=permit_id,
                revision=current_revision,
                mode=device.mode,
                cancel_event=cancel_event,
                # The monotonic end of this call's execution budget (finding
                # SDK-14), so ctx.remaining_ms() is what is really left for
                # the bridge -- never the response deadline of a call that
                # declares a longer execution bound.
                extra={"deadline_at": exec_at, **({_sim_timing.CONTEXT_KEY: timing_report}
                       if timing_report is not None else {})},
            )
            operation = self._start_operation(
                session=session,
                device=device,
                capability=capability,
                bridge=bridge,
                ctx=ctx,
                command_id=command_id,
                input_payload=input_payload,
                input_digest=input_digest,
                deadline_ms=deadline_ms,
                held_lock=device_lock if exclusive else None,
                cancel_event=cancel_event,
                latch_check=latch_applies,
                expected_revision=expected_int,
                long_running=long_running,
                response_at=response_at,
                returnable_permit=permit_id if consumed_permit else None,
                reservations=reservations,
            )
            if operation is None:
                # An e-stop landed while this command was in its pre-checks.
                return _refuse(_estop_engaged_error(self._current_revision(device)))
            if isinstance(operation, _RevisionConflict):
                # A non-exclusive command changed the state after the check
                # above: nothing ran, so a permit this call consumed is given
                # back -- unless an e-stop revoked it meanwhile.
                self._return_permit(device, permit_id if consumed_permit else None)
                operation = None
                return _refuse(_revision_conflict_error(expected_int, self._current_revision(device)))
            if isinstance(inflight_entry, dict):
                inflight_entry["operation"] = operation
                event = inflight_entry.get("event")
                if isinstance(event, threading.Event):
                    event.set()
            started_op: Operation = operation

            def record_unknown(reason: str, cancellation_requested: bool) -> dict[str, Any] | None:
                """Record ``unknown`` + ``MHS.OUTCOME.TIMEOUT`` unless the final receipt won the race."""
                with started_op.outcome_lock:
                    claimed = not (started_op.final_receipt is not None or started_op.finishing
                                   or started_op.unknown_claimed)
                    if claimed:
                        started_op.unknown_claimed = True
                if not claimed:
                    return None
                try:
                    if reason == "max_duration_exceeded":
                        message = (f"command exceeded its max_duration_ms bound of {exec_ms} ms "
                                   f"(deadline_ms {deadline_int}); its outcome is unknown")
                    else:
                        message = (f"no outcome within the {deadline_int} ms deadline; the command "
                                   "keeps running and its final receipt replaces this one")
                    timeout_error = MHSError(
                        "MHS.OUTCOME.TIMEOUT",
                        message,
                        {
                            "retryable": False,
                            "details": {"operation_id": started_op.operation_id,
                                        "reason": reason,
                                        "deadline_ms": deadline_int,
                                        "max_duration_ms": bound_ms if bound_ms is not None
                                        else (exec_ms if long_running else None),
                                        "long_running": long_running,
                                        "cancellation_requested": cancellation_requested,
                                        "reconcile": "observe state; operations.get or a replay of the "
                                                     "command_id returns the final receipt"},
                        },
                    )
                    receipt = self._finish_command(
                        session=session,
                        device=device,
                        capability=capability,
                        command_id=command_id,
                        input_payload=input_payload,
                        input_digest=input_digest,
                        status="unknown",
                        output=None,
                        started=started,
                        deadline_ms=deadline_ms,
                        permit_id=permit_id,
                        operation_id=started_op.operation_id,
                        error=timeout_error,
                        cancellation={
                            "requested_at": canonical.now_rfc3339(),
                            "requested_by": session.principal.get("id"),
                            "reason": started_op.cancel_reason or "max_duration_ms exceeded",
                            "safe_state_achieved": False,
                        } if cancellation_requested else None,
                        bump=False,
                        vendor=timing_report.vendor() if timing_report is not None else None,
                        # Never wait for a slow device to answer the caller.
                        read_timeout_s=_DEADLINE_RECEIPT_READ_BOUND_S,
                    )
                    started_op.unknown_receipt = receipt
                    # The unknown receipt is what the caller was told (and the
                    # stored receipt); the operation itself is still running.
                    self._running_receipt(started_op, session, exec_ms=exec_ms, deadline_ms=deadline_int,
                                          long_running=long_running, bound_ms=bound_ms, unknown=receipt)
                    return receipt
                finally:
                    started_op.unknown_recorded.set()

            def request_bound_cancellation() -> bool:
                if not capability.cancellable or started_op.cancel_event.is_set():
                    return False
                started_op.cancel_reason = "max_duration_ms exceeded"
                started_op.cancel_event.set()
                return True

            def on_execution_bound() -> None:
                # max_duration_ms bounds the execution (plan 3.7): a cancellable
                # operation is asked to stop; a long-running one whose caller
                # holds only a running receipt then gets its unknown receipt.
                try:
                    if started_op.done.is_set():
                        return
                    requested = request_bound_cancellation()
                    if requested and started_op.done.wait(_MAX_DURATION_GRACE_S):
                        return
                    if long_running:
                        record_unknown("max_duration_exceeded", requested or started_op.cancel_event.is_set())
                except Exception:  # noqa: BLE001 - a timer thread must report, not die silently
                    _log.exception("execution bound of %s failed", started_op.operation_id)

            def arm_execution_bound() -> None:
                if bound_ms is None and not long_running:
                    return
                timer = threading.Timer(max(0.0, exec_at - time.monotonic()), on_execution_bound)
                timer.daemon = True
                timer.name = f"mhs-exec-bound-{started_op.operation_id}"
                with started_op.outcome_lock:
                    if started_op.final_receipt is not None or started_op.finishing:
                        return
                    started_op.bound_timer = timer
                timer.start()

            def answered_by_others() -> dict[str, Any]:
                # The worker is recording its final receipt, or the unknown one
                # was already claimed: answer with whichever exists.
                if started_op.unknown_claimed:
                    started_op.unknown_recorded.wait(_UNKNOWN_RECORD_WAIT_S)
                    if started_op.final_receipt is not None:
                        return dict(started_op.final_receipt)
                    if started_op.unknown_receipt is not None:
                        return dict(started_op.unknown_receipt)
                started_op.done.wait(_FINAL_RECEIPT_WAIT_S)
                if started_op.final_receipt is not None:
                    return dict(started_op.final_receipt)
                return self._running_receipt(started_op, session, exec_ms=exec_ms, deadline_ms=deadline_int,
                                             long_running=long_running, bound_ms=bound_ms)

            started_op.done.wait(max(0.0, response_at - time.monotonic()))
            if started_op.final_receipt is not None:
                return dict(started_op.final_receipt)
            if bound_first:
                # The execution bound, not the deadline, ended the wait: a
                # cancellable command is asked to stop (it may still answer
                # within the deadline); otherwise its outcome is unknown.
                requested = request_bound_cancellation()
                if requested:
                    started_op.done.wait(max(0.0, min(_MAX_DURATION_GRACE_S, reply_by - time.monotonic())))
                    if started_op.final_receipt is not None:
                        return dict(started_op.final_receipt)
                receipt = record_unknown("max_duration_exceeded", requested or started_op.cancel_event.is_set())
                return dict(receipt) if receipt is not None else answered_by_others()
            if long_running:
                # Plan 3.7 / OP-010: the current, non-terminal receipt with its
                # operation_id; never evidence, never cancelled by the deadline.
                arm_execution_bound()
                if started_op.final_receipt is not None:
                    return dict(started_op.final_receipt)
                return self._running_receipt(started_op, session, exec_ms=exec_ms, deadline_ms=deadline_int,
                                             long_running=long_running, bound_ms=bound_ms)
            # Plan 3.7: unknown + MHS.OUTCOME.TIMEOUT (retryable false); the
            # command keeps running -- the deadline never cancels it.
            receipt = record_unknown("deadline_exceeded", False)
            if receipt is None:
                return answered_by_others()
            arm_execution_bound()
            return dict(receipt)
        except MHSError as exc:
            if exc.code in ("MHS.OUTCOME.UNKNOWN",):
                return self._finish_command(
                    session=session,
                    device=device,
                    capability=capability,
                    command_id=command_id,
                    input_payload=input_payload,
                    input_digest=input_digest,
                    status="unknown",
                    output=None,
                    started=started,
                    deadline_ms=deadline_ms,
                    permit_id=permit_id,
                    error=exc,
                    vendor=timing_report.vendor(final=operation is None) if timing_report is not None else None,
                    bump=False,  # no bridge call ran in this thread
                )
            raise
        except Exception as exc:  # noqa: BLE001 - bridge failures become receipts
            error = MHSError("MHS.DEVICE.FAULTED", str(exc), {"detail": type(exc).__name__}, cause=exc)
            return self._finish_command(
                session=session,
                device=device,
                capability=capability,
                command_id=command_id,
                input_payload=input_payload,
                input_digest=input_digest,
                status="failed",
                output=None,
                started=started,
                deadline_ms=deadline_ms,
                permit_id=permit_id,
                error=error,
                vendor=timing_report.vendor(final=operation is None) if timing_report is not None else None,
                bump=False,  # no bridge call ran in this thread
            )
        finally:
            # Once the operation is registered its worker owns (and releases)
            # the device lock and the in-flight entry; before that, this call
            # releases the lock exactly once and frees the command_id (a
            # receipt, if one was written, already answers a replay).
            if operation is None:
                if begin_state == "new":
                    self._finish_inflight(device.device_id, command_id, input_digest)
                if exclusive:
                    try:
                        device_lock.release()
                    except RuntimeError:
                        pass

    def _execution_bounds(self, capability: Capability) -> tuple[bool, int | None]:
        """``(long_running, max_duration_ms)`` of a binding (plan 3.7).

        Each comes from the binding's ``constraints``, else from its
        catalogue class (an extension class has none).  A binding value that
        is not a number raises (a failed receipt; strict mode refuses it at
        construction).  ``max_duration_ms`` is None when nothing declares it.
        """
        constraints = capability.constraints if isinstance(capability.constraints, Mapping) else {}
        cls = self._class_constraints_of(capability.capability_id)
        if "long_running" in constraints:
            long_running = constraints.get("long_running") is True
        else:
            long_running = cls.get("long_running") is True
        raw = constraints.get("max_duration_ms")
        bound: int | None
        if raw:
            bound = max(1, int(raw))
        else:
            declared = cls.get("max_duration_ms")
            bound = (declared if isinstance(declared, int) and not isinstance(declared, bool) and declared > 0
                     else None)
        return long_running, bound

    def _class_constraints_of(self, capability_id: str) -> dict[str, Any]:
        """The catalogue ``constraints`` of a class ({} for an extension or uncatalogued id)."""
        cached = self._class_constraints.get(capability_id)
        if cached is not None:
            return cached
        if _catalog.is_extension(capability_id):
            found: dict[str, Any] = {}
        else:
            try:
                entry = _catalog.get(capability_id)
            except Exception:  # noqa: BLE001 - no catalogue: nothing to inherit, retry next time
                return {}
            found = dict(entry.get("constraints") or {}) if isinstance(entry, Mapping) else {}
        self._class_constraints[capability_id] = found
        return found

    def _running_receipt(self, operation: Operation, session: Session, *, exec_ms: int,
                         deadline_ms: int, long_running: bool, bound_ms: int | None,
                         unknown: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """The current, non-terminal receipt of a running operation (plan 3.7, OP-003/OP-010).

        Built from the operation's provisional receipt: ``status: running``
        with its ``operation_id`` and no outcome fields.  It is not evidence;
        the final receipt is.  It becomes the operation's current receipt
        (``operations.get`` / ``list`` and a replay of the command return it
        until the final receipt exists); after an ``unknown`` answer
        ``x-vendor.unknown_receipt_id`` names the recorded unknown receipt.
        """
        base = dict(operation.receipt or {})
        receipt = {key: value for key, value in base.items()
                   if key not in ("error", "ended_at", "state_revision_after", "state_hash_after",
                                  "output", "effects", "cancellation", "evidence", "x-vendor")}
        receipt["status"] = "running"
        receipt["operation_id"] = operation.operation_id
        receipt["principal"] = dict(session.principal)
        progress = base.get("progress")
        receipt["progress"] = (dict(progress) if isinstance(progress, Mapping)
                               and base.get("status") in ("accepted", "running") else {"percent": 0})
        receipt["replayed"] = False
        vendor: dict[str, Any] = {"long_running": bool(long_running), "deadline_ms": int(deadline_ms),
                                  "max_duration_ms": int(exec_ms) if (bound_ms is not None or long_running)
                                  else None}
        if isinstance(unknown, Mapping) and unknown.get("receipt_id"):
            vendor["unknown_receipt_id"] = unknown.get("receipt_id")
        if operation.simulation_timing is not None:
            vendor.update(operation.simulation_timing.vendor())
            receipt["progress"]["ticks"] = vendor[_sim_timing.NAMESPACE]["known_completed_ticks"]
        receipt["x-vendor"] = vendor
        receipt = _plain(receipt)
        with operation.outcome_lock:
            if operation.final_receipt is None:
                operation.receipt = receipt
        return dict(receipt)

    def _replay_view(self, stored: Mapping[str, Any]) -> Mapping[str, Any]:
        """What a replay of a retained receipt returns (OP-003, plan 3.7).

        A command answered ``unknown`` at its deadline that is still running
        reports its current (running) state; once it ended, the stored
        receipt is its final receipt.
        """
        if stored.get("status") == "unknown":
            operation = self._operations.get(str(stored.get("operation_id")))
            if (operation is not None and operation.final_receipt is None and not operation.done.is_set()
                    and isinstance(operation.unknown_receipt, Mapping)
                    and operation.unknown_receipt.get("receipt_id") == stored.get("receipt_id")
                    and isinstance(operation.receipt, Mapping)
                    and operation.receipt.get("status") == "running"):
                return operation.receipt
        return stored

    def _achieve_safe_state(self, device: Device) -> bool:
        """Run the declared safe-state capabilities and report the outcome.

        This path deliberately bypasses session grants, permits and rate limits:
        ``safe_state.achieved_by`` capabilities are always callable (SAFE-029).
        All-must-succeed: the safe state is achieved only when every declared
        action succeeded and the bridge does not report otherwise; with no
        declared action only the bridge's own positive report counts.
        """
        bridge = device.bridge
        if bridge is None:
            return False
        achieved_by = (device.safety.safe_state or {}).get("achieved_by") or []
        failures = self._run_safe_state_actions(device)
        reported = _bridge_safe_state(bridge)
        if achieved_by:
            return not failures and reported is not False
        return reported is True

    def _start_operation(
        self,
        *,
        session: Session,
        device: Device,
        capability: Capability,
        bridge: Any,
        ctx: _Context,
        command_id: str,
        input_payload: dict[str, Any],
        input_digest: str,
        deadline_ms: int,
        held_lock: threading.Lock | None,
        cancel_event: threading.Event | None = None,
        latch_check: bool = False,
        expected_revision: int | None = None,
        long_running: bool = False,
        response_at: float | None = None,
        returnable_permit: str | None = None,
        reservations: list[tuple[tuple[str, str], float, str]] | None = None,
    ) -> "Operation | _RevisionConflict | None":
        """Register and start the operation worker.

        With ``latch_check`` the e-stop latch is re-read under ``self._lock`` in
        the same critical section that registers the operation, so an e-stop
        either sees (and cancels) the operation or the operation sees the latch
        and is not started (returns None).  This closes the window between the
        pre-checks and the bridge call (finding SDK-02, repro e7 b).
        ``expected_revision`` is re-checked in the same critical section
        (plan 3.6 step 12): a revision that moved since the check returns a
        :class:`_RevisionConflict` and nothing is started.  The worker checks
        it once more right before the bridge call, after its state read
        (RESIDUAL-B, 4d r3): a revision that moved during that read gives a
        ``rejected`` ``MHS.CONFLICT.REVISION`` receipt with the true current
        revision, nothing is dispatched, ``returnable_permit`` (a permit this
        command consumed) is given back and ``reservations`` (the command's
        cumulative-budget draws) are released, as on the registration-path
        refusal (RESIDUAL-B verifier: a fresh command was refused
        ``MHS.SAFETY.CUMULATIVE_LIMIT`` by the draw of one that never ran).

        The id is ``op_`` plus a full 26-character ULID (finding SDK-06: the
        old 20-character prefix collided within one millisecond); an id that
        is already registered is refused, never overwritten.

        Revisions (plan 3.7): a catalogued read class never advances the
        revision; any other outcome -- completed, failed, cancelled, unknown
        -- advances it only when the device state hash (every resource, with
        its ``hash_exclusions``) after the call differs from the hash before
        it (or cannot be computed).  A stop class or ``safe_state.achieved_by``
        action is never delayed by that state read (a bridge read may wait
        for a lock a running call holds, where a stop is dispatched beside
        it): it advances the revision whenever it runs, like the e-stop.

        ``response_at`` is the monotonic end of the caller's wait (the state
        reads around the call are bounded by it; ``ctx`` carries the
        execution budget instead).  Outcomes (plan 3.7): an output, or
        :mod:`mhs.signals` -- ``Cancelled`` (also ``asyncio`` /
        ``concurrent.futures`` cancellation and the legacy outputs
        ``{"status": "cancelled"}`` and, once cancellation was requested,
        ``{"cancelled": true}``) is ``cancelled``; ``DriverFailed`` is
        ``failed`` with its code; ``Busy`` is ``rejected`` ``MHS.DEVICE.BUSY``;
        ``OutcomeUnknown`` is ``unknown``; an ``MHSError`` keeps its code;
        anything else is ``MHS.ADAPTER.SHIM_FAILED`` with a redacted message.
        """
        operation_id = _new_operation_id()
        started = time.time()
        provisional = {
            "receipt_id": canonical.ulid(),
            "command_id": command_id,
            "operation_id": operation_id,
            "session_id": session.session_id,
            "endpoint_id": self.endpoint_id,
            "device_id": device.device_id,
            "capability_id": capability.capability_id,
            "resource_ids": [capability.resource],
            "input_digest": input_digest,
            "status": "accepted",
            "mode": device.mode,
            "principal": session.principal,
            "accepted_at": canonical.now_rfc3339(),
            "started_at": canonical.now_rfc3339(),
            "state_revision_before": self._current_revision(device),
            "replayed": False,
            "progress": {"percent": 0},
        }
        operation = Operation(
            operation_id=operation_id,
            device_id=device.device_id,
            capability_id=capability.capability_id,
            command_id=command_id,
            session_id=session.session_id,
            receipt=provisional,
            cancel_event=cancel_event or threading.Event(),
            owner=self._owner_of(session),
            resource=capability.resource,
            long_running=bool(long_running),
            cancellable=capability.cancellable,
            simulation_timing=_sim_timing.report_from_context(ctx),
        )
        # PROTO-003: the bridge must observe the operation's own cancellation
        # event; a private Event would make explicit cancellation a no-op.
        ctx.cancel_event = operation.cancel_event
        publisher = None
        if self._artifact_store is not None:
            scope = _artifacts.ArtifactScope(session.session_id, device.device_id, capability.resource,
                                             capability.capability_id, command_id)
            def artifact_guard() -> None:
                # Worker authority is the captured, already-authorized session;
                # never trust a principal copied from driver output or Context.
                with self._lock:
                    if (self._closed or self._sessions.get(session.session_id) is not session
                            or session.released or session.expired()):
                        raise MHSError("MHS.SESSION.EXPIRED", "artifact session is no longer active")
                    if not session.allows(device.device_id, capability.capability_id, capability.resource):
                        raise MHSError("MHS.SESSION.CAPABILITY_NOT_GRANTED", "artifact capability is not granted")
                if operation.cancel_event.is_set():
                    raise MHSError("MHS.CAPABILITY.OUTPUT_INVALID", "artifact publication was cancelled")
                deadline_at = (ctx.extra or {}).get("deadline_at")
                if isinstance(deadline_at, (int, float)) and time.monotonic() >= deadline_at:
                    raise MHSError("MHS.OUTCOME.TIMEOUT", "artifact publication exceeded its execution budget")
            publisher = self._artifact_store.publisher(scope, artifact_guard)
            ctx.extra = {**(ctx.extra or {}), _artifacts.CONTEXT_KEY: publisher}
        tracked = not self._is_read_capability(capability)
        # Stops are dispatched at once: no state read before them (see above).
        measured = tracked and not self._is_safe_state_action(device, capability.capability_id)
        configure = capability.capability_id == _CONFIGURE

        #: The state reads this worker started.  The device lock of an
        #: exclusive command is released only once every one of them returned:
        #: an exclusive call never runs beside the server's own state read
        #: (a native that is not thread-safe), not even one that outlived its
        #: bound (4d r2 verifier).
        reads: list[_StateRead] = []

        def remaining() -> float | None:
            # What is left of the caller's wait for the response (plan 3.7).
            if isinstance(response_at, (int, float)):
                return float(response_at) - time.monotonic()
            deadline_at = (getattr(ctx, "extra", None) or {}).get("deadline_at")
            return float(deadline_at) - time.monotonic() if isinstance(deadline_at, (int, float)) else None

        def before_bound() -> float:
            # Never let the read before the call use up the caller's budget.
            left = remaining()
            if left is None:
                return _REVISION_READ_BOUND_S
            return max(0.002, min(_REVISION_READ_BOUND_S, left / 2.0))

        def after_bound() -> float:
            # The read after the call answers inside the response deadline
            # (unanswered, it is an unknown change: the revision advances);
            # once the deadline passed the caller was answered, so the final
            # receipt may take the full bound.
            left = remaining()
            if left is None or left <= 0:
                return _REVISION_READ_BOUND_S
            return max(0.002, min(_REVISION_READ_BOUND_S, left - max(0.02, left / 4.0)))

        def read_state(bound: float) -> _StateRead:
            read = self._start_state_read(device)
            reads.append(read)
            read.done.wait(max(0.0, bound))
            return read

        def outcome_changed(before: str | None) -> tuple[bool, dict[str, Any] | None]:
            if not measured:
                return tracked, None
            try:
                after, document = self._state_read_digest(device, read_state(after_bound()))
            except Exception:  # noqa: BLE001 - an unreadable state is an unknown change
                return True, None
            return (before is None or after is None or after != before), document

        def release_device_lock() -> None:
            try:
                held_lock.release()  # type: ignore[union-attr]
            except RuntimeError:
                pass

        def release_after(pending: list[_StateRead]) -> None:
            for read in pending:
                read.done.wait()
            release_device_lock()

        def begin_final() -> dict[str, Any] | None:
            # Plan 3.7: exactly one final receipt per command.  From here on no
            # unknown receipt can be claimed; one already claimed (the response
            # deadline or the execution bound passed) is recorded first, and
            # this final receipt reconciles it.
            with operation.outcome_lock:
                operation.finishing = True
                claimed = operation.unknown_claimed
                timer = operation.bound_timer
            if timer is not None:
                timer.cancel()
            if claimed and not operation.unknown_recorded.wait(_UNKNOWN_RECORD_WAIT_S):
                _log.warning("operation %s: its unknown receipt was not recorded in time; the final "
                             "receipt follows without the reconciliation link", operation_id)
            unknown = operation.unknown_receipt
            if not isinstance(unknown, Mapping):
                return None
            return {"receipt_id": unknown.get("receipt_id"), "status": "unknown",
                    "mhs_code": (unknown.get("error") or {}).get("mhs_code")}

        def vendor_of(non_finite: Any, reconciles: Mapping[str, Any] | None) -> dict[str, Any] | None:
            vendor: dict[str, Any] = {}
            if non_finite:
                vendor["non_finite_output"] = non_finite
            if reconciles:
                vendor["reconciles"] = dict(reconciles)
            if operation.simulation_timing is not None:
                vendor.update(operation.simulation_timing.vendor(final=True))
            return vendor or None

        def finish(receipt: dict[str, Any], reconciles: Mapping[str, Any] | None) -> None:
            if reconciles and receipt.get("status") == "rejected":
                # A late rejection (Busy: nothing was actuated) resolves the
                # unknown receipt; like every rejected attempt it is not the
                # command's outcome, so the command id is free again (OP-005).
                key = (device.device_id, command_id)
                with self._lock:
                    self._forget_receipt(key, reconciles.get("receipt_id"))
            operation.final_receipt = receipt
            operation.state = receipt["status"]

        def worker() -> None:
            before: str | None = None
            try:
                if measured:
                    pre = read_state(before_bound())
                    if held_lock is not None:
                        # Exclusive: the call waits for a read that outlived its
                        # bound, as it would for the device lock.  The deadline
                        # bounds only the response (plan 3.7); an e-stop or a
                        # cancellation ends the wait, and nothing is dispatched.
                        while not pre.done.wait(0.02) and not operation.cancel_event.is_set():
                            pass
                    before = self._state_read_digest(device, pre)[0]
                native_error: BaseException | None = None
                moved_to: int | None = None
                if expected_revision is not None and not operation.cancel_event.is_set():
                    # The last check before dispatch (plan 3.6 step 12): another
                    # command may have completed while the state was read.
                    with self._lock:
                        current = self._current_revision(device)
                    if current != expected_revision:
                        moved_to = current
                if moved_to is not None:
                    self._return_permit(device, returnable_permit)
                    self._release_cumulative(list(reservations or []))
                    reconciles = begin_final()
                    receipt = self._finish_command(
                        session=session,
                        device=device,
                        capability=capability,
                        command_id=command_id,
                        input_payload=input_payload,
                        input_digest=input_digest,
                        status="rejected",
                        output=None,
                        started=started,
                        deadline_ms=deadline_ms,
                        permit_id=ctx.permit_id,
                        operation_id=operation_id,
                        error=_revision_conflict_error(expected_revision, moved_to),
                        vendor=vendor_of(None, reconciles),
                        bump=False,
                        read_timeout_s=_REVISION_READ_BOUND_S,
                        # This worker owns the reservation; nothing ran, so the
                        # command id is free for a retry (OP-005).
                        release_inflight=True,
                    )
                    finish(receipt, reconciles)
                    return
                if operation.cancel_event.is_set():
                    # Cancelled (an e-stop, operations.cancel) after it was
                    # registered but before it reached the bridge: never
                    # dispatch it to a bridge that may not poll the event.
                    output: Any = {"status": "cancelled"}
                else:
                    try:
                        output = _call_native(bridge, capability, input_payload, ctx)
                    except (_Cancelled, asyncio.CancelledError, concurrent.futures.CancelledError):
                        output = {"status": "cancelled"}
                    except BaseException as exc:  # noqa: BLE001 - classified below (plan 3.7)
                        native_error = exc
                        output = None
                if native_error is not None:
                    status, error = _native_outcome(native_error)
                    # failed / unknown advance the revision only on a state
                    # change; a rejection (Busy) never does.
                    changed, after = outcome_changed(before)
                    reconciles = begin_final()
                    receipt = self._finish_command(
                        session=session,
                        device=device,
                        capability=capability,
                        command_id=command_id,
                        input_payload=input_payload,
                        input_digest=input_digest,
                        status=status,
                        output=None,
                        started=started,
                        deadline_ms=deadline_ms,
                        permit_id=ctx.permit_id,
                        operation_id=operation_id,
                        error=error,
                        vendor=vendor_of(None, reconciles),
                        bump=changed and status != "rejected",
                        state_after=after,
                        read_timeout_s=_REVISION_READ_BOUND_S,
                        # This worker owns the reservation: a Busy rejection ends it.
                        release_inflight=True,
                    )
                    finish(receipt, reconciles)
                    return
                # PROTO-003: a cancellation is only "acknowledged" when the
                # worker reports it.  A cooperative bridge raises
                # mhs.signals.Cancelled or returns {"status": "cancelled"} (or,
                # legacy, {"cancelled": true} once cancellation was requested);
                # a bridge that ignored the request and applied its effect must
                # be receipted as completed so state and receipt agree.
                # A receipt is canonical JSON: NaN / infinities become null and
                # are listed (x-vendor.non_finite_output), in every mode.
                plain_output, non_finite = _strict.replace_non_finite(_plain(output))
                cancelled = isinstance(plain_output, Mapping) and (
                    str(plain_output.get("status")) == "cancelled"
                    or (operation.cancel_event.is_set() and plain_output.get("cancelled") is True)
                )
                safe_state = self._achieve_safe_state(device) if cancelled else None
                changed, after = outcome_changed(before)
                if configure and not cancelled:
                    plain_output = self._configure_output(device, capability, plain_output, input_payload, after)
                output_error = (None if cancelled
                                else self._check_output(device, capability, plain_output, non_finite))
                published = []
                if publisher is not None:
                    if cancelled or output_error is not None:
                        publisher.abort()
                    else:
                        published = publisher.prepare(plain_output)
                reconciles = begin_final()
                receipt = self._finish_command(
                    session=session,
                    device=device,
                    capability=capability,
                    command_id=command_id,
                    input_payload=input_payload,
                    input_digest=input_digest,
                    artifacts=published or None,
                    artifact_publisher=publisher if published else None,
                    status=("cancelled" if cancelled
                            else "failed" if output_error is not None else "completed"),
                    output=None if output_error is not None else plain_output,
                    error=output_error,
                    vendor=vendor_of(non_finite, reconciles),
                    started=started,
                    deadline_ms=deadline_ms,
                    permit_id=ctx.permit_id,
                    operation_id=operation_id,
                    cancellation=(
                        {
                            "requested_at": canonical.now_rfc3339(),
                            "requested_by": session.principal.get("id"),
                            "reason": getattr(operation, "cancel_reason", None) or "client cancelled",
                            "safe_state_achieved": bool(safe_state),
                        }
                        if cancelled
                        else None
                    ),
                    bump=changed,
                    state_after=after,
                    revision_output=configure and not cancelled and output_error is None,
                    read_timeout_s=_REVISION_READ_BOUND_S,
                )
                finish(receipt, reconciles)
            except Exception as exc:  # noqa: BLE001 - an internal failure still ends the command
                try:
                    changed, after = outcome_changed(before)
                    reconciles = begin_final()
                    receipt = self._finish_command(
                        session=session,
                        device=device,
                        capability=capability,
                        command_id=command_id,
                        input_payload=input_payload,
                        input_digest=input_digest,
                        status="unknown" if getattr(exc, "code", None) == "MHS.OUTCOME.UNKNOWN" else "failed",
                        output=None,
                        started=started,
                        deadline_ms=deadline_ms,
                        permit_id=ctx.permit_id,
                        operation_id=operation_id,
                        error=exc if isinstance(exc, MHSError)
                        else MHSError("MHS.INTERNAL.ERROR", f"internal error: {type(exc).__name__}",
                                      {"retryable": False, "details": {"exception_type": type(exc).__name__}}),
                        vendor=vendor_of(None, reconciles),
                        bump=changed,
                        state_after=after,
                        read_timeout_s=_REVISION_READ_BOUND_S,
                    )
                    finish(receipt, reconciles)
                except Exception:  # noqa: BLE001
                    _log.exception("operation %s: its final receipt could not be recorded", operation_id)
                    operation.state = "failed"
            finally:
                if publisher is not None:
                    publisher.abort()
                with operation.outcome_lock:
                    operation.finishing = True
                    timer = operation.bound_timer
                if timer is not None:
                    timer.cancel()
                operation.done.set()
                if held_lock is not None:
                    pending = [read for read in reads if not read.done.is_set()]
                    if pending:
                        # The receipt is out; the next exclusive command is
                        # MHS.DEVICE.BUSY until the device answered the reads.
                        threading.Thread(target=release_after, args=(pending,),
                                         name=f"mhs-op-release-{operation_id}", daemon=True).start()
                    else:
                        release_device_lock()

        thread = threading.Thread(target=worker, name=f"mhs-op-{operation_id}", daemon=True)
        operation.thread = thread
        with self._lock:
            if latch_check and self._latched.get(device.device_id):
                return None
            if expected_revision is not None and self._current_revision(device) != expected_revision:
                return _RevisionConflict(self._current_revision(device))
            if operation_id in self._operations:
                raise AssertionError(f"operation id collision: {operation_id} is already registered")
            self._operations[operation_id] = operation
            thread.start()
        return operation

    def _start_state_read(self, device: Device) -> "_StateRead":
        """Start one read of every resource of ``device`` in a daemon worker (plan 3.7).

        Every resource is read (a command may change more than its own
        resource; the revision is the device's).  :meth:`_state_read_digest`
        gives the hash the revision rule compares once the read answered.
        """
        bridge = device.bridge
        resources = list(device.resources)
        read = _StateRead({resource.resource_id: _plain(resource.state or {}) for resource in resources})
        if bridge is None:
            read.done.set()  # answered, with nothing read: the change is unknown
            return read

        def read_all() -> None:
            states: dict[str, Any] = {}
            complete = True
            try:
                for resource in resources:
                    try:
                        states[resource.resource_id] = _plain(bridge.read(resource.resource_id))
                    except Exception:  # noqa: BLE001 - an unreadable state is an unknown change
                        complete = False
            except BaseException:
                complete = False
                raise
            finally:
                read.states, read.complete = states, complete
                read.done.set()

        thread = threading.Thread(target=read_all, name="mhs-revision-read", daemon=True)
        read.thread = thread
        thread.start()
        return read

    def _state_read_digest(self, device: Device, read: "_StateRead") -> tuple[str | None, dict[str, Any]]:
        """The hash the revision rule compares (plan 3.7) and the state document of ``read``.

        Fail closed: the hash is None -- an unknown change, which advances the
        revision -- when the device has no bridge, when any read raises (the
        base ``Bridge.read`` ``unsupported`` too) or has not answered yet, or
        when the state is not canonical JSON.  It is never the hash of the
        declared ``Resource.state``: comparing that fallback with itself hid
        every change of a device whose state cannot be read, so a stale
        ``expected_revision`` executed (4d verifier p1).  The returned document
        still carries the declared state of a resource that could not be read,
        for the receipt's ``state_hash_after`` only (the fallback of
        :meth:`_resource_state_hash`).
        """
        if not read.done.is_set() or read.states is None:
            return None, read.fallback  # not answered in time: the change is unknown
        document = {resource_id: read.states.get(resource_id, state) for resource_id, state in read.fallback.items()}
        if not read.complete:
            return None, document
        try:
            return self._device_state_hash(device, document), document
        except Exception:  # noqa: BLE001 - not canonical JSON: the change is unknown
            return None, document

    def _configure_output(self, device: Device, capability: Capability, raw: Any,
                          patch: Mapping[str, Any], after: Mapping[str, Any] | None) -> dict[str, Any]:
        """The ``cap.device.configure.v1`` output ``{applied, revision}`` (FOLLOWUPS WP-02 -> WP-04).

        ``applied`` is what the bridge reports it applied (``{"applied":
        {...}}``, values after any device rounding); otherwise each patched
        parameter as the state reads back after the call (the patch value when
        the state does not carry it).  ``revision`` is set by
        :meth:`_finish_command` to the revision after the write.
        """
        reported = raw.get("applied") if isinstance(raw, Mapping) else None
        if isinstance(reported, Mapping):
            applied = dict(reported)
        else:
            state = (after or {}).get(capability.resource)
            applied = {key: (state[key] if isinstance(state, Mapping) and key in state else value)
                       for key, value in patch.items()}
        return {"applied": _plain(applied), "revision": self._current_revision(device)}

    def _finish_command(
        self,
        *,
        session: Session,
        device: Device,
        capability: Capability | None,
        command_id: str,
        input_payload: dict[str, Any],
        input_digest: str,
        status: str,
        output: Any,
        started: float,
        deadline_ms: int,
        permit_id: str | None,
        capability_id: str | None = None,
        operation_id: str | None = None,
        error: MHSError | None = None,
        cancellation: dict[str, Any] | None = None,
        effects: list[dict[str, Any]] | None = None,
        bump: bool = True,
        read_timeout_s: float | None = None,
        vendor: Mapping[str, Any] | None = None,
        artifacts: Sequence[Mapping[str, Any]] | None = None,
        artifact_publisher: _artifacts.ArtifactPublisher | None = None,
        resource_id: str | None = None,
        state_after: Mapping[str, Any] | None = None,
        revision_output: bool = False,
        release_inflight: bool = False,
    ) -> dict[str, Any]:
        """Record the receipt of one command outcome.

        ``bump``: advance the revision (the command worker passes whether the
        device state changed, plan 3.7; refusals pass False).  The revisions
        before and after are read in one critical section with the bump, so
        a concurrent completion cannot make ``after`` jump by two.
        ``resource_id`` names the resource when no binding resolved (an
        unbound resource).  ``state_after`` is the device state the worker
        already read (``{resource_id: state}``), hashed instead of reading
        again.  ``revision_output`` puts the revision after this command in
        ``output.revision`` (``cap.device.configure.v1``).

        A final receipt (``completed``, ``failed``, ``cancelled``,
        ``unknown``) releases the command id's reservation for the same input.
        A ``rejected`` receipt releases it only with ``release_inflight`` (the
        command worker, whose bridge answered ``Busy``): a refusal is usually
        a duplicate's, and the reservation it collided with belongs to the
        command still in flight (the caller that reserved the id releases it
        itself).
        """
        with self._lock:
            revision_before = self._current_revision(device)
            if bump:
                self._bump_revision(device, session)
            revision_after = self._current_revision(device)
        if revision_output and isinstance(output, Mapping):
            output = {**dict(output), "revision": revision_after}
        resolved_capability_id = (
            capability.capability_id if capability is not None else str(capability_id)
        )
        resolved_resource = (
            capability.resource if capability is not None
            else (resource_id or device.primary_resource.resource_id)
        )
        resource_state: Any = _NO_STATE
        if isinstance(state_after, Mapping) and resolved_resource in state_after:
            resource_state = state_after[resolved_resource]
        receipt = self._receipt(
            session=session,
            device=device,
            capability_id=resolved_capability_id,
            resource_ids=[resolved_resource],
            command_id=command_id,
            input_payload=input_payload,
            input_digest=input_digest,
            status=status,
            output=output,
            started=started,
            error=error,
            operation_id=operation_id,
            permit_id=permit_id,
            cancellation=cancellation,
            effects=effects,
            revision_before=revision_before,
            revision_after=revision_after,
            read_timeout_s=read_timeout_s,
            vendor=vendor,
            artifacts=artifacts,
            resource_state=resource_state,
            record=artifact_publisher is None,
        )
        if artifact_publisher is not None:
            # Every fallible precommit step precedes public retained indexes.
            # Grants activate before the no-I/O index closure, so an unlocked
            # idempotency lookup can never observe a completed but staged image.
            publish = self._retain_receipt((device.device_id, command_id), input_digest,
                                           receipt, deferred=True)
            with self._artifact_publication_lock:
                receipt = artifact_publisher.commit(lambda: self._record_receipt(receipt), publish)
            # Publication is irreversible. Each delivery step is independent:
            # journal failure cannot leave the reservation occupied or revoke
            # a completed receipt's already-active grant.
            try:
                with self._lock:
                    self._journal_retained_receipt((device.device_id, command_id), input_digest, receipt)
            except Exception:
                _log.exception("artifact receipt %s committed; journal delivery failed", receipt["receipt_id"])
            try:
                self._finish_inflight(device.device_id, command_id, input_digest)
            except Exception:
                _log.exception("artifact receipt %s committed; reservation release failed", receipt["receipt_id"])
            try:
                self._notify("state", device.device_id, {"revision": receipt.get("state_revision_after"),
                                                          "state_hash": receipt.get("state_hash_after")})
            except Exception:
                _log.exception("artifact receipt %s committed; notification delivery failed", receipt["receipt_id"])
            return receipt
        # Legacy receipt path is unchanged when no artifact was published.
        if status != "rejected":
            with self._lock:
                self._retain_receipt((device.device_id, command_id), input_digest, receipt)
        if status in ("completed", "failed", "cancelled", "unknown") or (
                status == "rejected" and release_inflight):
            self._finish_inflight(device.device_id, command_id, input_digest)
        self._notify("state", device.device_id, {"revision": receipt.get("state_revision_after"),
                                                  "state_hash": receipt.get("state_hash_after")})
        return receipt

    def _receipt(
        self,
        *,
        session: Session,
        device: Device,
        capability_id: str,
        resource_ids: list[str],
        command_id: str,
        input_payload: dict[str, Any],
        status: str,
        input_digest: str | None = None,
        output: Any = None,
        started: float | None = None,
        error: MHSError | None = None,
        operation_id: str | None = None,
        permit_id: str | None = None,
        effects: list[dict[str, Any]] | None = None,
        cancellation: dict[str, Any] | None = None,
        revision_before: int | None = None,
        read_timeout_s: float | None = None,
        vendor: Mapping[str, Any] | None = None,
        artifacts: Sequence[Mapping[str, Any]] | None = None,
        revision_after: int | None = None,
        resource_state: Any = None,
        record: bool = True,
    ) -> dict[str, Any]:
        revision = revision_after if revision_after is not None else self._current_revision(device)
        now = canonical.now_rfc3339()
        resource_id = resource_ids[0] if resource_ids else device.primary_resource.resource_id
        if resource_state is None or resource_state is _NO_STATE:
            state_hash_after = self._resource_state_hash(device, resource_id, timeout_s=read_timeout_s)
        else:
            state_hash_after = self._hash_resource_state(device, resource_id, resource_state)
        receipt: dict[str, Any] = {
            "receipt_id": canonical.ulid(),
            "command_id": command_id,
            "session_id": session.session_id,
            "endpoint_id": self.endpoint_id,
            "device_id": device.device_id,
            "capability_id": capability_id,
            "resource_ids": list(resource_ids),
            "input_digest": input_digest
            if input_digest is not None
            else action_digest(capability_id, resource_id, input_payload),
            "status": status,
            "mode": device.mode,
            "principal": dict(session.principal),
            "accepted_at": now,
            "started_at": now,
            "ended_at": canonical.now_rfc3339(),
            "state_revision_before": revision if revision_before is None else revision_before,
            "state_revision_after": revision,
            "state_hash_after": state_hash_after,
            "output": _plain(output),
            "effects": self._sanitize_effects(
                effects if effects is not None else self._effects_for(device, capability_id, status, resource_id),
                device,
                status,
            ),
            "progress": {"percent": 100 if status in ("completed", "failed", "cancelled", "unknown") else 0},
            "replayed": False,
        }
        if artifacts:
            receipt["artifacts"] = _plain(list(artifacts))
        if operation_id:
            receipt["operation_id"] = operation_id
        if started is not None:
            receipt["x-vendor"] = {"duration_ms": int(max(0.0, time.time() - started) * 1000)}
        if vendor:
            receipt.setdefault("x-vendor", {}).update(_plain(dict(vendor)))
            timing = vendor.get(_sim_timing.NAMESPACE)
            if isinstance(timing, Mapping):
                ticks = timing.get("known_completed_ticks")
                if isinstance(ticks, int) and not isinstance(ticks, bool) and ticks >= 0:
                    receipt["progress"]["ticks"] = ticks
        if permit_id:
            approvals = self._receipt_approvals(permit_id, session, now)
            if approvals:
                receipt["approvals"] = approvals
        if cancellation:
            receipt["cancellation"] = {
                key: value
                for key, value in dict(cancellation).items()
                if key in ("requested_at", "requested_by", "reason", "safe_state_achieved")
            }
        if error is not None:
            receipt["error"] = self._receipt_error(error)
        # The evidence chain stores the receipt as JSON; drop non-JSON values
        # early so a misbehaving bridge cannot corrupt the log.
        receipt = _plain(receipt)
        return self._record_receipt(receipt) if record else receipt

    def _record_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """Append a receipt and keep the record receipt.schema.json-valid.

        ``EvidenceLog.append`` stamps a top-level ``kind`` on every record.
        Receipts are closed documents (``additionalProperties: false``), so that
        stamp makes every exported receipt schema-invalid.  Strip it from the
        in-memory record and recompute its chain digest; the in-memory evidence
        chain stays continuous and offline verification still recomputes the
        same links.  (Server-side workaround for the foundation's evidence
        record wrapper; the evidence module itself is not modified.)
        """
        recorded = self._evidence.append_receipt(receipt)
        if "kind" in recorded:
            try:
                from .evidence import compute_record_digest

                with self._evidence._lock:  # noqa: SLF001 - see docstring
                    stored = self._evidence._records[-1]
                    stored.pop("kind", None)
                    prev = (stored.get("evidence") or {}).get("prev_digest")
                    digest = compute_record_digest(stored, prev)
                    stored.setdefault("evidence", {})["digest"] = digest
                    self._evidence._head = digest
                recorded.pop("kind", None)
                recorded.setdefault("evidence", {})["digest"] = digest
            except Exception:  # noqa: BLE001 - never lose the receipt itself
                pass
        return recorded

    def _receipt_error(self, error: MHSError) -> dict[str, Any]:
        """Return an error object valid against ``defs.schema.json#/$defs/error``."""
        data = dict(error.data or {})
        result: dict[str, Any] = {
            "mhs_code": str(error.code),
            "message": str(error.message or error.code),
            "retryable": bool(data.get("retryable", False)),
        }
        details = data.get("details")
        extras = {
            key: value
            for key, value in data.items()
            if key not in ("retryable", "details", "current_revision", "remediation", "interlocks")
        }
        merged: dict[str, Any] = dict(details) if isinstance(details, Mapping) else {}
        merged.update(extras)
        if merged:
            result["details"] = _plain(merged)
        if isinstance(data.get("current_revision"), int):
            result["current_revision"] = int(data["current_revision"])
        if isinstance(data.get("remediation"), str):
            result["remediation"] = data["remediation"]
        interlocks = data.get("interlocks")
        if isinstance(interlocks, list):
            cleaned = [
                {
                    key: item[key]
                    for key in ("id", "state", "description")
                    if key in item
                }
                for item in interlocks
                if isinstance(item, Mapping)
            ]
            if cleaned:
                result["interlocks"] = cleaned
        return result

    def _receipt_approvals(self, permit_id: str, session: Session, now: str) -> list[dict[str, Any]]:
        permit = self._permits.get(permit_id)
        approvals = list(getattr(permit, "approvals", None) or [])
        if not approvals:
            approvals = [{"principal": str((session.principal or {}).get("id") or "unknown"),
                          "method": "auto"}]
        cleaned: list[dict[str, Any]] = []
        for approval in approvals:
            if not isinstance(approval, Mapping):
                continue
            principal = approval.get("principal")
            if not isinstance(principal, str) or not principal:
                principal = str((session.principal or {}).get("id") or "unknown")
            entry: dict[str, Any] = {"permit_id": permit_id, "principal": principal}
            if approval.get("method") in ("human_click", "policy_rule", "dual_control", "auto"):
                entry["method"] = approval["method"]
            if isinstance(approval.get("approved_at"), str):
                entry["approved_at"] = approval["approved_at"]
            if isinstance(approval.get("evidence_ref"), str):
                entry["evidence_ref"] = approval["evidence_ref"]
            cleaned.append(entry or {"permit_id": permit_id, "principal": principal})
        return cleaned

    def _sanitize_effects(
        self, effects: Any, device: Device, status: str
    ) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for effect in effects if isinstance(effects, list) else []:
            if not isinstance(effect, Mapping):
                continue
            kind = str(effect.get("kind") or "").strip()
            if not kind:
                continue
            entry: dict[str, Any] = {
                "kind": kind,
                "summary": str(effect.get("summary") or kind),
                "reversible": bool(effect.get("reversible", status != "unknown")),
                "severity": effect.get("severity")
                if effect.get("severity") in ("R0", "R1", "R2", "R3")
                else device.safety.risk_class,
            }
            if isinstance(effect.get("irreversible_reason"), str):
                entry["irreversible_reason"] = effect["irreversible_reason"]
            cleaned.append(entry)
        if not cleaned:
            cleaned.append(
                {
                    "kind": "capability.invoke",
                    "summary": f"capability {status}",
                    "reversible": status != "unknown",
                    "severity": device.safety.risk_class,
                }
            )
        return cleaned

    def _effects_for(self, device: Device, capability_id: str, status: str,
                     resource: str | None = None) -> list[dict[str, Any]]:
        binding = device._by_binding.get((capability_id, str(resource)))
        candidates = [binding] if binding is not None else device.capabilities
        for cap in candidates:
            if cap.capability_id == capability_id:
                semantics = cap.semantics or {}
                effects = semantics.get("effects") or []
                return [
                    {
                        "kind": str(effect),
                        "summary": f"{capability_id} ({status})",
                        "reversible": status != "unknown",
                        "severity": device.safety.risk_class,
                    }
                    for effect in effects
                ] or [
                    {"kind": "capability.invoke", "summary": f"{capability_id} ({status})",
                     "reversible": status != "unknown", "severity": device.safety.risk_class}
                ]
        return [{"kind": "capability.invoke", "summary": f"{capability_id} ({status})",
                 "reversible": status != "unknown", "severity": device.safety.risk_class}]

    # -- safety checks ----------------------------------------------
    def _check_input(
        self,
        device: Device,
        capability: Capability,
        plan: _limits_plan.BindingPlan,
        payload: dict[str, Any],
        revision: int,
        *,
        strict: bool,
    ) -> MHSError | None:
        """Plan 3.6 steps 7-9 for one command; the refusal, or None.

        7. Structure: the served input schema without the bound keywords of
           limited fields -- a shape error is ``MHS.CAPABILITY.INPUT_INVALID``.
           A ``cap.device.configure.v1`` input (also ``mhs.resource.write``) is
           a patch of the resource's state: a key that is no ``state_schema``
           property is ``MHS.RESOURCE.FIELD_UNKNOWN``, a ``readOnly`` one
           ``MHS.RESOURCE.NOT_WRITABLE``; the served schema is the writable
           state properties (in every mode).
        8. Limits (:func:`mhs.limits.check`): every array element and nested
           leaf -> ``MHS.SAFETY.ENVELOPE_VIOLATION`` with the first
           violation's ``{path, kind, bound, value, unit, source, ...}`` and
           every violation in ``details.violations``.  Then
           ``MHS.SAFETY.LIMITS_UNSET``: a value set at an ``operator_required``
           path no overlay filled (every mode), or -- strict mode, hardware or
           hybrid, R1+, write/invoke -- at a numeric leaf no limit covers.
           Stop classes are never refused for a missing bound.
        9. The remaining schema bounds: the full served input schema.
        """
        if plan.error is not None or plan.limits is None:
            error = plan.error
            return MHSError(
                "MHS.ADAPTER.MANIFEST_INVALID",
                f"the limits of {capability.capability_id} cannot be enforced as declared: {error}",
                {"retryable": False, "current_revision": revision,
                 "details": {"reason": "limits_invalid", "rule": getattr(error, "rule", None),
                             "path": getattr(error, "path", None), "source": getattr(error, "source", None)},
                 "remediation": "Fix the limit declaration (binding limits, safety.envelope or site_limits)."},
            )
        # step 7
        if capability.capability_id == _CONFIGURE:
            refusal = self._check_configure_fields(device, capability, payload)
            if refusal is not None:
                return refusal
        if plan.first_pass_schema:
            errors = schema_validate(payload, plan.first_pass_schema)
            if errors:
                return _input_invalid(errors, revision)
        # step 8
        violations = _limits.check(payload, plan.limits)
        if violations:
            return MHSError(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                _limits_plan.violation_message(violations),
                {"details": _limits_plan.violation_details(violations),
                 "current_revision": revision, "retryable": False},
            )
        # A stop class is never refused for a missing bound (a declared one
        # still applies above): refusing a stop is never the safer outcome.
        stop = capability.capability_id in _STOP_CLASSES
        unset = [] if stop else _limits_plan.present_paths(plan, payload, plan.unset)
        if unset:
            return _limits_unset_error(capability, unset, "operator_required", revision)
        if strict and self._limits_unset_applies(device, capability, plan):
            unlimited = _limits_plan.present_paths(plan, payload, plan.unlimited)
            if unlimited:
                return _limits_unset_error(capability, unlimited, "no_limit", revision)
        # step 9
        if plan.two_pass and plan.served_schema:
            errors = schema_validate(payload, plan.served_schema)
            if errors:
                return _input_invalid(errors, revision)
        if not strict:
            self._warn_class_input(device, capability, plan, payload)
        return None

    @staticmethod
    def _check_configure_fields(device: Device, capability: Capability,
                                payload: Mapping[str, Any]) -> MHSError | None:
        """``cap.device.configure.v1``: the patch keys are writable properties of the resource state.

        A key outside the resource's ``state_schema`` is
        ``MHS.RESOURCE.FIELD_UNKNOWN`` (PROTO-025); a ``readOnly`` property (a
        measured value) is ``MHS.RESOURCE.NOT_WRITABLE`` (the class notes).
        Nested state follows the same rules at every depth (4d verifier p2):
        in an object property that declares ``properties`` (or
        ``patternProperties``), a key it does not declare is unknown unless
        ``additionalProperties`` admits it; a ``readOnly`` property -- or
        anything inside a ``readOnly`` object -- is not writable; array
        elements are checked against ``prefixItems`` / ``items``.  A free-form
        object (no ``properties``) takes any keys.
        A node is read together with its ``allOf`` / ``anyOf`` / ``oneOf`` /
        ``then`` / ``else`` branches and its local ``$ref`` (4d r2 verifier):
        ``readOnly`` in any branch makes it read-only, the keys any branch
        declares are declared, and a ``$ref`` that does not resolve inside the
        state schema is not writable (what it allows cannot be known).  A
        ``readOnly`` state root makes every key not writable; the draft-07
        tuple form ``items: [...]`` is read by position, then
        ``additionalItems``; a ``false`` schema admits nothing (unknown)
        (RESIDUAL-B, 4d r3).
        ``details.fields`` names state paths in the limit path syntax
        (``ch1.measured_current``, ``channels[1].reading``).
        """
        if not isinstance(payload, Mapping):
            return None  # not an object: the input schema refuses it (INPUT_INVALID)
        resource = device._by_resource.get(capability.resource)
        schema = (resource.state_schema if resource is not None else None) or {}
        nested_unknown: list[str] = []
        nested_read_only: list[str] = []

        def branches(node: Any, depth: int = 0) -> list[Mapping[str, Any]] | None:
            """``node`` and every branch it is composed of; None: a $ref that cannot be resolved."""
            if not isinstance(node, Mapping):
                return []
            if depth > 32:
                return None  # a $ref cycle
            out: list[Mapping[str, Any]] = [node]
            parts: list[Any] = []
            ref = node.get("$ref")
            if ref is not None:
                try:
                    target = _resolve_pointer(schema, ref) if isinstance(ref, str) and ref.startswith("#") else None
                except Exception:  # noqa: BLE001 - an unresolvable pointer: unknown
                    target = None
                if not isinstance(target, Mapping):
                    return None
                parts.append(target)
            for keyword in ("allOf", "anyOf", "oneOf"):
                group = node.get(keyword)
                if isinstance(group, (list, tuple)):
                    parts.extend(group)
            parts.extend(node.get(keyword) for keyword in ("then", "else"))
            for part in parts:
                found = branches(part, depth + 1)
                if found is None:
                    return None
                out.extend(found)
            return out

        def declares_keys(node: Mapping[str, Any]) -> bool:
            return isinstance(node.get("properties"), Mapping) or isinstance(node.get("patternProperties"), Mapping)

        def declared(nodes: list[Mapping[str, Any]], key: str) -> list[Any]:
            """The schemas the branches declare ``key`` with (``properties``, matching ``patternProperties``)."""
            targets: list[Any] = []
            for node in nodes:
                children = node.get("properties")
                patterns = node.get("patternProperties")
                if isinstance(children, Mapping) and key in children:
                    targets.append(children[key])
                if isinstance(patterns, Mapping):
                    for pattern, child in patterns.items():
                        try:
                            if re.search(str(pattern), key):
                                targets.append(child)
                        except re.error:
                            targets.append({"readOnly": True})  # an unusable pattern: fail closed
            return targets

        def walk(node: Any, value: Any, path: str) -> None:
            if node is False:
                nested_unknown.append(path)  # the schema admits nothing here
                return
            nodes = branches(node)
            if nodes is None or any(item.get("readOnly") for item in nodes):
                nested_read_only.append(path)
                return
            if isinstance(value, Mapping):
                keyed = [entry for entry in nodes if declares_keys(entry)]
                if not keyed:
                    return  # a free-form object
                extras = [entry.get("additionalProperties") for entry in keyed]
                for key, item in value.items():
                    child = f"{path}.{key}"
                    targets = declared(keyed, str(key))
                    if targets:
                        for target in targets:
                            walk(target, item, child)
                        continue
                    # Undeclared: written only when every branch that declares
                    # its keys admits more (true or a schema).
                    if all(extra is True or isinstance(extra, Mapping) for extra in extras):
                        for extra in extras:
                            if isinstance(extra, Mapping):
                                walk(extra, item, child)
                    else:
                        nested_unknown.append(child)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    for entry in nodes:
                        prefix = entry.get("prefixItems")
                        items = entry.get("items")
                        if isinstance(prefix, (list, tuple)) and index < len(prefix):
                            walk(prefix[index], item, f"{path}[{index}]")
                        elif isinstance(items, (list, tuple)):
                            # draft-07 tuple form: positional items, then additionalItems
                            walk(items[index] if index < len(items) else entry.get("additionalItems"),
                                 item, f"{path}[{index}]")
                        else:
                            walk(items, item, f"{path}[{index}]")

        roots = branches(schema)
        if roots is None or any(root.get("readOnly") for root in roots):
            # The state schema itself cannot be resolved, or the whole state is
            # readOnly (in any branch): nothing is writable.
            roots, unresolved = [], True
        else:
            unresolved = False
        properties: dict[str, Any] = {}
        for root in roots:
            children = root.get("properties")
            if isinstance(children, Mapping):
                for name, child in children.items():
                    properties.setdefault(str(name), child)
        unknown_top: list[str] = []
        for key, value in payload.items():
            if unresolved:
                nested_read_only.append(str(key))
                continue
            targets = [root["properties"][key] for root in roots
                       if isinstance(root.get("properties"), Mapping) and key in root["properties"]]
            if not targets:
                unknown_top.append(str(key))
            for target in targets:
                walk(target, value, str(key))
        unknown = sorted(set(unknown_top + nested_unknown))
        if unknown:
            return MHSError(
                "MHS.RESOURCE.FIELD_UNKNOWN",
                f"{', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} not "
                f"{'a property' if len(unknown) == 1 else 'properties'} of the state of {capability.resource!r}",
                {"retryable": False,
                 "details": {"fields": unknown, "resource": capability.resource,
                             "writable": sorted(name for name, item in properties.items()
                                                if isinstance(item, Mapping) and not item.get("readOnly"))}},
            )
        read_only = sorted(set(nested_read_only))
        if read_only:
            return MHSError(
                "MHS.RESOURCE.NOT_WRITABLE",
                f"{', '.join(read_only)} of {capability.resource!r} {'is' if len(read_only) == 1 else 'are'} "
                "read-only (a measured value, not a parameter)",
                {"retryable": False, "details": {"fields": read_only, "resource": capability.resource}},
            )
        return None

    def _warn_class_input(self, device: Device, capability: Capability, plan: _limits_plan.BindingPlan,
                          payload: Mapping[str, Any]) -> None:
        """Compatibility mode: a drifting binding's input is also checked against the class input.

        Plan 3.6 step 7 validates binding ∩ class; compatibility mode serves
        the drifting binding schema, so a call the class schema refuses is an
        :class:`MHSStrictWarning` (once per capability), not a refusal.
        """
        effective = plan.effective
        if effective is None or getattr(effective, "extension", False) or not getattr(effective, "drift", ()):
            return
        schema = getattr(effective, "class_input_schema", None)
        key = ("class-input", device.device_id, capability.capability_id)
        if not isinstance(schema, Mapping) or key in self._compat_warned:
            return
        try:
            errors = schema_validate(payload, schema)
        except Exception:  # noqa: BLE001 - an unevaluable class schema is not this call's fault
            return
        if errors:
            self._compat_warn(key, (
                f"{device.device_id} {capability.capability_id}: input does not match the class input "
                f"schema ({errors[0]}) -- compatibility mode: served with the drifting binding schema; "
                "strict=True refuses the binding (MHS.INTERNAL.SCHEMA_DRIFT)"))

    def _reserve_cumulative(
        self,
        device: Device,
        capability: Capability,
        plan: _limits_plan.BindingPlan,
        payload: dict[str, Any],
        revision: int,
    ) -> list[tuple[tuple[str, str], float, str]]:
        """Reserve the cumulative budgets the command draws on (SAFE-016, plan 3.6 step 10).

        The budgets are the intersected ``per`` rules of the binding's limits
        (:attr:`mhs.limits.EffectiveLimits.cumulative`); an amount is the sum
        of the magnitudes of the addressed values, so a negative value never
        refunds a budget.  Safe-state actions are exempt (SAFE-029).
        """
        reservations: list[tuple[tuple[str, str], float, str]] = []
        if self._is_safe_state_action(device, capability.capability_id):
            return reservations
        draws = _limits_plan.cumulative_amounts(plan, payload)
        if not draws:
            return reservations
        # RE-SAFE-002: pruning, usage calculation, every field check and the
        # reservations themselves are one transaction.  A reservation carries
        # its own token so a refusal releases exactly this command's usage.
        with self._cumulative_lock:
            try:
                now = time.time()
                for rule, requested in draws:
                    window_name = str(rule.per)
                    window_s = _CUMULATIVE_WINDOWS.get(window_name, None)
                    key = (f"{device.device_id}|{capability.capability_id}|{rule.path}", window_name)
                    usage = self._cumulative_usage.setdefault(key, [])
                    if window_s is not None:
                        cutoff = now - window_s
                        self._cumulative_usage[key] = usage = [
                            item for item in usage if float(item.get("t", 0)) >= cutoff
                        ]
                    elif window_name == "session":
                        cutoff = now - max(3600.0, float(self.receipt_retention_s))
                        self._cumulative_usage[key] = usage = [
                            item for item in usage if float(item.get("t", 0)) >= cutoff
                        ]
                    used = sum(float(item.get("amount", 0)) for item in usage)
                    amount = float(requested)
                    limit_value = rule.max.value
                    if used + amount > float(limit_value) + 1e-12:
                        raise MHSError(
                            "MHS.SAFETY.CUMULATIVE_LIMIT",
                            f"{rule.path}={amount:g} would exceed the {window_name} budget "
                            f"({used:g}+{amount:g} > {limit_value:g})",
                            {"details": {"field": rule.path, "path": rule.path, "used": used,
                                         "limit": limit_value, "requested": amount, "window": window_name,
                                         "unit": rule.unit, "source": rule.max.origin.label},
                             "current_revision": revision, "retryable": False},
                        )
                    token = canonical.ulid()
                    usage.append({"t": now, "amount": amount, "id": token})
                    reservations.append((key, amount, token))
                    # state_dir: a restart never refills a budget.
                    self._journal({"op": "draw", "key": key[0], "window": key[1], "t": now,
                                   "amount": amount, "id": token})
            except MHSError:
                self._release_cumulative(reservations)
                raise
        return reservations

    def _release_cumulative(
        self, reservations: list[tuple[tuple[str, str], float, str]]
    ) -> None:
        """Release exactly the reservations created by this command."""
        if not reservations:
            return
        with self._cumulative_lock:
            for key, _amount, token in reservations:
                self._journal({"op": "release", "id": token})
                usage = self._cumulative_usage.get(key)
                if not usage:
                    continue
                self._cumulative_usage[key] = [
                    item for item in usage if item.get("id") != token
                ]

    def _check_output(
        self, device: Device, capability: Capability, output: Any, non_finite: Sequence[str]
    ) -> MHSError | None:
        """Validate a completed call's output against its output schema (plan 3.6 step 12).

        Strict mode: a mismatch is ``MHS.CAPABILITY.OUTPUT_INVALID`` and the
        receipt is ``failed`` (the native call ran: its effect may have
        happened).  The schema is the served binding ∩ class one.
        Compatibility mode: the resolved schema is checked and a mismatch is
        an :class:`MHSStrictWarning`, once per capability; the receipt is
        unchanged.
        """
        strict = self._is_strict(device)
        if strict:
            schema = capability.output_schema or {"type": "object"}
        else:
            resolved = self._effective.get((device.device_id, capability.capability_id, capability.resource))
            schema = getattr(resolved, "output_schema", None)
        if not isinstance(schema, Mapping) or not schema:
            return None
        try:
            errors = schema_validate(output, schema)
        except Exception as exc:  # noqa: BLE001 - an unevaluable schema is a mismatch
            errors = [f"$: the output schema could not be evaluated ({type(exc).__name__})"]
        if not errors:
            return None
        if not strict:
            self._compat_warn(
                ("output", device.device_id, capability.capability_id),
                f"{device.device_id} {capability.capability_id}: output does not match the resolved "
                f"output_schema ({errors[0]}) -- compatibility mode: completed anyway; strict=True "
                "gives a failed receipt MHS.CAPABILITY.OUTPUT_INVALID",
            )
            return None
        details: dict[str, Any] = {"errors": errors[:8]}
        if non_finite:
            details["non_finite"] = list(non_finite)[:32]
        return MHSError(
            "MHS.CAPABILITY.OUTPUT_INVALID",
            f"the result of {capability.capability_id} does not match its output_schema",
            {"retryable": False, "details": details,
             "remediation": "Driver defect: map the native result onto the capability output."},
        )

    def _check_interlocks(self, device: Device, capability: Capability | None) -> None:
        # The e-stop latch is checked by _run_command (plan 3.6 step 5), with the
        # safe-state exemptions; interlocks are step 11.
        if capability is None:
            return
        required = device.safety.required_interlocks_for(capability.capability_id)
        if not required:
            return
        bridge = self._bridge(device)
        try:
            live = _plain(bridge.interlocks() or [])
        except Exception as exc:  # noqa: BLE001 - fail closed
            raise MHSError(
                "MHS.SAFETY.INTERLOCK_OPEN",
                "interlock state could not be read; treating required interlocks as open",
                {"interlocks": [{"id": entry.get("id"), "state": "unknown"} for entry in required],
                 "retryable": False, "details": {"error": type(exc).__name__}},
            ) from exc
        interlocks = {str(i.get("id")): str(i.get("state")) for i in live}
        blocked = [
            {"id": entry.get("id"), "state": interlocks.get(str(entry.get("id")), "unknown")}
            for entry in required
            if interlocks.get(str(entry.get("id"))) != "closed"
        ]
        if blocked:
            raise MHSError(
                "MHS.SAFETY.INTERLOCK_OPEN",
                "required interlock is not closed: " + ", ".join(str(b["id"]) for b in blocked),
                {"interlocks": blocked, "retryable": False},
            )

    def _verify_approvals(
        self,
        *,
        device: Device,
        capability_id: str,
        resource: str,
        input_digest: str,
        principal: str,
        approvals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Authenticate approvals according to the deployed trust policy.

        R3 hardware requires a configured approval authority that attests the
        human decision (SAFE-033/034).  Without one the endpoint fails closed.
        Simulated/hybrid fixtures may use the documented permissive policy; a
        string such as ``human:name`` is never treated as authentication.
        """
        requires_human = device.mode == "hardware" and device.safety.risk_class == "R3"
        if (not requires_human and self._hardware_effect(device, resource)
                and _RISK_ORDER.get(device.safety.risk_class, 0) >= 2):
            # SURF-01 / SAFE-032: a permit for an R2+ action on real hardware
            # is a human decision the endpoint must be able to verify; strict
            # mode fails closed without the approval verifier.
            if self._is_strict(device):
                requires_human = True
            else:
                self._compat_warn(
                    ("permit", device.device_id),
                    f"{device.device_id}: permit for {capability_id} on {device.safety.risk_class} "
                    f"{device.mode} issued without a verified human approval -- compatibility mode: "
                    "allowed; strict=True requires MHSServer(approval_verifier=...) (fail closed)",
                )
        normalised: list[dict[str, Any]] = []
        for approval in approvals:
            if isinstance(approval, Mapping):
                normalised.append(dict(approval))
        if requires_human:
            if self._approval_verifier is None:
                raise MHSError(
                    "MHS.SAFETY.APPROVAL_REQUIRED",
                    f"{device.safety.risk_class} {device.mode} approval requires a configured "
                    "authenticated approval authority",
                    {"device_id": device.device_id, "capability_id": capability_id,
                     "resource": resource, "input_digest": input_digest,
                     "reason": "approval_authority_unavailable", "retryable": False},
                )
            request = {
                "device_id": device.device_id,
                "capability_id": capability_id,
                "resource": resource,
                "input_digest": input_digest,
                "principal": principal,
                "approvals": normalised,
                "risk_class": device.safety.risk_class,
                "mode": device.mode,
            }
            try:
                verified = self._approval_verifier(request)
            except Exception as exc:  # noqa: BLE001 - fail closed
                raise MHSError(
                    "MHS.SAFETY.APPROVAL_REQUIRED",
                    "approval authority rejected or failed the verification",
                    {"reason": "approval_verifier_failed", "detail": type(exc).__name__,
                     "retryable": False},
                ) from exc
            if not isinstance(verified, Mapping) or verified.get("verified") is not True:
                raise MHSError(
                    "MHS.SAFETY.APPROVAL_REQUIRED",
                    "approval authority did not verify a human approval for this action",
                    {"reason": "approval_not_verified", "retryable": False},
                )
            attested = verified.get("approvals")
            if not isinstance(attested, list) or not attested:
                attested = normalised
            cleaned: list[dict[str, Any]] = []
            for approval in attested:
                if not isinstance(approval, Mapping):
                    continue
                method = approval.get("method")
                if method not in ("human_click", "dual_control", "policy_rule", "auto"):
                    continue
                if method in ("auto", "policy_rule"):
                    continue  # cannot satisfy an R3 hardware requirement
                who = approval.get("principal") or approval.get("principal_id")
                if not isinstance(who, str) or not who:
                    continue
                entry: dict[str, Any] = {"principal": who, "method": method}
                if isinstance(approval.get("approved_at"), str):
                    entry["approved_at"] = approval["approved_at"]
                if isinstance(approval.get("evidence_ref"), str):
                    entry["evidence_ref"] = approval["evidence_ref"]
                cleaned.append(entry)
            if not cleaned or not any(a["method"] in ("human_click", "dual_control") for a in cleaned):
                raise MHSError(
                    "MHS.SAFETY.APPROVAL_REQUIRED",
                    "no verified human_click/dual_control approval for the exact action",
                    {"retryable": False},
                )
            return cleaned
        # Non-hardware (simulated/hybrid): the fixture policy may auto-approve,
        # but human-looking claims without an authority are downgraded.
        for approval in normalised:
            method = approval.get("method", "auto")
            if method in ("human_click", "dual_control") and self._approval_verifier is None:
                approval["method"] = "policy_rule"
                approval["x-vendor-unverified"] = True
        return normalised

    def _permit_required(self, device: Device, capability: Capability | None) -> bool:
        if capability is None:
            return False
        if self._is_safe_state_action(device, capability.capability_id):
            return False  # SAFE-029: safe-state actions are exempt from permits
        return bool(capability.requires_permit) or device.safety.permits_required_for(capability.capability_id)

    def _check_permit(
        self,
        session: Session,
        device: Device,
        capability: Capability | None,
        payload: dict[str, Any],
        input_digest: str,
        permit_id: str | None,
        *,
        consume: bool = False,
        resource_id: str | None = None,
    ) -> None:
        if capability is None or not self._permit_required(device, capability):
            return
        if not permit_id:
            raise MHSError(
                "MHS.SAFETY.PERMIT_INVALID",
                f"capability {capability.capability_id!r} requires an approved permit",
                {"capability_id": capability.capability_id, "retryable": False,
                 "remediation": "Call mhs.safety.permit with the exact input_digest."},
            )
        permit = self._permits.get(permit_id)
        if permit is None:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit does not exist", {"permit_id": permit_id})
        if permit.used:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit was already used", {"permit_id": permit_id})
        if permit.expires_at < time.time():
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit has expired", {"permit_id": permit_id})
        if permit.capability_id != capability.capability_id:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit is for a different capability")
        if permit.input_digest != input_digest:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit was issued for different input")
        if getattr(permit, "principal", None) and permit.principal != str((session.principal or {}).get("id")):
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit was issued to a different principal")
        target_resource = resource_id or capability.resource
        if permit.session_id is not None and permit.session_id != session.session_id:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit was issued in a different session",
                           {"permit_id": permit_id})
        if permit.device_id is not None and permit.device_id != device.device_id:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit is for a different device",
                           {"permit_id": permit_id})
        if permit.resource is not None and permit.resource != target_resource:
            raise MHSError("MHS.SAFETY.PERMIT_INVALID", "permit is for a different resource",
                           {"permit_id": permit_id})
        if consume:
            permit.used = True

    # -- helpers -----------------------------------------------------
    def _device(self, device_id: Any, *, adopt: bool = True) -> Device:
        """The device ``device_id`` names (full id or last path segment).

        ``adopt``: a strict device added after construction is resolved first
        (:meth:`_adopt_late_device`, which may refuse it); the e-stop path
        passes False, so every caller can still stop any device.
        """
        device = self._lookup_device(device_id)
        return self._adopt_late_device(device) if adopt else device

    def _lookup_device(self, device_id: Any) -> Device:
        if device_id is None:
            if len(self.devices) == 1:
                return next(iter(self.devices.values()))
            raise MHSError(
                "MHS.CAPABILITY.INPUT_INVALID",
                "device_id is required when the endpoint has several devices",
                {"devices": list(self.devices)},
            )
        if isinstance(device_id, str) and device_id in self.devices:
            return self.devices[device_id]
        if isinstance(device_id, str):
            matches = [
                device for key, device in self.devices.items()
                if key.rsplit("/", 1)[-1] == device_id or key == device_id
            ]
            if len(matches) == 1:
                return matches[0]
        raise MHSError(
            "MHS.DEVICE.UNKNOWN",
            f"unknown device {device_id!r}",
            {"device_id": device_id, "retryable": False},
        )

    def _device_from_session(self, session: Session, device_id: Any) -> Device:
        """Resolve an optional device_id against a session (single-device default)."""
        if device_id:
            device = self._device(device_id)
            if device.device_id not in session.device_ids:
                raise MHSError(
                    "MHS.SESSION.CAPABILITY_NOT_GRANTED",
                    "session does not cover this device",
                    {"device_id": device.device_id, "retryable": False},
                )
            return device
        if len(session.device_ids) == 1:
            return self._adopt_late_device(self.devices[session.device_ids[0]])
        raise MHSError(
            "MHS.CAPABILITY.INPUT_INVALID",
            "device_id is required when the session covers several devices",
            {"devices": list(session.device_ids)},
        )

    def _locate(self, session: Session, device_id: Any, resource_id: Any) -> tuple[Device, str]:
        if device_id is None:
            for candidate_id in session.device_ids:
                device = self.devices.get(candidate_id)
                if device and any(r.resource_id == resource_id for r in device.resources):
                    return self._adopt_late_device(device), str(resource_id)
            if len(session.device_ids) == 1:
                device = self._adopt_late_device(self.devices[session.device_ids[0]])
                return device, str(resource_id or device.primary_resource.resource_id)
            raise MHSError("MHS.CAPABILITY.INPUT_INVALID", "device_id is required when the session covers several devices")
        device = self._device(device_id)
        return device, str(resource_id or device.primary_resource.resource_id)

    def _session(self, session_id: Any) -> Session:
        if not isinstance(session_id, str) or not session_id:
            raise MHSError("MHS.SESSION.UNKNOWN", "session_id is required")
        session = self._sessions.get(session_id)
        if session is None or not self._owns_session(session):
            # A token-bound session is reported exactly like an unknown one to
            # any other caller (SURF-02: a leaked session id grants nothing).
            raise MHSError("MHS.SESSION.UNKNOWN", f"unknown session {session_id!r}", {"session_id": session_id})
        # A released session (the expiry timer keeps its record) is expired
        # even if a racing heartbeat moved expires_at.
        if session.released or session.expired():
            if not session.released:
                # Noticed before the timer: the same transition (cancel and
                # drive the devices safe), not only a release.
                self._expire_session(session, pop=True)
            raise MHSError("MHS.SESSION.EXPIRED", "session has expired", {"session_id": session_id})
        return session

    def _release_session(self, session: Session, reason: str, *, pop: bool = True) -> list[Operation]:
        """Release permits/subscriptions and cancel running operations.

        Returns the operations whose cancellation it requested.  With
        ``pop=False`` (the expiry timer) the session record stays, marked
        ``released``, so its next use still reports ``MHS.SESSION.EXPIRED``.
        """
        with self._lock:
            if pop:
                self._sessions.pop(session.session_id, None)
            session.released = True
            for subscription_id, subscription in list(self._subscriptions.items()):
                if subscription.get("session_id") == session.session_id:
                    self._subscriptions.pop(subscription_id, None)
            for permit in self._permits.values():
                if permit.session_id == session.session_id:
                    permit.used = True
            # A running stop / safe-state action is never cancelled (SAFE-029).
            operations = [
                operation for operation in self._operations.values()
                if operation.session_id == session.session_id and operation.final_receipt is None
                and not operation.cancel_event.is_set()
                and not (operation.device_id in self.devices and self._is_safe_state_action(
                    self.devices[operation.device_id], operation.capability_id))
            ]
            for operation in operations:
                operation.cancel_reason = reason
                operation.cancel_event.set()
        return operations

    def _prune_sessions(self, now: float) -> None:
        for session_id, session in list(self._sessions.items()):
            if session.released:
                with self._lock:
                    if self._sessions.get(session_id) is session and session.expired(now):
                        self._sessions.pop(session_id, None)
            elif session.expired(now):
                self._expire_session(session, pop=True)

    # -- session expiry timer ------------------------------------------
    def _ensure_session_reaper(self) -> None:
        """Start the session-expiry timer if it is not running (one per server)."""
        with self._lock:
            thread = self._reaper_thread
            if thread is not None and thread.is_alive():
                self._reaper_wake.set()
                return
            thread = threading.Thread(
                target=_session_reaper_loop, args=(weakref.ref(self), self._reaper_wake),
                name="mhs-session-expiry", daemon=True,
            )
            self._reaper_thread = thread
            thread.start()

    def _reap_expired_sessions(self) -> float | None:
        """Expire every session past its TTL; return seconds to the next expiry.

        Returns None (and lets the timer thread end) when no live session is
        left; the next ``mhs.session.open`` starts it again.
        """
        now = time.time()
        with self._lock:
            expired = [session for session in self._sessions.values()
                       if session.expired(now) and not session.released]
            live = [session.expires_at for session in self._sessions.values()
                    if not session.expired(now)]
            if not expired and not live:
                self._reaper_thread = None
                return None
        for session in expired:
            try:
                self._expire_session(session)
            except Exception:  # noqa: BLE001 - one bad session must not stop the timer
                _log.exception("session expiry failed for %s", session.session_id)
        if not live:
            return _REAPER_MAX_WAIT_S
        return max(0.0, min(live) - time.time())

    def _expire_session(self, session: Session, *, pop: bool = False) -> None:
        """Cancel an expired session's operations and drive its devices safe.

        00-architecture §6.5: expiry transitions any running operation to
        cancellation-to-safe-state.  Each device that was running an
        operation of the session gets its ``safe_state.achieved_by`` actions
        (bounded by the e-stop budget, in a daemon worker) besides the
        cancellation; read-only operations are only cancelled.  Whichever
        path notices the expiry first (the timer, a use of the session, a
        heartbeat, the pruning at ``session.open``) runs this once: only the
        first release returns the operations.  A device without
        ``achieved_by`` relies on cooperative cancellation alone (logged); a
        failed safe-state action is logged as an error.  ``pop=False`` (the
        timer) keeps the record, marked ``released``.
        """
        operations = self._release_session(session, "session expired", pop=pop)
        effectful: dict[str, Device] = {}
        for operation in operations:
            device = self.devices.get(operation.device_id)
            if device is None:
                continue
            capability = self._operation_binding(device, operation)
            if self._is_read_capability(capability) or self._is_safe_state_action(
                device, operation.capability_id
            ):
                continue
            effectful[device.device_id] = device
        for device in effectful.values():
            if not (device.safety.safe_state or {}).get("achieved_by"):
                _log.warning("session %s expired with a running operation on %s, which declares no "
                             "safe_state.achieved_by: only cooperative cancellation was requested",
                             session.session_id, device.device_id)
                continue
            _log.warning("session %s expired with a running operation on %s: running its safe-state "
                         "actions", session.session_id, device.device_id)
            worker = threading.Thread(
                target=self._expiry_safe_state, args=(device, session.session_id),
                name=f"mhs-expiry-safe-state-{device.device_id.rsplit('/', 1)[-1]}", daemon=True,
            )
            worker.start()

    def _expiry_safe_state(self, device: Device, session_id: str) -> None:
        """Worker of :meth:`_expire_session`: run and report the safe-state actions."""
        try:
            failures = self._run_safe_state_actions(device)
        except Exception:  # noqa: BLE001 - a daemon worker must report, not die silently
            _log.exception("session %s expired: the safe-state actions of %s raised",
                           session_id, device.device_id)
            return
        if failures:
            _log.error("session %s expired: safe-state actions failed on %s: %s",
                       session_id, device.device_id,
                       ", ".join(f"{item['capability_id']} ({item['error'].get('type')})"
                                 for item in failures))

    def _bridge(self, device: Device) -> Any:
        if device.bridge is None:
            raise MHSError("MHS.DEVICE.NOT_READY", f"device {device.device_id!r} has no bridge", {"device_id": device.device_id})
        return device.bridge

    def _read_state(self, device: Device, resource_id: str, fields: Any = None) -> dict[str, Any]:
        bridge = self._bridge(device)
        try:
            state = bridge.read(resource_id, fields=fields)
        except TypeError:
            state = bridge.read(resource_id)
        if state is None:
            state = {}
        if isinstance(state, Mapping):
            state = dict(state)
        else:
            state = {"value": _plain(state), "resource_id": resource_id}
        resource = device._by_resource.get(resource_id)
        if resource is not None and resource.state is not None and device.mode == "replay":
            state = dict(resource.state)
        return _plain(state)

    def _resource_state_hash(
        self, device: Device, resource_id: str, *, timeout_s: float | None = None
    ) -> str:
        """State hash of one resource.

        With ``timeout_s`` the bridge read runs in a daemon worker and falls back
        to the last declared state when the device does not answer in time (an
        e-stop receipt must not wait on a hung device).
        """
        resource = device._by_resource.get(resource_id)
        exclusions = list((resource.hash_exclusions if resource else None) or [])
        fallback = (resource.state if resource else None) or {}
        bridge = device.bridge
        if bridge is None:
            return canonical.state_hash(_plain(fallback), exclusions)
        if timeout_s is None:
            try:
                state = _plain(bridge.read(resource_id))
            except Exception:  # noqa: BLE001 - hashing must not fail the operation
                state = _plain(fallback)
            return canonical.state_hash(state, exclusions)
        holder: dict[str, Any] = {}

        def read() -> None:
            try:
                holder["state"] = _plain(bridge.read(resource_id))
            except Exception:  # noqa: BLE001
                pass

        reader = threading.Thread(target=read, name="mhs-state-read", daemon=True)
        reader.start()
        reader.join(max(0.0, float(timeout_s)))
        state = holder.get("state", _plain(fallback)) if not reader.is_alive() else _plain(fallback)
        try:
            return canonical.state_hash(state, exclusions)
        except Exception:  # noqa: BLE001 - a non-JSON state must not lose the receipt
            return canonical.state_hash(_plain(fallback), exclusions)

    def _hash_resource_state(self, device: Device, resource_id: str, state: Any) -> str:
        """``state_hash_after`` of a state already read (see :meth:`_resource_state_hash`)."""
        resource = device._by_resource.get(resource_id)
        exclusions = list((resource.hash_exclusions if resource else None) or [])
        try:
            return canonical.state_hash(_plain(state), exclusions)
        except Exception:  # noqa: BLE001 - a non-JSON state must not lose the receipt
            return self._resource_state_hash(device, resource_id)

    def _bump_revision(self, device: Device, session: Session | None = None) -> int:
        with self._lock:
            revision = self._revisions.get(device.device_id, 0) + 1
            self._revisions[device.device_id] = revision
            primary = device.primary_resource
            primary.revision = revision
        return revision

    def _safety_context(self, session: Session) -> dict[str, Any]:
        risk_class = max(
            (self.devices[d].safety.risk_class for d in session.device_ids if d in self.devices),
            key=lambda r: _RISK_ORDER.get(r, 0),
            default="R0",
        )
        engaged = any(self._latched.get(d) for d in session.device_ids)
        interlocks: list[dict[str, Any]] = []
        for device_id in session.device_ids:
            device = self.devices.get(device_id)
            if device is None:
                continue
            try:
                entries = _plain(device.bridge.interlocks() or []) if device.bridge else []
            except Exception:  # noqa: BLE001 - status must not fail a session
                continue
            for entry in entries:
                item = dict(entry)
                item.setdefault("device_id", device_id)
                interlocks.append(item)
        permits = [
            {
                "permit_id": permit.permit_id,
                "capability_id": permit.capability_id,
                "expires_at": canonical.rfc3339_from_ms(int(permit.expires_at * 1000)),
            }
            for permit in self._permits.values()
            if permit.session_id == session.session_id
            and not permit.used
            and permit.expires_at > time.time()
        ]
        return {
            "risk_class": risk_class,
            "certified": False,
            "estop": {
                "engaged": engaged,
                "latching": any(
                    bool(self.devices[d].safety.estop.get("latching", True))
                    for d in session.device_ids
                    if d in self.devices
                ),
                "kind": "software",
            },
            "estop_engaged": engaged,
            "interlocks": interlocks,
            "permits": permits,
            "requires_human_present": risk_class == "R3",
        }

    def _notify(self, stream: str, device_id: str, payload: Any) -> None:
        """Publish one event to every matching subscription, exactly once.

        ``stream="safety"`` (e-stop engaged, confirmed, released) is delivered
        on the ``control`` stream with ``type: "safety"``, the stream every
        subscription may request.  With a push transport attached (stdio,
        ``self._emit``) the events are queued in order under ``self._lock``
        and written by :meth:`_flush_outbox` after it is released; otherwise
        they are buffered per subscription for SSE / ``take_notifications``
        (bounded, with an explicit gap event on overflow).
        """
        event_type = None
        if stream == "safety":
            stream, event_type = "control", "safety"
        with self._lock:
            push = self._emit is not None
            for subscription_id, sub in list(self._subscriptions.items()):
                if device_id is not None and sub.get("device_id") not in (None, device_id):
                    continue
                requested = {
                    entry.get("stream") if isinstance(entry, Mapping) else entry
                    for entry in sub.get("streams") or []
                }
                if stream not in requested and "all" not in requested:
                    continue
                if push:
                    seq = int(sub.get("seq", 0)) + 1
                    sub["seq"] = seq
                    sub["delivered"] = int(sub.get("delivered", 0)) + 1
                    self._outbox.append(protocol.make_event(
                        subscription_id=subscription_id, seq=seq, stream=stream,
                        device_id=device_id, payload=payload, type=event_type,
                    ))
                    continue
                _buffer_event(sub, subscription_id, stream, device_id, payload, event_type)
        if push and not self._lock_held():
            # Non-blocking: a thread that is already writing drains the queue,
            # including these events, so an operation worker never waits on a
            # slow stdout here (the stdio flusher is the backstop).
            self._flush_outbox(blocking=False)

    def _lock_held(self) -> bool:
        """True when the calling thread holds ``self._lock`` (RLock)."""
        is_owned = getattr(self._lock, "_is_owned", None)
        return bool(is_owned()) if callable(is_owned) else False

    def _flush_outbox(self, *, blocking: bool = True) -> None:
        """Write queued push events in order, each exactly once (never under ``self._lock``)."""
        emit = self._emit
        if emit is None or not self._outbox:
            return
        if not self._emit_lock.acquire(blocking=blocking):
            return
        try:
            while True:
                try:
                    event = self._outbox.popleft()
                except IndexError:
                    return
                try:
                    emit(event)
                except Exception:  # noqa: BLE001 - a lost client never fails the operation
                    pass
        finally:
            self._emit_lock.release()


# ---------------------------------------------------------------------------
# Public session/subscription facades (thin, server-owned state)
# ---------------------------------------------------------------------------


class SessionManager:
    """Facade over one :class:`MHSServer`'s session table.

    Sessions are owned by the server (lifetime, grants, lease release).  This
    class exposes the small API hosts and tests use without duplicating state::

        manager = SessionManager(server)
        manager.open(principal={...}, capabilities=["cap.world.*"], mode="simulated")
        manager.require(session_id)
        manager.close(session_id)
    """

    def __init__(self, server: "MHSServer") -> None:
        self.server = server

    def open(self, **params: Any) -> dict[str, Any]:
        return self.server._m_session_open(dict(params))

    def get(self, session_id: str) -> Session | None:
        return self.server._sessions.get(str(session_id))

    def require(self, session_id: str) -> Session:
        return self.server._session(session_id)

    def heartbeat(self, session_id: str) -> dict[str, Any]:
        return self.server._m_session_heartbeat({"session_id": session_id})

    def close(self, session_id: str, reason: str | None = None) -> dict[str, Any]:
        return self.server._m_session_close({"session_id": session_id, "reason": reason})

    def __len__(self) -> int:
        return len(self.server._sessions)

    def __iter__(self):
        return iter(list(self.server._sessions.values()))


class SubscriptionHub:
    """Facade over one :class:`MHSServer`'s subscription table."""

    def __init__(self, server: "MHSServer") -> None:
        self.server = server

    def subscribe(self, session: Session | str, streams: Sequence[Any],
                  **params: Any) -> dict[str, Any]:
        session_id = session.session_id if isinstance(session, Session) else str(session)
        payload = {"session_id": session_id, "streams": list(streams)}
        payload.update(params)
        return self.server._m_subscribe(payload)

    def unsubscribe(self, session: Session | str, subscription_id: str) -> dict[str, Any]:
        session_id = session.session_id if isinstance(session, Session) else str(session)
        return self.server._m_unsubscribe(
            {"session_id": session_id, "subscription_id": subscription_id}
        )

    def publish(self, stream: str, device_id: str, payload: Any) -> None:
        self.server._notify(stream, device_id, payload)

    def drain(self) -> list[Any]:
        return self.server.take_notifications()

    def close(self) -> None:
        with self.server._lock:
            self.server._subscriptions.clear()
            self.server._outbox.clear()

    def __len__(self) -> int:
        return len(self.server._subscriptions)


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------

#: stdio methods that run on the FIFO lane of the device they target, so that
#: a device's commands and reads keep their arrival order.  Every other
#: request (hello, discovery, sessions, subscriptions, operations.get/list,
#: safety.status, evidence) uses the endpoint lane.
_DEVICE_LANE_METHODS = frozenset(
    {
        "mhs.command",
        "mhs.resource.read",
        "mhs.resource.write",
        "mhs.snapshot",
        "mhs.restore",
        "mhs.safety.reset",
        "mhs.safety.permit",
    }
)


class _StdioLane:
    """One FIFO of stdio jobs served by its own worker thread."""

    def __init__(self, name: str) -> None:
        self._jobs: deque[Callable[[], None]] = deque()
        self._cond = threading.Condition()
        self._closed = False
        self.thread = threading.Thread(target=self._run, name=f"mhs-stdio-lane-{name}", daemon=True)
        self.thread.start()

    def put(self, job: Callable[[], None]) -> None:
        with self._cond:
            self._jobs.append(job)
            self._cond.notify()

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def _run(self) -> None:
        while True:
            with self._cond:
                while not self._jobs and not self._closed:
                    self._cond.wait()
                if not self._jobs:
                    return
                job = self._jobs.popleft()
            try:
                job()
            except Exception:  # noqa: BLE001 - a lane never dies with one job
                _log.exception("stdio request failed")


class _StdioDispatcher:
    """Routes decoded stdio messages for :meth:`MHSServer.run_stdio`.

    * e-stops (``mhs.safety.estop``, ``mhs.command`` on ``cap.motion.estop.v1``)
      run in the reader thread itself: latched before the next line is read;
    * ``mhs.operations.cancel`` runs at once on its own thread (it waits for
      the operation's receipt and must not hold up the reader);
    * the rest goes to the FIFO lane of its device (:data:`_DEVICE_LANE_METHODS`
      with a resolvable device) or of the endpoint.
    """

    def __init__(self, server: MHSServer, emit: Callable[[Any], None], *,
                 auth: Mapping[str, Any] | None = None) -> None:
        self.server = server
        self.emit = emit
        #: The principal the pipe was authenticated as (``run_stdio(auth_token=...)``).
        self.auth = dict(auth) if auth else None
        self._lock = threading.Lock()
        self._lanes: dict[str, _StdioLane] = {}
        self._priority: list[threading.Thread] = []

    # -- routing ---------------------------------------------------------
    def submit(self, message: Any) -> None:
        if isinstance(message, list):
            self._submit_batch(message)
            return
        kind = _stdio_priority(message)
        if kind == "estop":
            self._respond(self._handle(message))
        elif kind == "cancel":
            self._spawn(lambda: self._respond(self._handle(message)))
        else:
            self._lane(self._lane_key(message)).put(lambda: self._respond(self._handle(message)))

    def _submit_batch(self, batch: list[Any]) -> None:
        if not batch or len(batch) > 64:
            self._respond(self._handle(batch))
            return
        # E-stops inside a batch latch now; the rest runs on the endpoint lane
        # and one response array carries every answer (PROTO: any order).
        first: list[Any] = []
        rest: list[Any] = []
        for item in batch:
            if _stdio_priority(item) == "estop":
                response = self._handle(item)
                if response is not None:
                    first.append(response.to_dict() if hasattr(response, "to_dict") else response)
            else:
                rest.append(item)
        if not rest:
            if first:
                self._respond(first)
            return

        def run_rest() -> None:
            responses = self._handle(rest)
            combined = list(first) + (list(responses) if isinstance(responses, list) else [])
            if combined:
                self._respond(combined)

        self._lane("").put(run_rest)

    def _lane_key(self, message: Any) -> str:
        if not isinstance(message, Mapping) or message.get("method") not in _DEVICE_LANE_METHODS:
            return ""
        params = message.get("params")
        if not isinstance(params, Mapping):
            return ""
        device_id = params.get("device_id")
        if isinstance(device_id, str) and device_id:
            try:
                return self.server._device(device_id, adopt=False).device_id  # noqa: SLF001
            except MHSError:
                return ""
        session_id = params.get("session_id")
        session = self.server._sessions.get(session_id) if isinstance(session_id, str) else None  # noqa: SLF001
        if session is not None and len(session.device_ids) == 1:
            return session.device_ids[0]
        if len(self.server.devices) == 1:
            return next(iter(self.server.devices))
        return ""

    def _lane(self, key: str) -> _StdioLane:
        with self._lock:
            lane = self._lanes.get(key)
            if lane is None:
                lane = _StdioLane(key.rsplit("/", 1)[-1] or "endpoint")
                self._lanes[key] = lane
            return lane

    def _spawn(self, job: Callable[[], None]) -> None:
        thread = threading.Thread(target=job, name="mhs-stdio-priority", daemon=True)
        with self._lock:
            self._priority = [item for item in self._priority if item.is_alive()]
            self._priority.append(thread)
        thread.start()

    # -- execution ---------------------------------------------------------
    def _handle(self, message: Any) -> Any:
        try:
            return self.server._handle_message(message, auth=self.auth)  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the wire
            request_id = message.get("id") if isinstance(message, Mapping) else None
            return protocol.make_error(request_id, MHSError(
                "MHS.INTERNAL.ERROR", f"internal error: {type(exc).__name__}"))

    def _respond(self, response: Any) -> None:
        if response is None:
            return
        try:
            self.emit(response)
        except (BrokenPipeError, OSError):
            pass

    def close(self, timeout: float) -> None:
        """Serve what was already read, then stop the lane workers."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._lock:
            lanes = list(self._lanes.values())
            priority = list(self._priority)
        for lane in lanes:
            lane.close()
        for thread in [lane.thread for lane in lanes] + priority:
            thread.join(max(0.0, deadline - time.monotonic()))


def _stdio_priority(message: Any) -> str | None:
    """'estop', 'cancel' or None for one decoded stdio message."""
    if not isinstance(message, Mapping):
        return None
    method = message.get("method")
    params = message.get("params")
    params = params if isinstance(params, Mapping) else {}
    if _is_estop_request(method, params):
        return "estop"
    if method == "mhs.operations.cancel":
        return "cancel"
    return None


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------


class _HTTPHandle:
    def __init__(self, server: ThreadingHTTPServer, thread: threading.Thread, host: str, port: int,
                 closing: threading.Event | None = None):
        self.server = server
        self.thread = thread
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        #: set on shutdown so open SSE streams end
        self.closing = closing or threading.Event()

    def shutdown(self) -> None:
        self.closing.set()
        try:
            self.server.shutdown()
        finally:
            self.server.server_close()

    def close(self) -> None:
        self.shutdown()


def _host_name(value: Any) -> str:
    """The lower-cased host of a ``Host`` header or host entry, without port/brackets."""
    text = str(value or "").strip().lower()
    if text.startswith("["):
        end = text.find("]")
        return text[1:end] if end > 0 else text
    if text.count(":") == 1:
        return text.split(":", 1)[0]
    return text


def _make_handler(mhs_server: MHSServer, *, bind_host: str | None = None,
                  closing: threading.Event | None = None) -> type[BaseHTTPRequestHandler]:
    """Build the request handler class for one HTTP endpoint (T2, TPT-010..017).

    Every request must name an allowed ``Host`` (``localhost``, ``127.0.0.1``,
    ``[::1]``, the bound address, ``MHSServer(allowed_hosts=...)``) -- this is
    what defeats DNS rebinding -- and, when it carries an ``Origin``, an
    allowed one (the endpoint's own loopback origin or
    ``MHSServer(allowed_origins=...)``).  With ``auth_tokens`` every route but
    the well-known descriptor needs ``Authorization: Bearer <token>``.
    """
    allowed_hosts = set(_LOOPBACK_HOST_NAMES)
    allowed_hosts.update(_host_name(host) for host in mhs_server.allowed_hosts)
    bound = _host_name(bind_host) if bind_host else ""
    if bound and bound not in ("0.0.0.0", "::"):
        allowed_hosts.add(bound)
    allowed_origins = set(mhs_server.allowed_origins)
    stop = closing or threading.Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "mhs-http/1.0"
        # Socket timeout for every read and write of the connection: a stalled
        # client is disconnected instead of holding this thread.
        timeout = mhs_server.http_timeout_s

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
            if os.environ.get("MHS_HTTP_LOG"):
                super().log_message(fmt, *args)

        def _send_json(self, status: int, payload: Any, headers: Mapping[str, str] | None = None) -> None:
            if hasattr(payload, "to_dict"):
                payload = payload.to_dict()
            try:
                body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False,
                                  allow_nan=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                request_id = payload.get("id") if isinstance(payload, Mapping) else None
                body = json.dumps(protocol.make_error(request_id, MHSError(
                    "MHS.INTERNAL.ERROR", "response is not JSON-encodable",
                    {"detail": type(exc).__name__})).to_dict(), separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: int, code: str, message: str,
                        headers: Mapping[str, str] | None = None) -> None:
            self._refuse(status, protocol.make_error(None, MHSError(code, message)), headers)

        def _refuse(self, status: int, payload: Any, headers: Mapping[str, str] | None = None) -> None:
            """Answer a refusal and close: an unread request body must never be
            parsed as the next request on a kept-alive connection."""
            self.close_connection = True
            merged = {"Connection": "close"}
            merged.update(headers or {})
            self._send_json(status, payload, merged)

        # -- request guards ----------------------------------------------
        def _host_allowed(self) -> bool:
            host = self.headers.get("Host")
            return bool(host) and _host_name(host) in allowed_hosts

        def _origin_allowed(self) -> bool:
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            origin = origin.strip().rstrip("/").lower()
            if origin in allowed_origins:
                return True
            parsed = urlparse(origin)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return False
            try:
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
            except ValueError:
                return False
            return parsed.hostname in allowed_hosts and port == self.server.server_address[1]

        #: The bearer token's principal of the current request (None without auth_tokens).
        principal: dict[str, Any] | None = None

        def _authorized(self) -> bool:
            """Check the bearer token (constant time) and remember its principal."""
            self.principal = None
            if not mhs_server._auth_tokens:  # noqa: SLF001
                return True
            scheme, _, presented = (self.headers.get("Authorization") or "").strip().partition(" ")
            if scheme.lower() != "bearer" or not presented.strip():
                return False
            self.principal = mhs_server._principal_for_token(presented.strip())  # noqa: SLF001
            return self.principal is not None

        def _guard(self, *, auth: bool = True) -> bool:
            """Host, then Origin, then bearer token; answers the refusal itself."""
            if not self._host_allowed():
                self._send_error(403, "MHS.AUTH.FORBIDDEN", "Host header is not allowed for this endpoint")
                return False
            if not self._origin_allowed():
                self._send_error(403, "MHS.AUTH.FORBIDDEN", "Origin is not allowed for this endpoint")
                return False
            if auth and not self._authorized():
                self._send_error(401, "MHS.AUTH.UNAUTHENTICATED", "a valid bearer token is required",
                                 {"WWW-Authenticate": "Bearer"})
                return False
            return True

        # -- GET ---------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802 - stdlib signature
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query or "", keep_blank_values=True)
            if path == "/.well-known/mhs.json":
                if not self._guard(auth=False):
                    return
                served = mhs_server._served_devices()  # noqa: SLF001
                self._send_json(200, {
                    "mhs_version": MHS_VERSION,
                    "endpoint_id": mhs_server.endpoint_id,
                    "display_name": "MHS endpoint",
                    "transports": {"http": "/mhs/v1/rpc", "sse": "/mhs/v1/events"},
                    "auth": ["bearer"] if mhs_server._auth_tokens else ["none"],  # noqa: SLF001
                    "devices": [d.device_id for d in served],
                    "features": mhs_server.features,
                    "conformance": mhs_server._conformance_claims(served),  # noqa: SLF001
                })
                return
            if not self._guard():
                return
            if path == "/mhs/v1/rpc":
                self._send_error(405, "MHS.PROTOCOL.INVALID_REQUEST", "use POST for JSON-RPC",
                                 {"Allow": "POST"})
                return
            if path == "/mhs/v1/events":
                self._serve_events(query)
                return
            if path == "/mhs/v1/schema" or path.startswith("/mhs/v1/schema/"):
                ref = unquote(path[len("/mhs/v1/schema"):].lstrip("/"))
                if not ref:
                    ref = (query.get("ref") or [""])[0]
                try:
                    result = mhs_server._m_schema_get({"ref": ref})  # noqa: SLF001
                except MHSError:
                    self._send_json(404, {"error": "schema not found"})
                    return
                schema = result.get("schema") if isinstance(result, Mapping) else None
                if schema is None:
                    self._send_json(404, {"error": "schema not found"})
                else:
                    self._send_json(200, schema)
                return
            self._send_json(404, {"error": "not found"})

        def _serve_events(self, query: Mapping[str, list[str]]) -> None:
            """SSE for one session's subscriptions (TPT-016/017)."""
            session_id = (query.get("session_id") or [""])[0]
            subscription_id = (query.get("subscription_id") or [None])[0] or None
            if not session_id:
                self._send_error(400, "MHS.PROTOCOL.INVALID_PARAMS",
                                 "session_id is required: an SSE stream delivers one session's events")
                return
            session = mhs_server._sessions.get(session_id)  # noqa: SLF001
            owner = self.principal
            # A token-bound session streams only to a request with its principal.
            owned = session is not None and (not session.authenticated or (
                owner is not None and owner.get("id") == (session.principal or {}).get("id")
                and owner.get("kind") == session.kind))
            if session is None or not owned or session.released or session.expired():
                self._send_error(403, "MHS.SESSION.UNKNOWN", "unknown or expired session")
                return
            if subscription_id is not None:
                owned = (mhs_server._subscriptions.get(subscription_id) or {}).get("session_id")  # noqa: SLF001
                if owned != session_id:
                    self._send_error(404, "MHS.SESSION.UNKNOWN", "unknown subscription for this session")
                    return
            principal = str((session.principal or {}).get("id") or "anonymous")
            with mhs_server._lock:  # noqa: SLF001
                active = mhs_server._sse_streams.get(principal, 0)  # noqa: SLF001
                if active >= _MAX_SSE_STREAMS_PER_PRINCIPAL:
                    refused = True
                else:
                    refused = False
                    mhs_server._sse_streams[principal] = active + 1  # noqa: SLF001
            if refused:
                self._send_error(429, "MHS.LIMIT.CONNECTION_LIMIT",
                                 f"at most {_MAX_SSE_STREAMS_PER_PRINCIPAL} SSE streams per principal",
                                 {"Retry-After": "1"})
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                self.wfile.write(b"retry: 3000\n\n")
                self.wfile.flush()
                last_write = time.monotonic()
                while not stop.is_set() and self._session_live(session_id) and not self._client_gone():
                    pending = mhs_server.take_notifications_for_session(session_id, subscription_id)
                    for message in pending:
                        plain = message.to_dict() if hasattr(message, "to_dict") else message
                        params = plain.get("params") or {}
                        data = json.dumps(plain, separators=(",", ":"), ensure_ascii=False)
                        frame = (f"id: {params.get('subscription_id')}:{params.get('seq')}\n"
                                 f"event: mhs.event\ndata: {data}\n\n")
                        self.wfile.write(frame.encode("utf-8"))
                    if pending:
                        self.wfile.flush()
                        last_write = time.monotonic()
                    elif time.monotonic() - last_write > _SSE_KEEPALIVE_S:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_write = time.monotonic()
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
                pass
            finally:
                with mhs_server._lock:  # noqa: SLF001
                    remaining = mhs_server._sse_streams.get(principal, 1) - 1  # noqa: SLF001
                    if remaining > 0:
                        mhs_server._sse_streams[principal] = remaining  # noqa: SLF001
                    else:
                        mhs_server._sse_streams.pop(principal, None)  # noqa: SLF001

        def _session_live(self, session_id: str) -> bool:
            session = mhs_server._sessions.get(session_id)  # noqa: SLF001
            return session is not None and not session.released and not session.expired()

        def _client_gone(self) -> bool:
            try:
                readable, _, _ = select.select([self.connection], [], [], 0)
                if not readable:
                    return False
                return self.connection.recv(1, socket.MSG_PEEK) == b""
            except (OSError, ValueError):
                return True

        # -- POST --------------------------------------------------------
        def do_POST(self) -> None:  # noqa: N802 - stdlib signature
            if not self._guard():
                return
            path = urlparse(self.path).path
            if path != "/mhs/v1/rpc":
                self._refuse(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0:
                self._refuse(411, protocol.make_error(None, MHSError("MHS.PROTOCOL.INVALID_REQUEST")))
                return
            if length > 1024 * 1024:
                self._refuse(413, protocol.make_error(None, MHSError("MHS.LIMIT.PAYLOAD_TOO_LARGE")))
                return
            # TPT-011: exactly application/json (parameters such as charset are
            # allowed); a missing type is refused, so a browser "simple"
            # request (text/plain, form) can never reach a method.
            content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._refuse(415, protocol.make_error(None, MHSError(
                    "MHS.PROTOCOL.INVALID_REQUEST", "Content-Type must be application/json")))
                return
            raw = self.rfile.read(length)
            try:
                message = _decode_wire(raw)
            except MHSError:
                self._send_json(400, protocol.make_error(None, MHSError("MHS.PROTOCOL.PARSE_ERROR")))
                return
            response = mhs_server._handle_message(message, auth=self.principal)  # noqa: SLF001 - internal route
            if response is None:
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._send_json(200, response)

    return Handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """Deep-copy a value into JSON-plain Python (no tuples, no dataclasses)."""
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return value


def _input_invalid(errors: Sequence[str], revision: int) -> MHSError:
    """Plan 3.6 steps 7 and 9: the input does not match its (served) schema."""
    return MHSError("MHS.CAPABILITY.INPUT_INVALID", "capability input does not match its schema",
                    {"details": {"errors": list(errors)[:8]}, "retryable": False})


def _limits_unset_error(capability: "Capability", paths: Sequence[str], reason: str, revision: int) -> MHSError:
    """``MHS.SAFETY.LIMITS_UNSET`` (plan 3.5): a value set where no bound can be enforced."""
    if reason == "operator_required":
        message = (f"{capability.capability_id}: {', '.join(paths)} declared operator_required and no "
                   "site_limits overlay fills it")
        remediation = "An operator supplies the bound in site-limits.json (MHSServer(site_limits=...))."
    else:
        message = (f"{capability.capability_id}: no limit covers the numeric input {', '.join(paths)} "
                   "on this hardware device")
        remediation = ("Declare a sourced limit for the field (binding limits or safety.envelope), or "
                       "operator_required so the operator overlay supplies it; never invent a bound.")
    return MHSError("MHS.SAFETY.LIMITS_UNSET", message,
                    {"retryable": False, "current_revision": revision, "remediation": remediation,
                     "details": {"paths": list(paths), "reason": reason,
                                 "capability_id": capability.capability_id}})


def _estop_engaged_error(revision: int) -> MHSError:
    return MHSError(
        "MHS.SAFETY.ESTOP_ENGAGED",
        "device is latched by an emergency stop; reset after clearing interlocks",
        {"retryable": False, "current_revision": revision},
    )


def _revision_conflict_error(expected: int, current: int) -> MHSError:
    return MHSError(
        "MHS.CONFLICT.REVISION",
        f"expected revision {expected} but current revision is {current}",
        {"current_revision": current, "retryable": False},
    )


def _journal_failed_error(command_id: str) -> MHSError:
    """The write-ahead ``begin`` of an effectful command could not be written (state_dir)."""
    return MHSError(
        "MHS.INTERNAL.ERROR",
        "the endpoint could not write the command's write-ahead record to its state directory; "
        "nothing was executed",
        {"retryable": False, "command_id": command_id,
         "details": {"reason": "journal_write_failed", "executed": False},
         "remediation": "Free space or fix the state directory, then retry the same command_id: "
                        "nothing ran, and a refusal is not the command's outcome."},
    )


class _RevisionConflict:
    """:meth:`MHSServer._start_operation` refused to start: the revision moved (plan 3.6 step 12)."""

    __slots__ = ("current",)

    def __init__(self, current: int) -> None:
        self.current = current


def _call_native(bridge: Any, capability: "Capability", payload: Mapping[str, Any], ctx: Any) -> Any:
    """The native call of one binding: ``bridge.call(capability_id, input, ctx)``.

    A ``cap.device.configure.v1`` binding whose bridge does not serve the class
    through ``call()`` (``MHS.CAPABILITY.NOT_BOUND``, the base ``unsupported``)
    but implements the parameter-patch method ``write(resource_id, patch,
    ctx)`` (documented return ``{"applied": {...}}``) is written through it.
    """
    try:
        return bridge.call(capability.capability_id, payload, ctx)
    except Exception as exc:  # noqa: BLE001 - re-raised unless it is the "unsupported" refusal
        if (capability.capability_id != _CONFIGURE or getattr(exc, "code", None) != "MHS.CAPABILITY.NOT_BOUND"
                or not _bridge_overrides(bridge, "write")):
            raise
    return bridge.write(capability.resource, payload, ctx)


def _estop_terminal(device: Any) -> str | None:
    """The declared terminal e-stop statement (``safety.estop.terminal``, CORE-087), or None."""
    estop = getattr(getattr(device, "safety", None), "estop", None)
    if not isinstance(estop, Mapping) or "terminal" not in estop:
        return None
    statement = estop.get("terminal")
    # A declaration that is present but malformed still fails closed (it is refused at start-up).
    return statement if isinstance(statement, str) and statement.strip() else "terminal e-stop declared"


def _estop_reenable(device: Any) -> str | None:
    """The declared re-enable capability (``safety.estop.reenable``, CORE-086), or None.

    Only a declaration that names a capability bound exactly once and exempt
    from nothing (not a stop class or a ``safe_state.achieved_by`` action)
    counts; anything else is refused at start-up or on first use of a late
    device, and is never reported as the re-enable meanwhile.
    """
    estop = getattr(getattr(device, "safety", None), "estop", None)
    value = estop.get("reenable") if isinstance(estop, Mapping) else None
    if not isinstance(value, str) or not value or value in _STOP_CLASSES:
        return None
    try:
        if len(device.bindings_of(value)) != 1:
            return None
        achieved_by = (device.safety.safe_state or {}).get("achieved_by") or []
    except Exception:  # noqa: BLE001 - a device that cannot answer has no usable declaration
        return None
    return None if value in {str(item) for item in achieved_by} else value


def _empty_input_problem(schema: Any) -> str | None:
    """Why ``{}`` is not a valid input of ``schema`` (the command-input validator decides), or None."""
    if schema is None or (isinstance(schema, Mapping) and not schema):
        return None
    if not isinstance(schema, Mapping):
        return "its input schema is not a JSON object schema"
    try:
        errors = schema_validate({}, dict(schema))
    except Exception as exc:  # noqa: BLE001 - an unevaluable schema cannot promise an empty input
        return f"its input schema cannot be evaluated ({type(exc).__name__})"
    return "; ".join(str(item) for item in errors[:3]) if errors else None


def _bridge_reset_hook(bridge: Any) -> str | None:
    """The decorated ``@reset`` method a driver bridge runs on a reset (``Driver.reset_hook``), or None."""
    try:
        hook = getattr(bridge, "reset_hook", None)
    except Exception:  # noqa: BLE001 - an unanswerable bridge declares nothing here
        return None
    return hook if isinstance(hook, str) and hook else None


def _estop_recovery_problems(device: Any) -> list[str]:
    """Problems of a device's declared recovery after an e-stop (CORE-086, CORE-087); empty when well formed.

    ``safety.estop.reenable`` names the one capability that re-arms the device
    after a completed reset.  It must be bound to exactly one resource, accept
    an empty input (``{}`` validates against its input schema), and be an
    ordinary effectful command: never a read, a stop class or a
    ``safe_state.achieved_by`` action (those are exempt from the latch, and
    the re-enable must be refused while latched).  A driver bridge that runs
    a decorated ``@reset`` hook (``Driver.reset_hook``) cannot serve such a
    device: its reset only releases the latch (SAFE-042).
    ``safety.estop.terminal`` states why the native stop cannot be undone
    without a new endpoint; it needs a stop path and excludes a re-enable.
    A manifest that declares neither has no problem here.
    """
    estop = getattr(device.safety, "estop", None)
    if not isinstance(estop, Mapping) or not ("reenable" in estop or "terminal" in estop):
        return []
    did = device.device_id
    problems: list[str] = []
    achieved_by = {str(item) for item in (device.safety.safe_state or {}).get("achieved_by") or []}
    if "terminal" in estop:
        statement = estop.get("terminal")
        if not isinstance(statement, str) or not statement.strip() or len(statement) > 500:
            problems.append(f"device {did}: safety.estop.terminal must state in one sentence (at most 500 "
                            "characters) why the native stop cannot be undone without a new endpoint")
        if "reenable" in estop:
            problems.append(f"device {did}: safety.estop.terminal and safety.estop.reenable exclude each other: no "
                            "reset undoes a terminal e-stop, so nothing can re-enable the device (CORE-087)")
        # A stop path is the declared native stop (a served view may have no bridge yet), a bridge that
        # implements estop, a bound cap.motion.estop.v1, or a safe-state action.
        bridge = getattr(device, "bridge", None)
        declared_native = isinstance(estop.get("native"), str) and bool(estop["native"].strip())
        has_native = (declared_native or bool(device.bindings_of(_MOTION_ESTOP))
                      or (bridge is not None and _bridge_overrides_estop(bridge)))
        if not has_native and not achieved_by:
            problems.append(f"device {did}: safety.estop.terminal describes a native stop, but the device has no "
                            "native e-stop and no safe_state.achieved_by action (CORE-087)")
    if "reenable" in estop:
        capability_id = estop.get("reenable")
        if not isinstance(capability_id, str) or not capability_id:
            problems.append(f"device {did}: safety.estop.reenable must name a bound capability id")
            return problems
        bindings = device.bindings_of(capability_id)
        if len(bindings) != 1:
            problems.append(f"device {did}: safety.estop.reenable names {capability_id!r}, which must be bound to "
                            f"exactly one resource of the device (bound {len(bindings)} time(s)) (CORE-086)")
        hook = _bridge_reset_hook(getattr(device, "bridge", None))
        if hook is not None:
            problems.append(f"device {did}: safety.estop.reenable names {capability_id!r}, but the driver runs the "
                            f"@reset hook {hook}() on a reset; a device that declares a re-enable is reset by "
                            "releasing the latch only, and its native recovery belongs in the re-enable "
                            "(SAFE-042, CORE-086)")
        if capability_id in achieved_by:
            problems.append(f"device {did}: safety.estop.reenable names {capability_id!r}, a "
                            "safe_state.achieved_by action that the e-stop latch exempts; the re-enable must be "
                            "refused while the device is latched (CORE-086)")
        if capability_id in _STOP_CLASSES:
            problems.append(f"device {did}: safety.estop.reenable cannot name the stop class {capability_id} "
                            "(CORE-086)")
        entry: Any = None
        if not _catalog.is_extension(capability_id):
            try:
                entry = _catalog.get(capability_id)
            except Exception:  # noqa: BLE001 - an unreadable catalogue leaves only the binding's own facts
                entry = None
        for capability in bindings:
            if capability.declared_verb == "read" or (isinstance(entry, Mapping) and entry.get("verb") == "read"):
                problems.append(f"device {did}: safety.estop.reenable names {capability_id!r}, a read; the "
                                "re-enable is an effectful command (CORE-086)")
            schema = capability.input_schema if isinstance(capability.input_schema, Mapping) else (
                (entry or {}).get("input_schema") if isinstance(entry, Mapping) else None) or {}
            refused = _empty_input_problem(schema)
            if refused is not None:
                problems.append(f"device {did}: safety.estop.reenable names {capability_id!r}, which does not accept "
                                f"an empty input ({refused}); the re-enable is called with an empty input "
                                "(CORE-086)")
    return problems


def _fresh_estop_state() -> dict[str, Any]:
    """Initial per-device e-stop bookkeeping (see ``MHSServer._estop_state``)."""
    return {"generation": 0, "seq": 0, "reason": None, "attempt": None, "confirmed": None,
            "attempts": 0, "unconfirmed": [], "supervisor": None, "supervisor_generation": None,
            "resetting": 0, "reset_hold_until": 0.0, "reset_seq": -1, "pending_attempts": []}


def _stop_path_pending(state: Mapping[str, Any]) -> bool:
    """True while any e-stop attempt of the device has not finished.

    That is the current attempt and every older one still in flight
    (``pending_attempts``: a re-assert after ``estop_during_reset`` or ``mhs.restore``
    may start a new attempt while an older native e-stop has not answered).
    """
    attempts = [state.get("attempt"), *(state.get("pending_attempts") or [])]
    return any(isinstance(attempt, _EstopAttempt) and not attempt.done.is_set() for attempt in attempts)


def _is_estop_request(method: Any, params: Mapping[str, Any]) -> bool:
    """``mhs.safety.estop``, or ``mhs.command`` naming ``cap.motion.estop.v1``.

    Such a request is never refused by a generic protocol gate (``mhs.hello``
    not yet sent, missing or invalid ``deadline_ms``) before it latched
    (plan 3.6: the e-stop is unconditional).
    """
    return method == "mhs.safety.estop" or (
        method == "mhs.command" and params.get("capability_id") == _MOTION_ESTOP
    )


def _envelope_defect(message: Mapping[str, Any]) -> tuple[str, str] | None:
    """Why a JSON-RPC envelope is unacceptable, as ``(error code, text)``; None for a well-formed one.

    The three defects the dispatcher refuses an ordinary request for: ``jsonrpc`` other than ``"2.0"``, an ``id`` that is not a
    string or an integer, and ``params`` (when given and not empty) that are not an object.
    """
    if message.get("jsonrpc") != "2.0":
        return "MHS.PROTOCOL.INVALID_REQUEST", "jsonrpc must be exactly '2.0'"
    if "id" in message and (not isinstance(message["id"], (str, int)) or isinstance(message["id"], bool)):
        return "MHS.PROTOCOL.INVALID_REQUEST", "id must be a string or integer"
    if not isinstance(message.get("params") or {}, Mapping):
        return "MHS.PROTOCOL.INVALID_PARAMS", "params must be an object"
    return None


def _recognisably_estop(method: Any, params: Any) -> bool:
    """``mhs.safety.estop`` whatever its params, or ``mhs.command`` naming ``cap.motion.estop.v1`` in object params."""
    return method == "mhs.safety.estop" or (isinstance(params, Mapping) and _is_estop_request(method, params))


def _estop_command_id(value: Any) -> str:
    """The supplied ``command_id`` when it is a ULID, otherwise a fresh one
    (a malformed id never refuses an e-stop)."""
    if value is not None and canonical.is_ulid(str(value)):
        return str(value)
    return canonical.ulid()


def _native_outcome(exc: BaseException) -> tuple[str, MHSError]:
    """``(receipt status, error)`` for an exception a bridge raised (plan 3.7).

    :func:`mhs.signals.outcome` classifies it: ``DriverFailed`` is ``failed``
    with its code, ``Busy`` is ``rejected`` ``MHS.DEVICE.BUSY``,
    ``OutcomeUnknown`` is ``unknown`` and anything else is ``failed``
    ``MHS.ADAPTER.SHIM_FAILED`` naming only the exception type (its message
    may carry paths, hosts or credentials).  An ``MHSError`` that is not a
    signal -- a bridge's own refusal such as ``MHS.SAFETY.ESTOP_ENGAGED`` --
    keeps its code (``unknown`` for ``MHS.OUTCOME.UNKNOWN``).  Cancellation is
    handled by the caller (a ``cancelled`` receipt, no error).
    """
    if isinstance(exc, MHSError) and not isinstance(exc, _signals.DriverSignal):
        return ("unknown" if exc.code == "MHS.OUTCOME.UNKNOWN" else "failed"), exc
    result = _signals.outcome(exc)
    if isinstance(exc, MHSError):
        # A signal that is also an MHSError (mhs.bridge.base.driver_failed ...).
        data = dict(exc.data or {})
        details = dict(data.get("details") or {}) if isinstance(data.get("details"), Mapping) else {}
        details.update(result.details)
        if details:
            data["details"] = details
        data.setdefault("retryable", result.retryable)
        error = MHSError(exc.code, exc.message, data)
    else:
        data = {"retryable": result.retryable}
        if result.details:
            data["details"] = dict(result.details)
        error = MHSError(result.code or "MHS.ADAPTER.SHIM_FAILED", result.message, data)
    status = result.status if result.status in ("failed", "rejected", "unknown") else "failed"
    return status, error


def _non_canonical_input(payload: Any, what: str = "input") -> MHSError | None:
    """``MHS.CAPABILITY.INPUT_INVALID`` when ``payload`` has no canonical JSON form.

    Its action digest (receipts, permits, idempotency) could not be computed:
    for example an integer beyond 2**53 - 1 (canonical.INTEGER_MAX).  Nothing
    is dispatched and no receipt can name the input.
    """
    try:
        canonical.digest({"input": payload})
    except canonical.CanonicalJSONError as exc:
        return MHSError(
            "MHS.CAPABILITY.INPUT_INVALID",
            f"{what} has no canonical JSON form: {exc}",
            {"retryable": False, "details": {"reason": "not_canonical_json"},
             "remediation": "Send integers beyond 2**53-1 as decimal strings."},
        )
    return None


def _estop_action_digest(resource: str | None, payload: Mapping[str, Any]) -> str:
    """The action digest of an e-stop command; never raises (an e-stop always latches)."""
    try:
        return action_digest(_MOTION_ESTOP, resource, dict(payload))
    except canonical.CanonicalJSONError:
        return action_digest(_MOTION_ESTOP, resource, {"x-mhs-unrepresentable-input": True})


def _estop_deadline_ms(value: Any, default_ms: int) -> int:
    """An e-stop's wait budget: a valid ``deadline_ms`` clamped to the endpoint
    maximum, otherwise the device's e-stop budget (never a refusal)."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return min(value, _MAX_DEADLINE_MS)
    return default_ms


def _bridge_overrides_estop(bridge: Any) -> bool:
    """True when ``bridge.estop`` is more than the base class's no-op default."""
    return _bridge_overrides(bridge, "estop")


def _bridge_overrides(bridge: Any, name: str) -> bool:
    """True when ``bridge.<name>`` is more than the :class:`mhs.bridge.base.Bridge` default."""
    method = getattr(bridge, name, None)
    if not callable(method):
        return False
    try:
        from .bridge.base import Bridge as _BaseBridge
    except ImportError:  # pragma: no cover - the bridge package ships with the SDK
        return True
    base = getattr(_BaseBridge, name, None)
    if base is None:
        return True
    return getattr(method, "__func__", None) is not base


def _describe_exception(exc: BaseException) -> dict[str, Any]:
    """Redacted description of a bridge failure (type and registered code only)."""
    out: dict[str, Any] = {"type": type(exc).__name__}
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.startswith("MHS."):
        out["mhs_code"] = code
    return out


def _sdk_settle_hook(bridge: Any) -> Any:
    """The bridge's ``settle_native_work`` only when it is the SDK's own simulator method, else None.

    The function object is compared with the SDK class attributes (the Gym and
    MuJoCo bridges and the simulator family driver), and an instance attribute
    must be that same method bound to the bridge: package code can neither
    supply nor override the hook the e-stop waits on.
    """
    if bridge is None:
        return None
    method = getattr(type(bridge), "settle_native_work", None)
    if method is None:
        return None
    # Never import on the e-stop path (review S10-4; an import can take longer than the stop's budget): a simulator
    # bridge or driver of the SDK exists only when its module was imported already, as for _sdk_ros_route.
    owners = ((f"{__package__}.bridge.gymnasium", "GymnasiumBridge"), (f"{__package__}.bridge.mujoco", "MujocoBridge"),
              (f"{__package__}.driver.families", "_SimDriver"))
    sdk_methods = [getattr(getattr(sys.modules.get(module), name, None), "settle_native_work", None)
                   for module, name in owners]
    if not any(sdk is not None and method is sdk for sdk in sdk_methods):
        return None
    bound = getattr(bridge, "settle_native_work", None)
    if getattr(bound, "__func__", None) is not method or getattr(bound, "__self__", None) is not bridge:
        return None
    return bound


def _settle_native_work(bridge: Any, timeout_s: float) -> None:
    """Bounded wait for a simulator bridge's in-flight native call to end (advisory).

    Runs in the e-stop attempt's worker, never under the server lock. Only the
    SDK's own Gym and MuJoCo hooks are consulted (:func:`_sdk_settle_hook`),
    and the call itself runs in a daemon thread joined for at most
    ``timeout_s``: a hook that raises or has not returned counts as not
    settled. Its result is ignored; ``safety_status`` decides, so a native call
    that never ends gives ``SAFE_STATE_UNREACHED`` and the background retry
    (SAFE-040), never a hung attempt.
    """
    settle = _sdk_settle_hook(bridge)
    if settle is None:
        return
    budget = max(0.0, float(timeout_s))

    def run() -> None:
        try:
            settle(budget)
        except Exception:  # noqa: BLE001 - advisory: safety_status decides the outcome
            pass

    worker = threading.Thread(target=run, name="mhs-estop-settle", daemon=True)
    worker.start()
    worker.join(budget)


def _sdk_ros_route(bridge: Any) -> bool:
    """True when the e-stop's safe-state calls reach the SDK's ROS bridge through SDK code only.

    Only that bridge answers a call from a stop request this e-stop already sent and reports it (CORE-074). The
    check reads the class attributes statically (no package code runs): the SDK's :class:`mhs.bridge.ros.RosBridge`
    itself (not a subclass), or a :class:`mhs.driver.RosDriver` whose ``call`` and ``make_bridge`` are the SDK's, so
    the inner bridge is the SDK's RosBridge. A package that overrides them gets no report list, and neither does an
    instance that carries its own ``call``, ``make_bridge``, ``estop`` or ``safety_status`` (on the driver or on its
    inner bridge): an instance attribute shadows the class's method (review S9-11). A driver class that overrides
    ``inner``, ``estop``, ``safety_status`` or ``_run_safe_state`` is not the SDK's route either, and an inner
    bridge must be exactly :class:`mhs.bridge.ros.RosBridge` (review S10-1).
    """
    # Never import on the e-stop path (an import can take longer than the stop's budget): a ROS bridge or driver
    # exists only when its module was imported already.
    ros = sys.modules.get(f"{__package__}.bridge.ros")
    families = sys.modules.get(f"{__package__}.driver.families")
    ros_bridge = getattr(ros, "RosBridge", None)
    ros_driver = getattr(families, "RosDriver", None)
    family_driver = getattr(families, "_FamilyDriver", None)
    cls = type(bridge)
    try:
        if isinstance(ros_bridge, type) and isinstance(bridge, ros_bridge):
            return cls is ros_bridge and not _instance_shadows_route(bridge)
        if isinstance(ros_driver, type) and isinstance(family_driver, type) and isinstance(bridge, ros_driver):
            if (inspect.getattr_static(cls, "call") is not family_driver.call
                    or inspect.getattr_static(cls, "make_bridge") is not ros_driver.make_bridge
                    or any(inspect.getattr_static(cls, name) is not inspect.getattr_static(family_driver, name)
                           for name in ("inner", "estop", "safety_status", "_run_safe_state"))
                    or _instance_shadows_route(bridge)):
                return False
            inner = inspect.getattr_static(bridge, "_inner_bridge", None)
            return inner is None or (type(inner) is ros_bridge and not _instance_shadows_route(inner))
    except AttributeError:
        return False
    return False


def _sdk_ros_route_class(cls: Any) -> bool:
    """The class half of :func:`_sdk_ros_route` for a RosDriver subclass, without an instance (gate G3).

    ``True`` when ``cls`` is a :class:`mhs.driver.RosDriver` whose ``call``, ``make_bridge``, ``inner``, ``estop``,
    ``safety_status`` and ``_run_safe_state`` are the SDK's, so a served instance without instance overrides is the
    SDK's own ROS route and the endpoint binds its sensed stop (SAFE-049, CORE-088; verification F3).
    """
    families = sys.modules.get(f"{__package__}.driver.families")
    ros_driver = getattr(families, "RosDriver", None)
    family_driver = getattr(families, "_FamilyDriver", None)
    if not (isinstance(cls, type) and isinstance(ros_driver, type) and isinstance(family_driver, type)
            and issubclass(cls, ros_driver)):
        return False
    try:
        return (inspect.getattr_static(cls, "call") is family_driver.call
                and inspect.getattr_static(cls, "make_bridge") is ros_driver.make_bridge
                and all(inspect.getattr_static(cls, name) is inspect.getattr_static(family_driver, name)
                        for name in ("inner", "estop", "safety_status", "_run_safe_state")))
    except AttributeError:
        return False


def _instance_shadows_route(obj: Any) -> bool:
    """True when the instance itself carries ``call``, ``make_bridge``, ``estop`` or ``safety_status`` (read statically,
    no package code)."""
    missing = object()
    for name in ("call", "make_bridge", "estop", "safety_status"):
        if inspect.getattr_static(obj, name, missing) is not inspect.getattr_static(type(obj), name, missing):
            return True
    return False


def _shared_stop_entry(reported: Any, capability_id: str, achieved_by: Sequence[str]) -> dict[str, Any] | None:
    """The receipt entry for a safe-state call a bridge answered from a request this e-stop already sent.

    The bridge appends ``{same_request_as}`` to the list of its call; only a sender the receipt can name (``native``
    or another ``achieved_by`` action) counts, and anything else a bridge or driver put there is ignored, never
    raised: the e-stop receipt must be written whatever the list holds.
    """
    try:
        for item in list(reported) if isinstance(reported, list) else []:
            sender = item.get("same_request_as") if isinstance(item, dict) else None
            if isinstance(sender, str) and (sender == "native" or sender in achieved_by):
                return {"capability_id": capability_id, "same_request_as": str(sender)}
    except Exception:  # noqa: BLE001 - never let a report break the e-stop path
        return None
    return None


def _bridge_safety_report(bridge: Any) -> tuple[bool | None, dict[str, Any] | None]:
    """One read of ``safety_status()``: ``safe_state.achieved`` (None when unknown) and the sensed confirmation.

    The report of a sensed-confirmation stop (``safe_state.confirmation.last``, SAFE-049, CORE-088) is taken only
    from the SDK's own ROS route (:func:`_sdk_ros_route`), so a package cannot put a confirmation it did not make
    into a receipt; anything else is ignored, never raised.
    """
    if bridge is None:
        return None, None
    try:
        status = _plain(bridge.safety_status() or {})
    except Exception:  # noqa: BLE001 - advisory only
        return None, None
    declared = status.get("safe_state") if isinstance(status, Mapping) else None
    if not isinstance(declared, Mapping):
        return None, None
    achieved = bool(declared["achieved"]) if isinstance(declared.get("achieved"), bool) else None
    confirmation = declared.get("confirmation")
    sensed = None
    try:
        if (isinstance(confirmation, Mapping) and confirmation.get("kind") == "sensed"
                and isinstance(confirmation.get("last"), Mapping) and _sdk_ros_route(bridge)):
            sensed = copy.deepcopy(dict(confirmation["last"]))
    except Exception:  # noqa: BLE001 - never let a report break the e-stop path
        sensed = None
    return achieved, sensed


def _confirmation_vendor(attempt: _EstopAttempt) -> dict[str, Any] | None:
    """``x-vendor`` of a background confirmation receipt: shared stop requests and the sensed confirmation."""
    vendor: dict[str, Any] = {}
    if attempt.shared_stops:
        vendor["shared_stop_requests"] = [dict(item) for item in attempt.shared_stops]
    if attempt.sensed is not None:
        vendor["sensed_confirmation"] = copy.deepcopy(attempt.sensed)
    return vendor or None


def _await_settled(operation: Operation) -> None:
    """Wait until a command in flight at the e-stop has settled (CORE-086), liveness-checked (verification F4).

    The worker sets ``done`` in its ``finally``; a worker thread that ended without setting it (stopped outside
    Python) can no longer reach the device, so the stop path runs again then instead of waiting forever.
    """
    while not operation.done.wait(0.05):
        worker = operation.thread
        if worker is not None and not worker.is_alive():
            return


def _sensed_stop_problems(device: Any) -> list[str]:
    """SAFE-049 / CORE-088: only a simulated device declares a sensed-confirmation stop (checked in every mode)."""
    estop = getattr(getattr(device, "safety", None), "estop", None)
    if not isinstance(estop, Mapping) or "confirmation" not in estop:
        return []
    mode = getattr(device, "mode", None)
    if mode != "simulated":
        return [f"device {device.device_id}: safety.estop.confirmation declares a sensed-confirmation stop, which is "
                f"for simulated devices only; the device's mode is {mode!r} (SAFE-049)"]
    confirmation = estop.get("confirmation")
    if not isinstance(confirmation, Mapping) or confirmation.get("kind") != "sensed":
        return [f"device {device.device_id}: safety.estop.confirmation.kind must be 'sensed'"]
    return []


def _bind_sensed_route(device: Any) -> bool:
    """SAFE-049 / CORE-088 (verification F3 of phase 3): bind the device's SDK ROS bridge to the mode this endpoint
    serves the device with, read from the served manifest. ``True`` when a binding was made.

    Only a device whose served manifest declares mode ``simulated`` and ``safety.estop.confirmation`` of kind
    ``sensed`` (:func:`_sensed_stop_problems` refused every other declaration) and whose bridge builds the SDK's
    RosBridge through SDK code is bound: the SDK's RosBridge itself, or a RosDriver whose class route members are the
    SDK's (:func:`_sdk_ros_route_class`) and whose instance carries no ``make_bridge``, ``inner`` or
    ``_grant_served_mode`` of its own (those decide which bridge is built and bound). Instance wrappers of the contract
    methods (the gate's phase windows) do not change which bridge confirms; whether a receipt may carry its report is
    :func:`_sdk_ros_route`'s separate question. A sensed stop anywhere else (a package's own Driver that builds a
    RosBridge, or a RosDriver that overrides its route) is never bound, so its confirmation never stands for a stop,
    whatever its constructor was told. Reads the route attributes statically (no package code runs) and never
    raises; it runs at start-up and on first use of a late device, never on the e-stop path.
    """
    try:
        estop = getattr(getattr(device, "safety", None), "estop", None)
        confirmation = estop.get("confirmation") if isinstance(estop, Mapping) else None
        if (getattr(device, "mode", None) != "simulated" or not isinstance(confirmation, Mapping)
                or confirmation.get("kind") != "sensed"):
            return False
        bridge = getattr(device, "bridge", None)
        ros = sys.modules.get(f"{__package__}.bridge.ros")
        families = sys.modules.get(f"{__package__}.driver.families")
        ros_bridge = getattr(ros, "RosBridge", None)
        if isinstance(ros_bridge, type) and type(bridge) is ros_bridge:
            bridge._bind_served_mode(device.mode)
            return True
        ros_driver = getattr(families, "RosDriver", None)
        missing = object()
        if (isinstance(ros_driver, type) and _sdk_ros_route_class(type(bridge))
                and all(inspect.getattr_static(bridge, name, missing)
                        is inspect.getattr_static(type(bridge), name, missing)
                        for name in ("make_bridge", "inner", "_grant_served_mode"))):
            ros_driver._grant_served_mode(bridge, device.mode)
            return True
    except Exception:  # noqa: BLE001 - an unbound bridge only withholds the confirmation (fail closed)
        return False
    return False


def _bridge_safe_state(bridge: Any) -> bool | None:
    """The bridge's own ``safety_status().safe_state.achieved``, if it reports one."""
    if bridge is None:
        return None
    try:
        status = _plain(bridge.safety_status() or {})
    except Exception:  # noqa: BLE001 - advisory only
        return None
    declared = status.get("safe_state") if isinstance(status, Mapping) else None
    if isinstance(declared, Mapping) and isinstance(declared.get("achieved"), bool):
        return bool(declared["achieved"])
    return None


def _new_operation_id() -> str:
    """``op_`` + a full 26-character ULID (finding SDK-06)."""
    return "op_" + canonical.ulid()


def _new_session_id() -> str:
    """``mhs_s_`` + a ULID + 64 random bits (16 hex).

    The ULID alone is monotonic (the next id of the same millisecond is the
    previous one plus 1), and the SSE stream is selected by session id: the
    random suffix keeps a session's id from being derived from another's.
    Alphanumeric, as ``receipt.schema.json`` requires.
    """
    return "mhs_s_" + canonical.ulid() + secrets.token_hex(8)


def _has_non_finite(value: Any, _depth: int = 0) -> bool:
    """True when ``value`` contains NaN or an infinity anywhere (not JSON)."""
    if isinstance(value, float):
        return not math.isfinite(value)
    if _depth > 64:
        return False
    if isinstance(value, Mapping):
        return any(_has_non_finite(item, _depth + 1) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_non_finite(item, _depth + 1) for item in value)
    return False


def _without_non_finite(value: Any, _depth: int = 0) -> Any:
    """A copy of ``value`` with every NaN / infinity replaced by None.

    Used only for an e-stop (never refused, plan 3.6), so that its receipt and
    digests stay canonical JSON; a subtree nested deeper than
    :func:`_has_non_finite` looks is dropped (None) for the same reason.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if _depth > 64:
        return None if isinstance(value, (Mapping, list, tuple)) else value
    if isinstance(value, Mapping):
        return {key: _without_non_finite(item, _depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_without_non_finite(item, _depth + 1) for item in value]
    return value


def _decode_wire(raw: bytes | str) -> Any:
    """Decode one transport message strictly (:func:`protocol.loads_strict`).

    A text that is invalid only because of ``NaN`` / ``Infinity`` literals is
    still handed on when it is an e-stop, or a batch holding one (plan 3.6: an
    e-stop is never refused before it latched); :meth:`MHSServer._handle_message`
    then replaces those values by null.  Everything else is the original
    ``MHS.PROTOCOL.PARSE_ERROR``.
    """
    try:
        return protocol.loads_strict(raw)
    except MHSError:
        try:
            text = bytes(raw).decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
            lenient = json.loads(text)
        except (UnicodeDecodeError, ValueError, RecursionError):
            lenient = None
        items = lenient if isinstance(lenient, list) else [lenient]
        if any(
            isinstance(item, Mapping) and isinstance(item.get("params"), Mapping)
            and _is_estop_request(item.get("method"), item["params"])
            for item in items
        ):
            return lenient
        raise


def _is_loopback_host(host: Any) -> bool:
    """True for ``localhost``, ``127.0.0.0/8`` and ``::1`` (never a wildcard)."""
    if not isinstance(host, str):
        return False
    name = host.strip().strip("[]").lower()
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def _conformance_report_digest(report: Mapping[str, Any]) -> str:
    """``sha256(JCS(report without report_digest and issuer.signature))`` (MHS-001 §7.2)."""
    body = {str(key): value for key, value in report.items() if key != "report_digest"}
    issuer = body.get("issuer")
    if isinstance(issuer, Mapping) and "signature" in issuer:
        body["issuer"] = {str(k): v for k, v in issuer.items() if k != "signature"}
    return canonical.digest(body)


def _drain_subscription(subscription: dict[str, Any]) -> list[Any]:
    """Take a subscription's buffered events (called under ``MHSServer._lock``)."""
    events = list(subscription.get("events") or [])
    subscription["events"] = []
    subscription["event_samples"] = []
    subscription["delivered"] = int(subscription.get("delivered", 0)) + len(events)
    # A delivered gap must not be re-emitted on the next publish.
    subscription["dropped_sample_from"] = None
    subscription["dropped_sample_to"] = None
    return events


def _event_params(event: Any) -> dict[str, Any]:
    try:
        return dict(event.to_dict().get("params") or {})
    except AttributeError:
        return {}


def _buffer_event(sub: dict[str, Any], subscription_id: str, stream: str, device_id: Any,
                  payload: Any, event_type: str | None) -> None:
    """Append one event to a subscription's bounded buffer (EVT-006/EVT-008).

    Called under ``MHSServer._lock``.  On overflow the oldest events are
    dropped and one coalesced ``control``/``gap`` event names the exact range
    of dropped samples.
    """
    events: list[Any] = sub.setdefault("events", [])
    samples: list[Any] = sub.setdefault("event_samples", [])
    while len(samples) < len(events):
        samples.append(None)
    max_buffer = max(2, int(sub.get("max_buffer") or 256))

    def _is_gap(event: Any) -> bool:
        return _event_params(event).get("type") == "gap"

    def _merge_dropped(low: Any, high: Any) -> None:
        if low is None:
            return
        current_low = sub.get("dropped_sample_from")
        current_high = sub.get("dropped_sample_to")
        sub["dropped_sample_from"] = low if current_low is None else min(current_low, low)
        upper = high if high is not None else low
        sub["dropped_sample_to"] = upper if current_high is None else max(current_high, upper)

    # A new publication counts as one sample in the delivery stream.
    sub["sample_seq"] = int(sub.get("sample_seq", 0)) + 1
    sample_number = int(sub["sample_seq"])

    # Drop any previously built gap from the buffer but retain its exact
    # dropped-sample range.
    index = 0
    while index < len(events):
        if _is_gap(events[index]):
            params = _event_params(events[index])
            _merge_dropped(params.get("from"), params.get("to"))
            events.pop(index)
            if index < len(samples):
                samples.pop(index)
            continue
        index += 1

    def _fits() -> bool:
        has_gap = sub.get("dropped_sample_from") is not None
        return len(events) + 1 + (1 if has_gap else 0) <= max_buffer

    while not _fits():
        dropped = events.pop(0)
        dropped_sample = samples.pop(0) if samples else None
        if _is_gap(dropped):
            params = _event_params(dropped)
            _merge_dropped(params.get("from"), params.get("to"))
            continue
        sub["dropped"] = int(sub.get("dropped", 0)) + 1
        _merge_dropped(dropped_sample, dropped_sample)

    if sub.get("dropped_sample_from") is not None:
        gap_seq = int(sub.get("seq", 0)) + 1
        gap = protocol.make_event(
            subscription_id=subscription_id,
            seq=gap_seq,
            stream="control",
            device_id=device_id,
            payload={
                "type": "gap",
                "from": sub.get("dropped_sample_from"),
                "to": sub.get("dropped_sample_to"),
            },
            type="gap",
        )
        gap.params["from"] = sub.get("dropped_sample_from")
        gap.params["to"] = sub.get("dropped_sample_to")
        events.append(gap)
        samples.append(None)
        sub["seq"] = gap_seq
    seq = int(sub.get("seq", 0)) + 1
    sub["seq"] = seq
    events.append(protocol.make_event(
        subscription_id=subscription_id,
        seq=seq,
        stream=stream,
        device_id=device_id,
        payload=payload,
        type=event_type,
    ))
    samples.append(sample_number)


def _session_reaper_loop(server_ref: "weakref.ReferenceType[MHSServer]", wake: threading.Event) -> None:
    """Session-expiry timer: expires sessions on time, without being asked.

    Holds only a weak reference between rounds, so a discarded server's timer
    ends; it also ends when no live session is left.
    """
    while True:
        server = server_ref()
        if server is None:
            return
        # Cleared before the round, so a session opened during it wakes the
        # next wait at once instead of being missed.
        wake.clear()
        try:
            wait_s = server._reap_expired_sessions()  # noqa: SLF001
        except Exception:  # noqa: BLE001 - keep the timer alive
            _log.exception("session expiry timer round failed")
            wait_s = _REAPER_MAX_WAIT_S
        del server
        if wait_s is None:
            return
        # Wake a little after the expiry instant: Session.expired() is strict.
        wake.wait(min(_REAPER_MAX_WAIT_S, wait_s + 0.005))


def _pattern_prefix_match(pattern: str, capability_id: str) -> bool:
    """Match ``cap.<class>.*``, ``cap.<class>.*.vN`` and ``cap.<class>.*`` styles."""
    if pattern == capability_id:
        return True
    if not pattern.endswith(("*", "v1", "v2", "v3")):
        return False
    if pattern.endswith(".*"):
        return capability_id.startswith(pattern[:-1])
    # cap.world.*.v1 style: prefix before the version suffix
    if ".*." in pattern:
        prefix = pattern.split(".*.", 1)[0] + "."
        version = pattern.rsplit(".", 1)[-1]
        return capability_id.startswith(prefix) and capability_id.endswith("." + version)
    return capability_id.startswith(pattern[:-1])


def _pattern_matches(pattern: str, capability_id: str) -> bool:
    if pattern == capability_id:
        return True
    if pattern.endswith(".*"):
        return capability_id.startswith(pattern[:-1])
    if pattern.endswith("*"):
        return capability_id.startswith(pattern[:-1])
    return False


MHSServer._METHODS = {
    Method.HELLO: MHSServer._m_hello,
    Method.DEVICES_LIST: MHSServer._m_devices_list,
    Method.DEVICES_GET: MHSServer._m_devices_get,
    Method.SCHEMA_GET: MHSServer._m_schema_get,
    Method.SESSION_OPEN: MHSServer._m_session_open,
    Method.SESSION_HEARTBEAT: MHSServer._m_session_heartbeat,
    Method.SESSION_CLOSE: MHSServer._m_session_close,
    Method.RESOURCE_READ: MHSServer._m_resource_read,
    Method.RESOURCE_WRITE: MHSServer._m_resource_write,
    Method.COMMAND: MHSServer._m_command,
    Method.OPERATIONS_GET: MHSServer._m_operations_get,
    Method.OPERATIONS_LIST: MHSServer._m_operations_list,
    Method.OPERATIONS_CANCEL: MHSServer._m_operations_cancel,
    Method.SUBSCRIBE: MHSServer._m_subscribe,
    Method.UNSUBSCRIBE: MHSServer._m_unsubscribe,
    Method.SNAPSHOT: MHSServer._m_snapshot,
    Method.RESTORE: MHSServer._m_restore,
    Method.SAFETY_STATUS: MHSServer._m_safety_status,
    Method.SAFETY_ESTOP: MHSServer._m_safety_estop,
    Method.SAFETY_RESET: MHSServer._m_safety_reset,
    Method.SAFETY_PERMIT: MHSServer._m_safety_permit,
    Method.EVIDENCE_EXPORT: MHSServer._m_evidence_export,
    Method.EVIDENCE_VERIFY: MHSServer._m_evidence_verify,
    Method.CONFORMANCE_REPORT: MHSServer._m_conformance_report,
    # mhs.registry.search is not an endpoint method: the registry is a separate
    # module (mhs.registry) and the endpoint answers METHOD_NOT_FOUND.
}

__all__ = [
    "Capability",
    "Device",
    "MHSServer",
    "MHSStrictError",
    "MHSStrictWarning",
    "Resource",
    "SafetyEnvelope",
    "SessionManager",
    "StateDirError",
    "SubscriptionHub",
    "MHS_VERSION",
]
