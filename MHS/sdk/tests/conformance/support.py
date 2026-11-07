"""Driver fixtures for the conformance-suite tests, ported from the WP-07 reviewer repros.

Every fixture is an in-process :class:`mhs.server.MHSServer` built from plain
``Device``/``Capability`` objects and a small bridge, so the suite can be run
against it through :class:`Loopback` without sockets.  Ported from the
reviewer scratch (read-only originals):

* ``conformance/inproc_driver.py`` -> :func:`heater_server` (recording fake,
  no-op e-stop, garbage output, hardware mode);
* ``drv-verify/null_driver.py`` + ``driver_v2.py`` -> :func:`null_server`;
* ``tests-run/driver/thermo_driver.py`` / ``thermo_reorder.py`` ->
  :func:`thermostat_server` (plain and ``limits`` variants, both orders);
* ``conformance/classfaithful_check.py`` / ``conformance-verify/v_conf01.py``
  -> :func:`class_faithful_server`;
* ``conformance-verify/v_pattern.py`` -> :func:`pattern_server`;
* ``conformance-verify/v_env.py`` -> :func:`envelope_server`;
* verification round 2 (``verify-WP-07/07a/r2``): ``acc_null.py`` /
  ``acc_null2.py`` -> :func:`null_extension_server`, ``acc_estop.py`` ->
  :func:`noop_safe_state_heater`, ``acc_hw_arm.py`` -> :func:`hardware_arm`;
* milestone 07b: ``fit-robots-ros/arm_probe.py`` / ``driver-authoring/arm_probe.py``
  (DRV-02, FIT-ROS-01, CONF-06: published array/nested limits the endpoint does
  not enforce) -> :class:`LimitBlindServer` + :func:`limited_arm`;
  ``conformance-verify/v_readverb.py`` (TESTS-04: a read advances the
  revision) -> :class:`ReadBumpServer`; :class:`NoopBumpServer`;
* milestone 07b verification fix (``verify-WP-07/07b/adv``): ``a_permit.py``
  -> :func:`limited_arm` ``permit_joint``; ``b_laser.py`` ->
  :func:`laser_server`; ``e_middle.py`` / ``f_trunc.py`` -> the ``middle`` and
  ``last_axis`` :data:`BLIND_RULES` and :func:`many_axes_server`;
  ``g_readbump.py`` -> :func:`world_state_heater` + :class:`WorldStateBumpServer`;
  :class:`SafeStateOnRefusalServer` (a refusal that drives ``Bridge.safe_state``);
* milestone 07b verification fix round 2 (``verify-WP-07/07b/r2/adv``):
  ``h_unsynth.py`` / ``i_allowed_pattern.py`` -> :func:`tool_arm` and the
  ``speed``/``gear`` :data:`BLIND_RULES`; ``j_tail_budget.py`` ->
  :func:`many_axes_server` ``array``; ``m_wildcard_tail.py`` ->
  :func:`points_server`; ``k_ext_read.py`` -> :func:`ext_read_heater` +
  :class:`ExtReadBumpServer`.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Iterable, Mapping, Sequence

from mhs import catalog
from mhs.bridge.base import Bridge
from mhs.client import MHSClient
from mhs.errors import MHSError
from mhs.schema import validate as schema_validate
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

ENDPOINT_ID = "mhs://localhost/test"

#: Fidelity contract of a fake backend standing in for hardware (WP-06 rule).
FAKE_FIDELITY = {
    "engine": "fake",
    "fidelity_level": "F0",
    "determinism": {"kind": "seeded"},
    "timestep_ms": 0,
    "realtime_factor": 0,
    "reset": "full",
    "snapshot_restore": False,
    "gaps": ["transport replaced by fake backend"],
}

#: Native calls of the recording fakes that actuate (reads are not listed).
NATIVE_ACTUATION = ("set_setpoint", "stop", "set_lid")


class Loopback:
    """Test-private in-process transport (the suite's own one lives in mhs.conformance.inprocess)."""

    kind = "loopback"
    timeout = 30.0

    def __init__(self, server: Any):
        self.server = server
        self.methods: list[str] = []

    def request(self, message: Mapping[str, Any], timeout: float | None = None) -> Any:
        self.methods.append(str(message.get("method")))
        response = self.server.handle(message)
        return response.to_dict() if hasattr(response, "to_dict") else response

    def drain_notifications(self) -> list[dict[str, Any]]:
        return []

    def close(self) -> None:
        pass


def client_for(server: Any) -> MHSClient:
    client = MHSClient(Loopback(server))
    client.hello()
    return client


def class_schema(capability_id: str, which: str = "input_schema") -> dict[str, Any]:
    return copy.deepcopy(catalog.get(capability_id)[which])


# ---------------------------------------------------------------------------
# heater (conformance/inproc_driver.py)
# ---------------------------------------------------------------------------


class FakeHeater:
    """Recording fake of a heater controller's native surface."""

    def __init__(self) -> None:
        self.setpoint = 20.0
        self.heater_on = True
        self.native_calls: list[tuple[Any, ...]] = []

    def set_setpoint(self, value: float) -> None:
        self.native_calls.append(("set_setpoint", value))
        self.setpoint = float(value)
        self.heater_on = True

    def stop(self) -> None:
        self.native_calls.append(("stop",))
        self.heater_on = False

    def set_lid(self, state: str) -> None:
        self.native_calls.append(("set_lid", state))

    def status(self) -> dict[str, Any]:
        return {"setpoint": self.setpoint, "heater_on": self.heater_on}

    def actuations(self) -> list[tuple[Any, ...]]:
        return [call for call in self.native_calls if call[0] in NATIVE_ACTUATION]


class HeaterBridge(Bridge):
    bridge_kind = "python-object"
    bridge_id = "tests.conformance.heater"

    def __init__(self, backend: FakeHeater, *, device_id: str, implement_estop: bool = True,
                 garbage_output: bool = False, interlock_state: str | None = None):
        super().__init__(device_id=device_id)
        self.backend = backend
        self.implement_estop = implement_estop
        self.garbage_output = garbage_output
        self.interlock_state = interlock_state

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == "cap.thermal.setpoint.v1":
            if self.garbage_output:
                return {"totally": "wrong", "setpoint": "not-a-number"}
            self.backend.set_setpoint(float(args["target_temperature"]))
            return {"setpoint": self.backend.setpoint}
        if capability_id == "cap.measure.temperature.v1":
            return {"temperature": self.backend.setpoint, "sampled_at": "2026-10-21T00:00:00Z"}
        if capability_id == "x-cap.example.heater_off.v1":
            self.backend.stop()
            return {"stopped": True}
        if capability_id == "x-cap.mhs-test.set_door.v1":
            # The reference-style door hook (conformance/door_hook.py): opens the lid interlock.
            self.backend.set_lid(str(args["state"]))
            self.interlock_state = "open" if args["state"] == "open" else "closed"
            return {"door": args["state"]}
        return super().call(capability_id, args, ctx)

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return self.backend.status()

    def interlocks(self) -> list[dict[str, str]]:
        if self.interlock_state is None:
            return []
        return [{"id": "lid_closed", "state": self.interlock_state, "description": "heater lid closed"}]

    def safety_status(self) -> dict[str, Any]:
        return {"safe_state": {"description": "heater off", "achieved": not self.backend.heater_on}}

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        if self.implement_estop:
            self.backend.stop()
        return {"estop": "engaged"}


HEATER_ID = ENDPOINT_ID + "/heater"


def heater_server(
    *,
    mode: str = "simulated",
    implement_estop: bool = True,
    garbage_output: bool = False,
    envelope: bool = True,
    setpoint_first: bool = True,
    risk: str = "R2",
    estop: Mapping[str, Any] | None = None,
    achieved_by: Iterable[str] = (),
    heater_off: bool = False,
    interlock: bool = False,
    envelope_key: str = "cap.thermal.setpoint.v1",
    capability_limits: Mapping[str, Any] | None = None,
    cancellable: bool = False,
    door_hook: bool = False,
    bridge_class: type | None = None,
    resource_kind: str = "thermal.zone",
    server_options: Mapping[str, Any] | None = None,
    server_class: type | None = None,
) -> tuple[MHSServer, FakeHeater]:
    """A heater with a recording fake backend; returns ``(server, backend)``.

    ``server_options`` are passed to :class:`MHSServer` (for example
    ``strict=True`` with ``resource_kind="instrument.incubator"``, a kind both
    bound classes accept, ``armed=...`` or ``site_limits=...``);
    ``server_class`` replaces :class:`MHSServer` (a misbehaving endpoint).
    """

    backend = FakeHeater()
    bridge = (bridge_class or HeaterBridge)(backend, device_id=HEATER_ID, implement_estop=implement_estop,
                                            garbage_output=garbage_output,
                                            interlock_state="closed" if interlock else None)
    setpoint = Capability(
        "cap.thermal.setpoint.v1",
        "heater",
        title="Set heater setpoint",
        verb="write",
        input_schema={
            "type": "object",
            "required": ["target_temperature"],
            "properties": {"target_temperature": {"type": "number", "minimum": 0, "maximum": 200, "x-mhs-unit": "Cel"}},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "required": ["setpoint"],
            "properties": {"setpoint": {"type": "number", "x-mhs-unit": "Cel"}},
            "additionalProperties": False,
        },
        constraints={"concurrency": "exclusive", "cancellable": cancellable,
                     "max_duration_ms": 10000 if cancellable else 1000},
        exclusive=True,
        limits=dict(capability_limits) if capability_limits else None,
    )
    measure = Capability(
        "cap.measure.temperature.v1",
        "heater",
        title="Measure temperature",
        verb="read",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema=class_schema("cap.measure.temperature.v1", "output_schema"),
        constraints={"concurrency": "shared", "cancellable": False, "max_duration_ms": 1000},
    )
    capabilities = [setpoint, measure] if setpoint_first else [measure, setpoint]
    if heater_off:
        capabilities.append(Capability(
            "x-cap.example.heater_off.v1", "heater", title="Heater off (safe state)",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"stopped": {"type": "boolean"}}},
        ))
    if door_hook:
        capabilities.append(Capability(
            "x-cap.mhs-test.set_door.v1", "heater", title="Open or close the lid (test hook)",
            input_schema={"type": "object", "required": ["state"],
                          "properties": {"state": {"type": "string", "enum": ["open", "closed"]}},
                          "additionalProperties": False},
            output_schema={"type": "object", "properties": {"door": {"type": "string"}}},
        ))
    safety = SafetyEnvelope(
        risk_class=risk,
        envelope={envelope_key: {"target_temperature": {"min": 0, "max": 80, "unit": "Cel",
                                                        "reason": "sample block rating"}}} if envelope else {},
        estop=dict(estop or {"kind": "software", "latching": True, "latency_ms": 100}),
        safe_state={"description": "heater off", "achieved_by": list(achieved_by)},
        interlocks=[{"id": "lid_closed", "required_for": ["cap.thermal.*"], "description": "heater lid closed"}]
        if interlock else [],
    )
    resource = Resource(
        "heater", resource_kind,
        state_schema={"type": "object", "properties": {"setpoint": {"type": "number", "x-mhs-unit": "Cel"},
                                                       "heater_on": {"type": "boolean"}}},
        state=backend.status(),
    )
    device = Device(
        HEATER_ID, "Heater", mode=mode, resources=[resource], capabilities=capabilities, safety=safety,
        fidelity=copy.deepcopy(FAKE_FIDELITY) if mode == "simulated" else None,
        models=[HEATER_ID + "-hardware"] if mode == "simulated" else None,
        instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V99", bridge=bridge,
    )
    options = {"log_ready": False, **dict(server_options or {})}
    return (server_class or MHSServer)(endpoint_id=ENDPOINT_ID, devices=[device], **options), backend


def hardware_heater(**options: Any) -> tuple[MHSServer, FakeHeater]:
    """A correctly declared R2 hardware heater (e-stop 'both' with a physical reference)."""

    options.setdefault("mode", "hardware")
    options.setdefault("estop", {"kind": "both", "latching": True, "latency_ms": 100,
                                 "physical_ref": "front-panel mushroom e-stop (manual section 4.2)"})
    options.setdefault("heater_off", True)
    options.setdefault("achieved_by", ["x-cap.example.heater_off.v1"])
    return heater_server(**options)


# ---------------------------------------------------------------------------
# null driver (drv-verify/null_driver.py over driver_v2.py)
# ---------------------------------------------------------------------------


class NullBridge(Bridge):
    """Accepts everything and does nothing (DRV-08)."""

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return {}

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        return {}


NULL_ID = ENDPOINT_ID + "/lab/thermo"


def null_server(*, mode: str = "hardware") -> MHSServer:
    capabilities = [
        Capability(
            "cap.thermal.setpoint.v1", "thermal", verb="write", exclusive=True, title="Set block setpoint",
            input_schema={"type": "object", "required": ["target_temperature"],
                          "properties": {"target_temperature": {"type": "number", "x-mhs-unit": "Cel",
                                                                "minimum": 4, "maximum": 95}},
                          "additionalProperties": False},
            constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 2000},
        ),
        Capability(
            "cap.measure.temperature.v1", "thermal", verb="read", title="Measure temperature",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        Capability(
            "x-cap.example.heater_off.v1", "thermal", title="Heater off (safe state)",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
    ]
    safety = SafetyEnvelope(
        risk_class="R2",
        envelope={"cap.thermal.setpoint.v1": {"target_temperature": {"min": 4, "max": 95, "unit": "Cel",
                                                                     "reason": "sample block rating"}}},
        interlocks=[],
        estop={"kind": "software", "latching": True},
        safe_state={"description": "heater off", "achieved_by": ["x-cap.example.heater_off.v1"]},
    )
    device = Device(
        NULL_ID, "Fake temperature controller", mode=mode,
        resources=[Resource("thermal", "thermal.zone", state_schema={"type": "object"})],
        capabilities=capabilities, safety=safety,
        fidelity=copy.deepcopy(FAKE_FIDELITY) if mode == "simulated" else None,
        conformance={"profile": "MHS-Device" if mode == "hardware" else "MHS-Sim", "level": "CL0"},
        bridge=NullBridge(device_id=NULL_ID),
    )
    return MHSServer(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False)


def null_factory() -> MHSServer:
    """Zero-argument factory for ``--factory tests.conformance.support:null_factory``."""
    return null_server()


def null_sim_factory() -> MHSServer:
    return null_server(mode="simulated")


NULL_ARM_ID = ENDPOINT_ID + "/arm"


def null_invoke_server(*, mode: str = "simulated", output_schema: Mapping[str, Any] | None = None,
                       estop_kind: str = "software", envelope: Mapping[str, Any] | None = None) -> MHSServer:
    """A null Bridge behind an invoke class with a permissive output schema (verifier null_variants.py).

    ``cap.motion.joint_position.v1`` takes the class input; the binding's
    ``output_schema`` is the skeleton ``{"type": "object"}`` (so the class
    output applies), ``achieved_by`` names a no-op halt and ``estop()`` is the
    inherited no-op.
    """

    entry = catalog.get("cap.motion.joint_position.v1")
    capabilities = [
        Capability("cap.motion.joint_position.v1", "arm", verb="invoke",
                   input_schema=copy.deepcopy(entry["input_schema"]),
                   output_schema=dict(output_schema) if output_schema is not None else {"type": "object"},
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}),
        Capability("x-cap.example.halt.v1", "arm", title="halt",
                   input_schema={"type": "object", "properties": {}, "additionalProperties": False}),
    ]
    device = Device(
        NULL_ARM_ID, "Null arm", mode=mode,
        resources=[Resource("arm", "robot.arm", state_schema={"type": "object"})],
        capabilities=capabilities,
        safety=SafetyEnvelope(risk_class="R2", envelope=dict(envelope or {}),
                              estop={"kind": estop_kind, "latching": True, "latency_ms": 100},
                              safe_state={"description": "halt", "achieved_by": ["x-cap.example.halt.v1"]}),
        fidelity=copy.deepcopy(FAKE_FIDELITY) if mode == "simulated" else None,
        instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V55", bridge=NullBridge(device_id=NULL_ARM_ID),
    )
    return MHSServer(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False)


NULL_EXT_ID = ENDPOINT_ID + "/ext"


class NoopEstopNullBridge(NullBridge):
    """A null bridge that overrides ``estop()`` with a no-op (verifier r2/acc_null2.py)."""

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        return {}


def null_extension_server(*, mode: str = "hardware", noop_estop: bool = False) -> MHSServer:
    """A null Bridge whose only probe is an ``x-cap`` extension (verifier r2/acc_null.py ``null_ext``).

    ``x-cap.acme.move.v1`` has a permissive ``output_schema`` (``{"type": "object"}``)
    and no catalogue class, so there is no class output to enforce; the device
    declares an envelope, an independent stop path and a no-op ``achieved_by``
    halt.  ``noop_estop`` overrides ``estop()`` with a no-op so the inherited
    no-op check cannot catch it.
    """

    capabilities = [
        Capability("x-cap.acme.move.v1", "arm", title="move", verb="invoke",
                   input_schema={"type": "object", "required": ["x"],
                                 "properties": {"x": {"type": "number", "minimum": -100, "maximum": 100}},
                                 "additionalProperties": False},
                   output_schema={"type": "object"},
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}),
        Capability("x-cap.acme.halt.v1", "arm", title="halt",
                   input_schema={"type": "object", "properties": {}, "additionalProperties": False}),
    ]
    estop = ({"kind": "software", "latching": True, "latency_ms": 100} if mode == "simulated"
             else {"kind": "both", "latching": True, "latency_ms": 100, "physical_ref": "panel"})
    safety = SafetyEnvelope(
        risk_class="R2",
        envelope={"x-cap.acme.move.v1": {"x": {"min": -50, "max": 50, "unit": "mm", "reason": "travel"}}},
        estop=estop,
        safe_state={"description": "halt", "achieved_by": ["x-cap.acme.halt.v1"]},
    )
    bridge = (NoopEstopNullBridge if noop_estop else NullBridge)(device_id=NULL_EXT_ID)
    device = Device(NULL_EXT_ID, "Null extension arm", mode=mode,
                    resources=[Resource("arm", "robot.arm", state_schema={"type": "object"})],
                    capabilities=capabilities, safety=safety,
                    fidelity=copy.deepcopy(FAKE_FIDELITY) if mode == "simulated" else None,
                    instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V44", bridge=bridge)
    return MHSServer(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False)


class NoopSafeStateHeaterBridge(HeaterBridge):
    """``estop()`` and the declared ``achieved_by`` action both do nothing (verifier r2/acc_estop.py).

    The bridge's own ``safety_status()`` honestly reports
    ``safe_state.achieved: false`` because the heater stays on.
    """

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == "x-cap.example.heater_off.v1":
            return {"stopped": True}
        return super().call(capability_id, args, ctx)


def noop_safe_state_heater(**options: Any) -> tuple[MHSServer, FakeHeater]:
    options.setdefault("implement_estop", False)
    options.setdefault("heater_off", True)
    options.setdefault("achieved_by", ["x-cap.example.heater_off.v1"])
    options.setdefault("bridge_class", NoopSafeStateHeaterBridge)
    return heater_server(**options)


# ---------------------------------------------------------------------------
# hardware arm with a per-joint envelope (verifier r2/acc_hw_arm.py)
# ---------------------------------------------------------------------------


class FakeArm:
    """Recording fake of an arm controller's native surface."""

    def __init__(self) -> None:
        self.q = [0.0, 0.0, 0.0]
        self.native_calls: list[tuple[Any, ...]] = []

    def move_joints(self, q: Sequence[float]) -> None:
        self.native_calls.append(("move_joints", list(q)))
        self.q = list(q)

    def halt(self) -> None:
        self.native_calls.append(("halt",))

    def actuations(self) -> list[tuple[Any, ...]]:
        return [call for call in self.native_calls if call[0] in ("move_joints", "halt")]


class FakeArmBridge(Bridge):
    def __init__(self, native: FakeArm, **kwargs: Any):
        super().__init__(**kwargs)
        self.native = native

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return {"q": list(self.native.q)}

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == "cap.motion.joint_position.v1":
            self.native.move_joints(args["joint_positions"])
            return {"reached": True, "joint_positions": list(self.native.q)}
        if capability_id == "x-cap.acme.halt.v1":
            self.native.halt()
            return {"halted": True}
        return super().call(capability_id, args, ctx)

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        self.native.halt()
        return {"estop": "engaged"}


HW_ARM_ID = ENDPOINT_ID + "/hw-arm"


def hardware_arm(*, scalar: bool = False, mode: str = "hardware") -> tuple[MHSServer, FakeArm]:
    """An R2 hardware arm whose ``joint_positions`` envelope is per joint (or a scalar ±1 rad)."""

    entry = catalog.get("cap.motion.joint_position.v1")
    schema = copy.deepcopy(entry["input_schema"])
    schema["properties"]["joint_positions"]["minItems"] = 3
    schema["properties"]["joint_positions"]["maxItems"] = 3
    capabilities = [
        Capability("cap.motion.joint_position.v1", "arm", verb="invoke", input_schema=schema,
                   output_schema=copy.deepcopy(entry["output_schema"]),
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}),
        Capability("x-cap.acme.halt.v1", "arm", title="halt",
                   input_schema={"type": "object", "properties": {}, "additionalProperties": False}),
    ]
    bounds = ({"min": -1.0, "max": 1.0} if scalar else {"min": [-1.0, -0.5, -2.0], "max": [1.0, 0.5, 2.0]})
    safety = SafetyEnvelope(
        risk_class="R2",
        envelope={"cap.motion.joint_position.v1": {"joint_positions": dict(bounds, unit="rad",
                                                                           reason="joint travel")}},
        estop={"kind": "both", "latching": True, "latency_ms": 100, "physical_ref": "teach pendant e-stop"},
        safe_state={"description": "halted", "achieved_by": ["x-cap.acme.halt.v1"]},
    )
    native = FakeArm()
    device = Device(HW_ARM_ID, "Arm", mode=mode,
                    fidelity={"engine": "fake", "fidelity_level": "F0", "determinism": {"kind": "exact"},
                              "snapshot_restore": False, "gaps": ["fake"]} if mode == "simulated" else None,
                    resources=[Resource("arm", "robot.arm", state_schema={"type": "object"})],
                    capabilities=capabilities, safety=safety, instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V22",
                    bridge=FakeArmBridge(native, device_id=HW_ARM_ID))
    return MHSServer(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False), native


def r0_thermostat_factory() -> MHSServer:
    """``--factory`` target: the original R0 thermostat (CAP-017 fails at CL0)."""
    return thermostat_server(risk="R0")


def typo_thermostat_factory() -> MHSServer:
    """``--factory`` target: the typo thermostat (CAP-035 fails at CL0)."""
    return thermostat_server(variant="typo")


def thermostat_factory() -> MHSServer:
    return thermostat_server()


class SealedHeaterBridge(HeaterBridge):
    """A bridge whose contract-plane methods cannot be shadowed on the instance."""

    _sealed = ("call", "write", "restore")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._sealed and hasattr(type(self), name):
            raise AttributeError(f"{type(self).__name__}.{name} is read-only")
        super().__setattr__(name, value)


# ---------------------------------------------------------------------------
# thermostat (tests-run/driver/thermo_driver.py, thermo_reorder.py)
# ---------------------------------------------------------------------------


class ThermoBridge(Bridge):
    bridge_id = "scratch.thermo"

    def __init__(self, device_id: str):
        super().__init__(device_id=device_id)
        self.state = {"temperature": 21.0, "setpoint": 21.0}
        self.effects = 0

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return copy.deepcopy(self.state)

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        args = dict(args or {})
        if capability_id in ("cap.thermal.setpoint.v1", TYPO_SETPOINT):
            self.effects += 1
            self.state["setpoint"] = float(args["target_temperature"])
            self.state["temperature"] = self.state["setpoint"]
            return {"output": {"setpoint": self.state["setpoint"]}, "state": {"zone": copy.deepcopy(self.state)}}
        if capability_id == "cap.measure.temperature.v1":
            return {"output": {"temperature": self.state["temperature"], "sampled_at": "2026-10-21T00:00:00Z"}}
        return super().call(capability_id, args, ctx)

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        return {"zone": copy.deepcopy(self.state)}

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self.state = copy.deepcopy(snapshot["zone"])
        return {"zone": copy.deepcopy(self.state)}


THERMO_ID = ENDPOINT_ID + "/lab/thermo"
#: The reviewer's typo variant (tests-run/driver/thermo_driver.py ``typo``): not a catalogue class.
TYPO_SETPOINT = "cap.thermal.setpiont.v1"


def thermostat_server(*, variant: str = "plain", setpoint_first: bool = False, risk: str = "R2") -> MHSServer:
    """The 'DeepSeek-style' thermostat; ``variant`` is ``plain``, ``limits`` or ``typo``.

    The original declared risk R0, below the R2 floor of cap.thermal.setpoint.v1
    (a CAP-017 failure at CL0); the port declares R2 by default so the
    order-dependence it demonstrated (CL2 tests) is exercised, and ``risk="R0"``
    reproduces the original.  ``typo`` binds ``cap.thermal.setpiont.v1``
    (a CAP-035 failure at CL0).

    Since WP-04 4b the SDK's compatibility server raises a risk class below
    the class floor to the floor (strict mode refuses the device), so the
    served manifest would no longer show the defect.  The declared class is
    restored after construction to model an endpoint that publishes the risk
    class as declared; the server's own limit plans keep the raised floor.
    """

    measure = Capability("cap.measure.temperature.v1", "zone")
    setpoint = Capability(
        TYPO_SETPOINT if variant == "typo" else "cap.thermal.setpoint.v1", "zone",
        input_schema={"type": "object", "properties": {"target_temperature": {"type": "number"}},
                      "required": ["target_temperature"]},
        exclusive=True,
    )
    capabilities = [setpoint, measure] if setpoint_first else [measure, setpoint]
    envelope = {}
    if variant == "limits":
        envelope = {"cap.thermal.setpoint.v1": {"target_temperature": {"min": 4, "max": 95}}}
    device = Device(
        THERMO_ID, "Scratch thermostat (simulated)", mode="simulated",
        resources=[Resource("zone", "thermal.zone", state_schema={"type": "object"},
                            state={"temperature": 21.0, "setpoint": 21.0})],
        capabilities=capabilities,
        safety=SafetyEnvelope(risk_class=risk, envelope=envelope),
        bridge=ThermoBridge(THERMO_ID),
        fidelity={"engine": "python", "fidelity_level": "F0", "determinism": {"kind": "exact"},
                  "snapshot_restore": True, "gaps": []},
        instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V77",
    )
    server = MHSServer(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False)
    device.safety.risk_class = risk  # publish the declared class (see the docstring)
    return server


# ---------------------------------------------------------------------------
# class-faithful bindings (classfaithful_check.py, v_conf01.py, v_pattern.py)
# ---------------------------------------------------------------------------


class CountingBridge(Bridge):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.n = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        self.n += 1
        self.calls.append((capability_id, dict(args)))
        return {"n": self.n}

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return {"n": self.n}


WORLD_ID = ENDPOINT_ID + "/world"


def class_faithful_server(capability_id: str, input_schema: Mapping[str, Any] | None = None,
                          *, mode: str = "simulated") -> tuple[MHSServer, CountingBridge]:
    entry = catalog.get(capability_id)
    schema = copy.deepcopy(dict(input_schema)) if input_schema is not None else copy.deepcopy(entry["input_schema"])
    capability = Capability(capability_id, "world", verb=entry.get("verb", "invoke"), input_schema=schema,
                            output_schema={"type": "object"},
                            constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000})
    bridge = CountingBridge(device_id=WORLD_ID)
    device = Device(
        WORLD_ID, "D", mode=mode, resources=[Resource("world", "sim", state={"n": 0})], capabilities=[capability],
        safety=SafetyEnvelope(risk_class=str(entry.get("risk_class") or "R0")),
        fidelity={"engine": "toy", "fidelity_level": "F0", "determinism": {"kind": "exact"},
                  "snapshot_restore": False, "gaps": []} if mode != "hardware" else None,
        instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V97", bridge=bridge,
    )
    return MHSServer(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False), bridge


PATTERN_SCHEMA = {
    "type": "object",
    "required": ["well"],
    "properties": {"well": {"type": "string", "pattern": "^[A-H][1-9][0-2]?$"}},
    "additionalProperties": False,
}


def pattern_server() -> tuple[MHSServer, CountingBridge]:
    return class_faithful_server("cap.world.step.v1", PATTERN_SCHEMA)


# ---------------------------------------------------------------------------
# envelope keys (conformance-verify/v_env.py)
# ---------------------------------------------------------------------------


class ArmBridge(Bridge):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.q = [0.0, 0.0]
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        self.calls.append((capability_id, dict(args)))
        if "v" in args:
            self.q = [float(args["v"]), self.q[1]]
        return {"q": list(self.q)}

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return {"q": list(self.q)}


ARM_ID = ENDPOINT_ID + "/arm"
SCALAR_SCHEMA = {"type": "object", "required": ["v"],
                 "properties": {"v": {"type": "number", "minimum": 0, "maximum": 200}},
                 "additionalProperties": False}


def envelope_server(*, envelope: Mapping[str, Any] | None = None,
                    limits: Mapping[str, Any] | None = None) -> tuple[MHSServer, ArmBridge]:
    capability = Capability("cap.motion.joint_position.v1", "arm", verb="invoke",
                            input_schema=copy.deepcopy(SCALAR_SCHEMA), output_schema={"type": "object"},
                            constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000},
                            limits=dict(limits) if limits else None)
    bridge = ArmBridge(device_id=ARM_ID)
    device = Device(
        ARM_ID, "Arm", mode="simulated", resources=[Resource("arm", "robot.arm", state={"q": [0, 0]})],
        capabilities=[capability],
        safety=SafetyEnvelope(risk_class="R2", envelope=dict(envelope or {}),
                              estop={"kind": "software", "latching": True, "latency_ms": 100},
                              safe_state={"description": "halt", "achieved_by": []}),
        fidelity={"engine": "toy", "fidelity_level": "F0", "determinism": {"kind": "exact"},
                  "snapshot_restore": False, "gaps": []},
        instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V98", bridge=bridge,
    )
    return MHSServer(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False), bridge


def statuses(report: Mapping[str, Any]) -> dict[str, str]:
    return {str(item["id"]): str(item["status"]) for item in report["tests"]}


def entry(report: Mapping[str, Any], test_id: str) -> dict[str, Any]:
    for item in report["tests"]:
        if item["id"] == test_id:
            return dict(item)
    raise KeyError(test_id)


# ---------------------------------------------------------------------------
# milestone 07b: endpoints that publish limits or revisions they do not honour
# ---------------------------------------------------------------------------

#: Which ``MHS.SAFETY.ENVELOPE_VIOLATION`` violations a :class:`LimitBlindServer` ignores.
BLIND_RULES = {
    # DRV-02 / FIT-ROS-01: the pre-0.9 server skipped every array (and object) value.
    "arrays": lambda item: "[" in str(item.get("path") or ""),
    # An endpoint that checks only the first element of an array.
    "tail": lambda item: re.search(r"\[[1-9][0-9]*\]", str(item.get("path") or "")) is not None,
    # An endpoint that checks only top-level fields (``position.z`` is never checked).
    "nested": lambda item: "." in str(item.get("path") or ""),
    # An endpoint that ignores the class-default limits of the catalogue.
    "class": lambda item: str(item.get("source") or "") == "class",
    # An endpoint that publishes the operator overlay (site-limits.json) in
    # x-mhs-effective-limits but enforces only the declared limits (see
    # LimitBlindServer: the declared limits are checked instead).
    "overlay": lambda item: False,
    # verify-WP-07/07b/adv/e_middle.py: checks the first and the last element only.
    "middle": lambda item: str(item.get("path") or "").endswith("[1]"),
    # verify-WP-07/07b/adv/b_laser.py: ignores the laser power limit.
    "power": lambda item: str(item.get("path") or "") == "power",
    # verify-WP-07/07b/adv/f_trunc.py: ignores the last of many limited axes.
    "last_axis": lambda item: str(item.get("path") or "") == MANY_AXES_FIELDS[-1],
    "first_axis": lambda item: str(item.get("path") or "") == MANY_AXES_FIELDS[0],
}


class LimitBlindServer(MHSServer):
    """An endpoint that publishes its limits but does not enforce some of them.

    ``blind`` (a :data:`BLIND_RULES` key) selects the violations it ignores.  A
    command whose only violations are ignored goes on to the full input schema,
    exactly as an endpoint without that limit check would: where the schema
    bound equals the limit it answers ``MHS.CAPABILITY.INPUT_INVALID`` (the
    CONF-06 case suite 1.2.0 accepted), otherwise it runs the command.
    """

    blind = "arrays"

    def _check_input(self, device, capability, plan, payload, revision, *, strict):  # type: ignore[override]
        if self.blind == "overlay":
            # Publish the overlay (devices.get), enforce the plan compiled without it.
            from mhs._server import limits_plan

            declared = limits_plan.compile_binding(device, capability, overlay=None, key=f"{plan.key}:declared")
            return super()._check_input(device, capability, declared, payload, revision, strict=strict)
        refusal = super()._check_input(device, capability, plan, payload, revision, strict=strict)
        if refusal is None or refusal.code != "MHS.SAFETY.ENVELOPE_VIOLATION":
            return refusal
        violations = list(((refusal.data or {}).get("details") or {}).get("violations") or [])
        if not violations or not all(BLIND_RULES[self.blind](item) for item in violations):
            return refusal
        if plan.served_schema:
            errors = schema_validate(payload, dict(plan.served_schema))
            if errors:
                return MHSError("MHS.CAPABILITY.INPUT_INVALID", "capability input does not match its schema",
                                {"details": {"errors": [str(item) for item in errors[:8]]}, "retryable": False})
        return None


def blind_server_class(blind: str) -> type:
    """A :class:`LimitBlindServer` subclass that ignores the ``blind`` violations."""

    if blind not in BLIND_RULES:
        raise KeyError(blind)
    return type(f"LimitBlind_{blind}", (LimitBlindServer,), {"blind": blind})


class ReadBumpServer(MHSServer):
    """TESTS-04 (``conformance-verify/v_readverb.py``): every completed command advances the revision.

    The pre-0.9 server did this for read classes too, so a measurement
    invalidated the agent's ``expected_revision``.
    """

    def _finish_command(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        if kwargs.get("status") == "completed":
            kwargs["bump"] = True
        return super()._finish_command(**kwargs)


class NoopBumpServer(ReadBumpServer):
    """Advances the revision on every completed command, also when nothing changed (plan 3.7)."""


class NoopWriteHeaterBridge(HeaterBridge):
    """A heater whose setpoint command is accepted and reported but changes nothing it reads back."""

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == "cap.thermal.setpoint.v1":
            self.backend.native_calls.append(("set_setpoint_ignored", float(args["target_temperature"])))
            return {"setpoint": float(args["target_temperature"])}
        return super().call(capability_id, args, ctx)


class LimitedArm:
    """Recording fake of an arm controller with joint and Cartesian moves."""

    def __init__(self) -> None:
        self.q = [0.0, 0.0, 0.0]
        self.pose = {"x": 300.0, "y": 0.0, "z": 250.0}
        self.native_calls: list[tuple[Any, ...]] = []

    def move_joints(self, q: Sequence[float]) -> None:
        self.native_calls.append(("move_joints", list(q)))
        self.q = list(q)

    def move_pose(self, position: Mapping[str, float]) -> None:
        self.native_calls.append(("move_pose", dict(position)))
        self.pose = dict(position)

    def halt(self) -> None:
        self.native_calls.append(("halt",))

    def moves(self) -> list[tuple[Any, ...]]:
        return [call for call in self.native_calls if call[0] in ("move_joints", "move_pose")]


class LimitedArmBridge(Bridge):
    def __init__(self, native: LimitedArm, **kwargs: Any):
        super().__init__(**kwargs)
        self.native = native

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return {"q": list(self.native.q), "pose": dict(self.native.pose)}

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == "cap.motion.joint_position.v1":
            self.native.move_joints(args["joint_positions"])
            return {"reached": True, "joint_positions": list(self.native.q)}
        if capability_id == "cap.motion.cartesian_pose.v1":
            self.native.move_pose(args["position"])
            return {"reached": True, "position": dict(self.native.pose)}
        if capability_id == "cap.motion.stop.v1":
            self.native.halt()
            return {"stopped": True}
        return super().call(capability_id, args, ctx)

    def safety_status(self) -> dict[str, Any]:
        return {"safe_state": {"description": "halted", "achieved": True}}

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        self.native.halt()
        return {"estop": "engaged"}


LIMITED_ARM_ID = ENDPOINT_ID + "/limited-arm"
#: Per-joint travel of :func:`limited_arm` (rad).
ARM_JOINT_MIN = [-1.0, -0.5, -2.0]
ARM_JOINT_MAX = [1.0, 0.5, 2.0]


def limited_arm(*, server_class: type | None = None, per_joint: bool = False, schema_bounds: bool = True,
                cartesian: bool = False, mode: str = "simulated", permit_joint: bool = False,
                achieved_by: Sequence[str] = ("cap.motion.stop.v1",),
                server_options: Mapping[str, Any] | None = None, bridge_class: type | None = None,
                extensions: Sequence[tuple[Capability, Mapping[str, Any]]] = ()) -> tuple[MHSServer, LimitedArm]:
    """A fake 3-joint arm with an envelope on ``joint_positions`` (and ``position.z`` with ``cartesian``).

    The scalar envelope is ±1 rad on every joint (``per_joint``: the
    :data:`ARM_JOINT_MIN`/:data:`ARM_JOINT_MAX` vectors).  With
    ``schema_bounds`` the binding schema repeats the scalar bound in
    ``items`` (and ``position.z`` 50..800 mm), the reference-arm style that
    made every suite 1.2.0 SAFE-014 pass come from the schema layer (CONF-06).
    The class input schemas are kept otherwise (no drift).  ``permit_joint``
    makes the joint binding permit-gated (``verify-WP-07/07b/adv/a_permit.py``);
    ``achieved_by`` is the declared safe-state action list.  ``extensions``
    adds ``(capability, envelope rules)`` pairs on the ``arm`` resource and
    ``bridge_class`` replaces :class:`LimitedArmBridge` (it must serve them).
    """

    joint = catalog.get("cap.motion.joint_position.v1")
    joint_schema = copy.deepcopy(joint["input_schema"])
    positions = joint_schema["properties"]["joint_positions"]
    positions["minItems"] = positions["maxItems"] = 3
    if schema_bounds and not per_joint:
        positions["items"] = dict(positions["items"], minimum=-1.0, maximum=1.0)
    stop = catalog.get("cap.motion.stop.v1")
    capabilities = [
        Capability("cap.motion.joint_position.v1", "arm", verb="invoke", input_schema=joint_schema,
                   output_schema=copy.deepcopy(joint["output_schema"]),
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000},
                   requires_permit=permit_joint),
        Capability("cap.motion.stop.v1", "arm", verb="invoke", input_schema=copy.deepcopy(stop["input_schema"]),
                   output_schema=copy.deepcopy(stop.get("output_schema") or {"type": "object"}),
                   constraints={"concurrency": "shared", "cancellable": False, "max_duration_ms": 1000}),
    ]
    joint_rule = ({"min": list(ARM_JOINT_MIN), "max": list(ARM_JOINT_MAX)} if per_joint
                  else {"min": -1.0, "max": 1.0})
    envelope: dict[str, Any] = {"cap.motion.joint_position.v1": {
        "joint_positions": dict(joint_rule, unit="rad", reason="joint travel")}}
    if cartesian:
        pose = catalog.get("cap.motion.cartesian_pose.v1")
        pose_schema = copy.deepcopy(pose["input_schema"])
        if schema_bounds:
            z = pose_schema["properties"]["position"]["properties"]["z"]
            z.update(minimum=50, maximum=800)
        capabilities.insert(1, Capability(
            "cap.motion.cartesian_pose.v1", "arm", verb="invoke", input_schema=pose_schema,
            output_schema=copy.deepcopy(pose["output_schema"]),
            constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}))
        envelope["cap.motion.cartesian_pose.v1"] = {
            "position.z": {"min": 50, "max": 800, "unit": "mm", "reason": "table surface and ceiling"}}
    for capability, rules in extensions:
        capabilities.append(capability)
        if rules:
            envelope[capability.capability_id] = copy.deepcopy(dict(rules))
    safety = SafetyEnvelope(
        risk_class="R2", envelope=envelope,
        estop={"kind": "software", "latching": True, "latency_ms": 100},
        safe_state={"description": "halted", "achieved_by": list(achieved_by)},
    )
    native = LimitedArm()
    device = Device(
        LIMITED_ARM_ID, "Limited arm (fake)", mode=mode,
        fidelity={"engine": "toy", "fidelity_level": "F0", "determinism": {"kind": "exact"},
                  "snapshot_restore": False, "gaps": ["fake arm"]} if mode == "simulated" else None,
        resources=[Resource("arm", "robot.arm", state_schema={"type": "object"})],
        capabilities=capabilities, safety=safety, instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V31",
        bridge=(bridge_class or LimitedArmBridge)(native, device_id=LIMITED_ARM_ID),
    )
    options = {"log_ready": False, **dict(server_options or {})}
    return (server_class or MHSServer)(endpoint_id=ENDPOINT_ID, devices=[device], **options), native


# ---------------------------------------------------------------------------
# milestone 07b verification fix (verify-WP-07/07b/adv): coverage of SAFE-014 and OP-001
# ---------------------------------------------------------------------------


class LaserStageBridge(Bridge):
    """A laser with a power envelope next to a heated stage (``b_laser.py``); records every native call."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.native_calls: list[tuple[str, dict[str, Any]]] = []
        self.state = {"power": 0.0, "setpoint": 20.0}

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return dict(self.state)

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        self.native_calls.append((capability_id, dict(args)))
        if capability_id == "cap.optics.set_power.v1":
            self.state["power"] = float(args["power"])
            return {"set_power_mw": float(args["power"])}
        if capability_id == "cap.thermal.setpoint.v1":
            self.state["setpoint"] = float(args["target_temperature"])
            return {"setpoint": self.state["setpoint"]}
        if capability_id == "x-cap.example.off.v1":
            self.state["power"] = 0.0
            return {"stopped": True}
        return super().call(capability_id, args, ctx)

    def safety_status(self) -> dict[str, Any]:
        return {"safe_state": {"description": "off", "achieved": self.state["power"] == 0.0}}

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        self.state["power"] = 0.0
        return {"estop": "engaged"}


LASER_ID = ENDPOINT_ID + "/laser"
#: The laser envelope of :func:`laser_server` (mW); the class allows up to 1000 mW.
LASER_MAX_MW = 50


def laser_server(*, server_class: type | None = None, stage: bool = True,
                 permit_binding: bool = False) -> tuple[MHSServer, LaserStageBridge]:
    """``cap.optics.set_power.v1`` (a class that requires a permit) with a 50 mW envelope.

    ``stage`` adds an enforced, permit-free ``cap.thermal.setpoint.v1``
    binding (the only binding suite 1.3.0 of 07b probed); ``permit_binding``
    also marks the laser binding itself permit-gated.
    """

    laser = catalog.get("cap.optics.set_power.v1")
    capabilities = [
        Capability("cap.optics.set_power.v1", "laser", verb="write", input_schema=copy.deepcopy(laser["input_schema"]),
                   output_schema=copy.deepcopy(laser["output_schema"]), requires_permit=permit_binding,
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}),
        Capability("x-cap.example.off.v1", "laser",
                   input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                   output_schema={"type": "object", "properties": {"stopped": {"type": "boolean"}}}),
    ]
    envelope: dict[str, Any] = {"cap.optics.set_power.v1": {
        "power": {"min": 0, "max": LASER_MAX_MW, "unit": "mW", "reason": "class 3B limit"}}}
    resources = [Resource("laser", "optics.laser", state_schema={"type": "object"})]
    if stage:
        setpoint = catalog.get("cap.thermal.setpoint.v1")
        capabilities.insert(1, Capability(
            "cap.thermal.setpoint.v1", "stage", verb="write", input_schema=copy.deepcopy(setpoint["input_schema"]),
            output_schema=copy.deepcopy(setpoint["output_schema"]),
            constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}))
        envelope["cap.thermal.setpoint.v1"] = {
            "target_temperature": {"min": 0, "max": 80, "unit": "Cel", "reason": "stage"}}
        resources.append(Resource("stage", "thermal.zone", state_schema={"type": "object"}))
    safety = SafetyEnvelope(risk_class="R2", envelope=envelope,
                            estop={"kind": "software", "latching": True, "latency_ms": 100},
                            safe_state={"description": "off", "achieved_by": ["x-cap.example.off.v1"]})
    bridge = LaserStageBridge(device_id=LASER_ID)
    device = Device(LASER_ID, "Laser + stage", mode="simulated", resources=resources, capabilities=capabilities,
                    safety=safety, fidelity=copy.deepcopy(FAKE_FIDELITY), models=[LASER_ID + "-hw"],
                    instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V77", bridge=bridge)
    return (server_class or MHSServer)(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False), bridge


class CountingAxesBridge(Bridge):
    """Counts the multi-axis moves of :func:`many_axes_server` (``f_trunc.py``)."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.moves: list[dict[str, Any]] = []

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        return {"n": len(self.moves)}

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id in ("x-cap.example.multi_axis.v1", "x-cap.example.path.v1"):
            self.moves.append(dict(args))
        return {"ok": True}

    def safety_status(self) -> dict[str, Any]:
        return {"safe_state": {"description": "idle", "achieved": True}}

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        return {"estop": "engaged"}


MANY_AXES_ID = ENDPOINT_ID + "/many"
#: More limited paths than the 07b suite's 32-probe budget spent on its min and max probes.
MANY_AXES = 20
MANY_AXES_FIELDS = [f"f{index:02d}" for index in range(MANY_AXES)]
MANY_AXES_MAX = 10
#: Scalar bound of the ``arr`` elements of :func:`many_axes_server` with ``array`` (mm).
MANY_AXES_ARRAY_MAX = 1


def many_axes_server(*, server_class: type | None = None, fields: Sequence[str] = tuple(MANY_AXES_FIELDS),
                     array: bool = False) -> tuple[MHSServer, CountingAxesBridge]:
    """An extension invoke with one limited number per axis (0..10 mm each).

    ``array`` adds ``arr``, a 3-element array under a scalar bound of
    :data:`MANY_AXES_ARRAY_MAX` (``verify-WP-07/07b/r2/adv/j_tail_budget.py``).
    """

    fields = list(fields)
    schema = {"type": "object", "required": fields + (["arr"] if array else []), "additionalProperties": False,
              "properties": {name: {"type": "number", "x-mhs-unit": "mm"} for name in fields}}
    if array:
        schema["properties"]["arr"] = {"type": "array", "minItems": 3, "maxItems": 3,
                                       "items": {"type": "number", "x-mhs-unit": "mm"}}
    capabilities = [
        Capability("x-cap.example.multi_axis.v1", "stage", verb="invoke", input_schema=schema,
                   output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}),
        Capability("x-cap.example.off.v1", "stage",
                   input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                   output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}}),
    ]
    envelope = {"x-cap.example.multi_axis.v1": {
        name: {"min": 0, "max": MANY_AXES_MAX, "unit": "mm", "reason": "travel"} for name in fields}}
    if array:
        envelope["x-cap.example.multi_axis.v1"]["arr"] = {
            "min": -MANY_AXES_ARRAY_MAX, "max": MANY_AXES_ARRAY_MAX, "unit": "mm", "reason": "travel"}
    safety = SafetyEnvelope(risk_class="R2", envelope=envelope,
                            estop={"kind": "software", "latching": True, "latency_ms": 100},
                            safe_state={"description": "idle", "achieved_by": ["x-cap.example.off.v1"]})
    bridge = CountingAxesBridge(device_id=MANY_AXES_ID)
    device = Device(MANY_AXES_ID, "Many axes", mode="simulated",
                    resources=[Resource("stage", "motion.stage", state_schema={"type": "object"})],
                    capabilities=capabilities, safety=safety, fidelity=copy.deepcopy(FAKE_FIDELITY),
                    models=[MANY_AXES_ID + "-hw"], instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V78", bridge=bridge)
    return (server_class or MHSServer)(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False), bridge


class WorldStateBumpServer(MHSServer):
    """``g_readbump.py``: only the deprecated read ``cap.world.state.v1`` advances the revision (TESTS-04)."""

    def _finish_command(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        capability = kwargs.get("capability")
        capability_id = kwargs.get("capability_id") or getattr(capability, "capability_id", None)
        if kwargs.get("status") == "completed" and capability_id == "cap.world.state.v1":
            kwargs["bump"] = True
        return super()._finish_command(**kwargs)


class WorldStateHeaterBridge(HeaterBridge):
    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == "cap.world.state.v1":
            return {"state": self.backend.status()}
        return super().call(capability_id, args, ctx)


def world_state_heater(*, server_class: type | None = None) -> tuple[MHSServer, FakeHeater]:
    """:func:`heater_server` that also binds the deprecated read ``cap.world.state.v1``."""

    server, backend = heater_server(server_class=server_class, bridge_class=WorldStateHeaterBridge)
    world_state = catalog.get("cap.world.state.v1")
    server.devices[HEATER_ID].capabilities.append(Capability(
        "cap.world.state.v1", "heater", verb="read", input_schema=copy.deepcopy(world_state["input_schema"]),
        output_schema=copy.deepcopy(world_state["output_schema"]),
        constraints={"concurrency": "shared", "cancellable": False, "max_duration_ms": 1000}))
    return server, backend


class SafeStateOnRefusalServer(MHSServer):
    """Refuses an out-of-limit command with ENVELOPE_VIOLATION, but drives ``bridge.safe_state()`` first."""

    def _check_input(self, device, capability, plan, payload, revision, *, strict):  # type: ignore[override]
        refusal = super()._check_input(device, capability, plan, payload, revision, strict=strict)
        if refusal is not None and refusal.code == "MHS.SAFETY.ENVELOPE_VIOLATION":
            device.bridge.safe_state()
        return refusal


# ---------------------------------------------------------------------------
# milestone 07b verification fix round 2 (verify-WP-07/07b/r2/adv)
# ---------------------------------------------------------------------------

#: ``h_unsynth.py``: an extension whose required ``tool_id`` is a pattern-constrained string.
TOOL_CAPABILITY = "x-cap.example.tool.v1"
TOOL_MAX_SPEED = 10
#: ``i_allowed_pattern.py``: an allowed set on a pattern-constrained string.
GEAR_CAPABILITY = "x-cap.example.gear.v1"
GEAR_ALLOWED = ["low", "mid"]

BLIND_RULES.update({
    # h_unsynth.py: ignores the tool speed limit.
    "speed": lambda item: str(item.get("path") or "") == "speed",
    # i_allowed_pattern.py: ignores the allowed gear set.
    "gear": lambda item: str(item.get("path") or "") == "gear",
})


class ToolArmBridge(LimitedArmBridge):
    """:class:`LimitedArmBridge` that also serves the tool and gear extensions (recorded as native calls)."""

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id in (TOOL_CAPABILITY, GEAR_CAPABILITY):
            self.native.native_calls.append((capability_id, dict(args)))
            return {"ok": True}
        return super().call(capability_id, args, ctx)


def tool_arm(*, server_class: type | None = None, tool: bool = True, gear_pattern: str | None = None,
             gear_default: str | None = "low") -> tuple[MHSServer, LimitedArm]:
    """:func:`limited_arm` (enforced joint envelope) plus a limited extension the suite cannot synthesize alone.

    ``tool`` adds :data:`TOOL_CAPABILITY`: required ``tool_id`` (pattern
    ``^T[0-9]{3}$``) and ``speed`` limited to 0..:data:`TOOL_MAX_SPEED` by the
    envelope; no class example, so only a fixture gives a valid input
    (``h_unsynth.py``).  ``gear_pattern`` adds :data:`GEAR_CAPABILITY`, a
    ``gear`` string with that pattern and the envelope allowed set
    :data:`GEAR_ALLOWED` (``i_allowed_pattern.py``).
    """

    extensions: list[tuple[Capability, Mapping[str, Any]]] = []
    output = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    constraints = {"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}
    if tool:
        schema = {"type": "object", "required": ["tool_id", "speed"], "additionalProperties": False,
                  "properties": {"tool_id": {"type": "string", "pattern": "^T[0-9]{3}$"},
                                 "speed": {"type": "number", "x-mhs-unit": "mm/s"}}}
        extensions.append((Capability(TOOL_CAPABILITY, "arm", verb="invoke", input_schema=schema,
                                      output_schema=copy.deepcopy(output), constraints=dict(constraints)),
                           {"speed": {"min": 0, "max": TOOL_MAX_SPEED, "unit": "mm/s", "reason": "tool"}}))
    if gear_pattern is not None:
        gear = {"type": "string", "pattern": gear_pattern}
        if gear_default is not None:
            gear["default"] = gear_default
        schema = {"type": "object", "required": ["gear"], "additionalProperties": False,
                  "properties": {"gear": gear}}
        extensions.append((Capability(GEAR_CAPABILITY, "arm", verb="invoke", input_schema=schema,
                                      output_schema=copy.deepcopy(output), constraints=dict(constraints)),
                           {"gear": {"allowed": list(GEAR_ALLOWED), "reason": "gearbox"}}))
    return limited_arm(server_class=server_class, bridge_class=ToolArmBridge, extensions=extensions)


POINTS_ID = ENDPOINT_ID + "/points"
POINTS_MAX_Z = 10


def points_server(*, server_class: type | None = None, length: int | None = 3,
                  labelled: bool = False, unique: bool = False) -> tuple[MHSServer, CountingAxesBridge]:
    """``m_wildcard_tail.py``: an envelope on a leaf inside an array of objects (``points[*].z``, 0..10 mm).

    ``length`` fixes the array length (``minItems == maxItems``); ``None``
    leaves it variable (no ``minItems``/``maxItems``).  ``labelled`` gives
    every point a required ``label`` (pattern ``^P[0-9]+$``), so only a
    fixture yields a valid input; ``unique`` sets ``uniqueItems`` (the suite
    cannot grow the array with a copy of an element).
    """

    item: dict[str, Any] = {"type": "object", "required": ["z"], "additionalProperties": False,
                            "properties": {"z": {"type": "number", "x-mhs-unit": "mm"}}}
    if labelled:
        item["required"] = ["label", "z"]
        item["properties"]["label"] = {"type": "string", "pattern": "^P[0-9]+$"}
    points: dict[str, Any] = {"type": "array", "items": item}
    if unique:
        points["uniqueItems"] = True
    if length is not None:
        points["minItems"] = points["maxItems"] = length
    schema = {"type": "object", "required": ["points"], "additionalProperties": False,
              "properties": {"points": points}}
    capabilities = [
        Capability("x-cap.example.path.v1", "stage", verb="invoke", input_schema=schema,
                   output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}),
        Capability("x-cap.example.off.v1", "stage",
                   input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                   output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}}),
    ]
    safety = SafetyEnvelope(
        risk_class="R2",
        envelope={"x-cap.example.path.v1": {"points[*].z": {"min": 0, "max": POINTS_MAX_Z, "unit": "mm",
                                                            "reason": "z travel"}}},
        estop={"kind": "software", "latching": True, "latency_ms": 100},
        safe_state={"description": "idle", "achieved_by": ["x-cap.example.off.v1"]})
    bridge = CountingAxesBridge(device_id=POINTS_ID)
    device = Device(POINTS_ID, "Path", mode="simulated",
                    resources=[Resource("stage", "motion.stage", state_schema={"type": "object"})],
                    capabilities=capabilities, safety=safety, fidelity=copy.deepcopy(FAKE_FIDELITY),
                    models=[POINTS_ID + "-hw"], instance_id="01J8ZQ3V6Y7M2N4P6R8S0T2V79", bridge=bridge)
    return (server_class or MHSServer)(endpoint_id=ENDPOINT_ID, devices=[device], log_ready=False), bridge


#: ``k_ext_read.py``: an extension binding that declares the read verb.
EXT_READ_CAPABILITY = "x-cap.example.probe_temp.v1"


class ExtReadHeaterBridge(HeaterBridge):
    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == EXT_READ_CAPABILITY:
            self.backend.native_calls.append(("probe_temp",))
            return {"temperature": self.backend.setpoint}
        return super().call(capability_id, args, ctx)


class ExtReadBumpServer(MHSServer):
    """Advances the revision on every completed :data:`EXT_READ_CAPABILITY` command (a read, TESTS-04)."""

    def _finish_command(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        capability = kwargs.get("capability")
        capability_id = kwargs.get("capability_id") or getattr(capability, "capability_id", None)
        if kwargs.get("status") == "completed" and capability_id == EXT_READ_CAPABILITY:
            kwargs["bump"] = True
        return super()._finish_command(**kwargs)


def ext_read_heater(*, hardware: bool = False, **options: Any) -> tuple[MHSServer, FakeHeater]:
    """:func:`heater_server` (or :func:`hardware_heater`) that also binds the extension read :data:`EXT_READ_CAPABILITY`."""

    options.setdefault("bridge_class", ExtReadHeaterBridge)
    server, backend = (hardware_heater if hardware else heater_server)(**options)
    server.devices[HEATER_ID].capabilities.append(Capability(
        EXT_READ_CAPABILITY, "heater", verb="read",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {"temperature": {"type": "number"}}},
        constraints={"concurrency": "shared", "cancellable": False, "max_duration_ms": 1000}))
    return server, backend


# ---------------------------------------------------------------------------
# RESIDUAL-B (verify-WP-07/07b/r3/adv): fields declared in a branch, fixture
# coverage, numeric allowed sets, reads OP-001 cannot send
# ---------------------------------------------------------------------------

#: ``n_anyof_class.py``: a second, enforced limited binding next to the setpoint.
FAN_CAPABILITY = "x-cap.example.fan.v1"
FAN_MAX = 50
#: ``n_anyof_class.py``: ``target_temperature`` declared only inside ``anyOf`` (and listed in ``required``).
ANYOF_SETPOINT = {"type": "object", "required": ["target_temperature"],
                  "anyOf": [{"properties": {"target_temperature": {"type": "number", "x-mhs-unit": "Cel"}}}]}
#: ``n_anyof_class.py --oneof`` / ``o_oneof_envelope.py``: a setpoint or a preset, each branch closed.
ONEOF_SETPOINT = {"type": "object", "oneOf": [
    {"required": ["target_temperature"], "additionalProperties": False,
     "properties": {"target_temperature": {"type": "number", "x-mhs-unit": "Cel"}}},
    {"required": ["preset"], "additionalProperties": False,
     "properties": {"preset": {"type": "string", "enum": ["standby", "eco"]}}}]}


class FanHeaterBridge(HeaterBridge):
    """:class:`HeaterBridge` that also serves :data:`FAN_CAPABILITY` (recorded as a native call)."""

    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == FAN_CAPABILITY:
            self.backend.native_calls.append(("fan", float(args["speed"])))
            return {"ok": True}
        return super().call(capability_id, args, ctx)


def branched_heater(schema: Mapping[str, Any], *, server_class: type | None = None, envelope: bool = False,
                    fan: bool = True) -> tuple[MHSServer, FakeHeater]:
    """:func:`heater_server` whose setpoint binding has ``schema`` (``target_temperature`` in a branch).

    Without ``envelope`` the setpoint is limited only by the class default
    (-50..300 Cel); ``fan`` adds the enforced :data:`FAN_CAPABILITY` (0..:data:`FAN_MAX`).
    """

    server, backend = heater_server(envelope=envelope, server_class=server_class, bridge_class=FanHeaterBridge)
    device = server.devices[HEATER_ID]
    for capability in device.capabilities:
        if capability.capability_id == "cap.thermal.setpoint.v1":
            capability.input_schema = copy.deepcopy(dict(schema))
    if fan:
        device.capabilities.append(Capability(
            FAN_CAPABILITY, "heater", verb="invoke",
            input_schema={"type": "object", "required": ["speed"], "additionalProperties": False,
                          "properties": {"speed": {"type": "number", "x-mhs-unit": "%"}}},
            output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}}))
        device.safety.envelope = dict(device.safety.envelope or {}, **{
            FAN_CAPABILITY: {"speed": {"min": 0, "max": FAN_MAX, "unit": "%", "reason": "fan"}}})
    return server, backend


#: A numeric allowed set on an integer field (verifier minor: one probe at max(allowed)+1 only).
STEP_CAPABILITY = "x-cap.example.step.v1"
STEP_ALLOWED = [1, 3, 5]

BLIND_RULES.update({
    # Enforces the allowed set as the range 1..5 (accepts 2 and 4).
    "step_range": lambda item: (str(item.get("path") or "") == "step" and item.get("kind") == "allowed"
                                and min(STEP_ALLOWED) <= float(item.get("value")) <= max(STEP_ALLOWED)),
    # Checks only the upper side of the allowed set (accepts 0, 2 and 4).
    "step_upper": lambda item: (str(item.get("path") or "") == "step" and item.get("kind") == "allowed"
                                and float(item.get("value")) <= max(STEP_ALLOWED)),
})


class StepArmBridge(LimitedArmBridge):
    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        if capability_id == STEP_CAPABILITY:
            self.native.native_calls.append((capability_id, dict(args)))
            return {"ok": True}
        return super().call(capability_id, args, ctx)


def step_arm(*, server_class: type | None = None) -> tuple[MHSServer, LimitedArm]:
    """:func:`limited_arm` plus :data:`STEP_CAPABILITY`: integer ``step`` 0..10 with the allowed set :data:`STEP_ALLOWED`."""

    schema = {"type": "object", "required": ["step"], "additionalProperties": False,
              "properties": {"step": {"type": "integer", "minimum": 0, "maximum": 10}}}
    capability = Capability(STEP_CAPABILITY, "arm", verb="invoke", input_schema=schema,
                            output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
                            constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000})
    return limited_arm(server_class=server_class, bridge_class=StepArmBridge,
                       extensions=[(capability, {"step": {"allowed": list(STEP_ALLOWED), "reason": "gear steps"}})])


#: An extension read whose required input only a fixture can give (a ``pattern`` string).
NAMED_READ_CAPABILITY = "x-cap.example.named_probe.v1"


def named_read_heater(**options: Any) -> tuple[MHSServer, FakeHeater]:
    """:func:`ext_read_heater` plus :data:`NAMED_READ_CAPABILITY` (``verb: read``; required ``sensor`` ``^S[0-9]+$``)."""

    server, backend = ext_read_heater(**options)
    server.devices[HEATER_ID].capabilities.append(Capability(
        NAMED_READ_CAPABILITY, "heater", verb="read",
        input_schema={"type": "object", "required": ["sensor"], "additionalProperties": False,
                      "properties": {"sensor": {"type": "string", "pattern": "^S[0-9]+$"}}},
        output_schema={"type": "object", "properties": {"temperature": {"type": "number"}}},
        constraints={"concurrency": "shared", "cancellable": False, "max_duration_ms": 1000}))
    return server, backend
