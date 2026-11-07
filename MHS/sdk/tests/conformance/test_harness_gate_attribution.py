"""The in-process hardware gate fails closed for shared and unshadowable bridges (MERGE-B fix round).

Ports of the WP-07 07a verifier repros (``scratch/verify-WP-07/07a/r3/``):

* ``shared_bridge.py`` (blocker): one ``Bridge`` instance serves a simulated
  and a hardware device.  The harness wrapped it once, under the first
  device's id, so a call for the hardware device was recorded under the
  simulated id and passed the gate while ``blocks(hardware)`` was true; with
  an endpoint that does not enforce the envelope the negative tests moved the
  hardware arm.
* ``silent_setattr.py`` (major): a bridge whose ``__setattr__`` silently
  ignores instance writes kept its own methods, yet the harness counted its
  wrappers as installed (``uninstrumented == []``, ``blocks() is True``).

Each unit test drives the bridge the way an endpoint that does not enforce
limits would (the bridge call is made directly), so the harness is the only
guard; each failed before the fix.
"""

from __future__ import annotations

import copy
import unittest

from mhs import catalog
from mhs.bridge.base import Bridge, BridgeContext
from mhs.conformance.inprocess import Harness, run_suite_inprocess
from mhs.errors import MHSError
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

from tests.conformance import support

EP = "mhs://localhost/shared"
SIM = EP + "/sim-arm"
HW = EP + "/hw-arm"
JOINT = "cap.motion.joint_position.v1"


class Native:
    """One controller connection driving two arms; every move is recorded with its target."""

    def __init__(self) -> None:
        self.q = {SIM: [0.0, 0.0, 0.0], HW: [0.0, 0.0, 0.0]}
        self.moves: list[tuple[str, list[float]]] = []

    def move(self, device_id: str, q) -> None:  # noqa: ANN001
        self.moves.append((device_id, list(q)))
        if device_id in self.q:
            self.q[device_id] = list(q)

    def hardware_moves(self) -> list[tuple[str, list[float]]]:
        return [move for move in self.moves if move[0] != SIM]


class SharedBridge(Bridge):
    """One bridge object for both devices; the target comes from ``ctx.device_id``."""

    def __init__(self, native: Native, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.native = native

    def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
        return {"sim": list(self.native.q[SIM]), "hw": list(self.native.q[HW])}

    def call(self, capability_id, args, ctx=None):  # noqa: ANN001
        if capability_id == JOINT:
            self.native.move(getattr(ctx, "device_id", None) or "?", args["joint_positions"])
            return {"reached": True, "joint_positions": list(args["joint_positions"])}
        if capability_id == "x-cap.acme.halt.v1":
            return {"halted": True}
        return super().call(capability_id, args, ctx)

    def estop(self, reason="", ctx=None):  # noqa: ANN001
        return {"estop": "engaged"}


def _device(device_id: str, mode: str, bridge: Bridge) -> Device:
    entry = catalog.get(JOINT)
    schema = copy.deepcopy(entry["input_schema"])
    schema["properties"]["joint_positions"]["minItems"] = 3
    schema["properties"]["joint_positions"]["maxItems"] = 3
    capabilities = [
        Capability(JOINT, "arm", verb="invoke", input_schema=schema,
                   output_schema=copy.deepcopy(entry["output_schema"]),
                   constraints={"concurrency": "exclusive", "cancellable": False, "max_duration_ms": 1000}),
        Capability("x-cap.acme.halt.v1", "arm", title="halt",
                   input_schema={"type": "object", "properties": {}, "additionalProperties": False}),
    ]
    safety = SafetyEnvelope(
        risk_class="R2",
        envelope={JOINT: {"joint_positions": {"min": -1.0, "max": 1.0, "unit": "rad", "reason": "travel"}}},
        estop={"kind": "both", "latching": True, "latency_ms": 100, "physical_ref": "pendant"},
        safe_state={"description": "halted", "achieved_by": ["x-cap.acme.halt.v1"]},
    )
    fidelity = {"engine": "fake", "fidelity_level": "F0", "determinism": {"kind": "exact"},
                "snapshot_restore": False, "gaps": ["fake"]}
    return Device(device_id, device_id.rsplit("/", 1)[-1], mode=mode,
                  fidelity=fidelity if mode == "simulated" else None,
                  resources=[Resource("arm", "robot.arm", state_schema={"type": "object"})],
                  capabilities=capabilities, safety=safety, bridge=bridge)


def shared_server(order: str = "sim-first") -> tuple[MHSServer, Native, SharedBridge]:
    native = Native()
    bridge = SharedBridge(native, device_id=SIM)
    devices = [_device(SIM, "simulated", bridge), _device(HW, "hardware", bridge)]
    if order != "sim-first":
        devices.reverse()
    return MHSServer(endpoint_id=EP, devices=devices, log_ready=False), native, bridge


class SharedBridgeGateTests(unittest.TestCase):
    def test_a_hardware_call_through_a_shared_bridge_is_blocked(self) -> None:
        for order in ("sim-first", "hw-first"):
            with self.subTest(order=order):
                server, native, bridge = shared_server(order)
                harness = Harness(server)
                try:
                    self.assertTrue(harness.blocks(HW))
                    harness.current_test = "SAFE-014"
                    with self.assertRaises(MHSError) as raised:
                        bridge.call(JOINT, {"joint_positions": [2.0, 1.0, 1.0]}, BridgeContext(device_id=HW))
                    self.assertEqual(raised.exception.code, "MHS.AUTH.HARDWARE_DISABLED")
                    self.assertEqual(native.hardware_moves(), [])
                    blocked = harness.blocked(HW)
                    self.assertEqual([(item.device_id, item.test_id) for item in blocked], [(HW, "SAFE-014")])
                finally:
                    harness.restore()

    def test_every_call_of_a_bridge_shared_with_hardware_is_gated(self) -> None:
        # Without a resolvable target the call could be for either device: it is
        # refused (fail closed) and attributed to the hardware device.  A call
        # that names the simulated device is refused too -- the same object
        # drives the hardware.
        server, native, bridge = shared_server("sim-first")
        harness = Harness(server)
        try:
            for ctx, attributed in ((None, HW), (BridgeContext(device_id=SIM), SIM)):
                with self.subTest(ctx=getattr(ctx, "device_id", None)):
                    mark = harness.mark()
                    with self.assertRaises(MHSError) as raised:
                        bridge.call(JOINT, {"joint_positions": [2.0, 0.0, 0.0]}, ctx)
                    self.assertEqual(raised.exception.code, "MHS.AUTH.HARDWARE_DISABLED")
                    self.assertEqual([item.device_id for item in harness.actuations(since=mark)], [attributed])
            self.assertEqual(native.moves, [])
        finally:
            harness.restore()

    def test_allow_actuation_lets_the_shared_bridge_act(self) -> None:
        server, native, bridge = shared_server("sim-first")
        harness = Harness(server, allow_actuation=True)
        try:
            bridge.call(JOINT, {"joint_positions": [0.5, 0.0, 0.0]}, BridgeContext(device_id=HW))
            self.assertEqual(native.moves, [(HW, [0.5, 0.0, 0.0])])
            self.assertEqual([item.device_id for item in harness.actuations()], [HW])
        finally:
            harness.restore()
        self.assertNotIn("call", vars(bridge))

    def test_a_suite_run_never_moves_the_hardware_arm(self) -> None:
        for order in ("sim-first", "hw-first"):
            with self.subTest(order=order):
                natives: list[Native] = []

                def factory(order=order):  # noqa: ANN001
                    server, native, _bridge = shared_server(order)
                    natives.append(native)
                    return server

                run_suite_inprocess(factory, profile="MHS-Device", level="CL3")
                self.assertEqual([move for native in natives for move in native.hardware_moves()], [])


class MixedModeSessionTests(unittest.TestCase):
    """The suite opens one session per device mode (MERGE-B verifier minor, probe ``v_mixed_modes.py``).

    One session for a simulated and a hardware device took the mode of the
    last listed device, so every command to the other device came back
    ``MHS.SESSION.MODE_MISMATCH`` -- reported as a required failure such as
    SAFE-014 "out-of-limit probe(s) not refused ... returned
    MHS.SESSION.MODE_MISMATCH".
    """

    def _factory(self, natives: list, order: str):  # noqa: ANN202
        def factory():  # noqa: ANN202
            native = Native()
            natives.append(native)
            devices = [_device(SIM, "simulated", SharedBridge(native, device_id=SIM)),
                       _device(HW, "hardware", SharedBridge(native, device_id=HW))]
            if order != "sim-first":
                devices.reverse()
            return MHSServer(endpoint_id=EP, devices=devices, log_ready=False)

        return factory

    def test_no_check_fails_on_the_suites_own_session_mode(self) -> None:
        for order in ("sim-first", "hw-first"):
            with self.subTest(order=order):
                natives: list[Native] = []
                report = run_suite_inprocess(self._factory(natives, order), profile="MHS-Device", level="CL3")
                # (MODE-002 / SESS-002 expect MODE_MISMATCH and pass with it.)
                mismatched = [(item["id"], item["status"]) for item in report["tests"]
                              if "MODE_MISMATCH" in str(item.get("detail") or "") and item["status"] != "pass"]
                self.assertEqual(mismatched, [])
                self.assertEqual([move for native in natives for move in native.hardware_moves()], [])


class QuietArmBridge(support.FakeArmBridge):
    """A bridge whose ``__setattr__`` silently ignores instance writes (a proxy, a frozen object)."""

    _frozen = False

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value) -> None:  # noqa: ANN001
        if getattr(self, "_frozen", False):
            return
        object.__setattr__(self, name, value)


class DescriptorArmBridge(support.FakeArmBridge):
    """``call`` is a class-level data descriptor whose setter drops the value."""

    def _get_call(self):  # noqa: ANN202
        return lambda capability_id, args, ctx=None: support.FakeArmBridge.call(self, capability_id, args, ctx)

    call = property(_get_call, lambda self, value: None)


def _quiet_arm(bridge_class=QuietArmBridge):  # noqa: ANN001
    server, native = support.hardware_arm()
    device = next(iter(server.devices.values()))
    device.bridge = bridge_class(native, device_id=device.device_id)
    return server, native, device


class WrapperInstallCheckTests(unittest.TestCase):
    def test_a_silently_ignored_wrapper_is_reported_uninstrumented(self) -> None:
        for bridge_class in (QuietArmBridge, DescriptorArmBridge):
            with self.subTest(bridge=bridge_class.__name__):
                server, native, device = _quiet_arm(bridge_class)
                harness = Harness(server)
                try:
                    self.assertIn(f"{device.device_id}:call", harness.uninstrumented)
                    self.assertIn("call", harness.uninstrumented_for(device.device_id))
                    self.assertFalse(harness.blocks(device.device_id),
                                     "a bridge the harness cannot gate must not be reported as blocked")
                finally:
                    harness.restore()

    def test_negative_tests_are_not_sent_to_an_ungated_hardware_bridge(self) -> None:
        natives = []

        def factory():  # noqa: ANN202
            server, native, _device = _quiet_arm()
            natives.append(native)
            return server

        report = run_suite_inprocess(factory, profile="MHS-Device", level="CL3")
        self.assertEqual([call for native in natives for call in native.actuations()], [])
        self.assertNotEqual(support.entry(report, "CON-031")["status"], "pass")
        for test_id in ("OP-005", "PROTO-027", "SAFE-014"):
            self.assertEqual(support.entry(report, test_id)["status"], "skip", support.entry(report, test_id))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
