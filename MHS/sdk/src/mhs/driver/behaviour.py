"""Gate G6: the behaviour of a driver, checked on fresh in-process endpoints (plan 3.9).

Every group of checks gets a fresh endpoint (a new driver instance, a new
backend object, a new strict :class:`mhs.server.MHSServer`), and bindings and
parameters are visited in sorted order, so a result never depends on the
order a driver declares its capabilities in or on what an earlier group did.
Inputs come from :mod:`mhs.conformance.synth` (the package's
``fixtures/conformance.json``, then the class examples, then envelope-aware
synthesis), exactly as the conformance suite builds them.

Native calls are counted on the :class:`mhs.testing.Recorder` around the
backend object and, independently, at the bridge boundary by the conformance
:class:`~mhs.conformance.inprocess.Harness`.  "Zero native calls" means no
recorded event outside a state read (the runtime reads the state for every
receipt, refused ones included).

Checks (finding codes ``G6.*``):

* ``READ_INVALID`` / ``READ_FAILED`` -- the resource state (every resource of
  a composed package) and every read capability's output match their schemas;
* ``NO_NATIVE_CALL`` / ``OUTPUT_INVALID`` / ``NOT_COMPLETED`` -- an in-range
  write of each parameter and an in-range call of each action complete and
  validate; a write must reach the backend (an action that does not is a
  warning: some are bookkeeping, and G8's effect test catches a do-nothing
  driver); ``UNIT_NOT_SEEN``, a warning, when a declared ``native_unit``
  conversion is not visible in the native arguments;
* ``ENVELOPE_NOT_ENFORCED`` / ``ENVELOPE_GAP`` -- every bound, array element
  and nested leaf just outside its limit is refused with
  ``MHS.SAFETY.ENVELOPE_VIOLATION``, with zero native and zero bridge calls
  and an unchanged revision;
* ``ESTOP_*`` -- an e-stop during a running action cancels it, answers within
  the bound and runs the native stop (when the driver declares one); every
  actuating capability is then refused ``MHS.SAFETY.ESTOP_ENGAGED`` with zero
  native calls;
* ``SENSED_FAIL_OPEN`` -- a sensed-confirmation stop (SAFE-049): with a gate-side
  filter on the transport that withholds every sensed sample, repeats one stamp
  on every sample, or nulls a predicate field, each e-stop must end ``failed``
  ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held (the package's own
  switches do not take part; the stock ``ESTOP_*`` checks run on the converging
  fake);
* ``STALL_FAIL_OPEN`` -- a ROS stall read-back (E1: a stopped world confirmed
  by a value that no longer advances): with a gate-side filter on the
  transport that gives the read-back's value a new value on every answer, as a
  world still running after the pause would, the e-stop must end ``failed``
  ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held (the package's own
  switches do not take part; the stock ``ESTOP_*`` checks run on the fake);
* ``FRESH_FAIL_OPEN`` -- a ROS fresh-sample topic read-back (E2: a stopped
  world confirmed by a boolean state flag in fresh topic samples): with a
  gate-side filter on the transport that (a) gives every sample of the
  read-back topic the opposite flag, as a world still running after the pause
  would, (b) withholds every sample, as a missing bridge would, or (c) answers
  each subscription only with a burst of stale samples that hold the flag, as a
  history replayed on subscribe would, the e-stop must end ``failed``
  ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held;
* ``HOST_FAIL_OPEN`` -- a backend in an isolated simulator host
  (``isolated_process_v1``): with a gate-side filter on the host that makes the
  read-back answer another value, makes the declared stop fail, or kills the host
  process before the stop, each e-stop must end ``failed``
  ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held;
* ``AGENT_RESET_ACCEPTED`` -- on the hardware view of a hardware driver
  (served over the same fake object; the hardware factory is never called)
  an agent's reset of a latched e-stop is refused and the native reset is not
  called;
* ``FAILURE_HIDDEN`` -- a native exception during a write or an action gives
  a ``failed`` receipt (or ``unknown``, when the bridge cannot tell whether the
  command took effect), never ``completed``: first with every actuating native
  call failing, then with only the first one failing (by name), so a driver
  that swallows the failed call and reads back the old value is caught too;
* ``OPERATOR_REQUIRED_*`` -- an ``operator_required`` bound refuses with
  ``MHS.SAFETY.LIMITS_UNSET`` (zero native calls) without an overlay and
  accepts the value under a synthesized narrow-only test overlay; an input
  that carries several such paths (a pose has x, y and z) is tested with one
  overlay that fills them all, and each path must also be refused while the
  others are filled;
  ``OVERLAY_INVALID`` -- the package's ``site-limits.example.json`` (when
  present) is refused by the endpoint (it must only narrow).
"""

from __future__ import annotations

import copy
import os
import signal
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .. import canonical
from ..conformance import synth
from ..conformance.inprocess import Harness
from ..schema import validate as _validate

__all__ = ["BehaviourRun", "Endpoint", "FreshFilter", "SensedFilter", "Session", "StallFilter"]

ESTOP_BOUND_S = 2.0
_DELAY_S = 3.0
_FINAL = ("completed", "failed", "rejected", "cancelled")
_STOP_CLASSES = ("cap.motion.stop.v1", "cap.motion.estop.v1")
_ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
_LATCHED = "MHS.SAFETY.ESTOP_ENGAGED"
_UNSET = "MHS.SAFETY.LIMITS_UNSET"
_PRINCIPAL = {"id": "mhs-driver-gate", "kind": "agent"}
#: Refusals that depend on the device's state, not on the driver contract: an in-range input that meets one is a
#: warning (the gate cannot know the device's state machine; supply fixtures/conformance.json inputs).
_STATEFUL_REFUSALS = ("MHS.DEVICE.PRECONDITION_UNMET", "MHS.DEVICE.BUSY", "MHS.SAFETY.INTERLOCK_OPEN",
                      "MHS.DEVICE.NOT_READY")


class Session:
    """One JSON-RPC session (principal: an agent) on one device of an in-process server."""

    def __init__(self, server: Any, device_id: str):
        self.server = server
        self.device_id = device_id
        self._ids = 0
        self.rpc("mhs.hello", {"protocol_versions": ["1.0"], "client": {"name": "mhs-driver-gate", "version": "0"}})
        device = server.devices[device_id]
        self.mode = device.mode
        opened = self.rpc("mhs.session.open", {"device_ids": [device_id], "mode": device.mode, "ttl_s": 300,
                                               "principal": dict(_PRINCIPAL)})
        self.session_id = opened["session_id"]
        self.resource_id = device.resources[0].resource_id
        #: capability id -> the resources it is bound to (a composed package binds some on extra resources)
        self._bound: dict[str, set[str]] = {}
        for capability in device.capabilities:
            self._bound.setdefault(str(capability.capability_id), set()).add(str(capability.resource))

    def resource_for(self, capability_id: str) -> str:
        """The resource a command of ``capability_id`` goes to: its one binding's resource, else the first one."""
        bound = self._bound.get(capability_id) or set()
        return next(iter(bound)) if len(bound) == 1 else self.resource_id

    def call(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        self._ids += 1
        response = self.server.handle({"jsonrpc": "2.0", "id": self._ids, "method": method, "params": dict(params)})
        return response.to_dict() if hasattr(response, "to_dict") else dict(response)

    def rpc(self, method: str, params: Mapping[str, Any]) -> Any:
        response = self.call(method, params)
        if "error" in response:
            error = response["error"]
            code = ((error.get("data") or {}).get("mhs_code")) or error.get("code")
            raise RuntimeError(f"{method}: {code}: {error.get('message')}")
        return response["result"]

    @staticmethod
    def _settled(receipt: Mapping[str, Any]) -> bool:
        """An ``unknown`` receipt with ``MHS.OUTCOME.UNKNOWN`` is an outcome, not a wait.

        A transport that fails mid-command (the failure injected for ``FAILURE_HIDDEN``) ends the operation as
        unknown and nothing changes that later; polling it would cost the whole bound for every injection.  An
        ``unknown`` with another code (``MHS.OUTCOME.TIMEOUT``) may still resolve and is polled.
        """
        error = receipt.get("error")
        return receipt.get("status") == "unknown" and isinstance(error, Mapping) \
            and error.get("mhs_code") == "MHS.OUTCOME.UNKNOWN"

    def _final(self, receipt: dict[str, Any], timeout_s: float = 15.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        while receipt.get("status") not in _FINAL and receipt.get("operation_id") and not self._settled(receipt) \
                and time.monotonic() < deadline:
            time.sleep(0.01)
            try:
                receipt = self.rpc("mhs.operations.get", {"session_id": self.session_id,
                                                          "operation_id": receipt["operation_id"],
                                                          "deadline_ms": 5000})
            except RuntimeError:
                break
        return receipt

    def _test_permit(self, capability_id: str, payload: Mapping[str, Any]) -> str:
        """One exact-input permit on a simulated gate endpoint, never hardware approval."""
        if self.mode != "simulated":
            raise RuntimeError("G6 test permits require a simulated endpoint; hardware approvals are not invented")
        from ..server import action_digest

        resource = self.resource_for(capability_id)
        permit = self.rpc("mhs.safety.permit", {
            "session_id": self.session_id, "device_id": self.device_id, "resource": resource,
            "capability_id": capability_id, "input": dict(payload),
            "input_digest": action_digest(capability_id, resource, dict(payload)), "ttl_s": 30,
        })
        return permit["permit_id"]

    def command(self, capability_id: str, payload: Mapping[str, Any], *, deadline_ms: int = 10000,
                wait: bool = True, test_permit: bool = False) -> dict[str, Any]:
        params = {"session_id": self.session_id, "device_id": self.device_id,
                  "capability_id": capability_id, "resource": self.resource_for(capability_id),
                  "input": dict(payload), "command_id": canonical.ulid(), "deadline_ms": deadline_ms}
        if test_permit:
            params["permit_id"] = self._test_permit(capability_id, payload)
        receipt = self.rpc("mhs.command", params)
        return self._final(receipt) if wait else receipt

    def write(self, patch: Mapping[str, Any], *, test_permit: bool = False) -> dict[str, Any]:
        params = {"session_id": self.session_id, "device_id": self.device_id,
                  "resource_id": self.resource_id, "patch": dict(patch),
                  "command_id": canonical.ulid(), "deadline_ms": 10000}
        if test_permit:
            params["permit_id"] = self._test_permit("cap.device.configure.v1", patch)
        receipt = self.rpc("mhs.resource.write", params)
        return self._final(receipt)

    def read(self, resource_id: str | None = None) -> dict[str, Any]:
        return self.rpc("mhs.resource.read", {"session_id": self.session_id, "device_id": self.device_id,
                                              "resource_id": resource_id or self.resource_id, "deadline_ms": 5000})

    def estop(self) -> dict[str, Any]:
        return self.rpc("mhs.safety.estop", {"session_id": self.session_id, "device_id": self.device_id,
                                             "reason": "acceptance gate (G6)", "deadline_ms": 5000})

    def reset(self) -> dict[str, Any]:
        return self.call("mhs.safety.reset", {"session_id": self.session_id, "device_id": self.device_id,
                                              "deadline_ms": 5000})

    def inspect(self) -> dict[str, Any]:
        return self.rpc("mhs.devices.get", {"device_id": self.device_id})


@dataclass
class Endpoint:
    """One fresh endpoint: server, harness, session, and the recorder log of its backend object (if any)."""

    server: Any
    harness: Harness
    session: Session
    log: Any
    close: Callable[[], None]

    @property
    def device_id(self) -> str:
        return self.session.device_id

    def mark(self) -> tuple[int, int]:
        return (self.log.mark() if self.log is not None else 0), self.harness.mark()

    def actuations(self, mark: tuple[int, int]) -> tuple[list[Any], list[Any]]:
        native = self.log.actuations(mark[0]) if self.log is not None else []
        bridge = self.harness.actuations(self.device_id, since=mark[1])
        return native, bridge


def _code(receipt: Mapping[str, Any]) -> str | None:
    return (receipt.get("error") or {}).get("mhs_code")


def _brief(receipt: Mapping[str, Any]) -> str:
    error = receipt.get("error") or {}
    text = f"status {receipt.get('status')}"
    if error:
        text += f", {error.get('mhs_code')}: {str(error.get('message'))[:300]}"
    return text


def _numbers(value: Any) -> list[float]:
    import re

    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        out = []
        for token in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", value):
            try:
                out.append(float(token))
            except ValueError:
                continue
        return out
    if isinstance(value, Mapping):
        return [item for member in value.values() for item in _numbers(member)]
    if isinstance(value, (list, tuple)):
        return [item for member in value for item in _numbers(member)]
    return []


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


@dataclass
class BehaviourRun:
    """Runs the G6 checks; ``endpoint(...)`` comes from the gate (it knows how to load the package)."""

    endpoint: Callable[..., Endpoint]
    model: Any
    hardware_view: Callable[[], Endpoint] | None
    fixtures: Any = None
    example_overlay: Mapping[str, Any] | None = None
    hardware_id: str | None = None
    recorded: bool = True
    has_prerequisites: bool = False
    #: a sensed-confirmation stop's sources: topic -> (stamp path, ROS version, a predicate field path) (SAFE-049)
    sensed: Mapping[str, tuple[str, int, str]] | None = None
    #: a ROS stall read-back (E1): ``(service, stall path)``, broken on purpose by :meth:`_stall_fail_open`
    stall: tuple[str, str] | None = None
    #: a ROS fresh-sample topic read-back (E2): ``(topic, flag path, confirming value)``, broken on purpose by
    #: :meth:`_fresh_fail_open`
    fresh: tuple[str, str, bool] | None = None
    #: the backend runs in an isolated simulator host (isolated_process_v1)
    hosted: bool = False
    findings: list[tuple[str, str, str, str | None]] = field(default_factory=list)

    # -- findings ---------------------------------------------------------------
    def error(self, code: str, message: str, path: str | None = None) -> None:
        self._add((f"G6.{code}", message, "error", path))

    def warning(self, code: str, message: str, path: str | None = None) -> None:
        self._add((f"G6.{code}", message, "warning", path))

    def _add(self, finding: tuple[str, str, str, str | None]) -> None:
        if finding not in self.findings:  # several groups may meet the same unbuildable input
            self.findings.append(finding)

    # -- helpers ------------------------------------------------------------------
    def _with(self, fn: Callable[[Endpoint], Any], *, gate_case: str | None = None, **options: Any) -> Any:
        if self.has_prerequisites and gate_case is not None:
            options['gate_case'] = gate_case
        endpoint = self.endpoint(**options)
        try:
            return fn(endpoint)
        finally:
            endpoint.close()

    def _discover(self, endpoint: Endpoint) -> tuple[dict[str, Any], dict[str, synth.Binding]]:
        published = endpoint.session.inspect()
        bindings = {binding.capability_id: binding for binding in synth.bindings_for(published, published)}
        return published, bindings

    def _valid(self, binding: synth.Binding) -> dict[str, Any] | None:
        try:
            payload, _source = synth.valid_input(binding, self.fixtures)
            return payload
        except synth.Unsynthesizable as exc:
            self.warning("NO_INPUT", f"{binding.capability_id}: no valid input can be built ({exc}); add it to "
                         "fixtures/conformance.json", binding.capability_id)
            return None

    def _param_value(self, binding: synth.Binding, name: str) -> Any:
        prop = (binding.schema.get("properties") or {}).get(name)
        if not isinstance(prop, Mapping):
            return None
        schema = {"type": "object", "properties": {name: prop}, "required": [name], "additionalProperties": False}
        fixture = (self.fixtures or synth.Fixtures()).entry(binding.device_id, binding.capability_id)
        valid = fixture.get("valid") if isinstance(fixture, Mapping) else None
        if isinstance(valid, Mapping) and name in valid:
            return copy.deepcopy(valid[name])
        try:
            payload = synth.synthesize(schema, binding.bounds)
        except synth.Unsynthesizable:
            return None
        return payload.get(name) if isinstance(payload, Mapping) else None

    def _check_output(self, binding: synth.Binding, receipt: Mapping[str, Any], what: str) -> bool:
        schema = binding.capability.get("output_schema")
        output = receipt.get("output")
        if isinstance(schema, Mapping) and schema:
            problems = _validate(output if output is not None else {}, schema)
            if problems:
                self.error("OUTPUT_INVALID", f"{what}: the output does not match the output schema: {problems[0]}",
                           binding.capability_id)
                return False
        return True

    def _actuating(self, binding: synth.Binding, achieved_by: Sequence[str]) -> bool:
        return (binding.verb in ("write", "invoke") and binding.capability_id not in _STOP_CLASSES
                and binding.capability_id not in achieved_by)

    # -- the checks ---------------------------------------------------------------
    def run(self) -> list[tuple[str, str, str, str | None]]:
        if not self.recorded:
            self.warning("NOT_RECORDED", "the fake backend is the upstream simulator itself: native calls are not "
                         "recorded (the bridge-boundary checks still apply)")
        published, bindings = self._with(self._discover)
        safety = published.get("safety") or {}
        achieved_by = list((safety.get("safe_state") or {}).get("achieved_by") or [])
        native_stop = (safety.get("estop") or {}).get("native")
        self._reads(bindings)
        configure = bindings.get("cap.device.configure.v1")
        writable = sorted((configure.schema.get("properties") or {})) if configure is not None else []
        for name in writable:
            self._write_param(configure, name)
        for capability_id in sorted(bindings):
            binding = bindings[capability_id]
            if capability_id == "cap.device.configure.v1" or binding.verb == "read":
                continue
            self._invoke(binding)
        for capability_id in sorted(bindings):
            if bindings[capability_id].bounds:
                self._envelope(bindings[capability_id])
        self._estop(bindings, achieved_by, native_stop)
        if self.sensed:
            self._sensed_fail_open()
        if self.stall is not None:
            self._stall_fail_open()
        if self.fresh is not None:
            self._fresh_fail_open()
        if self.hosted:
            self._host_fail_open()
        if self.hardware_view is not None:
            self._agent_reset()
        if self.recorded:
            for capability_id in sorted(bindings):
                binding = bindings[capability_id]
                if capability_id == "cap.device.configure.v1":
                    for name in writable:
                        self._failure(binding, {name: self._param_value(binding, name)}, f"write of {name!r}")
                elif self._actuating(binding, ()) and binding.verb != "read":
                    payload = self._valid(binding)
                    if payload is not None:
                        self._failure(binding, payload, capability_id)
        self._operator_required(bindings)
        if self.example_overlay is not None:
            self._example_overlay()
        return self.findings

    def _example_overlay(self) -> None:
        def loads(endpoint: Endpoint) -> None:
            endpoint.session.inspect()

        try:
            self._with(loads, site_limits=self.example_overlay)
        except Exception as exc:  # noqa: BLE001 - an overlay the endpoint refuses is a finding
            self.error("OVERLAY_INVALID", f"site-limits.example.json is refused by the endpoint ({type(exc).__name__}: "
                       f"{str(exc)[:500]}); an overlay may only narrow the driver's limits", "site-limits.example.json")

    def _reads(self, bindings: Mapping[str, synth.Binding]) -> None:
        def check(endpoint: Endpoint) -> None:
            published = endpoint.session.inspect()
            resource = (published.get("resources") or [{}])[0]
            try:
                state = endpoint.session.read()
            except RuntimeError as exc:
                self.error("READ_FAILED", f"mhs.resource.read failed: {exc}", "state")
                return
            document = state.get("state") if isinstance(state, Mapping) and "state" in state else state
            schema = resource.get("state_schema")
            if isinstance(schema, Mapping):
                problems = _validate(document, schema)
                if problems:
                    self.error("READ_INVALID", f"the resource state does not match its state_schema: {problems[0]}",
                               "state")
            for extra in (published.get("resources") or [])[1:]:
                # A composed package's further resources: each reads back a state that matches its own schema.
                extra_id = str(extra.get("resource_id"))
                try:
                    extra_state = endpoint.session.read(extra_id)
                except RuntimeError as exc:
                    self.error("READ_FAILED", f"mhs.resource.read of resource {extra_id!r} failed: {exc}",
                               f"state.{extra_id}")
                    continue
                extra_document = (extra_state.get("state") if isinstance(extra_state, Mapping)
                                  and "state" in extra_state else extra_state)
                extra_schema = extra.get("state_schema")
                if isinstance(extra_schema, Mapping):
                    problems = _validate(extra_document, extra_schema)
                    if problems:
                        self.error("READ_INVALID", f"the state of resource {extra_id!r} does not match its "
                                   f"state_schema: {problems[0]}", f"state.{extra_id}")
            for name in sorted(self.model_readable()):
                if isinstance(document, Mapping) and name not in document:
                    self.warning("READ_MISSING", f"the state has no value for read parameter {name!r} (its getter "
                                 "returned None or failed)", name)
            for capability_id in sorted(bindings):
                binding = bindings[capability_id]
                if binding.verb != "read":
                    continue
                payload = self._valid(binding)
                if payload is None:
                    continue
                receipt = endpoint.session.command(capability_id, payload)
                if receipt.get("status") != "completed":
                    self.error("READ_FAILED", f"{capability_id} with {payload}: {_brief(receipt)}", capability_id)
                    continue
                self._check_output(binding, receipt, f"{capability_id} with {payload}")

        self._with(check)

    def model_readable(self) -> list[str]:
        return [param.name for param in self.model.params if param.getter is not None]

    def _native_units(self) -> dict[str, tuple[str, str, bool]]:
        out: dict[str, tuple[str, str, bool]] = {}
        for param in self.model.params:
            if param.field.native_unit is not None and param.is_writable:
                out[param.name] = (str(param.field.unit), str(param.field.native_unit), param.field.delta)
        return out

    def _write_param(self, binding: synth.Binding, name: str) -> None:
        value = self._param_value(binding, name)
        if value is None:
            self.warning("NO_INPUT", f"no in-range value can be built for parameter {name!r}; add it to "
                         "fixtures/conformance.json (cap.device.configure.v1 valid)", name)
            return

        def check(endpoint: Endpoint) -> None:
            mark = endpoint.mark()
            receipt = endpoint.session.write({name: value})
            if receipt.get("status") != "completed":
                if _code(receipt) == _UNSET:
                    return  # operator_required: checked with an overlay below
                self._not_completed(f"an in-range write of {name} = {value!r}", receipt, name)
                return
            self._check_output(binding, receipt, f"write of {name} = {value!r}")
            native, _bridge = endpoint.actuations(mark)
            if self.recorded and not native:
                self.error("NO_NATIVE_CALL", f"an in-range write of {name} = {value!r} completed without a native "
                           "call: the setter must reach the device", name)
                return
            conversion = self._native_units().get(name)
            if conversion is not None and self.recorded:
                from .. import units

                unit, native_unit, delta = conversion
                expected = []
                for item in (value if isinstance(value, list) else [value]):
                    try:
                        expected.append(units.convert(float(item), unit, native_unit, delta=delta))
                    except Exception:  # noqa: BLE001 - nothing to compare
                        expected = []
                        break
                seen = [number for call in native for number in _numbers(list(call.args) + list(call.kwargs.values()))]
                if expected and not all(any(_close(item, number) for number in seen) for item in expected):
                    self.warning("UNIT_NOT_SEEN", f"write of {name} = {value!r} {unit}: the native call did not carry "
                                 f"the value in {native_unit} ({expected})", name)

        self._with(check)

    def _not_completed(self, what: str, receipt: Mapping[str, Any], path: str) -> None:
        if receipt.get("status") == "rejected" and _code(receipt) in _STATEFUL_REFUSALS:
            self.warning("NOT_EXERCISED", f"{what} was refused by the device state ({_brief(receipt)}); supply an "
                         "input the fake accepts in fixtures/conformance.json", path)
        else:
            self.error("NOT_COMPLETED", f"{what} was not completed: {_brief(receipt)}", path)

    def _invoke(self, binding: synth.Binding) -> None:
        if binding.requires_permit:
            self.warning("NOT_EXERCISED", f"{binding.capability_id} requires a permit: its in-range call is left to "
                         "the conformance suite (G8)", binding.capability_id)
            return
        payload = self._valid(binding)
        if payload is None:
            return

        def check(endpoint: Endpoint) -> None:
            mark = endpoint.mark()
            receipt = endpoint.session.command(binding.capability_id, payload)
            if receipt.get("status") != "completed":
                if _code(receipt) == _UNSET:
                    return  # operator_required: checked with an overlay below
                self._not_completed(f"{binding.capability_id} with an in-range input {payload}", receipt,
                                    binding.capability_id)
                return
            self._check_output(binding, receipt, f"{binding.capability_id} with {payload}")
            native, _bridge = endpoint.actuations(mark)
            if self.recorded and not native:
                # A warning only: some actions are bookkeeping (a simulator's seed); a do-nothing driver fails
                # the effect test of G8 (TCAP-003) and the parameter writes above.
                self.warning("NO_NATIVE_CALL", f"{binding.capability_id} with {payload} completed without a native "
                             "call: check that the action reaches the device", binding.capability_id)

        self._with(check, gate_case=binding.capability_id)

    def _envelope(self, binding: synth.Binding) -> None:
        if binding.limits_error:
            self.error("ENVELOPE_INVALID", f"{binding.capability_id}: the limits cannot be enforced "
                       f"({binding.limits_error})", binding.capability_id)
            return
        # operator_required fields stay out of the base input: without an overlay they refuse LIMITS_UNSET.
        unset = {path.split(".")[0].split("[")[0] for path in self._operator_paths(binding)}
        if binding.capability_id == "cap.device.configure.v1":
            base: dict[str, Any] | None = {}
            for name in sorted(binding.schema.get("properties") or {}):
                value = self._param_value(binding, name) if name not in unset else None
                if value is not None:
                    base[name] = value
            if not base:
                base = None
        else:
            base = self._valid(binding)
            if base is not None:
                required = set(binding.required_inputs)
                base = {key: value for key, value in base.items() if key not in unset or key in required}
        plan = synth.envelope_probe_plan(binding, base, base_error=None if base is not None else "no valid input")
        if plan.unprobed:
            self.warning("ENVELOPE_UNPROBED", f"{binding.capability_id}: {len(plan.unprobed)} array elements beyond "
                         f"the probe budget were not probed (e.g. {plan.unprobed[0]})", binding.capability_id)
        fixture = (self.fixtures or synth.Fixtures()).entry(binding.device_id, binding.capability_id)
        extra = [dict(item) for item in fixture.get("out_of_envelope") or [] if isinstance(item, Mapping)]
        refused: list[dict[str, Any]] = []

        def send(endpoint: Endpoint, payload: Mapping[str, Any], where: str, path: str) -> bool:
            before = self._revision(endpoint)
            mark = endpoint.mark()
            if binding.capability_id == "cap.device.configure.v1":
                receipt = endpoint.session.write(payload)
            else:
                receipt = endpoint.session.command(binding.capability_id, payload)
            native, bridge = endpoint.actuations(mark)
            after = self._revision(endpoint)
            if receipt.get("status") != "rejected" or _code(receipt) != _ENVELOPE:
                self.error("ENVELOPE_NOT_ENFORCED", f"{where}: expected rejected {_ENVELOPE}, got {_brief(receipt)}",
                           path)
            elif native or bridge:
                self.error("ENVELOPE_NOT_ENFORCED", f"{where}: refused, but {len(native)} native and "
                           f"{len(bridge)} bridge call(s) were made", path)
            elif before is not None and after is not None and before != after:
                self.error("ENVELOPE_NOT_ENFORCED", f"{where}: refused, but the revision changed {before} -> {after}",
                           path)
            else:
                return True
            return False

        def check(endpoint: Endpoint) -> None:
            for probe in plan.probes:
                send(endpoint, probe.payload, f"{binding.capability_id} {probe.path} {probe.kind} {probe.bound!r} "
                     f"(sent {probe.value!r})", probe.path)
            for index, payload in enumerate(extra):
                if send(endpoint, payload, f"{binding.capability_id} fixture out_of_envelope[{index}]",
                        binding.capability_id):
                    refused.append(payload)

        if plan.probes or extra:
            self._with(check)
        for gap in plan.gaps:
            # A fixture input refused for the same element and side covers the gap (as SAFE-014 counts it).
            if any((gap.kind in sides) if gap.kind else bool(sides)
                   for sides in (synth.fixture_sides(binding, payload, gap.path) for payload in refused)):
                continue
            self.error("ENVELOPE_GAP", f"{binding.capability_id}: no out-of-limit input can be built for {gap.path} "
                       f"({gap.kind or 'every side'}: {gap.reason}); add an out_of_envelope input to "
                       "fixtures/conformance.json", gap.path)

    @staticmethod
    def _revision(endpoint: Endpoint) -> Any:
        try:
            return endpoint.session.read().get("revision")
        except (RuntimeError, AttributeError):
            return None

    def _estop(self, bindings: Mapping[str, synth.Binding], achieved_by: Sequence[str], native_stop: Any) -> None:
        candidates = [bindings[key] for key in sorted(bindings) if self._actuating(bindings[key], achieved_by)]
        running: tuple[synth.Binding, dict[str, Any]] | None = None
        for binding in candidates:
            if binding.capability_id == "cap.device.configure.v1":
                patch = {name: self._param_value(binding, name) for name in sorted(binding.schema.get("properties") or {})}
                patch = {key: value for key, value in patch.items() if value is not None}
                if patch and not self._operator_paths(binding):
                    running = (binding, patch)
                    break
                continue
            payload = self._valid(binding) if not binding.requires_permit else None
            if payload is not None and not self._operator_paths(binding):
                running = (binding, payload)
                break

        def check(endpoint: Endpoint) -> None:
            outcome: dict[str, Any] = {}
            worker = None
            if running is not None:
                binding, payload = running

                def send() -> None:
                    try:
                        outcome["receipt"] = endpoint.session.command(binding.capability_id, payload,
                                                                      deadline_ms=int(_DELAY_S * 4000))
                    except Exception as exc:  # noqa: BLE001 - reported below
                        outcome["error"] = exc

                delay = endpoint.harness.delay_calls(endpoint.device_id, binding.capability_id, _DELAY_S)
                delay.__enter__()
                try:
                    worker = threading.Thread(target=send, name="mhs-gate-running-action", daemon=True)
                    worker.start()
                    deadline = time.monotonic() + 3.0
                    while (not endpoint.harness.busy(endpoint.device_id) and worker.is_alive()
                           and time.monotonic() < deadline):
                        time.sleep(0.005)
                    started_running = endpoint.harness.busy(endpoint.device_id)
                    mark = endpoint.mark()
                    started = time.monotonic()
                    estop = endpoint.session.estop()
                    elapsed = time.monotonic() - started
                    worker.join(_DELAY_S * 3)
                finally:
                    delay.__exit__(None, None, None)
            else:
                started_running = False
                mark = endpoint.mark()
                started = time.monotonic()
                estop = endpoint.session.estop()
                elapsed = time.monotonic() - started
            output = estop.get("output") or {}
            expected = ("engaged",) if native_stop else ("engaged", "software_only")
            if estop.get("status") != "completed" or output.get("estop") not in expected:
                self.error("ESTOP_FAILED", f"mhs.safety.estop: {_brief(estop)} (estop {output.get('estop')!r}, "
                           f"expected {' or '.join(expected)})", "estop")
            if elapsed > ESTOP_BOUND_S:
                self.error("ESTOP_SLOW", f"the e-stop took {elapsed:.2f} s with an action running (bound "
                           f"{ESTOP_BOUND_S} s): the @estop method must not wait for a running action", "estop")
            if running is not None and not started_running:
                receipt = outcome.get("receipt") or {}
                self.warning("NOT_EXERCISED", f"{running[0].capability_id} could not be started before the e-stop "
                             f"({_brief(receipt) if receipt else outcome.get('error')}); the e-stop was checked "
                             "without a running action", running[0].capability_id)
            elif running is not None:
                receipt = outcome.get("receipt") or {}
                if receipt.get("status") != "cancelled":
                    self.error("ESTOP_NOT_CANCELLED", f"{running[0].capability_id} running during the e-stop ended "
                               f"{_brief(receipt) if receipt else outcome.get('error')}, expected cancelled",
                               running[0].capability_id)
            if native_stop and self.recorded and endpoint.log is not None:
                stops = endpoint.log.in_phase("estop", mark[0])
                if not stops:
                    self.error("ESTOP_NO_NATIVE", f"the e-stop did not reach the device: the native stop "
                               f"({native_stop}) made no native call (a no-op @estop)", "estop")
            # Safe-state actions the runtime may still be running after the e-stop answered are not counted
            # against the latched refusals below.
            endpoint.harness.wait_idle(endpoint.device_id, timeout=5.0)
            for binding in candidates:
                if binding.capability_id == "cap.device.configure.v1":
                    for name in sorted(binding.schema.get("properties") or {}):
                        value = self._param_value(binding, name)
                        if value is not None:
                            self._latched(endpoint, binding, {name: value}, f"write of {name!r}", write=True)
                    continue
                payload = self._valid(binding)
                if payload is not None:
                    self._latched(endpoint, binding, payload, binding.capability_id)

        self._with(check, gate_case='safety')

    def _sensed_fail_open(self) -> None:
        """SAFE-049: a sensed-confirmation stop that the gate's filters break must stay unconfirmed and latched."""
        assert self.sensed is not None
        cases = (("withhold", "with every sensed sample withheld"),
                 ("frozen", "with one producer stamp repeated on every stamped sample, or a value that contradicts "
                  "the first predicate term when the source has no producer stamp"),
                 ("null", "with a predicate field of every sensed sample nulled"))
        for mode, what in cases:
            def check(endpoint: Endpoint, what: str = what) -> None:
                receipt = endpoint.session.estop()
                output = receipt.get("output") or {}
                if receipt.get("status") != "failed" or _code(receipt) != "MHS.SAFETY.SAFE_STATE_UNREACHED" \
                        or output.get("safe_state_achieved") is not False or output.get("latched") is not True:
                    self.error("SENSED_FAIL_OPEN", f"the sensed-confirmation stop {what}: the e-stop ended "
                               f"{_brief(receipt)} (safe_state_achieved {output.get('safe_state_achieved')!r}, "
                               "latched {0!r}); expected failed MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held"
                               .format(output.get("latched")), "estop")

            sources = dict(self.sensed)
            self._with(check, gate_case="safety",
                       native_filter=lambda native, mode=mode: SensedFilter(native, mode, sources))

    def _stall_fail_open(self) -> None:
        """E1: with the gate's filter advancing the stall read-back's value on every answer (a world that still runs
        after the pause), the e-stop must end failed ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held."""
        assert self.stall is not None
        service, path = self.stall

        def check(endpoint: Endpoint) -> None:
            receipt = endpoint.session.estop()
            output = receipt.get("output") or {}
            if receipt.get("status") != "failed" or _code(receipt) != "MHS.SAFETY.SAFE_STATE_UNREACHED" \
                    or output.get("safe_state_achieved") is not False or output.get("latched") is not True:
                self.error("STALL_FAIL_OPEN", f"with the stall read-back {service} answering a value at {path!r} "
                           f"that advances on every sample, the e-stop ended {_brief(receipt)} (safe_state_achieved "
                           f"{output.get('safe_state_achieved')!r}, latched {output.get('latched')!r}); expected "
                           "failed MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held", "estop")

        self._with(check, gate_case="safety", native_filter=lambda native: StallFilter(native, service, path))

    def _fresh_fail_open(self) -> None:
        """E2: with the gate's filter flipping, withholding or replaying the read-back topic's samples, the e-stop must
        end failed ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held."""
        assert self.fresh is not None
        topic, path, equals = self.fresh
        what = {"flip": f"every sample of {topic} carrying {path} = {not equals!r} (a world still running)",
                "silent": f"every sample of {topic} withheld (no bridge, a silent stream)",
                "replay": f"each subscription to {topic} answered only by a burst of stale samples with {path} = "
                          f"{equals!r} (a history replayed on subscribe)"}
        for mode, text in what.items():
            def check(endpoint: Endpoint, text: str = text) -> None:
                receipt = endpoint.session.estop()
                output = receipt.get("output") or {}
                if receipt.get("status") != "failed" or _code(receipt) != "MHS.SAFETY.SAFE_STATE_UNREACHED" \
                        or output.get("safe_state_achieved") is not False or output.get("latched") is not True:
                    self.error("FRESH_FAIL_OPEN", f"with {text}, the e-stop ended {_brief(receipt)} "
                               f"(safe_state_achieved {output.get('safe_state_achieved')!r}, latched "
                               f"{output.get('latched')!r}); expected failed MHS.SAFETY.SAFE_STATE_UNREACHED with the "
                               "latch held", "estop")

            self._with(check, gate_case="safety",
                       native_filter=lambda native, mode=mode: FreshFilter(native, topic, path, equals, mode))

    def _host_fail_open(self) -> None:
        """isolated_process_v1: a host that does not confirm its stop must leave the e-stop unreached and latched."""
        cases = (("readback", "with the read-back answering a value that is not the declared one"),
                 ("stop", "with the declared stop failing in the host"),
                 ("dead", "with the host process killed before the stop"))
        for mode, what in cases:
            def check(endpoint: Endpoint, what: str = what) -> None:
                receipt = endpoint.session.estop()
                output = receipt.get("output") or {}
                if receipt.get("status") != "failed" or _code(receipt) != "MHS.SAFETY.SAFE_STATE_UNREACHED" \
                        or output.get("safe_state_achieved") is not False or output.get("latched") is not True:
                    self.error("HOST_FAIL_OPEN", f"the simulator host {what}: the e-stop ended {_brief(receipt)} "
                               f"(safe_state_achieved {output.get('safe_state_achieved')!r}, latched "
                               f"{output.get('latched')!r}); expected failed MHS.SAFETY.SAFE_STATE_UNREACHED with the "
                               "latch held", "estop")

            self._with(check, gate_case="safety", native_filter=lambda native, mode=mode: HostFilter(native, mode))

    def _latched(self, endpoint: Endpoint, binding: synth.Binding, payload: Mapping[str, Any], what: str, *,
                 write: bool = False) -> None:
        mark = endpoint.mark()
        receipt = endpoint.session.write(payload) if write else endpoint.session.command(binding.capability_id, payload)
        native, bridge = endpoint.actuations(mark)
        if receipt.get("status") != "rejected" or _code(receipt) != _LATCHED:
            self.error("LATCH_NOT_ENFORCED", f"{what} while latched: expected rejected {_LATCHED}, got "
                       f"{_brief(receipt)}", binding.capability_id)
        elif native or bridge:
            self.error("LATCH_NOT_ENFORCED", f"{what} while latched was refused, but {len(native)} native and "
                       f"{len(bridge)} bridge call(s) were made", binding.capability_id)

    def _agent_reset(self) -> None:
        assert self.hardware_view is not None
        endpoint = self.hardware_view()
        try:
            estop = endpoint.session.estop()
            if estop.get("status") != "completed":
                self.error("ESTOP_FAILED", f"hardware view: mhs.safety.estop: {_brief(estop)}", "estop")
                return
            mark = endpoint.mark()
            response = endpoint.session.reset()
            receipt = response.get("result") or {}
            refused = "error" in response or receipt.get("status") == "rejected"
            resets = endpoint.log.in_phase("reset", mark[0]) if endpoint.log is not None else []
            if not refused:
                self.error("AGENT_RESET_ACCEPTED", f"hardware view: an agent reset a latched e-stop ({_brief(receipt)}); "
                           "only an operator may reset hardware", "reset")
            elif resets:
                self.error("AGENT_RESET_ACCEPTED", "hardware view: the refused agent reset still called the native "
                           "reset", "reset")
        finally:
            endpoint.close()

    def _failure(self, binding: synth.Binding, payload: Mapping[str, Any], what: str) -> None:
        if any(value is None for value in payload.values()) or self._operator_paths(binding, payload):
            return
        if binding.requires_permit:
            return

        def send(endpoint: Endpoint) -> dict[str, Any]:
            if binding.capability_id == "cap.device.configure.v1":
                return endpoint.session.write(payload)
            return endpoint.session.command(binding.capability_id, payload)

        hidden: list[bool] = []

        def check(endpoint: Endpoint) -> None:
            if endpoint.log is None:
                return
            with endpoint.log.fail() as failure:
                receipt = send(endpoint)
            # unknown is honest too: a transport that fails mid-exchange cannot tell whether the command took effect.
            if failure.raised and receipt.get("status") not in ("failed", "unknown"):
                hidden.append(True)
                self.error("FAILURE_HIDDEN", f"{what}: the native call raised, but the receipt is {_brief(receipt)}; "
                           "a native failure must give a failed receipt (raise DriverFailed or let it propagate)",
                           binding.capability_id)

        self._with(check)
        if hidden:
            return

        # Only the first actuating native call fails (every call of that name, so a retry fails too): a driver
        # that swallows it and goes on with other native calls (reading back the old value) must not report success.
        def first(endpoint: Endpoint) -> str | None:
            if endpoint.log is None:
                return None
            mark = endpoint.log.mark()
            if send(endpoint).get("status") != "completed":
                return None
            calls = [call for call in endpoint.log.actuations(mark) if call.phase == "act"]
            return calls[0].name if calls else None

        name = self._with(first)
        if name is None:
            return

        def check_first(endpoint: Endpoint) -> None:
            if endpoint.log is None:
                return
            with endpoint.log.fail(names=[name]) as failure:
                receipt = send(endpoint)
            if failure.raised and receipt.get("status") not in ("failed", "unknown"):
                self.error("FAILURE_HIDDEN", f"{what}: the first native call ({name}) raised, but the receipt is "
                           f"{_brief(receipt)}; a driver never swallows a failed native call and carries on "
                           "(raise DriverFailed or let it propagate)", binding.capability_id)

        self._with(check_first)

    # -- operator_required ------------------------------------------------------------
    @staticmethod
    def _operator_paths(binding: synth.Binding, payload: Mapping[str, Any] | None = None) -> list[str]:
        limits = binding.capability.get("limits") or {}
        paths = sorted(str(path) for path, rule in limits.items() if rule == "operator_required")
        if payload is None:
            return paths
        return [path for path in paths if path.split(".")[0].split("[")[0] in payload]

    def _operator_required(self, bindings: Mapping[str, synth.Binding]) -> None:
        for capability_id in sorted(bindings):
            binding = bindings[capability_id]
            for path in self._operator_paths(binding):
                self._operator_path(binding, path)

    @staticmethod
    def _leaf_of(payload: Mapping[str, Any], tokens: Sequence[Any]) -> Any:
        leaf: Any = payload.get(str(tokens[0]))
        for token in tokens[1:]:
            if isinstance(leaf, Mapping) and isinstance(token, str):
                leaf = leaf.get(token)
            elif isinstance(leaf, list) and isinstance(token, int) and token < len(leaf):
                leaf = leaf[token]
            elif isinstance(leaf, list):
                continue  # [*]: the rule covers every element
            else:
                leaf = None
        return leaf

    @classmethod
    def _test_rule(cls, payload: Mapping[str, Any], tokens: Sequence[Any]) -> dict[str, Any] | None:
        """The narrow-only test overlay rule that admits exactly the value ``payload`` carries at ``tokens``."""
        leaf = cls._leaf_of(payload, tokens)
        numbers = _numbers(leaf)
        if isinstance(leaf, (str, bool)) or (leaf is not None and not numbers):
            rule: dict[str, Any] = {"allowed": [leaf]}
        elif numbers:
            rule = {"min": min(numbers), "max": max(numbers)}
        else:
            return None
        rule.update({"source": "operator", "reason": "acceptance gate test overlay (G6)"})
        return rule

    def _operator_path(self, binding: synth.Binding, path: str) -> None:
        from ..limits import LimitConfigError, parse_path

        try:
            tokens = parse_path(path)
        except LimitConfigError:
            self.error("OPERATOR_REQUIRED_INVALID", f"{binding.capability_id}: operator_required path {path!r} is "
                       "invalid", path)
            return
        top = str(tokens[0])
        configure = binding.capability_id == "cap.device.configure.v1"
        if configure:
            payload: dict[str, Any] | None = {}
            value = self._param_value(binding, top)
            if value is not None:
                payload[top] = value
        else:
            payload = self._valid(binding)
            if payload is not None and top not in payload:
                value = self._param_value(binding, top)
                if value is not None:
                    payload[top] = value
        if not payload or top not in payload:
            self.warning("NO_INPUT", f"{binding.capability_id}: no input carrying operator_required {path!r} can be "
                         "built; add it to fixtures/conformance.json", path)
            return
        rule = self._test_rule(payload, tokens)
        if rule is None and not configure:
            # The valid input leaves the optional container empty (a MuJoCo step's action.ctrl): build the path
            # inside the other limits, as the envelope probes build theirs, so the refusal is exercised.
            from ..limits import WILDCARD

            carried = synth._ensure(payload, binding.schema, binding.bounds,
                                    [0 if token is WILDCARD else token for token in tokens])
            if carried is not None:
                payload = carried
                rule = self._test_rule(payload, tokens)
        if rule is None:
            self.warning("NO_INPUT", f"{binding.capability_id}: operator_required {path!r} has no value to test", path)
            return
        # An input may carry several operator_required paths (a pose has x, y and z): the endpoint refuses it until
        # every one is filled, so the test overlays below fill the companions with the values the payload carries.
        companions: dict[str, dict[str, Any]] = {}
        for other in self._operator_paths(binding, payload):
            if other == path:
                continue
            try:
                companion = self._test_rule(payload, parse_path(other))
            except LimitConfigError:
                continue
            if companion is not None:
                companions[other] = companion
        device = self.hardware_id or binding.device_id

        def overlay_of(rules: Mapping[str, Any]) -> dict[str, Any]:
            entry = dict(rules) if configure else {binding.capability_id: dict(rules)}
            return {"openmhs": "0.9", "site": "acceptance gate (G6)", "devices": {device: entry}}

        def refused(endpoint: Endpoint) -> tuple[bool, str]:
            mark = endpoint.mark()
            receipt = (endpoint.session.write(payload) if configure
                       else endpoint.session.command(binding.capability_id, payload))
            native, bridge = endpoint.actuations(mark)
            if receipt.get("status") != "rejected" or _code(receipt) != _UNSET:
                return False, f"expected rejected {_UNSET}, got {_brief(receipt)}"
            if native or bridge:
                return False, f"refused {_UNSET}, but {len(native)} native and {len(bridge)} bridge call(s) were made"
            return True, ""

        def unset(endpoint: Endpoint) -> None:
            ok, why = refused(endpoint)
            if not ok:
                self.error("OPERATOR_REQUIRED_NOT_ENFORCED", f"{binding.capability_id} {path} is operator_required: "
                           f"without an overlay {why}", path)

        self._with(unset)

        if companions:
            def alone(endpoint: Endpoint) -> None:
                ok, why = refused(endpoint)
                if not ok:
                    self.error("OPERATOR_REQUIRED_NOT_ENFORCED", f"{binding.capability_id} {path} is operator_required: "
                               f"with an overlay that fills {sorted(companions)} but not {path} {why}", path)

            try:
                self._with(alone, site_limits=overlay_of(companions))
            except Exception as exc:  # noqa: BLE001 - an overlay the endpoint refuses is a finding
                self.error("OPERATOR_REQUIRED_OVERLAY", f"{binding.capability_id} {path}: the test overlay of the "
                           f"other paths was refused ({type(exc).__name__}: {exc})", path)

        filled = {path: rule, **companions}

        def overlaid(endpoint: Endpoint) -> None:
            # Limits and authorization are independent. Only this positive fake
            # control obtains an exact-input, single-use stock permit. The
            # missing/partial-overlay probes above remain unpermitted.
            options = {"test_permit": True} if binding.requires_permit else {}
            receipt = (endpoint.session.write(payload, **options) if configure
                       else endpoint.session.command(binding.capability_id, payload, **options))
            if receipt.get("status") != "completed":
                self.error("OPERATOR_REQUIRED_OVERLAY", f"{binding.capability_id} {path}: with a test overlay "
                           f"{filled} the in-range input {payload} was not completed: {_brief(receipt)}", path)

        try:
            self._with(overlaid, site_limits=overlay_of(filled), gate_case=binding.capability_id)
        except Exception as exc:  # noqa: BLE001 - an overlay the endpoint refuses is a finding
            self.error("OPERATOR_REQUIRED_OVERLAY", f"{binding.capability_id} {path}: the test overlay was refused "
                       f"({type(exc).__name__}: {exc})", path)


def _put_path(document: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        if isinstance(document, dict) and part in document:
            document = document[part]
        elif isinstance(document, list) and part.isdigit() and int(part) < len(document):
            document = document[int(part)]
        else:
            return
    last = parts[-1]
    if isinstance(document, dict) and last in document:
        document[last] = value
    elif isinstance(document, list) and last.isdigit() and int(last) < len(document):
        document[int(last)] = value


class HostFilter:
    """The gate's filter between an isolated simulator host and its bridge (G6 ``HOST_FAIL_OPEN``).

    ``readback`` makes the read-back answer ``None`` (never a declared value); ``stop`` makes the declared stop raise;
    ``dead`` kills the host process (SIGKILL) and waits for it to end before the stop is sent. Everything else passes
    through unchanged.
    """

    def __init__(self, target: Any, mode: str):
        if mode not in ("readback", "stop", "dead"):
            raise ValueError(f"unknown host filter {mode!r}")
        self._target = target
        self._mode = mode

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)

    def readback(self) -> Any:
        if self._mode == "readback":
            self._target.readback()
            return None
        return self._target.readback()

    def stop(self) -> Any:
        if self._mode == "stop":
            raise RuntimeError("the gate made the declared stop fail")
        if self._mode == "dead":
            pid = self._target.describe().get("pid")
            if isinstance(pid, int) and pid > 0:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and self._target.state().get("state") not in ("dead", "broken"):
                    time.sleep(0.01)
        return self._target.stop()


class SensedFilter:
    """The gate's filter between a sensed-confirmation device's fake transport and its bridge (G6, SAFE-049).

    ``withhold`` drops every sample of a sensed source; ``frozen`` gives every stamped sample the same producer
    stamp, and on an arrival source (no producer stamp) writes a value that contradicts the first predicate term
    into that term's field (the value is carried on the source tuple: the opposite of a boolean ``equals``, a
    different value of the same type for another ``equals``, and JSON ``true`` for a numeric term, which is not a
    finite number, so the window ends ``sensed_invalid``). A NaN cannot cross the transport's ``allow_nan=False``
    copy and would fail the connection instead of the sample. ``null`` sets a predicate field of every such sample
    to ``null``. Everything else passes through unchanged.
    """

    def __init__(self, target: Any, mode: str, sources: Mapping[str, tuple[str, int, str]]):
        if mode not in ("withhold", "frozen", "null"):
            raise ValueError(f"unknown sensed filter {mode!r}")
        self._target = target
        self._mode = mode
        self._sources = dict(sources)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)

    def recv(self, *, timeout_s: float | None = None) -> Any:
        deadline = time.monotonic() + (0.05 if timeout_s is None else float(timeout_s))
        while True:
            message = self._target.recv(timeout_s=max(0.001, deadline - time.monotonic()))
            topic = message.get("topic") if isinstance(message, dict) else None
            if not (isinstance(message, dict) and message.get("op") == "publish" and topic in self._sources
                    and isinstance(message.get("msg"), dict)):
                return message
            if self._mode == "withhold":
                if time.monotonic() >= deadline:
                    raise TimeoutError("sensed sample withheld by the gate")
                continue
            message = copy.deepcopy(message)
            stamp_path, ros_version, field_path = self._sources[topic][:3]
            freshness = self._sources[topic][3] if len(self._sources[topic]) > 3 else "stamp"
            if self._mode == "frozen" and freshness != "arrival" and stamp_path:
                _put_path(message["msg"], stamp_path,
                          {"secs": 1, "nsecs": 0} if ros_version == 1 else {"sec": 1, "nanosec": 0})
            elif self._mode == "frozen":
                # The fifth tuple member is the contradiction for this term. A short tuple is a numeric field,
                # and JSON true fails that field's finite-number check.
                poison = self._sources[topic][4] if len(self._sources[topic]) > 4 else True
                _put_path(message["msg"], field_path, poison)
            else:
                _put_path(message["msg"], field_path, None)
            return message


class StallFilter:
    """The gate's filter between a stall read-back device's fake transport and its bridge (G6, E1).

    Every answer of the read-back service gets a new value at the stall path, as a world that kept running after the
    pause would give: a number becomes the answer's sequence number, an object (a ROS time ``{sec, nanosec}`` or
    ``{secs, nsecs}``) gets that number in each of its numeric members, anything else becomes it as a string.
    Everything else passes through unchanged.
    """

    def __init__(self, target: Any, service: str, path: str):
        self._target = target
        self._service = service
        self._parts = path.split(".")
        self._count = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)

    def recv(self, *, timeout_s: float | None = None) -> Any:
        message = self._target.recv(timeout_s=timeout_s)
        if not (isinstance(message, dict) and message.get("op") == "service_response"
                and message.get("service") == self._service and isinstance(message.get("values"), dict)):
            return message
        message = copy.deepcopy(message)
        self._count += 1
        holder: Any = message["values"]
        for part in self._parts[:-1]:
            holder = holder.get(part) if isinstance(holder, dict) else None
        last = self._parts[-1]
        if isinstance(holder, dict) and last in holder:
            value = holder[last]
            if isinstance(value, dict):
                holder[last] = {key: (self._count if isinstance(item, (int, float)) and not isinstance(item, bool)
                                      else item) for key, item in value.items()}
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                holder[last] = self._count
            else:
                holder[last] = str(self._count)
        return message


class FreshFilter:
    """The gate's filter between a fresh-sample read-back device's fake transport and its bridge (G6, E2).

    It acts only on ``publish`` messages of the read-back topic; everything else passes through unchanged. Mode
    ``flip`` gives the flag at the read-back path the opposite of the confirming value (a world still running after
    the pause); ``silent`` withholds every such sample (no bridge, a dead stream); ``replay`` withholds the live
    samples but answers each new subscription to the topic with :attr:`DEPTH` back-to-back copies of its first sample
    carrying the confirming value (a history replayed on subscribe, older than the stop request). A withheld sample is
    reported to the reader as a receive timeout, as silence would be.
    """

    DEPTH = 5

    def __init__(self, target: Any, topic: str, path: str, equals: bool, mode: str):
        if mode not in ("flip", "silent", "replay"):
            raise ValueError(f"unknown FreshFilter mode {mode!r}")
        self._target = target
        self._topic = topic
        self._parts = path.split(".")
        self._equals = equals
        self._mode = mode
        self._armed = False
        self._queued: list[Any] = []
        self._lock = threading.Lock()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)

    def send(self, message: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(message, Mapping) and message.get("op") == "subscribe" and message.get("topic") == self._topic:
            with self._lock:
                self._armed = True
        return self._target.send(message, *args, **kwargs)

    def _with_flag(self, message: Any, value: bool) -> Any:
        message = copy.deepcopy(message)
        holder: Any = message.get("msg")
        for part in self._parts[:-1]:
            holder = holder.get(part) if isinstance(holder, dict) else None
        if isinstance(holder, dict):
            holder[self._parts[-1]] = value
        return message

    def recv(self, *, timeout_s: float | None = None) -> Any:
        with self._lock:
            if self._queued:
                return self._queued.pop(0)
        message = self._target.recv(timeout_s=timeout_s)
        if not (isinstance(message, dict) and message.get("op") == "publish" and message.get("topic") == self._topic):
            return message
        if self._mode == "flip":
            return self._with_flag(message, not self._equals)
        if self._mode == "replay":
            with self._lock:
                if self._armed:
                    self._armed = False
                    stale = self._with_flag(message, self._equals)
                    self._queued.extend(copy.deepcopy(stale) for _ in range(self.DEPTH - 1))
                    return stale
        raise TimeoutError("sample withheld by the gate's fresh read-back filter")
