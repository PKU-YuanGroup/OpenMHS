"""Conformance test cases (stable ids, negative tests included).

The suite is endpoint-generic: it discovers the device manifests, resolves
every binding against the capability catalogue (verb, risk floor, effective
limits, exactly as the runtime does) and tests the *driver* through them:

* **Probe selection** is by catalogue verb, never by declaration order: the
  probe is a ``write`` or ``invoke`` binding with at least one input, no
  permit, not a safe-state action, not a stop class and not deprecated; ties
  are broken by a fixed ranking and then by capability id (TESTS-03).
* **Inputs** come from the fixture file, then the class examples, then
  envelope-aware synthesis (:mod:`mhs.conformance.synth`).  When no valid
  input or no distinct alternate exists the test is skipped with the reason.
* **Hardware and hybrid subjects** get no actuating test unless the operator
  passes ``allow_actuation`` (CON-031).  Negative tests (commands built to be
  refused) are sent to them only when the in-process harness blocks every
  write/invoke at their bridge, so a check the endpoint fails to make cannot
  move the device; over any other transport they are skipped, and the suite
  never sends a bound actuating capability to such a device (send guard).
  E-stops go only to ``software``/``both`` e-stops (CON-032); permits are never
  self-issued on hardware; test hooks (``x-cap.mhs-test.*``) are never invoked
  on them.  A command the endpoint dispatches to hardware anyway (blocked at
  the bridge, or any receipt other than ``rejected``) fails ``CON-031``.
* **In-process runs** (:mod:`mhs.conformance.inprocess`) add a call recorder
  and fault injection at the bridge boundary, so interlock, deadline,
  cancellation and unknown-outcome tests no longer need reference-only hooks.

Test IDs are stable and traceable (``traceability.json``):

* ``PROTO-*`` wire protocol / discovery / reads
* ``SESS-*``  sessions, mode discipline, grants, lifetime
* ``OP-*``/``CAP-*``/``TCAP-*`` commands, idempotency, revisions, schemas, outputs
* ``SAFE-*``/``TSAFE-*`` safety status, e-stop latch/reset, interlocks, permits, envelopes
* ``EVID-*``  evidence export, chain verification and tamper detection
* ``FID-*``   fidelity-contract disclosure and replay
* ``CON-*``/``TCON-*`` profile/subject consistency and suite self-checks
"""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from mhs import canonical
from mhs.conformance import static as _static
from mhs.conformance import synth as _synth
from mhs.conformance.model import (
    CODE_ALIASES,
    LEVELS,
    TestCase,
    TestOutcome,
    code_matches,
    normalize_code,
)
from mhs.conformance.presence import check_method_presence, probe_table
from mhs.conformance.requirements import MODE_EXEMPTIONS, methods_introduced_at
from mhs.conformance.synth import (
    Binding,
    Probe,
    Unsynthesizable,
    alternate_input,
    bindings_for,
    envelope_probe_plan,
    load_fixtures,
    served_input,
    synthesize,
    valid_input,
)

__all__ = [
    "CODE_ALIASES",
    "LEVELS",
    "PREFERRED_PROBES",
    "RunLog",
    "RunOptions",
    "SUITE_PRINCIPAL",
    "SuiteContext",
    "TestCase",
    "TestOutcome",
    "TESTS",
    "cases_for_level",
    "next_level",
    "normalize_code",
]

_DIGEST_PREFIX = "sha256:"

#: The suite's own principal (CON-021).
SUITE_PRINCIPAL = {"id": "mhs-conformance", "kind": "service"}

#: Classes ranked first among eligible probes: their minimal catalogue input has
#: no device preconditions.  Ranking only breaks ties; it never depends on the
#: order in which a driver declares its capabilities.
PREFERRED_PROBES = ("cap.world.step.v1", "cap.motion.joint_position.v1", "cap.fluid.transfer.v1")

#: Stop classes are safe-state actions, never probes.
STOP_CLASSES = ("cap.motion.stop.v1", "cap.motion.estop.v1", "cap.compute.cancel.v1")

_SCHEMA_REFUSALS = ("MHS.SCHEMA.", "MHS.CAPABILITY.INPUT_INVALID", "MHS.PROTOCOL.INVALID_PARAMS")
#: SAFE-014 (plan 3.5): a value outside an effective limit is refused with
#: ``MHS.SAFETY.ENVELOPE_VIOLATION`` (legacy alias ``LIMIT_EXCEEDED``) -- also
#: where the schema repeats the bound, because the limits are checked before
#: the remaining schema bounds.  An input refusal (``INPUT_INVALID``, which
#: suite 1.2.0 still accepted) or a protocol refusal never counts.
_ENVELOPE_REFUSALS = ("MHS.SAFETY.ENVELOPE_VIOLATION", "MHS.SAFETY.LIMIT_EXCEEDED")
#: Bridge methods a refused command must never reach (in-process).  A refusal
#: may still read the device state for its receipt (``read``).
_ACTUATING_METHODS = ("call", "write", "restore", "estop", "reset", "snapshot", "safe_state")
#: Refusal codes of the permit check (plan 3.6 step 10), which runs after the limits (step 8).
_PERMIT_REFUSALS = ("MHS.SAFETY.PERMIT",)
#: Receipt statuses of a command the endpoint did not dispatch to the device.
_NOT_DISPATCHED = (None, "rejected")
#: Test hooks of the reference fixtures; never sent to hardware without the operator's opt-in.
TEST_HOOK_PREFIX = "x-cap.mhs-test."


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _error_code(exc: BaseException | None) -> str | None:
    return getattr(exc, "code", None) if exc is not None else None


def _receipt_error(receipt: Any) -> Mapping[str, Any]:
    if isinstance(receipt, Mapping) and isinstance(receipt.get("error"), Mapping):
        return receipt["error"]
    return {}


def _receipt_code(receipt: Any, exc: BaseException | None = None) -> str | None:
    code = _error_code(exc)
    if code:
        return code
    return _receipt_error(receipt).get("mhs_code")


def _receipt_status(receipt: Any) -> str | None:
    return receipt.get("status") if isinstance(receipt, Mapping) else None


def _is_success(receipt: Any) -> bool:
    return _receipt_status(receipt) in ("completed", "accepted", "running")


def _digest_ok(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(_DIGEST_PREFIX) and len(value) == len(_DIGEST_PREFIX) + 64


def _code_matches(code: str | None, prefixes: Iterable[str]) -> bool:
    return code_matches(code, prefixes)


def _synthesize(schema: Any, *, depth: int = 0) -> Any:
    """Schema-only synthesis (no limits); ``None`` when no value can be built."""

    try:
        return synthesize(schema if isinstance(schema, Mapping) else {})
    except Unsynthesizable:
        return None


def _state_candidates(state: Any, resource_id: str) -> list[Any]:
    candidates = [state]
    if isinstance(state, Mapping):
        if resource_id in state:
            candidates.insert(0, state[resource_id])
        candidates.append({resource_id: state})
    return candidates


def _state_without_metadata(state: Any, resource_id: str) -> Any:
    """Strip server-injected metadata (``resource_id``) from a read state."""

    if isinstance(state, Mapping):
        cleaned = {str(key): value for key, value in state.items() if key != "resource_id"}
        if resource_id in cleaned and len(cleaned) == 1:
            return cleaned[resource_id]
        return cleaned
    return state


def _verify_state_hash(
    result: Mapping[str, Any],
    resource_id: str,
    exclusions: Sequence[str],
    *,
    device_id: str | None = None,
    resource_count: int = 1,
) -> str | None:
    """Verify a read's state_hash.

    Returns ``"spec"`` when the hash is the canonical digest of the resource
    state document (MHS-000 section 3.3, the conformant form), ``"server"`` when
    it only matches the reference server's current non-normative
    ``{"device_id", "state"}`` wrapper, or ``None`` when it does not verify.
    """

    stated = result.get("state_hash")
    state = result.get("state")
    if not _digest_ok(stated) or state is None:
        return None
    cleaned = _state_without_metadata(state, resource_id)
    for candidate in _state_candidates(cleaned, resource_id):
        try:
            if canonical.state_hash(candidate, exclusions) == stated:
                return "spec"
        except Exception:  # noqa: BLE001 - canonicalisation error is a test failure, not a crash
            continue
    if device_id and resource_count == 1:
        try:
            filtered = _apply_root_exclusions({resource_id: cleaned}, exclusions)
            if canonical.digest({"device_id": device_id, "state": filtered}) == stated:
                return "server"
        except Exception:  # noqa: BLE001
            return None
    return None


def _apply_root_exclusions(state: Mapping[str, Any], exclusions: Sequence[str]) -> dict[str, Any]:
    """Apply JSON pointers to a copied state document (reference-server form)."""

    copied = copy.deepcopy(dict(state))
    for pointer in exclusions:
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            continue
        parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
        cursor: Any = copied
        for part in parts[:-1]:
            if isinstance(cursor, dict) and part in cursor:
                cursor = cursor[part]
            else:
                cursor = None
                break
        if isinstance(cursor, dict) and parts and parts[-1] in cursor:
            del cursor[parts[-1]]
    return copied


def _cancelled_output(receipt: Any) -> bool:
    """Legacy cancellation outputs (``{'status': 'cancelled'}``, ``{'cancelled': True}``; plan 3.7)."""

    output = receipt.get("output") if isinstance(receipt, Mapping) else None
    return isinstance(output, Mapping) and (output.get("status") == "cancelled" or output.get("cancelled") is True)


# ---------------------------------------------------------------------------
# run options and log
# ---------------------------------------------------------------------------


@dataclass
class RunOptions:
    """Operator choices for one run."""

    allow_actuation: bool = False
    read_only: bool = False
    fixtures: Any = None
    approvals: Sequence[Mapping[str, Any]] | None = None


@dataclass
class RunLog:
    """What the suite did during one run (shared by every context of the run)."""

    estop_targets: list[tuple[str, str]] = field(default_factory=list)
    reset_targets: list[tuple[str, str]] = field(default_factory=list)
    estop_withheld: list[str] = field(default_factory=list)
    permits: list[tuple[str, str]] = field(default_factory=list)
    gated: list[str] = field(default_factory=list)
    harnesses: list[Any] = field(default_factory=list)
    #: ``(test id, device id, capability id, receipt status)`` of every command a
    #: test sent to a hardware/hybrid device without ``allow_actuation`` that the
    #: endpoint dispatched instead of refusing (CON-031 fails on any).
    hardware_dispatches: list[tuple[str, str, str, str]] = field(default_factory=list)
    #: ``(test id, device id, what)`` of every command the suite's send guard kept
    #: from a hardware/hybrid device without ``allow_actuation`` (nothing was sent).
    withheld: list[tuple[str, str, str]] = field(default_factory=list)
    #: ``(test id, device id)`` of every e-stop sent to a device that declares a
    #: terminal e-stop (CORE-087): its endpoint cannot be reset afterwards.
    terminal_stops: list[tuple[str, str]] = field(default_factory=list)
    lock: Any = field(default_factory=threading.Lock)


class _NoApprovals(RuntimeError):
    """Raised instead of inventing a permit on hardware (CON-031)."""


class _Withheld(RuntimeError):
    """The suite's send guard refused to send a command to hardware without ``allow_actuation`` (CON-031)."""

    code = "MHS.AUTH.HARDWARE_DISABLED"


# ---------------------------------------------------------------------------
# suite context
# ---------------------------------------------------------------------------


class SuiteContext:
    """Shared state and convenience helpers for one endpoint instance of a run."""

    def __init__(
        self,
        client: Any,
        *,
        profile: str,
        requested_level: str = "CL4",
        options: RunOptions | None = None,
        harness: Any = None,
        run_log: RunLog | None = None,
    ):
        self.client = client
        self.profile = profile
        self.requested_level = requested_level
        self.options = options or RunOptions()
        self.harness = harness
        self.run_log = run_log or RunLog()
        if harness is not None and harness not in self.run_log.harnesses:
            self.run_log.harnesses.append(harness)
        self.fixtures = load_fixtures(self.options.fixtures)
        self.hello: dict[str, Any] = {}
        self.devices: list[dict[str, Any]] = []
        self.endpoint_id: str | None = None
        self.session_id: str | None = None
        #: Sessions of the other device modes of a mixed endpoint (mode -> session id).
        self.mode_sessions: dict[str, str] = {}
        #: operation id -> the session whose command started it (operations are per session).
        self.operation_sessions: dict[str, str] = {}
        self.extra_sessions: list[str] = []
        self.last_receipt: dict[str, Any] | None = None
        self.last_mutation: dict[str, Any] | None = None
        self._current_test: str | None = None
        self.notes: list[str] = []
        self.bindings: list[Binding] = []
        self.probe: Binding | None = None
        self._capability_index: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self._primary: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
        self._probe_input: tuple[dict[str, Any], str] | None = None
        self._read_probes: list[tuple[Binding, dict[str, Any], str]] | None = None
        #: ``(binding, reason)`` of every read OP-001 would send but cannot build an input for
        self.unsent_reads: list[tuple[Binding, str]] = []
        #: Devices of this endpoint whose declared terminal e-stop (CORE-087) the suite engaged:
        #: no reset of this endpoint undoes it, so the runner gives later tests a new endpoint.
        self.terminated: set[str] = set()

    # -- discovery ---------------------------------------------------------
    def load(self) -> None:
        self.hello = _as_dict(self.client.hello())
        self.devices = [dict(item) for item in (self.client.devices() or []) if isinstance(item, Mapping)]
        if not self.devices:
            raise RuntimeError("endpoint exposes no devices; cannot run conformance tests")
        self.endpoint_id = self.hello.get("endpoint_id") or self.devices[0].get("device_id", "")
        for manifest in self.devices:
            for capability in manifest.get("capabilities") or []:
                if isinstance(capability, Mapping):
                    self._capability_index.append((manifest, dict(capability)))
            self.bindings.extend(bindings_for(manifest, published=self._published(manifest)))
        self._fill_declared_verbs()
        self._select_primary()
        self._gate_harness()

    def _fill_declared_verbs(self) -> None:
        """Take each binding's own declared verb from the hello device summaries when the manifest omits it.

        A compatibility-mode endpoint publishes ``verb`` only in its device
        summaries; an extension's declared verb is the one the runtime uses.
        """

        declared: dict[tuple[str, str, str | None], str] = {}
        for summary in self.hello.get("devices") or []:
            if not isinstance(summary, Mapping):
                continue
            for entry in summary.get("capabilities") or []:
                if isinstance(entry, Mapping) and entry.get("verb") in ("read", "write", "invoke"):
                    resource = entry.get("resource")
                    declared[(str(summary.get("device_id")), str(entry.get("capability_id")),
                              str(resource) if isinstance(resource, str) else None)] = str(entry["verb"])
        for binding in self.bindings:
            if binding.declared_verb is None:
                binding.declared_verb = declared.get((binding.device_id, binding.capability_id, binding.resource))

    def _published(self, manifest: Mapping[str, Any]) -> dict[str, Any] | None:
        """The endpoint's ``devices.get`` result for ``manifest`` (its ``x-mhs-effective-limits``), or None."""

        inspect = getattr(self.client, "inspect", None)
        if not callable(inspect):
            return None
        try:
            result = inspect(str(manifest.get("device_id")))
        except Exception:  # noqa: BLE001 - no published limits: the declared ones apply
            return None
        if not isinstance(result, Mapping) or result.get("device_id") != manifest.get("device_id"):
            return None
        return dict(result)

    @property
    def current_test(self) -> str | None:
        return self._current_test

    @current_test.setter
    def current_test(self, value: str | None) -> None:
        self._current_test = value
        if self.harness is not None and hasattr(self.harness, "current_test"):
            self.harness.current_test = value

    def _gate_harness(self) -> None:
        """Give the in-process harness the run's actuation policy (CON-031): it blocks hardware writes."""

        gate = getattr(self.harness, "gate", None)
        if not callable(gate):
            return
        reads: dict[str, list[str]] = {}
        for binding in self.bindings:
            if _trusted_read(binding):
                reads.setdefault(binding.device_id, []).append(binding.capability_id)
        gate(self.hardware_ids, allow_actuation=bool(self.options.allow_actuation), read_capabilities=reads)

    def probe_candidates(self) -> list[Binding]:
        """Eligible probes in a fixed, declaration-order-independent order."""

        out: list[Binding] = []
        for binding in self.bindings:
            capability_id = binding.capability_id
            if binding.manifest.get("mode") == "replay":
                continue
            if binding.verb not in ("write", "invoke") or not binding.input_properties:
                continue
            if binding.requires_permit or binding.deprecated:
                continue
            if capability_id in STOP_CLASSES or capability_id.startswith("x-cap.mhs-test."):
                continue
            if capability_id in _static.achieved_by(binding.manifest):
                continue
            if capability_id == _reenable_id(binding.manifest):
                continue  # the declared re-enable (CORE-086) is TSAFE-001's, never the probe
            out.append(binding)
        preferred = self.fixtures.probe

        def rank(binding: Binding) -> tuple[Any, ...]:
            capability_id = binding.capability_id
            return (
                0 if preferred and capability_id == preferred else 1,
                PREFERRED_PROBES.index(capability_id) if capability_id in PREFERRED_PROBES else len(PREFERRED_PROBES),
                0 if binding.required_inputs else 1,
                1 if binding.extension else 0,
                capability_id,
                binding.device_id,
                binding.resource or "",
            )

        return sorted(out, key=rank)

    def _select_primary(self) -> None:
        candidates = self.probe_candidates()
        if candidates:
            self.probe = candidates[0]
            manifest = self.device_for(self.probe.device_id)
            self._primary = (manifest, self.probe.capability, manifest)
            return
        manifest = sorted(self.devices, key=lambda item: str(item.get("device_id")))[0]
        capabilities = [dict(item) for item in manifest.get("capabilities") or [] if isinstance(item, Mapping)]
        capabilities.sort(key=lambda item: str(item.get("capability_id")))
        capability = capabilities[0] if capabilities else {"capability_id": "cap.x.none.v1"}
        self._primary = (manifest, capability, manifest)

    @property
    def primary(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        if self._primary is None:
            raise RuntimeError("suite context is not loaded")
        return self._primary

    @property
    def primary_device(self) -> dict[str, Any]:
        return self.primary[0]

    @property
    def primary_capability(self) -> dict[str, Any]:
        return self.primary[1]

    @property
    def primary_resource(self) -> str:
        resources = [str(item.get("resource_id")) for item in self.primary_device.get("resources") or []]
        bound = self.primary_capability.get("resource")
        if isinstance(bound, str) and bound in resources:
            return bound
        if resources:
            return resources[0]
        return str(bound or "state")

    @property
    def capability_ids(self) -> set[str]:
        return {str(capability.get("capability_id")) for _manifest, capability in self._capability_index}

    def device_for(self, device_id: str) -> dict[str, Any]:
        for manifest in self.devices:
            if manifest.get("device_id") == device_id:
                return manifest
        return self.devices[0]

    def resource_for(self, device_id: str) -> str:
        manifest = self.device_for(device_id)
        resources = manifest.get("resources") or []
        return str(resources[0].get("resource_id")) if resources else "state"

    def resource_meta(self, device_id: str, resource_id: str) -> dict[str, Any]:
        for item in self.device_for(device_id).get("resources") or []:
            if item.get("resource_id") == resource_id:
                return dict(item)
        return {}

    def binding(self, device_id: str, capability_id: str) -> Binding | None:
        for binding in self.bindings:
            if binding.device_id == device_id and binding.capability_id == capability_id:
                return binding
        return None

    def bindings_of(self, device_id: str, capability_id: str) -> list[Binding]:
        return [binding for binding in self.bindings
                if binding.device_id == device_id and binding.capability_id == capability_id]

    def is_hardware(self, device_id: str) -> bool:
        return str(self.device_for(device_id).get("mode")) in _static.HARDWARE_MODES

    def may_actuate(self, device_id: str) -> bool:
        """True unless ``device_id`` is hardware/hybrid and the operator did not pass ``allow_actuation``."""

        return bool(self.options.allow_actuation) or not self.is_hardware(device_id)

    def bridge_blocks(self, device_id: str) -> bool:
        """True when the in-process harness refuses write/invoke calls at ``device_id``'s bridge (CON-031)."""

        blocks = getattr(self.harness, "blocks", None)
        if not callable(blocks):
            return False
        try:
            return bool(blocks(device_id))
        except Exception:  # noqa: BLE001 - an unknown harness cannot be trusted to block
            return False

    @property
    def negative_tests_contained(self) -> bool:
        """True when a negative test cannot move hardware even if the endpoint fails to refuse it.

        That holds when actuation is allowed (or there is no hardware), or when
        the in-process harness blocks every hardware bridge of the run.  Over a
        plain client nothing stands between an unenforced check and the device.
        """

        return self.actuation_allowed or all(self.bridge_blocks(device_id) for device_id in self.hardware_ids)

    @property
    def actuation_capped(self) -> bool:
        """True when a hardware/hybrid device binds an actuating capability the gate keeps untested (CL1 cap)."""

        if self.actuation_allowed:
            return False
        hardware = set(self.hardware_ids)
        return any(binding.device_id in hardware and binding.verb in ("write", "invoke")
                   for binding in self.bindings)

    def uninstrumented(self, device_id: str) -> list[str]:
        """Actuating bridge methods of ``device_id`` the harness could not shadow (zero-call proofs fail)."""

        if self.harness is None:
            return []
        getter = getattr(self.harness, "uninstrumented_for", None)
        return list(getter(device_id)) if callable(getter) else []

    def find_capability(self, capability_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        for manifest, capability in self._capability_index:
            if capability.get("capability_id") == capability_id:
                return manifest, capability, self.device_for(manifest["device_id"])
        raise KeyError(capability_id)

    def find_capability_prefix(self, prefix: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        for manifest, capability in self._capability_index:
            if str(capability.get("capability_id", "")).startswith(prefix):
                return manifest, capability, self.device_for(manifest["device_id"])
        return None

    @property
    def gated_binding(self) -> Binding | None:
        gated = [binding for binding in self.bindings
                 if binding.requires_permit and binding.manifest.get("mode") != "replay"
                 and binding.verb in ("write", "invoke")]
        gated.sort(key=lambda item: (item.device_id, item.capability_id, item.resource or ""))
        return gated[0] if gated else None

    @property
    def gated_capability(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        binding = self.gated_binding
        if binding is None:
            return None
        manifest = self.device_for(binding.device_id)
        return manifest, binding.capability, manifest

    @property
    def replay_device(self) -> dict[str, Any] | None:
        for manifest in self.devices:
            if manifest.get("mode") == "replay":
                return manifest
        return None

    def cancellable_capabilities(self) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
        """Every binding that declares ``constraints.cancellable: true`` (OP-011), in id order.

        Replay-mode devices are left out: they refuse every command before any
        effect (FID-024), so there is no operation to cancel.
        """

        found: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
        for manifest, capability in self._capability_index:
            if manifest.get("mode") == "replay":
                continue
            constraints = capability.get("constraints")
            if isinstance(constraints, Mapping) and constraints.get("cancellable") is True:
                found.append((manifest, capability, self.device_for(manifest["device_id"])))
        found.sort(key=lambda item: (str(item[1].get("capability_id")), str(item[0].get("device_id"))))
        return found

    @property
    def first_cancellable(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        found = self.cancellable_capabilities()
        return found[0] if found else None

    def determinism_kind(self, device_id: str | None = None) -> str:
        manifest = self.device_for(device_id) if device_id else self.primary_device
        return str(((manifest.get("fidelity") or {}).get("determinism") or {}).get("kind") or "none")

    def snapshot_restore_supported(self, device_id: str | None = None) -> bool:
        manifest = self.device_for(device_id) if device_id else self.primary_device
        return bool((manifest.get("fidelity") or {}).get("snapshot_restore"))

    # -- policy ------------------------------------------------------------
    @property
    def hardware_ids(self) -> list[str]:
        return [str(manifest.get("device_id")) for manifest in _static.hardware_devices(self)]

    @property
    def actuation_allowed(self) -> bool:
        return bool(self.options.allow_actuation) or not self.hardware_ids

    def exempt(self, test_id: str) -> bool:
        """MODE_EXEMPTIONS keyed on the mode of the device the test targets (CON-017)."""

        if self._primary is None:
            return False
        mode = str(self.primary_device.get("mode"))
        return test_id in MODE_EXEMPTIONS.get(mode, ())

    def estop_kind(self, device_id: str | None = None) -> str:
        manifest = self.device_for(device_id) if device_id else self.primary_device
        return str(((manifest.get("safety") or {}).get("estop") or {}).get("kind") or "software")

    # -- sessions ----------------------------------------------------------
    def _open(self, **kwargs: Any) -> Any:
        try:
            return self.client.open_session(principal=dict(SUITE_PRINCIPAL), **kwargs)
        except TypeError:
            return self.client.open_session(**kwargs)

    def _session_mode(self, device_id: str | None) -> str | None:
        """The mode of the session for ``device_id``; None when every device has one mode.

        A session has a single mode (the endpoint refuses a device of another
        mode with ``MHS.SESSION.MODE_MISMATCH``), so a mixed endpoint gets one
        session per mode; ``device_id`` None means the primary device.
        """
        modes = {str(manifest.get("mode")) for manifest in self.devices}
        if len(modes) <= 1:
            return None
        target = device_id or self.primary_device.get("device_id")
        return str(self.device_for(str(target)).get("mode"))

    def ensure_session(self, device_id: str | None = None) -> str:
        mode = self._session_mode(device_id)
        primary_mode = None if mode is None else str(self.primary_device.get("mode"))
        if mode is None or mode == primary_mode:
            if self.session_id:
                return self.session_id
        elif mode in self.mode_sessions:
            return self.mode_sessions[mode]
        session = self._open(
            device_ids=[manifest["device_id"] for manifest in self.devices
                        if mode is None or str(manifest.get("mode")) == mode],
            capabilities=None,
            mode=mode,
            ttl_s=600,
        )
        session_id = _session_id(session)
        if mode is None or mode == primary_mode:
            self.session_id = session_id
        else:
            self.mode_sessions[mode] = session_id
        return session_id

    def open_session(self, **kwargs: Any) -> Any:
        return self._open(**kwargs)

    def close(self) -> None:
        for session_id in [self.session_id, *self.mode_sessions.values()] + self.extra_sessions:
            if not session_id:
                continue
            closer = getattr(self.client, "close_session", None)
            try:
                if callable(closer):
                    closer(session_id)
            except Exception:  # noqa: BLE001 - closing is best effort
                pass

    # -- reads / commands --------------------------------------------------
    def read(self, resource_id: str | None = None, device_id: str | None = None, fields: Any = None) -> dict[str, Any]:
        resource = resource_id or self.primary_resource
        target = device_id or self.primary_device["device_id"]
        try:
            return _as_dict(self.client.read(resource, device_id=target, fields=fields,
                                             session_id=self.ensure_session(str(target))))
        except TypeError:
            return _as_dict(self.client.read(resource, device_id=target, fields=fields))

    def current_revision(self, device_id: str | None = None, resource_id: str | None = None) -> int:
        result = self.read(resource_id, device_id)
        revision = result.get("revision")
        return int(revision) if isinstance(revision, int) else 0

    def invoke(
        self,
        capability_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        *,
        device_id: str | None = None,
        command_id: str | None = None,
        **kwargs: Any,
    ) -> tuple[dict[str, Any] | None, BaseException | None]:
        capability = capability_id or str(self.primary_capability.get("capability_id"))
        if device_id:
            target_device = device_id
        elif capability == self.primary_capability.get("capability_id"):
            target_device = self.primary_device["device_id"]
        elif capability in self.capability_ids:
            target_device = self.find_capability(capability)[0]["device_id"]
        else:
            target_device = self.primary_device["device_id"]
        invocation = {
            "input": dict(payload) if payload is not None else {},
            "device_id": target_device,
            "session_id": self.ensure_session(str(target_device)),
            "command_id": command_id or canonical.ulid(),
            "deadline_ms": kwargs.pop("deadline_ms", 30000),
        }
        resource = kwargs.pop("resource", None)
        bound = self.bindings_of(str(target_device), capability)
        if resource is None and len(bound) == 1:
            resource = bound[0].resource
        if resource:
            # Plan 3.6 step 3: bindings are keyed by (capability_id, resource).
            invocation["resource"] = resource
        invocation.update(kwargs)
        if bound and not all(_trusted_read(binding) for binding in bound) and not self.may_actuate(str(target_device)) \
                and not self.bridge_blocks(str(target_device)):
            # CON-031 send guard: nothing between the endpoint's checks and the device can stop this command.
            with self.run_log.lock:
                self.run_log.withheld.append((str(self.current_test or "?"), str(target_device), capability))
            return None, _Withheld(
                f"the suite withheld {capability} from {target_device}: hardware/hybrid device without "
                "--allow-actuation and no in-process harness to block it at the bridge (CON-031)"
            )
        try:
            try:
                receipt = self.client.invoke(capability, **invocation)
            except TypeError as exc:
                if "resource" not in invocation or "resource" not in str(exc):
                    raise
                invocation.pop("resource")  # a duck-typed client without the resource parameter
                receipt = self.client.invoke(capability, **invocation)
        except BaseException as exc:  # noqa: BLE001 - protocol/session errors are verdicts here
            return None, exc
        receipt = _as_dict(receipt)
        self.last_receipt = receipt
        operation_id = receipt.get("operation_id")
        if isinstance(operation_id, str) and operation_id:
            self.operation_sessions[operation_id] = str(invocation.get("session_id"))
        self._note_dispatch(str(target_device), capability, bound, receipt)
        return receipt, None

    def _note_dispatch(self, device_id: str, capability_id: str, bound: Sequence[Binding],
                       receipt: Mapping[str, Any]) -> None:
        """Record a command that reached a hardware/hybrid device without the operator's opt-in (CON-031)."""

        if self.may_actuate(device_id):
            return
        status = receipt.get("status")
        if status in _NOT_DISPATCHED or receipt.get("replayed") is True:
            return
        if bound and all(_trusted_read(binding) for binding in bound):
            return
        with self.run_log.lock:
            self.run_log.hardware_dispatches.append(
                (str(self.current_test or "?"), device_id, capability_id, str(status)))

    def invoke_ok(self, capability_id: str | None = None, payload: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        receipt, error = self.invoke(capability_id, payload, **kwargs)
        if error is not None:
            raise error
        if not _is_success(receipt):
            raise AssertionError(f"command was not accepted: {receipt}")
        return receipt or {}

    def synthesize(self, capability: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """A valid input for ``capability`` (fixture, class example, envelope-aware synthesis)."""

        capability = capability or self.primary_capability
        for binding in self.bindings:
            if binding.capability is capability or binding.capability == dict(capability):
                try:
                    return valid_input(binding, self.fixtures)[0]
                except Unsynthesizable:
                    break
        return _synthesize(capability.get("input_schema") or {}) or {}

    def probe_input(self) -> tuple[dict[str, Any], str]:
        """``(payload, source)`` for the probe; raises :class:`Unsynthesizable`."""

        if self.probe is None:
            raise Unsynthesizable("no probe capability")
        if self._probe_input is None:
            self._probe_input = valid_input(self.probe, self.fixtures)
        payload, source = self._probe_input
        return copy.deepcopy(payload), source

    @property
    def read_probes(self) -> list[tuple[Binding, dict[str, Any], str]]:
        """``(binding, input, source)`` of every read command OP-001 sends (plan 3.7: reads keep the revision).

        Every read-verb binding the runtime treats as a read that needs no
        permit and has a valid input: a catalogued class whose verb is
        ``read`` (the verb comes from the catalogue, never from the binding),
        and an extension (``x-cap.*`` or an uncatalogued id) that declares
        ``verb: read``.  The probe's device first, then catalogued before
        extension, non-deprecated before deprecated, then by capability id.
        Deprecated reads (``cap.world.state.v1``, the TESTS-04 case) are held
        to the rule like every other read.  An extension's verb is the
        driver's own claim, so its reads are sent only to a device the suite
        may actuate (not hardware/hybrid without ``allow_actuation``, CON-031);
        catalogued reads have no effect, so sending all of them is cheap and safe.
        A read whose input the suite cannot build is listed in
        :attr:`unsent_reads` (OP-001 names it and asks for a fixture).
        """

        if self._read_probes is None:
            probe_device = self.probe.device_id if self.probe is not None else None
            candidates = [binding for binding in self.bindings
                          if (_trusted_read(binding) or (binding.extension and self.may_actuate(binding.device_id)
                                                         and "read" in (binding.verb, binding.declared_verb)))
                          and binding.manifest.get("mode") != "replay"
                          and not binding.requires_permit and not binding.capability_id.startswith(TEST_HOOK_PREFIX)]
            candidates.sort(key=lambda item: (0 if item.device_id == probe_device else 1, 1 if item.extension else 0,
                                              1 if item.deprecated else 0, item.capability_id, item.device_id,
                                              item.resource or ""))
            found: list[tuple[Binding, dict[str, Any], str]] = []
            self.unsent_reads = []
            for binding in candidates:
                try:
                    payload, source = served_input(binding, self.fixtures)
                except Unsynthesizable as exc:
                    self.unsent_reads.append((binding, str(exc)))
                    continue
                found.append((binding, payload, source))
            self._read_probes = found
        return list(self._read_probes)

    @property
    def read_probe(self) -> tuple[Binding, dict[str, Any], str] | None:
        """The first of :attr:`read_probes` (the read a read-only endpoint must complete), or None."""

        reads = self.read_probes
        return reads[0] if reads else None

    def probe_alternate(self, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        if self.probe is None:
            return None
        return alternate_input(self.probe, payload, self.fixtures)

    # -- safety / evidence / snapshots ------------------------------------
    def safety_status(self, device_id: str | None = None) -> dict[str, Any]:
        target = device_id or self.primary_device["device_id"]
        return _as_dict(self.client.safety_status(device_id=target))

    def _guard(self, what: str, device_id: str) -> None:
        """CON-031 send guard for e-stop, reset and restore on hardware without ``allow_actuation``."""

        if self.may_actuate(device_id):
            return
        with self.run_log.lock:
            self.run_log.withheld.append((str(self.current_test or "?"), str(device_id), what))
        raise _Withheld(f"the suite never sends {what} to hardware/hybrid device {device_id} without "
                        "--allow-actuation (CON-031)")

    def estop(self, reason: str = "conformance e-stop test", device_id: str | None = None) -> Any:
        target = device_id or self.primary_device["device_id"]
        self._guard("mhs.safety.estop", str(target))
        kind = self.estop_kind(target)
        with self.run_log.lock:
            self.run_log.estop_targets.append((str(target), kind))
            if _terminal_statement(self.device_for(str(target))) is not None:
                # Recorded before the request: whatever it answers, this endpoint
                # may now hold a stop no reset undoes (CORE-087).
                self.terminated.add(str(target))
                self.run_log.terminal_stops.append((str(self.current_test or "?"), str(target)))
        return self.client.estop(reason, device_id=target, session_id=self.ensure_session(str(target)))

    def reset(self, device_id: str | None = None) -> Any:
        target = device_id or self.primary_device["device_id"]
        kind = self.estop_kind(target)
        if kind not in ("software", "both"):
            # CON-032: a hardware-only e-stop is exercised (and released) by a human.
            raise RuntimeError(f"the suite never resets the {kind!r} e-stop of {target}")
        self._guard("mhs.safety.reset", str(target))
        with self.run_log.lock:
            self.run_log.reset_targets.append((str(target), kind))
        return self.client.reset(device_id=target, session_id=self.ensure_session(str(target)))

    def permit(
        self,
        capability_id: str,
        input: Mapping[str, Any] | None = None,
        *,
        input_digest: str | None = None,
        device_id: str | None = None,
        resource: str | None = None,
        ttl_s: int = 60,
        approvals: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        resolved_device = device_id or str(self.primary_device.get("device_id"))
        mode = str(self.device_for(resolved_device).get("mode"))
        records = list(approvals or self.options.approvals or [])
        if not records:
            if mode in _static.HARDWARE_MODES:
                raise _NoApprovals(
                    f"{resolved_device} is {mode}: the suite never invents permits on hardware (CON-031); "
                    "supply operator approvals (--approvals)"
                )
            records = [{"principal": SUITE_PRINCIPAL["id"], "method": "policy_rule",
                        "approved_at": canonical.now_rfc3339()}]
        with self.run_log.lock:
            self.run_log.permits.append((resolved_device, "operator" if approvals or self.options.approvals else "suite"))
        # SAFE-002: a permit is bound to the session that will present it.
        bound_session = self.ensure_session(resolved_device)
        if input is not None:
            return _as_dict(
                self.client.permit(
                    capability_id,
                    input,
                    ttl_s=ttl_s,
                    approvals=records,
                    device_id=resolved_device,
                    resource=resource,
                    session_id=bound_session,
                )
            )
        return _as_dict(
            self.client.permit(
                capability_id,
                input_digest=input_digest,
                ttl_s=ttl_s,
                approvals=records,
                device_id=resolved_device,
                resource=resource,
                session_id=bound_session,
            )
        )

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        return _as_dict(self.client.snapshot(device_id=device_id or self.primary_device["device_id"]))

    def restore(self, snapshot: Mapping[str, Any], device_id: str | None = None) -> Any:
        target = device_id or self.primary_device["device_id"]
        self._guard("mhs.restore", str(target))
        return self.client.restore(dict(snapshot), device_id=target)

    def export_evidence(self) -> dict[str, Any]:
        result = _as_dict(self.client.export_evidence())
        bundle = result.get("bundle")
        if isinstance(bundle, Mapping):
            return dict(bundle)
        return result

    def wait_operation(self, operation_id: str, timeout_s: float = 5.0) -> dict[str, Any]:
        """Poll ``operations.get`` until the operation is terminal (or the timeout)."""

        deadline = time.monotonic() + timeout_s
        last: dict[str, Any] = {}
        getter = getattr(self.client, "get_operation", None)
        while callable(getter):
            try:
                last = _as_dict(getter(operation_id, session_id=self.operation_sessions.get(
                    str(operation_id)) or self.ensure_session()))
            except TypeError:
                last = _as_dict(getter(operation_id))
            except BaseException:  # noqa: BLE001 - an unknown operation ends the wait
                return last
            if last.get("status") not in ("accepted", "running") or time.monotonic() >= deadline:
                return last
            time.sleep(0.01)
        return last


def _estop_declaration(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    estop = (manifest.get("safety") or {}).get("estop") if isinstance(manifest, Mapping) else None
    return estop if isinstance(estop, Mapping) else {}


def _terminal_statement(manifest: Mapping[str, Any]) -> str | None:
    """The declared terminal e-stop statement of a device manifest (``safety.estop.terminal``, CORE-087)."""
    estop = _estop_declaration(manifest)
    if "terminal" not in estop:
        return None
    statement = estop.get("terminal")
    return statement if isinstance(statement, str) and statement.strip() else "terminal e-stop declared"


def _reenable_id(manifest: Mapping[str, Any]) -> str | None:
    """The declared re-enable capability of a device manifest (``safety.estop.reenable``, CORE-086)."""
    value = _estop_declaration(manifest).get("reenable")
    return value if isinstance(value, str) and value else None


def _trusted_read(binding: Binding) -> bool:
    """A catalogued read class: the only read the hardware gate trusts (CON-031).

    An extension's (or an uncatalogued id's) declared verb is the driver's own
    claim; like the runtime's latch and arming, the gate treats it as actuating.
    """

    return binding.verb == "read" and binding.class_entry is not None


def _session_id(session: Any) -> str:
    if isinstance(session, Mapping):
        value = session.get("session_id")
        if isinstance(value, str):
            return value
    return str(session)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _pattern_matches(pattern: str, capability_id: str) -> bool:
    import fnmatch

    if pattern.endswith(".*"):
        return capability_id.startswith(pattern[:-1])
    return fnmatch.fnmatchcase(capability_id, pattern)


def _probe_required(ctx: SuiteContext) -> bool:
    return ctx.probe is not None


def _op001_required(ctx: SuiteContext) -> bool:
    """OP-001 is required with a probe, on gated hardware that binds actuating capabilities, and for a read.

    The second case keeps the CL1 cap of CON-031 when every actuating binding is
    permit-gated (no probe): the gate skips OP-001 and the skip is required.  A
    read-only endpoint is held to the read revision rule (plan 3.7) when the
    read can be sent, i.e. unless a hardware device without ``allow_actuation``
    gates every command test of the run.
    """

    return ctx.probe is not None or ctx.actuation_capped or (ctx.read_probe is not None and ctx.actuation_allowed)


def _no_probe() -> TestOutcome:
    return TestOutcome.skipped(
        "no write/invoke capability with inputs to probe (read-only device, or every actuating binding is "
        "permit-gated or a safe-state action); not applicable (CON-026a)"
    )


def _probe_setup(ctx: SuiteContext) -> tuple[Binding, dict[str, Any], str] | TestOutcome:
    if ctx.probe is None:
        return _no_probe()
    try:
        payload, source = ctx.probe_input()
    except Unsynthesizable as exc:
        return TestOutcome.skipped(f"no valid input for probe {ctx.probe.capability_id}: {exc}")
    return ctx.probe, payload, source


# ---------------------------------------------------------------------------
# CL1 -- observable
# ---------------------------------------------------------------------------


def proto_001(ctx: SuiteContext) -> TestOutcome:
    hello = ctx.hello
    if not isinstance(hello, Mapping) or not hello:
        return TestOutcome.failed("mhs.hello returned no result object")
    problems = []
    version = hello.get("mhs_version")
    if not isinstance(version, str) or not version.startswith("1."):
        problems.append(f"mhs_version={version!r} is not 1.x")
    if not isinstance(hello.get("endpoint_id"), str) or not hello.get("endpoint_id"):
        problems.append("endpoint_id is missing")
    devices = hello.get("devices")
    if not isinstance(devices, list) or not devices:
        problems.append("devices[] summary is missing or empty")
    if problems:
        return TestOutcome.failed("; ".join(problems))
    return TestOutcome.passed(
        f"hello ok: {version}, {len(devices)} device(s)", request_digest=canonical.digest(hello)
    )


def proto_002(ctx: SuiteContext) -> TestOutcome:
    checks = []
    for manifest in ctx.devices:
        missing = [
            field_name
            for field_name in ("device_id", "mode", "resources", "capabilities", "safety")
            if not manifest.get(field_name)
        ]
        if missing:
            checks.append(f"{manifest.get('device_id')}: missing {missing}")
            continue
        inspect = _as_dict(ctx.client.inspect(manifest["device_id"]))
        if inspect.get("device_id") != manifest["device_id"]:
            checks.append(f"inspect({manifest['device_id']}) returned a different device")
        elif not inspect.get("capabilities"):
            checks.append(f"inspect({manifest['device_id']}) has no capabilities")
    if checks:
        return TestOutcome.failed("; ".join(checks[:5]))
    return TestOutcome.passed(f"devices.list/get ok for {len(ctx.devices)} device(s)")


def proto_003(ctx: SuiteContext) -> TestOutcome:
    try:
        from mhs.schema import SchemaStore

        store = SchemaStore()
    except Exception as exc:  # noqa: BLE001 - validator absent: cannot verify manifests
        return TestOutcome.skipped(f"mhs.schema validator unavailable: {exc}")
    errors: list[str] = []
    for manifest in ctx.devices:
        found = store.validate(manifest, "device.schema.json")
        errors.extend(f"{manifest.get('device_id')}: {item}" for item in found[:5])
    if errors:
        return TestOutcome.failed("; ".join(errors[:5]))
    return TestOutcome.passed(f"{len(ctx.devices)} device manifest(s) validate against device.schema.json")


def proto_004(ctx: SuiteContext) -> TestOutcome:
    resource_id = ctx.primary_resource
    device_id = ctx.primary_device["device_id"]
    result = ctx.read(resource_id, device_id)
    revision = result.get("revision")
    state_hash = result.get("state_hash")
    if not isinstance(revision, int):
        return TestOutcome.failed("resource.read result has no integer revision")
    if result.get("state") is None:
        return TestOutcome.failed("resource.read result has no state document")
    if not _digest_ok(state_hash):
        return TestOutcome.failed(f"state_hash={state_hash!r} is not a sha256 digest")
    meta = ctx.resource_meta(device_id, resource_id)
    exclusions = [str(item) for item in meta.get("hash_exclusions") or []]
    resource_count = len(ctx.device_for(device_id).get("resources") or [])
    verdict = _verify_state_hash(
        result, resource_id, exclusions, device_id=device_id, resource_count=resource_count
    )
    if verdict == "spec":
        return TestOutcome.passed(f"read {resource_id}@r{revision} hash verifies", response_digest=state_hash)
    if verdict == "server":
        return TestOutcome.warned(
            "state_hash matches the reference server's {device_id,state} wrapper, not the "
            "MHS-000 section 3.3 canonical resource-state digest",
            response_digest=state_hash,
        )
    return TestOutcome.failed("state_hash does not equal canonical JCS digest of the state document")


def proto_005(ctx: SuiteContext) -> TestOutcome:
    resource_id = ctx.primary_resource
    device_id = ctx.primary_device["device_id"]
    first = ctx.read(resource_id, device_id)
    second = ctx.read(resource_id, device_id)
    if first.get("revision") != second.get("revision"):
        return TestOutcome.failed("two reads without a mutation returned different revisions")
    if first.get("state_hash") != second.get("state_hash"):
        return TestOutcome.failed("two reads without a mutation returned different state hashes")
    return TestOutcome.passed(f"read is stable at revision {first.get('revision')}")


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------


def sess_001(ctx: SuiteContext) -> TestOutcome:
    session = ctx.ensure_session()
    if not isinstance(session, str) or not session.startswith("mhs_s_"):
        return TestOutcome.failed(f"session id {session!r} does not match ^mhs_s_")
    raw = ctx.open_session(
        device_ids=[manifest["device_id"] for manifest in ctx.devices],
        capabilities=None,
        mode=None,
        ttl_s=120,
    )
    raw_dict = _as_dict(raw)
    ctx.extra_sessions.append(_session_id(raw_dict))
    missing = [
        field_name
        for field_name in ("session_id", "granted", "mode", "expires_at")
        if field_name not in raw_dict
    ]
    if missing:
        return TestOutcome.failed(f"session.open result is missing {missing}")
    if raw_dict.get("mode") != ctx.primary_device.get("mode"):
        return TestOutcome.failed(
            f"session mode {raw_dict.get('mode')!r} does not match device mode {ctx.primary_device.get('mode')!r}"
        )
    if not raw_dict.get("granted"):
        return TestOutcome.failed("session.open granted no capabilities")
    return TestOutcome.passed(f"session opened with {len(raw_dict.get('granted') or [])} granted capability(s)")


def sess_002(ctx: SuiteContext) -> TestOutcome:
    device_mode = str(ctx.primary_device.get("mode"))
    wrong = "hardware" if device_mode != "hardware" else "simulated"
    try:
        session = ctx.open_session(
            device_ids=[ctx.primary_device["device_id"]], capabilities=None, mode=wrong, ttl_s=60
        )
    except BaseException as exc:  # noqa: BLE001
        code = _error_code(exc)
        if _code_matches(code, ("MHS.SESSION.MODE_MISMATCH",)):
            return TestOutcome.passed(f"mode {wrong!r} rejected with {code}", mhs_code=code)
        return TestOutcome.failed(f"mode mismatch raised unexpected error {code or exc!r}")
    session_id = _session_id(_as_dict(session))
    if session_id:
        ctx.extra_sessions.append(session_id)
    return TestOutcome.failed(
        f"session.open accepted mode {wrong!r} on a {device_mode!r} device instead of MHS.SESSION.MODE_MISMATCH"
    )


def sess_003(ctx: SuiteContext) -> TestOutcome:
    """Session TTL/heartbeat: optional because the high-level client may not expose it."""

    heartbeat = getattr(ctx.client, "heartbeat", None)
    if not callable(heartbeat):
        return TestOutcome.skipped("client API does not expose session heartbeat/TTL inspection")
    session_id = ctx.ensure_session()
    try:
        result = _as_dict(heartbeat(session_id))
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"session heartbeat failed: {_error_code(exc) or exc!r}")
    if "expires_at" not in result:
        return TestOutcome.failed("session heartbeat result has no expires_at")
    return TestOutcome.passed("session heartbeat refreshed the lease")


# ---------------------------------------------------------------------------
# CL2 -- actuating
# ---------------------------------------------------------------------------


def _device_reads(ctx: SuiteContext, device_id: str) -> dict[str, dict[str, Any]]:
    """``resource.read`` of every resource of ``device_id`` (the revision is per device, the hash per resource)."""

    out: dict[str, dict[str, Any]] = {}
    for item in ctx.device_for(device_id).get("resources") or []:
        if isinstance(item, Mapping) and item.get("resource_id") is not None:
            resource_id = str(item["resource_id"])
            out[resource_id] = ctx.read(resource_id, device_id)
    return out


def _revision_of(result: Mapping[str, Any] | None, default: int = 0) -> int:
    revision = (result or {}).get("revision")
    return revision if isinstance(revision, int) and not isinstance(revision, bool) else default


def _read_revision_check(ctx: SuiteContext, binding: Binding, payload: Mapping[str, Any], source: str, *,
                         standalone: bool) -> TestOutcome:
    """Plan 3.7 / TESTS-04: a read-verb command never advances the revision, whatever its outcome."""

    resource_id = binding.resource or ctx.resource_for(binding.device_id)
    before = ctx.read(resource_id, binding.device_id)
    revision_before = _revision_of(before)
    receipt, error = ctx.invoke(binding.capability_id, payload, device_id=binding.device_id,
                                resource=binding.resource, command_id=canonical.ulid())
    after = ctx.read(resource_id, binding.device_id)
    revision_after = _revision_of(after, revision_before)
    receipt_before, receipt_after = _receipt_revisions(receipt)
    label = f"read-verb {binding.capability_id} ({source} input)"
    moved = None
    if revision_after != revision_before:
        moved = f"r{revision_before}->r{revision_after}"
    elif isinstance(receipt_before, int) and isinstance(receipt_after, int) and receipt_after != receipt_before:
        moved = f"r{receipt_before}->r{receipt_after} in its receipt"
    if moved:
        return TestOutcome.failed(
            f"{label} advanced the revision {moved}: a read never advances it (plan 3.7, TESTS-04), otherwise every "
            "measurement invalidates an agent's expected_revision"
        )
    if error is not None or _receipt_status(receipt) != "completed":
        what = f"{label} did not complete ({_error_code(error) or _receipt_status(receipt)!r} {_receipt_error(receipt)})"
        if standalone:
            return TestOutcome.failed(what)
        return TestOutcome.passed(f"{what}; the revision stayed at r{revision_before}")
    return TestOutcome.passed(f"{label} completed and kept the revision at r{revision_before}",
                              request_digest=receipt.get("input_digest") if isinstance(receipt, Mapping) else None)


def _reads_revision_check(ctx: SuiteContext, *, standalone: bool) -> TestOutcome | None:
    """Plan 3.7 for every read binding (:attr:`SuiteContext.read_probes`); None when there is none.

    Every read must keep the revision, whatever its outcome; with
    ``standalone`` (a read-only endpoint) the first read must also complete.
    """

    reads = ctx.read_probes
    if not reads:
        return None
    outcomes: list[TestOutcome] = []
    for position, read in enumerate(reads):
        checked = _read_revision_check(ctx, *read, standalone=standalone and position == 0)
        if checked.status != "pass":
            return checked
        outcomes.append(checked)
    first, others = outcomes[0], sorted({binding.capability_id for binding, _payload, _source in reads[1:]})
    if len(outcomes) == 1:
        return first
    return TestOutcome(first.status, f"{first.detail}; {len(outcomes) - 1} other read-verb command(s) kept it too: "
                       + ", ".join(others[:8]), request_digest=first.request_digest)


def _unsent_reads_note(ctx: SuiteContext) -> str | None:
    """OP-001's note on the read-verb commands it could not send (no buildable input), or None."""

    ctx.read_probes  # noqa: B018 - fills ctx.unsent_reads
    if not ctx.unsent_reads:
        return None
    names = [f"{binding.capability_id} on {binding.device_id} ({reason[:120]})" for binding, reason in ctx.unsent_reads]
    return (f"{len(names)} read-verb command(s) not sent, so not held to the read revision rule: "
            + "; ".join(names[:4]) + ("; ..." if len(names) > 4 else "")
            + "; supply a fixture (valid) for them")


def _with_unsent_reads(ctx: SuiteContext, outcome: TestOutcome) -> TestOutcome:
    note = _unsent_reads_note(ctx)
    if note is None:
        return outcome
    outcome.note = f"{outcome.note}; {note}" if outcome.note else note
    return outcome


def cap_001(ctx: SuiteContext) -> TestOutcome:
    """OP-001 (see :func:`_cap_001`); the reads it could not send are named in its note (RESIDUAL-B)."""

    return _with_unsent_reads(ctx, _cap_001(ctx))


def _cap_001(ctx: SuiteContext) -> TestOutcome:
    """OP-001: a valid command completes, and the revision follows plan 3.7.

    The probe (a write/invoke binding) must complete; the device revision must
    advance when any resource state changed and must stay when none did.
    Every read-verb command (:attr:`SuiteContext.read_probes`: catalogued
    reads and extensions that declare ``verb: read``) must never advance the
    revision.  A read-only endpoint is checked with its reads alone (the
    first must complete).
    """

    if ctx.probe is None:
        checked = _reads_revision_check(ctx, standalone=True)
        return _no_probe() if checked is None else checked
    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, source = setup
    capability_id = probe.capability_id
    before_all = _device_reads(ctx, probe.device_id)
    before = before_all.get(str(probe.resource)) or ctx.read(probe.resource, probe.device_id)
    revision_before = _revision_of(before)
    receipt, error = ctx.invoke(capability_id, payload, device_id=probe.device_id,
                                resource=probe.resource, command_id=canonical.ulid())
    if error is not None:
        return TestOutcome.failed(f"{capability_id} raised {_error_code(error) or error!r}: {error}")
    if not _is_success(receipt):
        return TestOutcome.failed(
            f"{capability_id} ({source} input {payload}) receipt status={_receipt_status(receipt)!r} "
            f"error={_receipt_error(receipt)}"
        )
    problems = []
    if not _digest_ok(receipt.get("input_digest")):
        problems.append("receipt.input_digest is not a digest")
    revision_after = receipt.get("state_revision_after")
    if not isinstance(revision_after, int) or revision_after < revision_before:
        problems.append(f"state_revision_after={revision_after!r} went backwards from {revision_before}")
    state_hash_after = receipt.get("state_hash_after")
    if state_hash_after is not None and not _digest_ok(state_hash_after):
        problems.append("receipt.state_hash_after is not a digest")
    after_all = _device_reads(ctx, probe.device_id)
    after = after_all.get(str(probe.resource)) or ctx.read(probe.resource, probe.device_id)
    if state_hash_after and after.get("state_hash") != state_hash_after:
        problems.append("receipt.state_hash_after does not match the next read")
    after_revision = _revision_of(after, revision_before)
    changed = sorted(resource_id for resource_id, result in after_all.items()
                     if result.get("state_hash") != (before_all.get(resource_id) or {}).get("state_hash"))
    if changed and after_revision <= revision_before:
        problems.append(f"the state of {', '.join(changed)} changed but the revision did not advance")
    if not changed and after_revision > revision_before:
        problems.append(f"the revision advanced r{revision_before}->r{after_revision} although no resource state "
                        "changed (plan 3.7: only a state change advances it)")
    if problems:
        return TestOutcome.failed("; ".join(problems))
    moved = "advanced" if after_revision > revision_before else "unchanged (no state change)"
    detail = (f"{capability_id} ({probe.verb}, {source} input) completed r{revision_before}->r{revision_after}; "
              f"revision {moved}")
    checked = _reads_revision_check(ctx, standalone=False)
    if checked is None:
        detail += "; no read-verb binding to check the read revision rule"
    elif checked.status != "pass":
        return TestOutcome(checked.status, f"{detail}; but {checked.detail}", mhs_code=checked.mhs_code)
    else:
        detail += f"; {checked.detail}"
    return TestOutcome.passed(
        detail,
        request_digest=receipt.get("input_digest"),
        response_digest=receipt.get("receipt_id") and canonical.digest(receipt) or None,
    )


def _class_required_outputs(probe: Binding) -> list[str]:
    """Output fields the class requires; a binding inherits or narrows them, never waives them (CAP-016)."""

    entry = probe.class_entry or {}
    class_schema = entry.get("output_schema")
    if not isinstance(class_schema, Mapping):
        return []
    return [str(item) for item in class_schema.get("required") or []]


def _skeleton(schema: Any) -> bool:
    try:
        from mhs.catalog import is_skeleton
    except Exception:  # noqa: BLE001 - the catalogue is optional for a standalone suite
        return not (isinstance(schema, Mapping) and schema.get("properties"))
    return bool(is_skeleton(schema))


def tcap_001(ctx: SuiteContext) -> TestOutcome:
    """A completed command's output validates against its output contract (MHS-003 §3, OUTPUT_INVALID).

    Required in this suite version: the output validates against the binding
    ``output_schema``, and the output is not *empty* where the class requires
    output fields (a null driver; a skeleton binding ``output_schema`` inherits
    the class output, and no binding may waive a required class field).  Other
    mismatches with the class output are advisory until the reference
    fixtures' class realignment.
    """

    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id, resource=probe.resource)
    if error is not None or not _is_success(receipt):
        return TestOutcome.failed(
            f"{probe.capability_id} did not complete: {_error_code(error) or _receipt_status(receipt)!r} "
            f"{_receipt_error(receipt)}"
        )
    output = (receipt or {}).get("output")
    schema = probe.capability.get("output_schema")
    schema = dict(schema) if isinstance(schema, Mapping) else {"type": "object"}
    try:
        from mhs.schema import validate as schema_validate

        errors = schema_validate(output, schema)
    except Exception as exc:  # noqa: BLE001
        return TestOutcome.skipped(f"output schema could not be evaluated: {exc}")
    if errors:
        return TestOutcome.failed(
            f"{probe.capability_id} output {output!r} does not validate against its output_schema: "
            + "; ".join(str(item) for item in errors[:3]),
            mhs_code="MHS.CAPABILITY.OUTPUT_INVALID",
        )
    required_fields = _class_required_outputs(probe)
    if required_fields and (output is None or output == {}):
        how = ("its binding output_schema is a skeleton, so the class output applies"
               if _skeleton(probe.capability.get("output_schema")) else "a binding cannot waive class output fields")
        return TestOutcome.failed(
            f"{probe.capability_id} returned no output ({output!r}) although the class requires "
            f"{', '.join(required_fields)} ({how}): the driver does not report what it did",
            mhs_code="MHS.CAPABILITY.OUTPUT_INVALID",
        )
    note = None
    entry = probe.class_entry or {}
    class_schema = entry.get("output_schema")
    if isinstance(class_schema, Mapping):
        try:
            class_errors = schema_validate(output, dict(class_schema))
        except Exception:  # noqa: BLE001
            class_errors = []
        if class_errors:
            note = ("advisory (CAP-016, required in a later suite version): output does not match the class "
                    "output_schema: " + "; ".join(str(item) for item in class_errors[:2]))[:1000]
    return TestOutcome.passed(f"{probe.capability_id} output validates against the binding output_schema",
                              note=note)


def _effect_check_required(ctx: SuiteContext) -> bool:
    """TCAP-003 is required for a write probe and for an invoke probe without a class output contract.

    An invoke probe whose class requires output fields is covered by TCAP-001
    (an empty output fails there); for an extension, or a class without
    required outputs, nothing else shows that the command did anything.
    """

    probe = ctx.probe
    if probe is None:
        return False
    return probe.verb == "write" or not _class_required_outputs(probe)


def _same_output(first: Any, second: Any) -> bool:
    try:
        return canonical.digest(first) == canonical.digest(second)
    except Exception:  # noqa: BLE001 - a non-canonical output compares by equality
        return first == second


def _invoke_effect(ctx: SuiteContext, probe: Binding, payload: dict[str, Any]) -> TestOutcome:
    """An invoke probe has an observable effect: the resource state or the output depends on the input."""

    alternate = ctx.probe_alternate(payload)
    hashes = [ctx.read(probe.resource, probe.device_id).get("state_hash")]
    outputs: list[Any] = []
    values = [payload] + ([alternate] if alternate is not None else [])
    for value in values:
        receipt, error = ctx.invoke(probe.capability_id, value, device_id=probe.device_id, resource=probe.resource)
        if error is not None or not _is_success(receipt):
            return TestOutcome.failed(
                f"invoke {value} did not complete: {_error_code(error) or _receipt_status(receipt)!r} "
                f"{_receipt_error(receipt)}"
            )
        outputs.append((receipt or {}).get("output"))
        hashes.append(ctx.read(probe.resource, probe.device_id).get("state_hash"))
    if probe.extension or probe.class_entry is None:
        contract = "it is an extension, so no class output contract applies"
    elif not _class_required_outputs(probe):
        contract = "its class requires no output field"
    else:
        contract = "only the class output fields (TCAP-001) report it"
    if len(set(hashes)) > 1:
        return TestOutcome.passed(f"invoke {probe.capability_id} changed resource {probe.resource!r} state")
    empty = all(output is None or output == {} or output == [] for output in outputs)
    if alternate is not None and not empty and not _same_output(outputs[0], outputs[1]):
        return TestOutcome.passed(f"invoke {probe.capability_id} outputs depend on the input "
                                  f"({payload} vs {alternate}); resource state unchanged")
    if alternate is None and not empty:
        return TestOutcome.passed(
            f"invoke {probe.capability_id} returned an output; resource state unchanged",
            note="only one valid input exists, so the effect is shown by a non-empty output only; supply an "
                 "'alternate' fixture for a stronger check",
        )
    shown = "no output" if empty else f"the identical output {outputs[0]!r}"
    tried = f"{payload} and {alternate}" if alternate is not None else f"{payload}"
    return TestOutcome.failed(
        f"no observable effect: invoke {probe.capability_id} with {tried} left resource {probe.resource!r} "
        f"unchanged ({hashes[0]}) and returned {shown}; {contract}, so nothing shows that the command reached "
        "the device (report what it did in the output or expose it in the resource state)"
    )


def tcap_003(ctx: SuiteContext) -> TestOutcome:
    """A probe command has an observable effect (CAP-013: writes are mutations).

    A write probe: two different writes leave different resource states.  An
    invoke probe: the resource state changes, or the outputs of two distinct
    inputs differ (required when the probe has no class output contract,
    advisory otherwise).
    """

    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    if probe.verb != "write":
        return _invoke_effect(ctx, probe, payload)
    alternate = ctx.probe_alternate(payload)
    if alternate is None:
        return TestOutcome.skipped(f"no distinct valid second input for {probe.capability_id}; supply a fixture")
    hashes = []
    for value in (payload, alternate):
        receipt, error = ctx.invoke(probe.capability_id, value, device_id=probe.device_id, resource=probe.resource)
        if error is not None or not _is_success(receipt):
            return TestOutcome.failed(
                f"write {value} did not complete: {_error_code(error) or _receipt_status(receipt)!r} "
                f"{_receipt_error(receipt)}"
            )
        hashes.append(ctx.read(probe.resource, probe.device_id).get("state_hash"))
    if hashes[0] == hashes[1]:
        return TestOutcome.failed(
            f"writes {payload} and {alternate} left resource {probe.resource!r} in the same state ({hashes[0]}): "
            "the write never reaches the device state"
        )
    return TestOutcome.passed(f"writes {payload} and {alternate} produced different resource states")


def cap_002(ctx: SuiteContext) -> TestOutcome:
    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    capability_id = probe.capability_id
    command_id = canonical.ulid()
    first, error = ctx.invoke(capability_id, payload, device_id=probe.device_id,
                              resource=probe.resource, command_id=command_id)
    if error is not None or not _is_success(first):
        return TestOutcome.failed(f"first invoke failed: {_error_code(error) or _receipt_status(first)!r}")
    revision = ctx.current_revision(probe.device_id, probe.resource)
    second, error = ctx.invoke(capability_id, payload, device_id=probe.device_id,
                               resource=probe.resource, command_id=command_id)
    if error is not None:
        return TestOutcome.failed(f"replayed invoke raised {_error_code(error) or error!r}")
    if not _is_success(second):
        return TestOutcome.failed(f"replayed command was not accepted: {_receipt_error(second)}")
    if second.get("replayed") is not True:
        return TestOutcome.failed("replayed command receipt does not carry replayed=true")
    if second.get("receipt_id") != first.get("receipt_id"):
        return TestOutcome.failed("replayed command returned a different receipt_id")
    if ctx.current_revision(probe.device_id, probe.resource) != revision:
        return TestOutcome.failed("replayed command advanced the device revision")
    return TestOutcome.passed("duplicate command_id with identical input replayed without a second effect")


def cap_003(ctx: SuiteContext) -> TestOutcome:
    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    capability_id = probe.capability_id
    command_id = canonical.ulid()
    first, error = ctx.invoke(capability_id, payload, device_id=probe.device_id,
                              resource=probe.resource, command_id=command_id)
    if error is not None or not _is_success(first):
        return TestOutcome.failed(f"first invoke failed: {_error_code(error) or _receipt_status(first)!r}")
    revision = ctx.current_revision(probe.device_id, probe.resource)
    different = ctx.probe_alternate(payload)
    note = None
    if different is None:
        # The command_id lookup precedes input validation (plan 3.6 step 4), so a
        # schema-different input still has to be refused as a reuse.
        different = dict(payload)
        different["x-mhs-conformance-alternate"] = 1
        note = "no distinct valid input exists; a schema-different input was used (idempotency precedes validation)"
    second, error = ctx.invoke(capability_id, different, device_id=probe.device_id,
                               resource=probe.resource, command_id=command_id)
    code = _receipt_code(second, error)
    if _code_matches(code, ("MHS.CONFLICT.COMMAND_ID_REUSE",)):
        if ctx.current_revision(probe.device_id, probe.resource) != revision:
            return TestOutcome.failed("command_id reuse rejection still advanced the revision")
        return TestOutcome.passed(f"command_id reuse with different input rejected with {code}", mhs_code=code,
                                  note=note)
    return TestOutcome.failed(
        f"reusing command_id with a different input returned {code or 'success'}, expected "
        "MHS.CONFLICT.COMMAND_ID_REUSE" + (f" ({note})" if note else "")
    )


def cap_004(ctx: SuiteContext) -> TestOutcome:
    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    revision = ctx.current_revision(probe.device_id, probe.resource)
    mark = ctx.harness.mark() if ctx.harness is not None else 0
    receipt, error = ctx.invoke(
        probe.capability_id, payload, device_id=probe.device_id, resource=probe.resource, command_id=canonical.ulid(),
        expected_revision=revision + 7,
    )
    code = _receipt_code(receipt, error)
    if _code_matches(code, ("MHS.CONFLICT.REVISION",)):
        error_obj = _receipt_error(receipt)
        if not isinstance(error_obj.get("current_revision"), int) and _error_code(error) is None:
            return TestOutcome.warned(f"revision conflict rejected with {code} but no current_revision hint")
        if ctx.current_revision(probe.device_id, probe.resource) != revision:
            return TestOutcome.failed("revision conflict rejection advanced the revision")
        return TestOutcome.passed(f"stale expected_revision rejected with {code}", mhs_code=code)
    if _not_armed(ctx, probe.device_id, mark, receipt, error):
        return _not_reached("the stale expected_revision command")
    return TestOutcome.failed(
        f"expected_revision mismatch returned {code or 'success'}, expected MHS.CONFLICT.REVISION"
        + _blocked_suffix(ctx, probe.device_id, mark)
    )


def _wrong_type(schema: Mapping[str, Any]) -> Any:
    expected = schema.get("type")
    if isinstance(expected, list):
        expected = next((item for item in expected if item != "null"), None)
    if expected == "array":
        return "not-an-array"
    if expected in ("integer", "number"):
        return "not-a-number"
    if expected == "string":
        return 12345
    if expected == "object":
        return "not-an-object"
    if expected == "boolean":
        return "not-a-boolean"
    return {"not": "a valid value"}


def cap_005(ctx: SuiteContext) -> TestOutcome:
    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    revision = ctx.current_revision(probe.device_id, probe.resource)
    schema = probe.schema
    properties = schema.get("properties") or {}
    required = [str(item) for item in schema.get("required") or []]
    typed = [name for name in sorted(properties) if isinstance(properties[name], Mapping)
             and properties[name].get("type") not in (None, "null")]
    invalid: dict[str, Any] = dict(payload)
    field_name = required[0] if required else (typed[0] if typed else None)
    if field_name is None:
        invalid = {"__mhs_invalid_field__": {"not": "allowed"}}
        what = "an undeclared field"
    else:
        invalid[field_name] = _wrong_type(properties.get(field_name) or {})
        what = f"a wrongly typed {field_name!r}"
    mark = ctx.harness.mark() if ctx.harness is not None else 0
    receipt, error = ctx.invoke(probe.capability_id, invalid, device_id=probe.device_id,
                                resource=probe.resource, command_id=canonical.ulid())
    code = _receipt_code(receipt, error)
    if _code_matches(code, _SCHEMA_REFUSALS):
        if ctx.current_revision(probe.device_id, probe.resource) != revision:
            return TestOutcome.failed("schema-invalid input advanced the revision")
        return TestOutcome.passed(f"input with {what} rejected with {code}", mhs_code=code)
    if _not_armed(ctx, probe.device_id, mark, receipt, error):
        return _not_reached(f"the input with {what}")
    return TestOutcome.failed(
        f"input with {what} returned {code or 'success'}, expected MHS.CAPABILITY.INPUT_INVALID"
        + _blocked_suffix(ctx, probe.device_id, mark)
    )


def cap_006(ctx: SuiteContext) -> TestOutcome:
    receipt, error = ctx.invoke("cap.mhs-conformance.does_not_exist.v1", {}, command_id=canonical.ulid())
    code = _receipt_code(receipt, error)
    if _code_matches(code, ("MHS.CAPABILITY.UNKNOWN", "MHS.PROTOCOL.METHOD_NOT_FOUND")):
        return TestOutcome.passed(f"unknown capability rejected with {code}", mhs_code=code)
    return TestOutcome.failed(f"unknown capability returned {code or 'success'}, expected MHS.CAPABILITY.UNKNOWN")


def cap_007_operations(ctx: SuiteContext) -> TestOutcome:
    getter = getattr(ctx.client, "get_operation", None)
    if not callable(getter):
        return TestOutcome.skipped("client API does not expose operations.get")
    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id, resource=probe.resource)
    if error is not None or not _is_success(receipt):
        return TestOutcome.failed(f"probe command failed: {_error_code(error) or _receipt_status(receipt)!r}")
    operation_id = (receipt or {}).get("operation_id")
    if not operation_id:
        return TestOutcome.skipped("the completed command returned no operation handle to query")
    snapshot = ctx.wait_operation(str(operation_id), timeout_s=2.0)
    if snapshot.get("command_id") not in (None, receipt.get("command_id")):
        return TestOutcome.failed("operations.get returned a different command")
    if snapshot.get("status") != receipt.get("status"):
        return TestOutcome.failed(
            f"operations.get status {snapshot.get('status')!r} differs from the receipt {receipt.get('status')!r}"
        )
    return TestOutcome.passed(f"operations.get({operation_id}) returns the receipt snapshot")


def _hook_or_harness(ctx: SuiteContext, hook: str) -> str | None:
    if ctx.harness is not None:
        return "harness"
    if ctx.find_capability_prefix(hook) is not None:
        return "hook"
    return None


def cap_008_deadline(ctx: SuiteContext) -> TestOutcome:
    """PROTO-011: a deadline bounds the response; a late completion is never returned."""

    how = _hook_or_harness(ctx, "x-cap.mhs-test.delay.v1")
    if how is None:
        return TestOutcome.skipped(
            "no way to slow a command over this transport; run in-process (mhs.conformance.inprocess)"
        )
    if how == "harness":
        setup = _probe_setup(ctx)
        if isinstance(setup, TestOutcome):
            return setup
        probe, payload, _source = setup
        with ctx.harness.delay_calls(probe.device_id, probe.capability_id, 0.4):
            receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id,
                                        resource=probe.resource, command_id=canonical.ulid(), deadline_ms=60)
        operation_id = (receipt or {}).get("operation_id")
        ctx.harness.wait_idle(probe.device_id, 5.0)
        if operation_id:
            ctx.wait_operation(str(operation_id), timeout_s=5.0)
        target = probe.capability_id
    else:
        _manifest, capability, _device = ctx.find_capability_prefix("x-cap.mhs-test.delay.v1")
        target = capability["capability_id"]
        receipt, error = ctx.invoke(target, {"ms": 500}, command_id=canonical.ulid(), deadline_ms=50)
        operation_id = (receipt or {}).get("operation_id")
        if operation_id:
            ctx.wait_operation(str(operation_id), timeout_s=5.0)
    code = _receipt_code(receipt, error)
    status = _receipt_status(receipt)
    if _code_matches(code, ("MHS.OUTCOME.TIMEOUT", "MHS.TRANSPORT.TIMEOUT")):
        return TestOutcome.passed(f"deadline exceeded on {target} surfaced as {code} (status {status!r})",
                                  mhs_code=code)
    if status == "unknown":
        return TestOutcome.passed(f"deadline exceeded on {target} surfaced as an unknown outcome", mhs_code=code)
    if status in ("accepted", "running") and operation_id:
        return TestOutcome.passed(f"long-running {target} answered {status!r} with operation {operation_id}")
    return TestOutcome.failed(
        f"a {target} call slower than its deadline returned {code or status or 'success'}; expected "
        "MHS.OUTCOME.TIMEOUT, an unknown outcome or a running operation handle"
    )


def _cancellation_applies(ctx: SuiteContext) -> bool:
    """OP-011 is required whenever the endpoint declares a cancellable binding (CON-027)."""

    return ctx.first_cancellable is not None


def cap_009_cancellation(ctx: SuiteContext) -> TestOutcome:
    found = ctx.find_capability_prefix("x-cap.mhs-test.delay.v1") if ctx.harness is None else None
    if found is not None and found[0].get("mode") == "replay":
        found = None  # a replay device refuses every command (FID-024): nothing to cancel
    if found is None:
        found = ctx.first_cancellable
    if found is None:
        return TestOutcome.skipped("endpoint does not declare a cancellable capability; OP-011 is not applicable")
    manifest, capability, _device = found
    capability_id = str(capability["capability_id"])
    device_id = str(manifest["device_id"])
    resource = capability.get("resource") or None
    binding = next((item for item in ctx.bindings_of(device_id, capability_id)
                    if item.resource == resource), None)
    if binding is None:
        return TestOutcome.failed(f"cancellable capability {capability_id} has no matching resource binding")
    if capability_id.startswith("x-cap.mhs-test.delay.v1"):
        payload: dict[str, Any] = {"ms": 2000}
    else:
        try:
            payload = valid_input(binding, ctx.fixtures)[0]
        except Unsynthesizable as exc:
            return TestOutcome.skipped(f"no valid input for cancellable {capability_id}: {exc}")
    permission: dict[str, Any] = {}
    if binding.requires_permit and ctx.may_actuate(device_id):
        try:
            permit = ctx.permit(capability_id, payload, device_id=device_id, resource=resource)
        except _NoApprovals as exc:
            return TestOutcome.skipped(str(exc))
        except BaseException as exc:  # noqa: BLE001 - a refused positive authorization is a failed control
            return TestOutcome.failed(f"cancellable command permit failed: {(_error_code(exc) or '')} {exc}")
        if not isinstance(permit, Mapping) or not isinstance(permit.get("permit_id"), str) or not permit["permit_id"]:
            return TestOutcome.failed("cancellable command permit result has no permit_id")
        permission["permit_id"] = permit["permit_id"]
    delay = ctx.harness.delay_calls(device_id, capability_id, 3.0) if ctx.harness is not None else None
    if delay is not None:
        delay.__enter__()
    final: dict[str, Any] = {}
    try:
        receipt, error = ctx.invoke(capability_id, payload, device_id=device_id, command_id=canonical.ulid(),
                                    resource=resource, deadline_ms=100, **permission)
        if error is not None:
            return TestOutcome.failed(f"cancellable command raised {_error_code(error) or error!r}")
        operation_id = (receipt or {}).get("operation_id") or _operation_for(ctx, device_id, receipt)
        if _receipt_status(receipt) == "completed" and not _cancelled_output(receipt):
            if ctx.harness is None:
                return TestOutcome.skipped(
                    f"{capability_id} completed within its deadline, before a cancellation could be sent; "
                    "run in-process (mhs.conformance.inprocess) to test cancellation"
                )
            return TestOutcome.failed(f"{capability_id} completed although its native call was still running")
        if not operation_id:
            return TestOutcome.failed(
                f"capability {capability_id} declares cancellable but the invocation returned no operation "
                "handle, so cancellation cannot be verified"
            )
        try:
            owner = ctx.operation_sessions.get(str(operation_id))
            try:
                result = _as_dict(ctx.client.cancel(operation_id, deadline_ms=5000, session_id=owner)
                                  if owner else ctx.client.cancel(operation_id, deadline_ms=5000))
            except TypeError:   # a duck-typed client without the session parameter
                result = _as_dict(ctx.client.cancel(operation_id, deadline_ms=5000))
        except BaseException as exc:  # noqa: BLE001
            return TestOutcome.failed(f"operations.cancel failed: {_error_code(exc) or exc!r}")
        final = result
        if result.get("status") in ("accepted", "running"):
            final = ctx.wait_operation(str(operation_id), timeout_s=5.0) or result
    finally:
        if delay is not None:
            delay.__exit__(None, None, None)
        if ctx.harness is not None:
            ctx.harness.wait_idle(device_id, 5.0)
    status = final.get("status")
    cancelled = status == "cancelled" or _cancelled_output(final)
    if not cancelled:
        return TestOutcome.failed(f"cancellation of {capability_id} resolved to {status!r}, not cancelled")
    cancellation = final.get("cancellation") if isinstance(final.get("cancellation"), Mapping) else {}
    safe = cancellation.get("safe_state_achieved", final.get("safe_state_achieved"))
    form = "" if status == "cancelled" else " with a cancelled output (legacy form, plan 3.7)"
    scope = ("; in-process the harness delay at the bridge boundary stood in for the native call, so this "
             "exercises the endpoint's cancellation plumbing, not the driver's own cancellation"
             if delay is not None else "")
    return TestOutcome.passed(
        f"cancellation of {capability_id} resolved to {status!r}{form} (safe_state_achieved={safe!r}){scope}"
    )


def _operation_for(ctx: SuiteContext, device_id: str, receipt: Any) -> str | None:
    """Find the operation of ``receipt``'s command through ``operations.list`` (receipt without a handle)."""

    command_id = (receipt or {}).get("command_id") if isinstance(receipt, Mapping) else None
    lister = getattr(ctx.client, "operations", None)
    if not command_id or not callable(lister):
        return None
    try:
        listing = _as_dict(lister(device_id, session_id=ctx.ensure_session(device_id)))
    except BaseException:  # noqa: BLE001 - listing is optional (PROTO-031)
        return None
    for item in listing.get("operations") or []:
        if isinstance(item, Mapping) and item.get("command_id") == command_id and item.get("operation_id"):
            return str(item["operation_id"])
    return None


def cap_010_unknown_outcome(ctx: SuiteContext) -> TestOutcome:
    how = _hook_or_harness(ctx, "x-cap.mhs-test.fault_inject.v1")
    if how is None:
        return TestOutcome.skipped(
            "no way to lose a response over this transport; run in-process (mhs.conformance.inprocess)"
        )
    setup = _probe_setup(ctx)
    if isinstance(setup, TestOutcome):
        return setup
    probe, payload, _source = setup
    if how == "harness":
        with ctx.harness.drop_responses(probe.device_id, probe.capability_id):
            receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id,
                                        resource=probe.resource, command_id=canonical.ulid())
        ctx.harness.wait_idle(probe.device_id, 5.0)
    else:
        enabled, error = ctx.invoke("x-cap.mhs-test.fault_inject.v1", {"fault": "lost_receipt", "enabled": True})
        if error is not None or not _is_success(enabled):
            return TestOutcome.failed("could not enable the lost-receipt fault")
        receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id, resource=probe.resource,
                                    command_id=canonical.ulid())
        try:
            ctx.invoke("x-cap.mhs-test.fault_inject.v1", {"fault": "lost_receipt", "enabled": False})
        except BaseException:  # noqa: BLE001 - fault cleanup is best effort
            pass
    code = _receipt_code(receipt, error)
    status = _receipt_status(receipt)
    # CON-024: never retry an unknown outcome; observe state first.
    observed = ctx.read(probe.resource, probe.device_id).get("revision")
    if _code_matches(code, ("MHS.OUTCOME.UNKNOWN",)):
        return TestOutcome.passed(f"lost response surfaced as {code} (status {status!r}; observed r{observed})",
                                  mhs_code=code)
    return TestOutcome.failed(
        f"lost response returned status {status!r} code {code!r}; expected MHS.OUTCOME.UNKNOWN semantics"
    )


# ---------------------------------------------------------------------------
# CL3 -- governed
# ---------------------------------------------------------------------------


def safe_001(ctx: SuiteContext) -> TestOutcome:
    status = ctx.safety_status()
    required = ("risk_class", "estop", "interlocks", "safe_state")
    missing = [field_name for field_name in required if field_name not in status]
    if missing:
        return TestOutcome.failed(f"mhs.safety.status is missing {missing}")
    if status.get("risk_class") not in ("R0", "R1", "R2", "R3"):
        return TestOutcome.failed(f"risk_class={status.get('risk_class')!r} is invalid")
    estop = status.get("estop")
    if not isinstance(estop, Mapping) or "engaged" not in estop:
        return TestOutcome.failed("safety.status estop block is missing engaged/latching")
    interlocks = status.get("interlocks")
    if not isinstance(interlocks, list):
        return TestOutcome.failed("safety.status interlocks is not an array")
    for interlock in interlocks:
        if not isinstance(interlock, Mapping) or "id" not in interlock or interlock.get("state") not in (
            "closed",
            "open",
            "unknown",
        ):
            return TestOutcome.failed(f"malformed interlock entry: {interlock!r}")
    return TestOutcome.passed(
        f"safety.status ok: risk {status.get('risk_class')}, {len(interlocks)} interlock(s)"
    )


def _estop_engaged(status: Mapping[str, Any]) -> bool:
    """Accept both spec form (estop.engaged) and the reference server's estop_engaged."""

    estop = status.get("estop")
    if isinstance(estop, Mapping) and "engaged" in estop:
        return bool(estop.get("engaged"))
    return bool(status.get("estop_engaged"))


def _latching_estop(ctx: SuiteContext) -> bool:
    estop = ((ctx.primary_device.get("safety") or {}).get("estop") or {})
    return bool(estop.get("latching"))


def _software_estop(ctx: SuiteContext) -> bool:
    return ctx.estop_kind() in ("software", "both")


def _estop_test_required(ctx: SuiteContext) -> bool:
    return ctx.replay_device is None and _latching_estop(ctx) and _software_estop(ctx)


def _withhold_estop(ctx: SuiteContext) -> TestOutcome | None:
    if _software_estop(ctx):
        return None
    with ctx.run_log.lock:
        ctx.run_log.estop_withheld.append(str(ctx.primary_device.get("device_id")))
    return TestOutcome.skipped(
        f"{ctx.primary_device.get('device_id')} declares a {ctx.estop_kind()!r} e-stop: a hardware-only e-stop "
        "is exercised by a human, never by the suite (CON-032)"
    )


def _latency_problem(ctx: SuiteContext, receipt: Any) -> str | None:
    output = (receipt or {}).get("output") if isinstance(receipt, Mapping) else None
    if not isinstance(output, Mapping):
        return None
    declared = ((ctx.primary_device.get("safety") or {}).get("estop") or {}).get("latency_ms")
    observed = output.get("latency_ms")
    if isinstance(declared, (int, float)) and isinstance(observed, (int, float)) and observed > declared + 1000:
        return f"e-stop took {observed} ms, more than the declared {declared} ms + 1000 ms (SAFE-040)"
    return None


def _reenable_permit_unavailable(ctx: SuiteContext, binding: Binding) -> str | None:
    """Why the suite cannot obtain the re-enable's permit, decided before TSAFE-001 sends anything.

    An e-stop revokes every permit of the device (SAFE-036, CORE-084), so the
    permit cannot be taken before the e-stop; whether one can be taken after
    the reset is known in advance: the suite never invents a permit on
    hardware (CON-031).
    """
    if not binding.requires_permit:
        return None
    mode = str(binding.manifest.get("mode"))
    if mode in _static.HARDWARE_MODES and not ctx.options.approvals:
        return (f"the declared re-enable {binding.capability_id} needs a permit and {binding.device_id} is {mode}: "
                "the suite never invents permits on hardware (CON-031); supply operator approvals (--approvals). "
                "Nothing was sent: no e-stop, no reset")
    return None


def _send_reenable(ctx: SuiteContext, binding: Binding) -> tuple[dict[str, Any] | None, BaseException | None]:
    """Invoke the declared re-enable with its empty input (CORE-086), with a permit when the binding needs one."""

    extra: dict[str, Any] = {}
    if binding.requires_permit:
        permit = ctx.permit(binding.capability_id, {}, device_id=binding.device_id, resource=binding.resource)
        if isinstance(permit, Mapping) and isinstance(permit.get("permit_id"), str):
            extra["permit_id"] = permit["permit_id"]
    return ctx.invoke(binding.capability_id, {}, device_id=binding.device_id, resource=binding.resource,
                      command_id=canonical.ulid(), **extra)


def _terminal_outcome(ctx: SuiteContext, terminal: str, reset_receipt: Any, status_after: Mapping[str, Any],
                      probe: Binding | None, payload: Mapping[str, Any] | None, reset_mark: int) -> TestOutcome:
    """TSAFE-001 for a declared terminal e-stop (CORE-087): the reset is refused with the declared reason
    and the latch is retained."""

    device_id = str(ctx.primary_device.get("device_id"))
    reset = _as_dict(reset_receipt) if isinstance(reset_receipt, Mapping) else {}
    code = _receipt_code(reset)
    details = _receipt_error(reset).get("details")
    details = details if isinstance(details, Mapping) else {}
    reason = details.get("reason")
    shown = terminal if len(terminal) <= 200 else terminal[:197] + "..."
    if _is_success(reset) or not _estop_engaged(status_after):
        return TestOutcome.failed(
            f"{device_id} declares a terminal e-stop ({shown}), but mhs.safety.reset after the e-stop returned "
            f"{_receipt_status(reset)!r} and the latch is {'engaged' if _estop_engaged(status_after) else 'released'}"
            "; a terminal e-stop is never reset on the endpoint that engaged it (CORE-087)",
            mhs_code=code)
    if (_receipt_status(reset) != "rejected" or not _code_matches(code, ("MHS.SAFETY.RESET_REFUSED",))
            or reason != "terminal_estop"):
        return TestOutcome.failed(
            f"{device_id} declares a terminal e-stop, but the reset after it returned {_receipt_status(reset)!r} "
            f"{code or ''} ({reason}), not a rejected MHS.SAFETY.RESET_REFUSED with details.reason terminal_estop "
            "(CORE-087)", mhs_code=code)
    if details.get("terminal") != terminal:
        return TestOutcome.failed(
            f"the terminal_estop refusal does not carry the declared reason: details.terminal is "
            f"{details.get('terminal')!r}, the manifest declares {shown!r} (CORE-087)", mhs_code=code)
    if ctx.harness is not None and ctx.harness.since(reset_mark, device_id=device_id, methods=("reset",)):
        return TestOutcome.failed("the terminal_estop refusal still called the bridge's reset (CORE-087: the bridge "
                                  "is not called)", mhs_code=code)
    still = ""
    if probe is not None and payload is not None:
        receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id, resource=probe.resource,
                                    command_id=canonical.ulid())
        retained = _receipt_code(receipt, error)
        if not _code_matches(retained, ("MHS.SAFETY.ESTOP_ENGAGED",)):
            return TestOutcome.failed(
                f"after the refused reset of the terminal e-stop a command returned "
                f"{retained or _receipt_status(receipt) or 'success'}; the latch must be retained (CORE-087)")
        still = ", a new command was still refused"
    return TestOutcome.passed(
        f"terminal e-stop declared ({shown}): e-stop latched within its declared latency, blocked commands, reset "
        f"refused with MHS.SAFETY.RESET_REFUSED (terminal_estop) and the declared reason, latch retained{still}",
        mhs_code="MHS.SAFETY.RESET_REFUSED")


def safe_002(ctx: SuiteContext) -> TestOutcome:
    """TSAFE-001: SAFE-040 latch, SAFE-042 release without auto-resume, and the declared recovery.

    A device that declares ``safety.estop.reenable`` (CORE-086) must refuse the
    re-enable while latched and accept it after the reset, before the recovery
    probe.  A device that declares ``safety.estop.terminal`` (CORE-087) must
    refuse the reset with ``terminal_estop`` and the declared reason, without
    calling the bridge, and keep the latch; that endpoint is not used again
    (CON-022).  A device that declares neither is tested as before.
    """
    if not _latching_estop(ctx):
        return TestOutcome.skipped("primary device declares a non-latching e-stop")
    withheld = _withhold_estop(ctx)
    if withheld is not None:
        return withheld
    device_id = str(ctx.primary_device.get("device_id"))
    terminal = _terminal_statement(ctx.primary_device)
    reenable_id = _reenable_id(ctx.primary_device)
    reenable: Binding | None = None
    if reenable_id is not None:
        bound = ctx.bindings_of(device_id, reenable_id)
        if len(bound) != 1:
            return TestOutcome.failed(f"safety.estop.reenable names {reenable_id}, which {device_id} binds "
                                      f"{len(bound)} time(s); a declared re-enable is bound to exactly one resource "
                                      "(CORE-086)")
        reenable = bound[0]
        missing = _reenable_permit_unavailable(ctx, reenable)
        if missing is not None:
            return TestOutcome.skipped(missing)
    probe = ctx.probe
    payload: dict[str, Any] | None = None
    if probe is not None:
        try:
            payload = ctx.probe_input()[0]
        except Unsynthesizable:
            payload = None
    try:
        estop_receipt = ctx.estop("conformance: latching e-stop test")
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"mhs.safety.estop failed: {_error_code(exc) or exc!r}")
    status = ctx.safety_status()
    if not _estop_engaged(status):
        return TestOutcome.failed("safety.status does not report the e-stop as engaged")
    latency = _latency_problem(ctx, estop_receipt)
    if latency:
        return TestOutcome.failed(latency)
    if probe is not None and payload is not None:
        receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id, resource=probe.resource,
                                    command_id=canonical.ulid())
        code = _receipt_code(receipt, error)
        if not _code_matches(code, ("MHS.SAFETY.ESTOP_ENGAGED", "MHS.SAFETY.INTERLOCK_OPEN", "MHS.SAFETY.SAFE_STATE")):
            return TestOutcome.failed(
                f"command while e-stop engaged returned {code or _receipt_status(receipt) or 'success'}"
            )
    if reenable is not None:
        # CORE-086: the re-enable is an effectful command; the latch refuses it before any bridge call.
        mark = ctx.harness.mark() if ctx.harness is not None else 0
        receipt, error = ctx.invoke(reenable.capability_id, {}, device_id=device_id, resource=reenable.resource,
                                    command_id=canonical.ulid())
        code = _receipt_code(receipt, error)
        if not _code_matches(code, ("MHS.SAFETY.ESTOP_ENGAGED",)) or (
                receipt is not None and _receipt_status(receipt) != "rejected"):
            return TestOutcome.failed(
                f"the declared re-enable {reenable.capability_id} sent while the e-stop was engaged returned "
                f"{code or _receipt_status(receipt) or 'success'}, not a rejected MHS.SAFETY.ESTOP_ENGAGED (CORE-086)")
        if ctx.harness is not None and ctx.harness.actuations(device_id, since=mark):
            return TestOutcome.failed(f"the declared re-enable {reenable.capability_id} was refused while latched, "
                                      "but it still reached the bridge")
    reset_mark = ctx.harness.mark() if ctx.harness is not None else 0
    try:
        reset_receipt = ctx.reset()
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"mhs.safety.reset failed after e-stop: {_error_code(exc) or exc!r}")
    status_after = ctx.safety_status()
    if terminal is not None:
        return _terminal_outcome(ctx, terminal, reset_receipt, status_after, probe, payload, reset_mark)
    if _estop_engaged(status_after):
        reset_dict = _as_dict(reset_receipt) if isinstance(reset_receipt, Mapping) else {}
        if reset_dict and not _is_success(reset_dict):
            # The endpoint refused the reset (strict hardware: operator only;
            # stop_path_pending; ...): say so instead of calling it successful.
            code = _receipt_code(reset_dict)
            reason = (_receipt_error(reset_dict).get("details") or {}).get("reason")
            return TestOutcome.failed(
                f"mhs.safety.reset after the e-stop returned {_receipt_status(reset_dict)!r} {code or ''}"
                + (f" ({reason})" if reason else "") + "; the e-stop stays engaged",
                mhs_code=code,
            )
        return TestOutcome.failed("e-stop is still engaged after a successful reset")
    # SAFE-042: releasing the e-stop does not restart anything; a new command is required.
    first = ctx.read()
    time.sleep(0.02)
    second = ctx.read()
    if first.get("revision") != second.get("revision") or first.get("state_hash") != second.get("state_hash"):
        return TestOutcome.failed("the device state changed after reset without a new command (auto-resume)")
    reenabled = ""
    if reenable is not None:
        # CORE-086: the declared re-enable is the new start command; it runs after the reset, before the probe.
        try:
            receipt, error = _send_reenable(ctx, reenable)
        except _NoApprovals as exc:
            # Decided before the e-stop (_reenable_permit_unavailable); once the e-stop and the reset were sent,
            # a missing permit is a verdict, never a skip.
            return TestOutcome.failed(f"the declared re-enable {reenable.capability_id} needs a permit the suite "
                                      f"could not obtain after the e-stop and the reset: {exc}")
        except BaseException as exc:  # noqa: BLE001 - a permit refusal is a verdict here
            return TestOutcome.failed(f"the declared re-enable {reenable.capability_id} could not be sent after the "
                                      f"reset: {_error_code(exc) or exc!r}")
        if error is not None or not _is_success(receipt):
            return TestOutcome.failed(
                f"the declared re-enable {reenable.capability_id} failed after the reset: "
                f"{_error_code(error) or _receipt_code(receipt) or _receipt_status(receipt)!r} (CORE-086)")
        reenabled = (f", the declared re-enable {reenable.capability_id} was refused while latched and accepted "
                     "after the reset")
    if probe is not None and payload is not None:
        receipt, error = ctx.invoke(probe.capability_id, payload, device_id=probe.device_id, resource=probe.resource,
                                    command_id=canonical.ulid())
        if error is not None or not _is_success(receipt):
            return TestOutcome.failed(
                f"command after e-stop reset failed: {_error_code(error) or _receipt_status(receipt)!r}"
            )
    return TestOutcome.passed(
        "e-stop latched within its declared latency, blocked commands, reset released the latch without "
        "auto-resume" + reenabled + (", a new command recovered" if probe is not None and payload is not None else "")
    )


def _estop_reach_required(ctx: SuiteContext) -> bool:
    risk = str((ctx.primary_device.get("safety") or {}).get("risk_class") or "R0")
    return ctx.replay_device is None and _software_estop(ctx) and risk in ("R1", "R2", "R3")


def safe_028(ctx: SuiteContext) -> TestOutcome:
    """SAFE-028: the e-stop takes effect -- the device reaches its declared safe state."""

    if ctx.replay_device is not None:
        return TestOutcome.skipped("replay endpoints are read-only")
    withheld = _withhold_estop(ctx)
    if withheld is not None:
        return withheld
    device_id = str(ctx.primary_device.get("device_id"))
    mark = ctx.harness.mark() if ctx.harness is not None else 0
    try:
        receipt = _as_dict(ctx.estop("conformance: e-stop reaches the device", device_id=device_id))
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"mhs.safety.estop failed: {_error_code(exc) or exc!r}")
    problems: list[str] = []
    output = receipt.get("output") if isinstance(receipt.get("output"), Mapping) else {}
    try:
        if receipt.get("status") not in (None, "completed"):
            problems.append(f"e-stop receipt is {receipt.get('status')!r} ({_receipt_error(receipt).get('mhs_code')})")
        if output.get("latched") is False:
            problems.append("the e-stop did not latch")
        if output.get("estop") == "software_only":
            problems.append("the e-stop latched in software only; nothing reached the device")
        if output.get("safe_state_achieved") is not True:
            problems.append("the receipt reports safe_state_achieved="
                            f"{output.get('safe_state_achieved')!r}: the device did not reach its declared "
                            "safe state (make it observable through safety_status or safe_state.achieved_by)")
        if "latency_ms" not in output:
            problems.append("the receipt does not record the observed latency_ms")
        latency = _latency_problem(ctx, receipt)
        if latency:
            problems.append(latency)
        # The receipt flag is the server's view; the device's own report must agree (a no-op
        # achieved_by action or e-stop leaves safe_state.achieved false there).
        unreached = _safe_state_unreached(ctx, device_id)
        if unreached:
            problems.append("after the e-stop " + " and ".join(unreached)
                            + (" report" if len(unreached) > 1 else " reports")
                            + " safe_state.achieved=false: the device did not reach its declared safe state")
        if ctx.harness is not None:
            calls = ctx.harness.estops(device_id, since=mark)
            if not calls:
                problems.append("the driver's estop() was never invoked")
            elif not all(call.ok for call in calls):
                problems.append("the driver's estop() raised " + ", ".join(str(call.error) for call in calls))
            bridge = _bridge_of(ctx.harness, device_id)
            if bridge is not None and _inherits_noop_estop(bridge):
                problems.append(f"{type(bridge).__name__} does not implement estop() (the Bridge default is a no-op)")
    finally:
        try:
            ctx.reset(device_id)
        except BaseException:  # noqa: BLE001 - cleanup only
            pass
    if problems:
        return TestOutcome.failed("; ".join(problems))
    return TestOutcome.passed(
        f"e-stop reached {device_id}: latched, safe state achieved in {output.get('latency_ms')} ms"
        + ("; driver estop() invoked" if ctx.harness is not None else "")
    )


def _safe_state_unreached(ctx: SuiteContext, device_id: str) -> list[str]:
    """Sources that report ``safe_state.achieved: false`` now (safety.status, and in-process the driver)."""

    sources: list[tuple[str, Any]] = []
    try:
        status = ctx.safety_status(device_id)
    except BaseException:  # noqa: BLE001 - an unreadable status is reported by SAFE-001
        status = {}
    inner = status.get("status") if isinstance(status.get("status"), Mapping) else {}
    sources.append(("mhs.safety.status (status.safe_state)", inner.get("safe_state")))
    sources.append(("mhs.safety.status (safe_state)", status.get("safe_state")))
    if ctx.harness is not None:
        reader = getattr(_bridge_of(ctx.harness, device_id), "safety_status", None)
        if callable(reader):
            try:
                report = reader()
            except Exception:  # noqa: BLE001 - a raising status is not evidence either way
                report = None
            sources.append(("the driver's safety_status()",
                            report.get("safe_state") if isinstance(report, Mapping) else None))
    return [label for label, block in sources
            if isinstance(block, Mapping) and block.get("achieved") is False]


def _bridge_of(harness: Any, device_id: str) -> Any:
    devices = getattr(getattr(harness, "server", None), "devices", None)
    device = devices.get(device_id) if isinstance(devices, Mapping) else None
    return getattr(device, "bridge", None)


def _inherits_noop_estop(bridge: Any) -> bool:
    try:
        from mhs.bridge.base import Bridge
    except Exception:  # noqa: BLE001
        return False
    return isinstance(bridge, Bridge) and getattr(type(bridge), "estop", None) is Bridge.estop


def _interlock_targets(ctx: SuiteContext) -> list[tuple[str, str, Binding]]:
    """``(device_id, interlock_id, binding)`` for each declared interlock that gates an actuating binding."""

    out: list[tuple[str, str, Binding]] = []
    for manifest in sorted(ctx.devices, key=lambda item: str(item.get("device_id"))):
        if manifest.get("mode") == "replay":
            continue
        device_id = str(manifest.get("device_id"))
        for entry in (manifest.get("safety") or {}).get("interlocks") or []:
            if not isinstance(entry, Mapping) or not entry.get("id"):
                continue
            patterns = [str(item) for item in entry.get("required_for") or []]
            for binding in sorted(ctx.bindings, key=lambda item: (item.capability_id, item.resource or "")):
                if binding.device_id != device_id or binding.verb not in ("write", "invoke"):
                    continue
                if binding.requires_permit or binding.capability_id.startswith("x-cap.mhs-test."):
                    continue
                if any(_pattern_matches(pattern, binding.capability_id) for pattern in patterns):
                    out.append((device_id, str(entry["id"]), binding))
                    break
    return out


def _interlock_required(ctx: SuiteContext) -> bool:
    return ctx.replay_device is None and bool(_interlock_targets(ctx))


def _latched(ctx: SuiteContext, device_id: str) -> bool:
    try:
        return _estop_engaged(ctx.safety_status(device_id))
    except BaseException:  # noqa: BLE001 - an unreadable status is reported by SAFE-001
        return False


def _latched_problem(ctx: SuiteContext, device_id: str, interlock_id: str) -> str | None:
    if not _latched(ctx, device_id):
        return None
    return (f"{device_id} is latched (e-stop engaged) before the probe -- an earlier e-stop was not released -- "
            f"so interlock {interlock_id!r} cannot be evaluated (an ESTOP_ENGAGED refusal is not interlock evidence)")


def _blocked_records(ctx: SuiteContext, device_id: str, mark: int) -> list[Any]:
    blocked = getattr(ctx.harness, "blocked", None)
    return list(blocked(device_id, since=mark)) if callable(blocked) else []


def _reached(ctx: SuiteContext, device_id: str, mark: int) -> str:
    if _blocked_records(ctx, device_id, mark):
        return ("reached the bridge (the harness blocked it before the driver: hardware without "
                "--allow-actuation, CON-031)")
    return "reached the driver"


def _blocked_suffix(ctx: SuiteContext, device_id: str, mark: int) -> str:
    if ctx.harness is None or not _blocked_records(ctx, device_id, mark):
        return ""
    return (": the endpoint dispatched it to the bridge, where the harness blocked it before the driver "
            "(hardware without --allow-actuation, CON-031)")


def _not_armed(ctx: SuiteContext, device_id: str, mark: int, receipt: Any, error: BaseException | None) -> bool:
    """The endpoint itself refused the command because hardware actuation is not armed.

    Plan 3.6 checks arming (step 6) before structure, limits, revisions and
    interlocks, so an unarmed hardware endpoint (a strict endpoint arms none by
    default) answers a negative test with ``MHS.AUTH.HARDWARE_DISABLED``
    before the check that test targets.  Only a ``rejected`` receipt counts:
    a command the harness blocked at the bridge, or one the suite withheld
    (CON-031), is not an endpoint refusal.
    """

    return (error is None and _receipt_status(receipt) == "rejected"
            and _code_matches(_receipt_code(receipt), ("MHS.AUTH.HARDWARE_DISABLED",))
            and not _blocked_records(ctx, device_id, mark))


def _not_reached(what: str) -> TestOutcome:
    """A negative test the endpoint refused at its arming step; skipped, so it still caps the level."""

    return TestOutcome.skipped(
        f"check not reached: the endpoint refused {what} with MHS.AUTH.HARDWARE_DISABLED (hardware actuation "
        "is not armed; plan 3.6 checks arming at step 6, before the check this test targets)"
    )


def _uninstrumented_problem(ctx: SuiteContext, device_id: str) -> str | None:
    missing = ctx.uninstrumented(device_id)
    if not missing:
        return None
    return (f"{device_id}: bridge method(s) {', '.join(missing)} are not instrumented by the call recorder, so a "
            "refusal 'with no bridge call' cannot be shown")


def _injected_interlock(ctx: SuiteContext, state: str) -> TestOutcome:
    targets = _interlock_targets(ctx)
    if not targets:
        return TestOutcome.skipped("no declared interlock gates an actuating binding")
    problems: list[str] = []
    passed: list[str] = []
    unreached: list[str] = []
    for device_id, interlock_id, binding in targets:
        blocker = _uninstrumented_problem(ctx, device_id) or _latched_problem(ctx, device_id, interlock_id)
        if blocker is not None:
            problems.append(blocker)
            continue
        try:
            payload = valid_input(binding, ctx.fixtures)[0]
        except Unsynthesizable as exc:
            problems.append(f"{binding.capability_id}: no valid input ({exc})")
            continue
        revision = ctx.current_revision(device_id, binding.resource)
        mark = ctx.harness.mark()
        with ctx.harness.force_interlocks(device_id, state, [interlock_id]):
            receipt, error = ctx.invoke(binding.capability_id, payload, device_id=device_id,
                                        resource=binding.resource, command_id=canonical.ulid())
        code = _receipt_code(receipt, error)
        if _not_armed(ctx, device_id, mark, receipt, error):
            unreached.append(f"{binding.capability_id} with interlock {interlock_id!r} {state}")
            continue
        # The device was not latched, so only the interlock may refuse (plan 3.6 step 11).
        if not _code_matches(code, ("MHS.SAFETY.INTERLOCK_OPEN",)):
            problems.append(f"{binding.capability_id} with interlock {interlock_id!r} {state} returned "
                            f"{code or _receipt_status(receipt) or 'success'}, not MHS.SAFETY.INTERLOCK_OPEN"
                            + _blocked_suffix(ctx, device_id, mark))
            continue
        if ctx.current_revision(device_id, binding.resource) != revision:
            problems.append(f"{binding.capability_id}: refusal advanced the revision")
            continue
        if ctx.harness.actuations(device_id, since=mark):
            problems.append(f"{binding.capability_id}: the refused command still {_reached(ctx, device_id, mark)}")
            continue
        passed.append(f"{binding.capability_id} ({interlock_id} {state}: {code})")
    if problems:
        return TestOutcome.failed("; ".join(problems[:4]))
    if unreached:
        return _not_reached("; ".join(unreached[:4]))
    return TestOutcome.passed("refused with no bridge call: " + "; ".join(passed[:4]),
                              mhs_code="MHS.SAFETY.INTERLOCK_OPEN")


def safe_003(ctx: SuiteContext) -> TestOutcome:
    """SAFE-011: an open interlock blocks actuation before any effect."""

    if ctx.harness is not None:
        return _injected_interlock(ctx, "open")
    found = ctx.find_capability_prefix(TEST_HOOK_PREFIX + "set_door.v1")
    if found is None:
        return TestOutcome.skipped(
            "no way to open an interlock over this transport; run in-process (mhs.conformance.inprocess)"
        )
    _manifest, door_capability, door_device = found
    device_id = door_device["device_id"]
    if not ctx.may_actuate(device_id):
        # CON-031: opening a door through a test hook actuates the device.
        with ctx.run_log.lock:
            ctx.run_log.gated.append("SAFE-011")
        return TestOutcome.skipped(
            f"{device_id} is {door_device.get('mode')}: the {door_capability['capability_id']} hook actuates the "
            "device, so it needs the operator's --allow-actuation (CON-031); or run in-process"
        )
    latched = _latched_problem(ctx, device_id, "the door interlock")
    if latched is not None:
        return TestOutcome.failed(latched)
    try:
        ctx.invoke_ok(door_capability["capability_id"], {"state": "open"}, device_id=device_id)
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"could not open the simulated door: {_error_code(exc) or exc!r}")
    try:
        status = ctx.safety_status(device_id)
        open_interlocks = [
            item for item in status.get("interlocks") or []
            if isinstance(item, Mapping) and item.get("state") == "open"
        ]
        if not open_interlocks:
            return TestOutcome.failed("safety.status reports no open interlock after opening the door")
        target = _capability_requiring(ctx, device_id, str(open_interlocks[0].get("id")))
        if target is None:
            return TestOutcome.failed("no capability declares the opened interlock as required")
        revision = ctx.current_revision(device_id)
        receipt, error = ctx.invoke(
            target["capability_id"], ctx.synthesize(target),
            device_id=device_id, command_id=canonical.ulid(),
        )
        code = _receipt_code(receipt, error)
        # The device was not latched before the door opened: ESTOP_ENGAGED counts only
        # when opening the door is what latched it.
        accepted = ("MHS.SAFETY.INTERLOCK_OPEN", "MHS.SAFETY.ESTOP_ENGAGED") if _estop_engaged(status) else (
            "MHS.SAFETY.INTERLOCK_OPEN",)
        if not _code_matches(code, accepted):
            return TestOutcome.failed(
                f"command with interlock {open_interlocks[0].get('id')!r} open returned "
                f"{code or _receipt_status(receipt) or 'success'}"
            )
        if ctx.current_revision(device_id) != revision:
            return TestOutcome.failed("interlock refusal advanced the revision")
    finally:
        try:
            ctx.invoke_ok(door_capability["capability_id"], {"state": "closed"}, device_id=device_id)
        except BaseException:  # noqa: BLE001 - cleanup is best effort
            pass
        try:
            ctx.reset(device_id)  # an opened door may latch the device
        except BaseException:  # noqa: BLE001 - a refused reset (not latched) is fine here
            pass
    return TestOutcome.passed(
        f"open interlock {open_interlocks[0].get('id')!r} blocked {target['capability_id']} with {code}",
        mhs_code=code,
    )


def safe_012(ctx: SuiteContext) -> TestOutcome:
    """SAFE-012: an interlock whose state is unknown blocks actuation (fail closed)."""

    if ctx.harness is None:
        return TestOutcome.skipped(
            "an unknown interlock state can only be injected in-process (mhs.conformance.inprocess)"
        )
    return _injected_interlock(ctx, "unknown")


def safe_041(ctx: SuiteContext) -> TestOutcome:
    """SAFE-041: reset is refused while a hard interlock is open."""

    if ctx.harness is None:
        return TestOutcome.skipped("interlocks can only be forced open in-process (mhs.conformance.inprocess)")
    withheld = _withhold_estop(ctx)
    if withheld is not None:
        return withheld
    targets = [item for item in _interlock_targets(ctx) if item[0] == ctx.primary_device.get("device_id")]
    if not targets:
        return TestOutcome.skipped("the primary device declares no interlock that gates actuation")
    device_id, interlock_id, _binding = targets[0]
    if _terminal_statement(ctx.device_for(device_id)) is not None:
        # Every reset after its e-stop is refused (terminal_estop), so an interlock refusal cannot be told apart.
        return TestOutcome.skipped(f"{device_id} declares a terminal e-stop (CORE-087): every reset after an e-stop "
                                   "is refused with terminal_estop, so a refusal for an open interlock cannot be "
                                   "shown")
    refused = False
    detail = ""
    try:
        ctx.estop("conformance: reset with an open interlock", device_id=device_id)
        with ctx.harness.force_interlocks(device_id, "open", [interlock_id]):
            try:
                result = _as_dict(ctx.reset(device_id))
                code = _receipt_code(result)
                refused = _receipt_status(result) in ("rejected", "failed") or bool(code)
                detail = f"reset returned {_receipt_status(result)!r} {code or ''}".strip()
            except BaseException as exc:  # noqa: BLE001 - a refusal may be a JSON-RPC error
                refused = True
                detail = f"reset refused with {_error_code(exc) or exc!r}"
    finally:
        try:
            ctx.reset(device_id)
        except BaseException:  # noqa: BLE001
            pass
    if refused:
        return TestOutcome.passed(f"{detail} while {interlock_id!r} was open")
    return TestOutcome.failed(f"reset succeeded while interlock {interlock_id!r} was open ({detail})")


def _capability_requiring(ctx: SuiteContext, device_id: str, interlock_id: str) -> dict[str, Any] | None:
    manifest = ctx.device_for(device_id)
    patterns: list[str] = []
    for entry in (manifest.get("safety") or {}).get("interlocks") or []:
        if isinstance(entry, Mapping) and entry.get("id") == interlock_id:
            patterns.extend(str(item) for item in entry.get("required_for") or [])
    for capability in manifest.get("capabilities") or []:
        capability_id = str(capability.get("capability_id"))
        for pattern in patterns:
            if _pattern_matches(pattern, capability_id):
                return dict(capability)
    return None


def safe_004(ctx: SuiteContext) -> TestOutcome:
    """SAFE-031 (with SAFE-030): a gated capability needs a permit, which is bound to its input and single-use.

    A gated binding whose input schema admits only the empty object (:func:`mhs.conformance.synth.only_empty_input`)
    has no second valid input to present the permit with; :func:`_safe_031_input_free` tests what applies to it
    instead of skipping.  Every other binding is tested exactly as in suite 1.4.0.
    """

    binding = ctx.gated_binding
    if binding is None:
        return TestOutcome.skipped("endpoint declares no gated (requires_permit) capability")
    capability_id = binding.capability_id
    device_id = binding.device_id
    mode = str(binding.manifest.get("mode"))
    if mode in _static.HARDWARE_MODES and not ctx.options.approvals:
        return TestOutcome.skipped(
            f"{device_id} is {mode}: the suite never invents permits on hardware (CON-031); supply operator "
            "approvals (--approvals) to test permits"
        )
    try:
        payload = valid_input(binding, ctx.fixtures)[0]
    except Unsynthesizable as exc:
        return TestOutcome.skipped(f"no valid input for gated {capability_id}: {exc}")
    different = alternate_input(binding, payload, ctx.fixtures)
    if different is None:
        input_free = _synth.only_empty_input(binding) if payload == {} else None
        if input_free is not None:
            return _safe_031_input_free(ctx, binding, input_free)
        return TestOutcome.skipped(f"no distinct valid second input for {capability_id} to test permit binding")
    receipt, error = ctx.invoke(capability_id, payload, command_id=canonical.ulid(), device_id=device_id,
                                resource=binding.resource)
    code = _receipt_code(receipt, error)
    if not _code_matches(
        code, ("MHS.SAFETY.PERMIT_REQUIRED", "MHS.SAFETY.APPROVAL_REQUIRED", "MHS.SAFETY.PERMIT_INVALID")
    ):
        return TestOutcome.failed(
            f"gated capability without a permit returned {code or _receipt_status(receipt) or 'success'}"
        )
    try:
        permit = ctx.permit(capability_id, payload, device_id=device_id, resource=binding.resource)
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"mhs.safety.permit failed: {(_error_code(exc) or '')} {exc}".strip())
    permit_id = permit.get("permit_id") if isinstance(permit, Mapping) else None
    if not isinstance(permit_id, str):
        return TestOutcome.failed("permit result has no permit_id")
    granted, error = ctx.invoke(capability_id, payload, command_id=canonical.ulid(), permit_id=permit_id,
                                device_id=device_id, resource=binding.resource)
    if error is not None or not _is_success(granted):
        return TestOutcome.failed(
            f"permit-gated command failed with the issued permit: {_error_code(error) or _receipt_error(granted)}"
        )
    bad, error = ctx.invoke(capability_id, different, command_id=canonical.ulid(), permit_id=permit_id,
                            device_id=device_id, resource=binding.resource)
    bad_code = _receipt_code(bad, error)
    if not _code_matches(bad_code, ("MHS.SAFETY.PERMIT_INVALID", "MHS.SAFETY.PERMIT_EXPIRED")):
        return TestOutcome.failed(
            f"reused permit with a different input returned {bad_code or _receipt_status(bad) or 'success'}"
        )
    return TestOutcome.passed(
        f"permit required, accepted for the bound input, rejected for a different input ({bad_code})"
    )


#: The refusals a permit check gives a permit presented for another input digest or a second time.
_PERMIT_MISMATCH = ("MHS.SAFETY.PERMIT_INVALID", "MHS.SAFETY.PERMIT_EXPIRED")


def _calls_of(ctx: SuiteContext, binding: Binding, mark: int) -> list[Any]:
    """Bridge ``call``s of ``binding``'s capability on its device since ``mark`` (in-process only).

    Keyed on the capability, so a stop path the endpoint retries in the background (``estop``,
    ``safe_state`` or an ``achieved_by`` action) is never mistaken for the presented command.  Only
    ``call`` records name a capability; the receipt status (``rejected``, or a JSON-RPC error) is the
    dispatch check every transport has.
    """

    if ctx.harness is None:
        return []
    return [record for record in ctx.harness.since(mark, device_id=binding.device_id, methods=("call",))
            if record.capability_id == binding.capability_id]


def _binding_label(binding: Binding) -> str:
    return f"{binding.capability_id} on {binding.resource}" if binding.resource else binding.capability_id


def _input_free_siblings(ctx: SuiteContext, binding: Binding) -> list[Binding]:
    """Other gated bindings of ``binding``'s device that also take only the empty object.

    At most one of each kind, in a fixed order: the same capability bound to another resource, then
    another capability.  The digest of ``{capability_id, resource, input}`` differs from the permit's
    for both, while every check before the permit's (structure, limits, schema bounds) passes for the
    empty input, so the permit check decides (CORE-060 step 10).  Left out: ``safe_state.achieved_by``
    actions (exempt from permits, SAFE-029, so the permit would not be checked and the action would run),
    stop classes (never sent as a probe), test hooks and replay devices.
    """

    achieved_by = {str(item) for item in
                   (((binding.manifest.get("safety") or {}).get("safe_state") or {}).get("achieved_by") or [])}
    same: Binding | None = None
    other: Binding | None = None
    for candidate in sorted(ctx.bindings, key=lambda item: (item.capability_id, item.resource or "")):
        if candidate.device_id != binding.device_id or candidate.manifest.get("mode") == "replay":
            continue
        if candidate.capability_id == binding.capability_id and candidate.resource == binding.resource:
            continue
        if not candidate.requires_permit or candidate.verb not in ("write", "invoke"):
            continue
        if (candidate.capability_id in achieved_by or candidate.capability_id in STOP_CLASSES
                or candidate.capability_id.startswith(TEST_HOOK_PREFIX)):
            continue
        if _synth.only_empty_input(candidate) is None:
            continue
        if candidate.capability_id == binding.capability_id:
            same = same or candidate
        else:
            other = other or candidate
    return [item for item in (same, other) if item is not None]


def _safe_031_input_free(ctx: SuiteContext, binding: Binding, input_free: str) -> TestOutcome:
    """SAFE-031 for a gated binding whose input schema admits only the empty object.

    The permit is bound to the digest of ``{capability_id, resource, {}}`` (PROTO-036).  A presentation
    with another input never reaches the permit check: the structure check refuses it first (CORE-060
    step 7 before step 10), and a refused command never consumes a permit (CORE-060, SAFE-019).  So the
    distinct-input presentation of the general case is not applicable and is recorded so (the
    ``evidence.note`` of the report entry); what applies is tested, in this order:

    1. without a permit the command is refused (SAFE-030), exactly as for every gated binding;
    2. the permit presented with an undeclared field is refused before any effect (a ``rejected`` receipt or a
       JSON-RPC error, and no bridge call of the capability in-process) and is not consumed;
    3. where the device has another gated binding that also takes only ``{}``, the permit presented for it
       (another resource of the same capability, or another capability) is refused by the permit check:
       the digest binds the capability and the resource too; a refusal before the permit check for another
       reason is reported and not counted;
    4. the permit is accepted for its bound input, which shows that no refusal above consumed it;
    5. the consumed permit is refused when presented again with the same input (single use).

    Expiry and session scope (SAFE-033) and revocation (SAFE-036) hold for every permit whatever its input
    schema; they are not part of this test and have no executable check in this suite version.
    """

    capability_id = binding.capability_id
    device_id = binding.device_id
    payload: dict[str, Any] = {}
    receipt, error = ctx.invoke(capability_id, payload, command_id=canonical.ulid(), device_id=device_id,
                                resource=binding.resource)
    code = _receipt_code(receipt, error)
    if not _code_matches(
        code, ("MHS.SAFETY.PERMIT_REQUIRED", "MHS.SAFETY.APPROVAL_REQUIRED", "MHS.SAFETY.PERMIT_INVALID")
    ):
        return TestOutcome.failed(
            f"gated capability without a permit returned {code or _receipt_status(receipt) or 'success'}"
        )
    try:
        permit = ctx.permit(capability_id, payload, device_id=device_id, resource=binding.resource)
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"mhs.safety.permit failed: {(_error_code(exc) or '')} {exc}".strip())
    permit_id = permit.get("permit_id") if isinstance(permit, Mapping) else None
    if not isinstance(permit_id, str):
        return TestOutcome.failed("permit result has no permit_id")

    # 2. another input: refused before any effect, and the permit is kept
    other_input = {_synth.UNDECLARED_FIELD: {"not": "allowed"}}
    mark = ctx.harness.mark() if ctx.harness is not None else 0
    refused, error = ctx.invoke(capability_id, other_input, command_id=canonical.ulid(), permit_id=permit_id,
                                device_id=device_id, resource=binding.resource)
    refused_code = _receipt_code(refused, error)
    if (_receipt_status(refused) not in _NOT_DISPATCHED
            or not _code_matches(refused_code, _SCHEMA_REFUSALS + _PERMIT_REFUSALS)):
        return TestOutcome.failed(
            f"the permit presented with an undeclared field ({_synth.UNDECLARED_FIELD!r}) returned "
            f"{refused_code or _receipt_status(refused) or 'success'}; {capability_id} admits only the empty "
            "object, so that input must be refused before any effect (MHS.CAPABILITY.INPUT_INVALID, CORE-060 "
            "step 7)"
        )
    if _calls_of(ctx, binding, mark):
        return TestOutcome.failed(
            f"the permit presented with an undeclared field was refused ({refused_code}) but {capability_id} "
            "reached the bridge"
        )

    # 3. another gated binding of the device: the permit's digest names one capability and one resource
    refused_for: list[str] = []
    not_reached: list[str] = []
    for sibling in _input_free_siblings(ctx, binding):
        where = _binding_label(sibling)
        mark = ctx.harness.mark() if ctx.harness is not None else 0
        bad, error = ctx.invoke(sibling.capability_id, {}, command_id=canonical.ulid(), permit_id=permit_id,
                                device_id=device_id, resource=sibling.resource)
        bad_code = _receipt_code(bad, error)
        reached = _calls_of(ctx, sibling, mark)
        if _receipt_status(bad) not in _NOT_DISPATCHED or reached:
            outcome = "reached the bridge" if reached else f"returned a {_receipt_status(bad)!r} receipt"
            return TestOutcome.failed(
                f"the permit of {_binding_label(binding)} was presented for {where} (another input digest) and "
                f"the command {outcome}; a permit is bound to the exact input digest (SAFE-031)"
            )
        if _code_matches(bad_code, _PERMIT_MISMATCH):
            refused_for.append(f"{where} ({bad_code})")
        else:
            not_reached.append(f"{where} ({bad_code or _receipt_status(bad) or 'no receipt'})")

    # 4. the bound input: accepted, so nothing above consumed the permit
    granted, error = ctx.invoke(capability_id, payload, command_id=canonical.ulid(), permit_id=permit_id,
                                device_id=device_id, resource=binding.resource)
    if error is not None or not _is_success(granted):
        return TestOutcome.failed(
            "permit-gated command failed with the issued permit after the refused presentations (a refused "
            f"command never consumes a permit, CORE-060): {_error_code(error) or _receipt_error(granted)}"
        )

    # 5. single use
    again, error = ctx.invoke(capability_id, payload, command_id=canonical.ulid(), permit_id=permit_id,
                              device_id=device_id, resource=binding.resource)
    again_code = _receipt_code(again, error)
    if _receipt_status(again) not in _NOT_DISPATCHED or not _code_matches(again_code, _PERMIT_MISMATCH):
        return TestOutcome.failed(
            f"reused permit with the same input returned {again_code or _receipt_status(again) or 'success'}"
        )
    note = f"distinct-input check not applicable: {_binding_label(binding)}: {input_free}"
    if refused_for:
        scope = "; presented for another gated binding of the device it was refused: " + ", ".join(refused_for)
    else:
        scope = "; the device has no other gated binding that takes only the empty object"
    if not_reached:
        scope += "; refused before the permit check, so not counted: " + ", ".join(not_reached)
    return TestOutcome.passed(
        f"permit required, accepted for the bound input, rejected on reuse ({again_code}); presented first with an "
        f"undeclared field, it was refused before any effect ({refused_code}) and not consumed{scope}; {note}",
        note=note,
    )


def _envelope_bindings(ctx: SuiteContext) -> list[Binding]:
    """Every limited write/invoke binding SAFE-014 probes (replay devices and test hooks aside).

    Permit-gated bindings are included: the limits (plan 3.6 step 8) are
    checked before the permit (step 10), so their probes go without a permit
    and must still be refused with ``ENVELOPE_VIOLATION``.  So are the
    ``safe_state.achieved_by`` actions and the stop classes: they are exempt
    from the latch, the permit, budgets and the device lease, not from limits.
    """

    out = []
    for binding in ctx.bindings:
        if binding.manifest.get("mode") == "replay" or binding.verb not in ("write", "invoke"):
            continue
        if binding.capability_id.startswith(TEST_HOOK_PREFIX):
            continue
        if not binding.bounds:
            continue
        out.append(binding)
    out.sort(key=lambda item: (item.device_id, item.capability_id, item.resource or ""))
    return out


def _violation_paths(receipt: Any, error: BaseException | None) -> list[str]:
    """Concrete paths an ``ENVELOPE_VIOLATION`` names (``details.path`` and ``details.violations[].path``)."""

    data = getattr(error, "data", None) if error is not None else _receipt_error(receipt)
    details = data.get("details") if isinstance(data, Mapping) else None
    if not isinstance(details, Mapping):
        return []
    out = [str(details["path"])] if details.get("path") is not None else []
    for item in details.get("violations") or []:
        if isinstance(item, Mapping) and item.get("path") is not None:
            out.append(str(item["path"]))
    return out


def _receipt_revisions(receipt: Any) -> tuple[Any, Any]:
    if not isinstance(receipt, Mapping):
        return None, None
    return receipt.get("state_revision_before"), receipt.get("state_revision_after")


def _violation_limit_paths(binding: Binding, receipt: Any, error: BaseException | None) -> list[str]:
    """Limit paths of ``binding`` an ``ENVELOPE_VIOLATION`` names (``details.limit_path`` or a concrete path)."""

    data = getattr(error, "data", None) if error is not None else _receipt_error(receipt)
    details = data.get("details") if isinstance(data, Mapping) else None
    if not isinstance(details, Mapping):
        return []
    out: list[str] = []
    for item in [details, *[entry for entry in details.get("violations") or [] if isinstance(entry, Mapping)]]:
        for candidate in (item.get("limit_path"), item.get("path")):
            if candidate is None:
                continue
            limit_path = _synth.limit_path_of(binding, str(candidate))
            if limit_path is not None and limit_path not in out:
                out.append(limit_path)
                break
    return out


def _listing(items: Sequence[str], limit: int = 4) -> str:
    """``a, b, c, ..., z``: the first ``limit`` items and the last one."""

    if len(items) <= limit + 1:
        return ", ".join(items)
    return ", ".join([*items[:limit], "...", items[-1]])


def safe_005(ctx: SuiteContext) -> TestOutcome:
    """SAFE-014: values outside the effective limits are refused with MHS.SAFETY.ENVELOPE_VIOLATION before any effect.

    Limits are resolved exactly like the runtime (``mhs._server.limits_plan``:
    class ∩ binding ∩ envelope, patterns included) and intersected with the
    limits the endpoint publishes (``devices.get`` ``x-mhs-effective-limits``,
    which carry the operator overlay).  Every limited write/invoke binding is
    probed -- permit-gated bindings (sent without a permit: limits come before
    permits, plan 3.6), safe-state actions and stop classes included -- and
    every limited path of it gets shape-correct values just outside both sides
    of its bound (and outside its allowed set), inside the schema range when
    the schema allows one: each nested leaf, the first and the last element of
    every array on the path (``points[*].z``), every element of an array with
    a per-element bound, every class-default bound.  Each probe must be
    ``rejected`` with ``MHS.SAFETY.ENVELOPE_VIOLATION`` (plan 3.5: limits are
    checked before the remaining schema bounds, so ``INPUT_INVALID`` does not
    count even where the schema repeats the bound; a ``PERMIT_*`` refusal does
    not count either), leave the revision unchanged and, in-process, reach no
    bridge method but a state read.

    The test never passes with a limited element or side unprobed: a binding
    without a valid base input, a side without a buildable out-of-limit value
    (an allowed set on a ``pattern`` string no candidate matches) and elements
    beyond the probe budget make it skip, unless a probe that was sent found a
    violation (then it fails).  Without a valid base input, one is derived
    from the ``out_of_envelope`` fixture inputs (their out-of-limit values put
    back inside), and the normal probes run from it; a fixture refusal by
    itself covers only the element and side each named violation proves.  A
    field declared only in an ``anyOf`` / ``oneOf`` branch, or admitted
    without being declared, is probed.  Only a class-default limit on a field
    no valid input of the binding can carry is not applicable (a note): the
    schema, read with the validator's own keywords, rejects every input
    carrying it, and no input built from the base that carries it inside its
    limits validates (RESIDUAL-B).
    """

    bindings = _envelope_bindings(ctx)
    if not bindings:
        return TestOutcome.skipped("endpoint declares no limits on an actuating binding")
    sent = 0
    first_code: str | None = None
    problems: list[str] = []
    notes: list[str] = []
    unproven: list[str] = []
    unreached: list[str] = []
    probed_paths: set[tuple[str, str, str]] = set()
    #: limit paths and concrete paths the refusals of fixture ``out_of_envelope`` inputs named
    fixture_paths: set[tuple[str, str, str]] = set()
    over_budget: list[str] = []
    gaps: list[tuple[str, str, _synth.Gap]] = []
    not_applicable: list[str] = []
    refused: list[str] = []
    in_schema = 0
    for binding in bindings:
        missing = _uninstrumented_problem(ctx, binding.device_id)
        if missing is not None:
            if missing not in unproven:
                unproven.append(missing)
            continue
        for note in binding.limit_notes:
            notes.append(f"{binding.capability_id}: {note}")
        if binding.limits_error:
            notes.append(f"{binding.capability_id}: the runtime cannot enforce the declared limits "
                         f"({binding.limits_error}); it refuses every command of the binding")
        fixture = ctx.fixtures.entry(binding.device_id, binding.capability_id).get("out_of_envelope")
        fixture_inputs = [dict(item) for item in fixture or [] if isinstance(item, Mapping)]
        try:
            base: dict[str, Any] | None = valid_input(binding, ctx.fixtures)[0]
            base_error = None
        except Unsynthesizable as exc:
            base, base_error = None, str(exc)
            # The refused fixture inputs carry the fields only the driver author can
            # supply: with each out-of-limit value put back inside, the normal probes
            # run from them (a refusal alone covers only the element and side it names).
            base = _synth.base_from_fixture(binding, fixture_inputs)
            if base is not None:
                notes.append(f"{binding.capability_id}: the base input of the probes was derived from its "
                             "out_of_envelope fixture")
        plan = envelope_probe_plan(binding, base, base_error=base_error)
        probes = list(plan.probes)
        over_budget.extend(f"{binding.capability_id} {path}" for path in plan.unprobed)
        gaps.extend((binding.device_id, binding.capability_id, gap) for gap in plan.gaps)
        not_applicable.extend(f"{binding.capability_id} {path}" for path in plan.not_applicable)
        for payload in reversed(fixture_inputs):
            probes.insert(0, Probe(binding.capability_id, binding.device_id, "fixture", "fixture", None, None,
                                   payload, True))
        for probe in probes:
            revision = ctx.current_revision(binding.device_id, binding.resource)
            mark = ctx.harness.mark() if ctx.harness is not None else 0
            receipt, error = ctx.invoke(binding.capability_id, probe.payload, device_id=binding.device_id,
                                        resource=binding.resource, command_id=canonical.ulid())
            calls = (ctx.harness.since(mark, device_id=binding.device_id, methods=_ACTUATING_METHODS)
                     if ctx.harness is not None else [])
            sent += 1
            code = _receipt_code(receipt, error)
            label = (f"{binding.capability_id} fixture out_of_envelope {probe.payload}" if probe.kind == "fixture"
                     else f"{binding.capability_id} {probe.path}={probe.value!r} ({probe.kind} {probe.bound!r})")
            if _not_armed(ctx, binding.device_id, mark, receipt, error):
                unreached.append(label)
                continue
            if _is_success(receipt) or not _code_matches(code, _ENVELOPE_REFUSALS):
                expected = "" if _is_success(receipt) else " instead of MHS.SAFETY.ENVELOPE_VIOLATION"
                if _code_matches(code, _PERMIT_REFUSALS):
                    expected += " (limits are checked before permits: plan 3.6 step 8 before step 10)"
                problems.append(f"{label} returned {code or _receipt_status(receipt) or 'success'}{expected}"
                                + _blocked_suffix(ctx, binding.device_id, mark))
                continue
            if receipt is not None and _receipt_status(receipt) != "rejected":
                problems.append(f"{label}: the refusal is a {_receipt_status(receipt)!r} receipt, not 'rejected' "
                                "(a limit is checked before the device is touched)")
                continue
            before, after = _receipt_revisions(receipt)
            if (isinstance(before, int) and isinstance(after, int) and after != before) or \
                    ctx.current_revision(binding.device_id, binding.resource) != revision:
                problems.append(f"{label}: the refusal advanced the revision")
                continue
            if calls:
                methods = ", ".join(sorted({record.method for record in calls}))
                problems.append(f"{label}: the refused command still {_reached(ctx, binding.device_id, mark)} "
                                f"({methods})")
                continue
            first_code = first_code or code
            if probe.kind == "fixture":
                covered = _violation_limit_paths(binding, receipt, error)
                probed_paths.update((binding.device_id, binding.capability_id, path) for path in covered)
                # Only the concrete element and side each named violation proves, never the whole path.
                fixture_paths.update((binding.device_id, binding.capability_id, path, side)
                                     for path in _violation_paths(receipt, error)
                                     for side in _synth.fixture_sides(binding, probe.payload, path))
                refused.append(f"fixture {', '.join(covered) or 'out_of_envelope'}")
                continue
            named = _violation_paths(receipt, error)
            if named and probe.path not in named and probe.limit_path not in named:
                notes.append(f"{label}: refused, but the violation names {', '.join(named[:3])}")
            in_schema += 1 if probe.in_schema else 0
            refused.append(f"{probe.path}={probe.value!r}")
            if probe.limit_path is not None:
                probed_paths.add((binding.device_id, binding.capability_id, probe.limit_path))
    if unproven:
        return TestOutcome.failed("; ".join(unproven[:3]))
    if problems:
        return TestOutcome.failed(
            f"{len(problems)}/{sent} out-of-limit probe(s) not refused with MHS.SAFETY.ENVELOPE_VIOLATION before "
            "any effect: " + "; ".join(problems[:4])
        )
    if unreached:
        return _not_reached(f"{len(unreached)}/{sent} out-of-limit probe(s) ({'; '.join(unreached[:3])})")
    paths = sorted({f"{capability_id} {path}" for _device_id, capability_id, path in probed_paths})
    if not_applicable:
        notes.append("class-default limit(s) on field(s) no valid input of the binding can carry (its input "
                     "schema rejects every input that carries them: nothing can be sent): "
                     + ", ".join(dict.fromkeys(not_applicable)))
    done = (f"{sent} out-of-limit probe(s) refused with MHS.SAFETY.ENVELOPE_VIOLATION before any effect, covering "
            f"{len(paths)} limited path(s){': ' + _listing(paths, 6) if paths else ''}") if sent else \
        "no out-of-limit probe was sent"
    # A gap is covered only by a fixture refusal that names its element with a value on its side; neither a
    # refusal at another element or side nor a synthesized probe ever covers it.
    open_gaps: dict[tuple[str, str, str], list[str]] = {}
    for device_id, capability_id, gap in gaps:
        sides = [gap.kind] if gap.kind else ["max", "min", "allowed"]
        if gap.kind is None and any((device_id, capability_id, gap.path, side) in fixture_paths for side in sides):
            continue
        if gap.kind is not None and (device_id, capability_id, gap.path, gap.kind) in fixture_paths:
            continue
        listed = open_gaps.setdefault((capability_id, gap.path, gap.reason), [])
        if gap.kind and gap.kind not in listed:
            listed.append(gap.kind)
    uncovered = [f"{capability_id} {path} ({'/'.join(kinds) + ': ' if kinds else ''}{reason})"
                 for (capability_id, path, reason), kinds in open_gaps.items()]
    if over_budget or uncovered:
        parts = []
        if uncovered:
            parts.append(f"{len(uncovered)} limited path(s) or element(s) could not be probed: "
                         + "; ".join(uncovered[:4]) + ("; ..." if len(uncovered) > 4 else ""))
        if over_budget:
            parts.append(f"{len(over_budget)} limited path(s) or array element(s) exceed the suite's probe "
                         f"budget ({_synth._MAX_PATH_PROBES} elements per binding) and were not probed: "
                         + _listing(over_budget, 3))
        return TestOutcome.skipped(
            f"{done}, but " + "; and ".join(parts) + "; enforcement of every limit cannot be shown"
            + ("; supply a fixture (valid / out_of_envelope) for them" if uncovered else ""),
            note=("; ".join(notes)[:1000] or None),
        )
    if not sent:
        return TestOutcome.skipped("no out-of-limit probe could be built: " + "; ".join(notes[:3]))
    return TestOutcome.passed(
        f"{sent} out-of-limit probe(s) refused with MHS.SAFETY.ENVELOPE_VIOLATION before any effect "
        f"({in_schema} inside the schema range), covering {len(paths)} limited path(s): {', '.join(paths[:8])}; "
        f"values {', '.join(refused[:12])}",
        mhs_code=normalize_code(first_code),
        note=("; ".join(notes)[:1000] or None),
    )


def safe_006(ctx: SuiteContext) -> TestOutcome:
    features = ctx.hello.get("features") or []
    if isinstance(features, list) and "MHS.SAFETY.NOT_CERTIFIED" in features:
        return TestOutcome.passed("hello advertises MHS.SAFETY.NOT_CERTIFIED")
    return TestOutcome.failed(
        "hello.features does not advertise MHS.SAFETY.NOT_CERTIFIED (required disclosure for CL3+)"
    )


# ---------------------------------------------------------------------------
# CL4 -- reproducible
# ---------------------------------------------------------------------------


def evid_001(ctx: SuiteContext) -> TestOutcome:
    try:
        bundle = ctx.export_evidence()
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"mhs.evidence.export failed: {_error_code(exc) or exc!r}")
    receipts = bundle.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        return TestOutcome.failed("evidence bundle contains no receipts")
    if not _digest_ok(bundle.get("head_digest")):
        return TestOutcome.failed("evidence bundle has no valid head_digest")
    try:
        from mhs.evidence import verify_bundle
    except ImportError:
        return TestOutcome.warned("mhs.evidence verifier unavailable; bundle shape checked only")
    try:
        report = verify_bundle(bundle)
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"evidence verification raised: {exc}")
    if not report.get("valid"):
        details = " ".join(str(item.get("detail") if isinstance(item, Mapping) else item)
                           for item in report.get("errors") or [])
        return TestOutcome.failed(f"offline evidence verification failed: {details[:400]}")
    return TestOutcome.passed(
        f"evidence bundle verified offline ({report.get('checked')} receipts, head {bundle.get('head_digest')})",
        response_digest=bundle.get("head_digest"),
    )


def evid_002(ctx: SuiteContext) -> TestOutcome:
    try:
        from mhs.evidence import verify_bundle
    except ImportError:
        return TestOutcome.skipped("mhs.evidence verifier unavailable")
    try:
        bundle = copy.deepcopy(ctx.export_evidence())
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"evidence export failed: {_error_code(exc) or exc!r}")
    receipts = bundle.get("receipts") or []
    if not receipts:
        return TestOutcome.failed("cannot tamper-test an empty evidence bundle")
    tampered = copy.deepcopy(bundle)
    target = tampered["receipts"][0]
    if isinstance(target, dict):
        target["output"] = {"tampered": True}
        target["status"] = "completed"
    report = verify_bundle(tampered)
    if report.get("valid"):
        return TestOutcome.failed("tampered evidence bundle still verified as valid")
    return TestOutcome.passed(f"tampered bundle rejected: {(report.get('errors') or ['digest mismatch'])[0]}")


def evid_003(ctx: SuiteContext) -> TestOutcome:
    try:
        bundle = ctx.export_evidence()
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"evidence export failed: {_error_code(exc) or exc!r}")
    receipts = bundle.get("receipts") or []
    if not receipts:
        return TestOutcome.failed("evidence bundle contains no receipts")
    previous = None
    seen = []
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, Mapping):
            return TestOutcome.failed(f"receipt {index} is not an object")
        link = receipt.get("evidence")
        if not isinstance(link, Mapping):
            continue
        seen.append(link)
        if previous is not None and link.get("prev_digest") not in (None, previous):
            return TestOutcome.failed(f"receipt {index} prev_digest does not chain to the previous digest")
        if not _digest_ok(link.get("digest")):
            return TestOutcome.failed(f"receipt {index} evidence digest is invalid")
        previous = link.get("digest")
    if not seen:
        return TestOutcome.failed("no receipt carries an evidence chain link")
    if previous is not None and bundle.get("head_digest") != previous:
        return TestOutcome.failed("bundle head_digest does not equal the last receipt evidence digest")
    return TestOutcome.passed(f"evidence chain links verified across {len(seen)} receipt(s)")


def fid_001(ctx: SuiteContext) -> TestOutcome:
    problems = []
    for manifest in ctx.devices:
        mode = manifest.get("mode")
        fidelity = manifest.get("fidelity")
        if mode in ("simulated", "hybrid"):
            if not isinstance(fidelity, Mapping):
                problems.append(f"{manifest.get('device_id')}: simulated device without a fidelity contract")
                continue
            if not fidelity.get("engine"):
                problems.append(f"{manifest.get('device_id')}: fidelity.engine missing")
            if fidelity.get("fidelity_level") not in ("F0", "F1", "F2", "F3"):
                problems.append(f"{manifest.get('device_id')}: fidelity_level invalid")
            determinism = fidelity.get("determinism") or {}
            if determinism.get("kind") not in ("exact", "seeded", "statistical", "none"):
                problems.append(f"{manifest.get('device_id')}: determinism.kind invalid")
            if "gaps" not in fidelity:
                problems.append(f"{manifest.get('device_id')}: fidelity.gaps is not disclosed")
            if determinism.get("kind") == "exact" and fidelity.get("snapshot_restore") is not True:
                problems.append(
                    f"{manifest.get('device_id')}: exact determinism without snapshot_restore breaks CL4 replay"
                )
    if problems:
        return TestOutcome.failed("; ".join(problems[:5]))
    return TestOutcome.passed(f"fidelity contracts disclosed for {len(ctx.devices)} device(s)")


def _replay_sequence(ctx: SuiteContext) -> list[tuple[str, dict[str, Any]]]:
    probe = ctx.probe
    if probe is None:
        raise Unsynthesizable("no probe capability")
    payload = ctx.probe_input()[0]
    second = ctx.probe_alternate(payload) or dict(payload)
    return [(probe.capability_id, payload), (probe.capability_id, second)]


def _run_sequence(ctx: SuiteContext, sequence: Sequence[tuple[str, dict[str, Any]]]) -> list[str | None]:
    hashes: list[str | None] = []
    device_id = ctx.probe.device_id if ctx.probe is not None else None
    resource = ctx.probe.resource if ctx.probe is not None else None
    for capability_id, payload in sequence:
        receipt, error = ctx.invoke(capability_id, payload, device_id=device_id, resource=resource,
                                    command_id=canonical.ulid())
        if error is not None or not _is_success(receipt):
            raise AssertionError(f"replay sequence command failed: {_error_code(error) or _receipt_error(receipt)}")
        state_hash = (receipt or {}).get("state_hash_after")
        if not state_hash:
            state_hash = ctx.read().get("state_hash")
        hashes.append(state_hash)
    return hashes


def _hardware_replay_skip(ctx: SuiteContext, test_id: str) -> TestOutcome | None:
    if str(ctx.primary_device.get("mode")) == "hardware":
        return TestOutcome.skipped(f"hardware device: {test_id} replay is not tested on hardware and does not "
                                   "affect the level (CON-017)")
    return None


def replay_001(ctx: SuiteContext) -> TestOutcome:
    hardware = _hardware_replay_skip(ctx, "FID-016")
    if hardware is not None:
        return hardware
    if ctx.probe is None:
        return _no_probe()
    if not ctx.snapshot_restore_supported():
        return TestOutcome.failed(
            "primary device declares fidelity.snapshot_restore=false; CL4 deterministic replay is impossible"
        )
    try:
        sequence = _replay_sequence(ctx)
    except Unsynthesizable as exc:
        return TestOutcome.skipped(f"no valid input for the replay sequence: {exc}")
    try:
        snapshot = ctx.snapshot()
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"mhs.snapshot failed: {_error_code(exc) or exc!r}")
    if not isinstance(snapshot.get("state_hash"), str):
        return TestOutcome.failed("snapshot result has no state_hash")
    try:
        first_pass = _run_sequence(ctx, sequence)
        ctx.restore(snapshot)
        second_pass = _run_sequence(ctx, sequence)
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"deterministic replay run failed: {exc}")
    if first_pass != second_pass:
        return TestOutcome.failed(f"state_hash sequences differ across restore: {first_pass} vs {second_pass}")
    return TestOutcome.passed(
        f"restored snapshot reproduced identical state_hash sequence ({len(first_pass)} commands)"
    )


def replay_002(ctx: SuiteContext) -> TestOutcome:
    hardware = _hardware_replay_skip(ctx, "FID-025")
    if hardware is not None:
        return hardware
    if ctx.determinism_kind() != "seeded":
        return TestOutcome.skipped("primary device does not declare seeded determinism")
    found = ctx.find_capability_prefix("cap.world.seed.v1")
    if found is None:
        return TestOutcome.failed("seeded device does not expose cap.world.seed.v1")
    seed_capability = found[1]
    if not ctx.snapshot_restore_supported():
        return TestOutcome.failed("seeded device does not support snapshot_restore; seeded replay cannot be tested")
    if ctx.probe is None:
        return _no_probe()
    seed = 42
    try:
        snapshot = ctx.snapshot()
        ctx.invoke_ok(seed_capability["capability_id"], {"seed": seed})
        first_pass = _run_sequence(ctx, _replay_sequence(ctx))
        ctx.restore(snapshot)
        ctx.invoke_ok(seed_capability["capability_id"], {"seed": seed})
        second_pass = _run_sequence(ctx, _replay_sequence(ctx))
    except Unsynthesizable as exc:
        return TestOutcome.skipped(f"no valid input for the replay sequence: {exc}")
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"seeded replay run failed: {exc}")
    if first_pass != second_pass:
        return TestOutcome.failed(f"same seed produced different state_hash sequences: {first_pass} vs {second_pass}")
    return TestOutcome.passed(f"same seed ({seed}) reproduced an identical state_hash sequence")


def replay_003(ctx: SuiteContext) -> TestOutcome:
    manifest = ctx.replay_device
    if manifest is None:
        return TestOutcome.skipped("endpoint does not expose a replay-mode device")
    device_id = manifest["device_id"]
    resource_id = ctx.resource_for(device_id)
    try:
        before = ctx.read(resource_id, device_id)
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"read on replay device failed: {_error_code(exc) or exc!r}")
    if not _digest_ok(before.get("state_hash")):
        return TestOutcome.failed("replay device read returned no state_hash")
    mutation = None
    mutation_input: dict[str, Any] = {}
    capabilities = sorted((item for item in manifest.get("capabilities") or [] if isinstance(item, Mapping)),
                          key=lambda item: str(item.get("capability_id")))
    if capabilities:
        mutation = capabilities[0].get("capability_id")
        mutation_input = _synthesize(capabilities[0].get("input_schema") or {}) or {}
    code = None
    if mutation:
        receipt, error = ctx.invoke(mutation, mutation_input, command_id=canonical.ulid(), device_id=device_id)
        code = _receipt_code(receipt, error)
    if not _code_matches(code, ("MHS.MODE.READ_ONLY", "MHS.RESOURCE.READ_ONLY")):
        return TestOutcome.failed(f"mutation on a replay endpoint returned {code or 'success'}")
    after = ctx.read(resource_id, device_id)
    # CON-025: verify the absence of the forbidden effect, not only the code.
    if after.get("revision") != before.get("revision") or after.get("state_hash") != before.get("state_hash"):
        return TestOutcome.failed("the refused mutation changed the replay device's revision or state")
    try:
        snapshot = ctx.snapshot(device_id)
    except BaseException as exc:  # noqa: BLE001
        return TestOutcome.failed(f"snapshot on replay device failed: {_error_code(exc) or exc!r}")
    if not isinstance(snapshot.get("state_hash"), str):
        return TestOutcome.failed("replay snapshot has no state_hash")
    return TestOutcome.passed(f"replay device is read-only ({code}), unchanged, and snapshots work")


# ---------------------------------------------------------------------------
# Requirement-matrix checks (SPEC-001)
# ---------------------------------------------------------------------------


def _presence_for_level(ctx: SuiteContext, level: str) -> TestOutcome:
    """Probe the methods introduced at ``level`` at the dispatch boundary.

    SPEC-001: an empty-params probe is not evidence.  ``presence.py`` uses a
    method-specific, syntactically valid request, so a deleted method surfaces as
    METHOD_NOT_FOUND instead of a generic pre-dispatch deadline/validation error.
    """

    methods = methods_introduced_at(level)
    if not methods:
        return TestOutcome.skipped(f"no mandatory methods are introduced at {level}")
    missing, unverified, results = check_method_presence(ctx, methods)
    table = probe_table(results)
    if missing or unverified:
        problems = []
        if missing:
            problems.append("METHOD_NOT_FOUND: " + ", ".join(missing))
        if unverified:
            problems.append("presence not established: " + ", ".join(unverified))
        return TestOutcome.failed(
            f"mandatory {level} methods failed dispatch-level presence ({'; '.join(problems)}); probes: {table}",
            mhs_code="MHS.PROTOCOL.METHOD_NOT_FOUND" if missing else None,
        )
    return TestOutcome.passed(
        f"{len(methods)}/{len(methods)} {level} mandatory methods reached dispatch; probes: {table}"
    )


def cap_method_presence_cl1(ctx: SuiteContext) -> TestOutcome:
    return _presence_for_level(ctx, "CL1")


def cap_method_presence_cl2(ctx: SuiteContext) -> TestOutcome:
    return _presence_for_level(ctx, "CL2")


def cap_method_presence_cl3(ctx: SuiteContext) -> TestOutcome:
    return _presence_for_level(ctx, "CL3")


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def _not_replay(ctx: SuiteContext) -> bool:
    return ctx.replay_device is None


TESTS: list[TestCase] = [
    # CL0 -- declared (static, manifest only)
    TestCase("ADPT-005", "device manifests validate against the MHS schema", "CL0", proto_003),
    TestCase("TCON-001", "the profile matches the subject kind and every device mode", "CL0",
             _static.static_profile),
    TestCase("CAP-035", "bound classes are catalogue classes or extensions", "CL0", _static.static_cap_035),
    TestCase("CAP-017", "bindings do not lower their class risk floor", "CL0", _static.static_cap_017),
    TestCase("CAP-016", "binding schemas do not drift from their class (advisory)", "CL0",
             _static.static_cap_016, required=False),
    TestCase("TCAP-002", "bindings target a resource kind their class accepts (advisory)", "CL0",
             _static.static_kind, required=False),
    TestCase("CON-031", "hardware is not actuated without allow_actuation (suite check)", "CL0",
             _static.con_031, post=True),
    TestCase("CON-032", "e-stops are sent only to software/both e-stops (suite check)", "CL0",
             _static.con_032, post=True),
    # CL1 -- observable
    TestCase("TPROTO-901", "every mandatory CL1 method is implemented (dispatch-level probe)",
             "CL1", cap_method_presence_cl1),
    TestCase("TPROTO-902", "every mandatory CL2 method is implemented (dispatch-level probe)",
             "CL2", cap_method_presence_cl2, actuation="inert"),
    TestCase("TPROTO-903", "every mandatory CL3 method is implemented (dispatch-level probe)",
             "CL3", cap_method_presence_cl3, actuation="inert"),
    TestCase("PROTO-013", "mhs.hello negotiates the protocol and lists devices", "CL1", proto_001),
    TestCase("PROTO-021", "devices.list/get return complete manifests", "CL1", proto_002),
    TestCase("PROTO-023", "resource.read returns a verifiable revision and state hash", "CL1", proto_004),
    TestCase("PROTO-024", "reads are stable without mutations", "CL1", proto_005),
    TestCase("SESS-001", "session.open returns a grant, mode and expiry", "CL1", sess_001),
    TestCase("MODE-002", "session mode mismatch is rejected", "CL1", sess_002),
    TestCase("SESS-005", "session heartbeat refreshes the lease", "CL3", sess_003, required=False),
    # CL2 -- actuating
    TestCase("OP-001", "a valid command returns a completed receipt", "CL2", cap_001,
             required=_op001_required, group="OP", actuation="effect"),
    TestCase("TCAP-001", "a completed command's output validates against its output_schema", "CL2", tcap_001,
             required=_probe_required, group="OP", actuation="effect"),
    TestCase("TCAP-003", "a probe command has an observable effect (writes change state)", "CL2", tcap_003,
             required=_effect_check_required, group="OP", actuation="effect"),
    TestCase("OP-003", "command_id idempotency replays without re-execution", "CL2", cap_002,
             required=_probe_required, group="OP", actuation="effect"),
    TestCase("OP-004", "command_id reuse with different input is a conflict", "CL2", cap_003,
             required=_probe_required, group="OP", actuation="effect"),
    TestCase("OP-005", "expected_revision conflicts are rejected", "CL2", cap_004,
             required=_probe_required, group="OP", actuation="negative"),
    TestCase("PROTO-027", "schema-invalid input is rejected without effects", "CL2", cap_005,
             required=_probe_required, group="OP", actuation="negative"),
    TestCase("PROTO-014", "unknown capabilities are rejected", "CL2", cap_006, group="OP", actuation="inert"),
    TestCase("PROTO-030", "operations can be queried for commands", "CL2", cap_007_operations, required=False,
             group="OP", actuation="effect"),
    TestCase("PROTO-011", "deadlines surface as a timeout outcome", "CL2", cap_008_deadline, required=False,
             group="OP", actuation="effect"),
    TestCase("OP-011", "cancellation resolves to a declared safe state", "CL3", cap_009_cancellation,
             required=_cancellation_applies, group="SAFE", actuation="effect"),
    TestCase("OP-013", "unknown-outcome semantics survive a lost receipt", "CL2", cap_010_unknown_outcome,
             required=False, group="OP", actuation="effect"),
    # CL3 -- governed
    TestCase("SAFE-001", "safety.status exposes risk, e-stop, interlocks and safe state", "CL3", safe_001),
    TestCase("SAFE-045", "hardware R2+ devices declare an independent stop path", "CL3",
             _static.static_safe_045, required=_static.safe_045_required),
    TestCase("SAFE-029", "safe_state.achieved_by resolves to bound, permit-free actions", "CL3",
             _static.static_safe_029),
    TestCase("TSAFE-001", "e-stop latches, blocks commands and reset releases it", "CL3", safe_002,
             required=_estop_test_required, group="SAFE", actuation="effect", estops=True),
    TestCase("SAFE-028", "the e-stop reaches the device and its safe state", "CL3", safe_028,
             required=_estop_reach_required, group="SAFE", actuation="effect", estops=True),
    TestCase("SAFE-011", "open interlocks block actuation", "CL3", safe_003, required=_interlock_required,
             group="SAFE", actuation="negative"),
    TestCase("SAFE-012", "interlocks in an unknown state block actuation", "CL3", safe_012,
             required=lambda ctx: ctx.harness is not None and _interlock_required(ctx), group="SAFE",
             actuation="negative"),
    TestCase("SAFE-041", "reset is refused while a hard interlock is open", "CL3", safe_041, required=False,
             group="SAFE", actuation="effect", estops=True),
    TestCase(
        "SAFE-031",
        "gated capabilities require a valid single-use permit",
        "CL3",
        safe_004,
        required=lambda ctx: _not_replay(ctx) and ctx.gated_binding is not None,
        group="SAFE",
        actuation="effect",
    ),
    TestCase("SAFE-014", "safety envelope bounds are enforced before effects", "CL3", safe_005, group="SAFE",
             actuation="negative"),
    TestCase("SAFE-050", "MHS.SAFETY.NOT_CERTIFIED is disclosed in hello", "CL3", safe_006),
    # CL4 -- reproducible
    TestCase("EVID-015", "evidence exports and verifies offline", "CL4", evid_001, group="OP"),
    TestCase("EVID-016", "tampered evidence is detected", "CL4", evid_002, group="OP"),
    TestCase("EVID-010", "receipt evidence links form a hash chain", "CL4", evid_003, group="OP"),
    TestCase("FID-005", "simulated devices disclose a complete fidelity contract", "CL4", fid_001),
    TestCase(
        "FID-016",
        "restore reproduces an identical state_hash sequence",
        "CL4",
        replay_001,
        required=lambda ctx: _not_replay(ctx) and ctx.probe is not None,
        group="FID",
        actuation="effect",
    ),
    TestCase(
        "FID-025",
        "seeded replay reproduces identical sequences for the same seed",
        "CL4",
        replay_002,
        required=lambda ctx: ctx.determinism_kind() == "seeded",
        group="FID",
        actuation="effect",
    ),
    TestCase(
        "MODE-005",
        "replay endpoints are read-only but readable and snapshotable",
        "CL1",
        replay_003,
        required=lambda ctx: ctx.replay_device is not None,
        # Commands only replay-mode devices, which have no actuator.
        actuation="inert",
    ),
]


def cases_for_level(level: str) -> list[TestCase]:
    """Return tests at or below ``level``, in stable registry order (``ValueError`` for an unknown level)."""

    if level not in LEVELS:
        raise ValueError(f"unknown conformance level {level!r}; expected one of {', '.join(LEVELS)}")
    limit = LEVELS.index(level)
    return [case for case in TESTS if LEVELS.index(case.level) <= limit]


def next_level(level: str) -> str:
    index = LEVELS.index(level)
    return LEVELS[index + 1] if index + 1 < len(LEVELS) else level
