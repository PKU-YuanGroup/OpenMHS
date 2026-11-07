"""WP-04 step 4d: bindings keyed by ``(capability_id, resource)``, revisions, ``resource.write``.

Ports of the reviewer repros:

* fit-lab-automation ``drv/dup2.py`` (LAB-01): one class bound to two pipettes
  with different maxima; the last binding used to win, so a 500 uL aspirate on
  the 20 uL pipette completed;
* fit-robots-ros ``biman_probe2.py`` (FIT-ROS-03): one grasp class on two
  grippers with 5 N and 100 N limits; the 5 N limit was lost and the ungranted
  arm ran;
* fit-lab-automation-verify ``res_mismatch.py`` and ``hybrid.py``: a binding of
  ``left`` ran on ``right`` and on a resource that does not exist, and a
  binding of a model-authority arm drove the hardware-authority arm;
* tests-run TESTS-04 / sdk-core ``e2.py`` and ``e7.py`` (a) / SDK-07: a read
  (or a command that changes nothing, or a failed one) advanced the revision,
  and ``expected_revision`` was checked against a revision read before the
  slow pre-checks;
* conformance-verify ``v_replay.py``: a refused command on the replay device
  was ``failed`` and reported a revision the device never had;
* fit-lab-instruments-verify ``v_write_coupling.py``, the driver-authoring
  ``resource.write`` namespace finding and the 4c verifier's ``p11``: a write
  passed the patch (state names) as the input of a class keyed by input names,
  so its limits never applied, readOnly fields were written and unknown keys
  reached the bridge;
* the 4d verifier's ``p1_unreadable.py`` (a bridge that cannot read its state:
  the hash rule compared the declared state with itself, so the revision never
  moved and a stale ``expected_revision`` ran), ``p2_write.py`` (a nested
  readOnly leaf and a nested unknown key were written) and ``p3_late_dup.py``
  (a duplicate pair appended after construction was served with the wider
  limit).
"""

from __future__ import annotations

import copy
import threading
import time
import unittest
import warnings
from typing import Any, Mapping
from unittest import mock

import mhs.server as server_module
from mhs import canonical
from mhs.bridge.base import Bridge, unsupported
from mhs.reference import build_endpoint, build_server
from mhs.server import Capability, Device, MHSServer, MHSStrictError, MHSStrictWarning, Resource, SafetyEnvelope

from ._support import FIDELITY, Rpc, conveyor, error_code
from ._limits_support import details

ASPIRATE = "cap.fluid.aspirate.v1"
GRASP = "cap.manipulation.grasp.v1"
STOP = "cap.motion.stop.v1"
TEMPERATURE = "cap.measure.temperature.v1"
SETPOINT = "cap.thermal.setpoint.v1"
CONFIGURE = "cap.device.configure.v1"
MOVE = "x-cap.test.move.v1"
NOOP = "x-cap.test.noop.v1"
TOUCH = "x-cap.test.touch.v1"
FAIL = "x-cap.test.fail.v1"
FAIL_AFTER = "x-cap.test.fail_after_change.v1"
GATED = "x-cap.test.gated.v1"
OBJECT = {"type": "object", "properties": {}}

#: The fixtures are deliberately not catalogue-faithful in compatibility mode;
#: their MHSStrictWarnings are not what these tests are about.
_QUIET = warnings.catch_warnings()


def setUpModule() -> None:  # noqa: N802 - unittest hook
    _QUIET.__enter__()
    warnings.simplefilter("ignore", MHSStrictWarning)


def tearDownModule() -> None:  # noqa: N802 - unittest hook
    _QUIET.__exit__(None, None, None)


class MultiBridge(Bridge):
    """One state document per resource; records ``(capability, ctx.resource, input)``."""

    bridge_id = "tests.safety.bindings"

    def __init__(self, device_id: str, states: Mapping[str, Mapping[str, Any]]) -> None:
        super().__init__(device_id=device_id)
        self.states: dict[str, dict[str, Any]] = {key: dict(value) for key, value in states.items()}
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []
        self.interlock_states: dict[str, str] = {}
        self.interlock_delay = 0.0
        self._calls_lock = threading.Lock()

    def native(self, capability_id: str | None = None) -> list[tuple[str, Any, dict[str, Any]]]:
        with self._calls_lock:
            return [item for item in self.calls if capability_id is None or item[0] == capability_id]

    def read(self, resource_id: str, fields=None, ctx=None):  # noqa: ANN001
        return copy.deepcopy(self.states.get(resource_id, {}))

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        args = copy.deepcopy(dict(args or {}))
        resource = getattr(ctx, "resource", None)
        with self._calls_lock:
            self.calls.append((capability_id, resource, args))
        state = self.states.setdefault(str(resource), {})
        if capability_id == ASPIRATE:
            state["volume"] = state.get("volume", 0) + args.get("volume", 0)
            return {"aspirated": args.get("volume")}
        if capability_id == GRASP:
            state["grasped"] = True
            return {"grasped": True}
        if capability_id == STOP:
            state["moving"] = False
            return {"stopped": True}
        if capability_id == CONFIGURE:
            state.update(args)
            return {"applied": args}
        if capability_id == TEMPERATURE:
            state["reads"] = state.get("reads", 0) + 1  # a read whose bridge touches its state
            return {"temperature": 21.5}
        if capability_id in (TOUCH, MOVE, GATED):
            state["n"] = state.get("n", 0) + 1
            return {"n": state["n"]}
        if capability_id == FAIL:
            raise RuntimeError("the native call failed")
        if capability_id == FAIL_AFTER:
            state["n"] = state.get("n", 0) + 1
            raise RuntimeError("the native call failed after it moved")
        return {"ok": True}

    def interlocks(self):
        if self.interlock_delay:
            time.sleep(self.interlock_delay)
        return [{"id": key, "state": value} for key, value in self.interlock_states.items()]


def make_device(device_id: str, resources: list[Resource], capabilities: list[Capability], *,
                mode: str = "simulated", risk: str = "R1", envelope: Mapping[str, Any] | None = None,
                achieved_by: tuple[str, ...] = (), interlocks: list[dict[str, Any]] | None = None,
                fidelity: Mapping[str, Any] | None = None, states: Mapping[str, Any] | None = None,
                bridge: Bridge | None = None, strict: bool | None = None) -> Device:
    if fidelity is None and mode in ("simulated", "hybrid"):
        fidelity = dict(FIDELITY)
    return Device(
        device_id, "Bindings test device", mode=mode, resources=resources, capabilities=capabilities,
        safety=SafetyEnvelope(
            risk_class=risk, envelope=dict(envelope or {}), interlocks=list(interlocks or []),
            estop={"kind": "software", "latching": True, "latency_ms": 50},
            safe_state={"description": "stopped", "achieved_by": list(achieved_by)},
        ),
        fidelity=dict(fidelity) if fidelity else None,
        bridge=bridge if bridge is not None else MultiBridge(
            device_id, states or {resource.resource_id: {} for resource in resources}),
        strict=strict,
    )


def serve(dev: Device, *, session: bool = True, **kwargs: Any) -> tuple[MHSServer, Rpc, str | None]:
    kwargs.setdefault("log_ready", False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        server = MHSServer("mhs://localhost/bindings", [dev], **kwargs)
    rpc = Rpc(server)
    rpc("mhs.hello", protocol_versions=["1.0"])
    sid = rpc("mhs.session.open", device_ids=[dev.device_id], mode=dev.mode)["session_id"] if session else None
    return server, rpc, sid


def command(rpc: Rpc, session: str, capability_id: str, payload: Mapping[str, Any], **params: Any
            ) -> dict[str, Any]:
    params.setdefault("deadline_ms", 3000)
    params.setdefault("command_id", canonical.ulid())
    return rpc("mhs.command", session_id=session, capability_id=capability_id, input=dict(payload), **params)


def revision(rpc: Rpc, session: str, resource_id: str) -> int:
    return int(rpc("mhs.resource.read", session_id=session, resource_id=resource_id, deadline_ms=2000)["revision"])


def pipettes(*, left: Mapping[str, Any] | None = None, right: Mapping[str, Any] | None = None,
             only_left: bool = False) -> Device:
    """dup2.py: cap.fluid.aspirate.v1 on a P20 ('left') and a P1000 ('right')."""
    def schema(maximum: int) -> dict[str, Any]:
        return {"type": "object",
                "properties": {"volume": {"type": "number", "minimum": 0, "maximum": maximum, "x-mhs-unit": "uL"}}}
    caps = [Capability(ASPIRATE, "left", input_schema=schema(20), limits=dict(left) if left else None)]
    if not only_left:
        caps.append(Capability(ASPIRATE, "right", input_schema=schema(1000), limits=dict(right) if right else None))
    return make_device("mhs://localhost/bindings/ot2",
                       [Resource("left", "lab.pipette", state={}), Resource("right", "lab.pipette", state={})],
                       caps)


def grippers(**kwargs: Any) -> Device:
    """biman_probe2.py: cap.manipulation.grasp.v1 on two grippers, 5 N and 100 N."""
    caps = [Capability(GRASP, "left_arm", limits={"force": {"min": 0, "max": 5, "unit": "N"}}),
            Capability(GRASP, "right_arm", limits={"force": {"min": 0, "max": 100, "unit": "N"}}),
            Capability(STOP, "left_arm"), Capability(STOP, "right_arm")]
    kwargs.setdefault("achieved_by", (STOP,))
    return make_device("mhs://localhost/bindings/aloha",
                       [Resource("left_arm", "robot.arm"), Resource("right_arm", "robot.arm")],
                       caps, **kwargs)


def probe_device(**kwargs: Any) -> Device:
    """A thermometer with a read, a no-op, a state-changing, two failing and one exclusive gated class."""
    caps = [Capability(TEMPERATURE, "probe", verb="read", input_schema=OBJECT),
            Capability(NOOP, "probe", input_schema=OBJECT), Capability(TOUCH, "probe", input_schema=OBJECT),
            Capability(FAIL, "probe", input_schema=OBJECT), Capability(FAIL_AFTER, "probe", input_schema=OBJECT),
            Capability(GATED, "probe", input_schema=OBJECT, exclusive=True)]
    return make_device("mhs://localhost/bindings/probe", [Resource("probe", "instrument.thermometer")], caps,
                       interlocks=[{"id": "lid", "required_for": [GATED]}], **kwargs)


class DuplicateBindingTests(unittest.TestCase):
    def test_two_pipettes_are_validated_against_their_own_binding(self) -> None:
        dev = pipettes()
        server, rpc, session = serve(dev)
        left = command(rpc, session, ASPIRATE, {"volume": 500}, resource="left")
        self.assertEqual(left["status"], "rejected", left)
        self.assertIn(error_code(left), ("MHS.CAPABILITY.INPUT_INVALID", "MHS.SAFETY.ENVELOPE_VIOLATION"), left)
        self.assertEqual(left["resource_ids"], ["left"])
        self.assertEqual(dev.bridge.native(), [], "the P20 never saw a 500 uL aspirate")
        right = command(rpc, session, ASPIRATE, {"volume": 500}, resource="right")
        self.assertEqual(right["status"], "completed", right)
        self.assertEqual(right["resource_ids"], ["right"])
        small = command(rpc, session, ASPIRATE, {"volume": 10}, resource="left")
        self.assertEqual(small["status"], "completed", small)
        self.assertEqual([(cid, res) for cid, res, _ in dev.bridge.native()], [(ASPIRATE, "right"), (ASPIRATE, "left")])

    def test_two_grippers_keep_their_own_limits_and_grants(self) -> None:
        dev = grippers(mode="hardware")
        server, rpc, _ = serve(dev, session=False, armed=True)
        opened = rpc("mhs.session.open", device_ids=[dev.device_id], mode="hardware",
                     capabilities=["cap.manipulation.*"])
        granted = sorted((item["capability_id"], item["resource"]) for item in opened["granted"])
        self.assertEqual(granted, [(GRASP, "left_arm"), (GRASP, "right_arm")])
        session = opened["session_id"]
        left = command(rpc, session, GRASP, {"force": 50}, resource="left_arm")
        self.assertEqual(error_code(left), "MHS.SAFETY.ENVELOPE_VIOLATION", left)
        self.assertEqual((details(left)["path"], details(left)["bound"]), ("force", 5))
        right = command(rpc, session, GRASP, {"force": 50}, resource="right_arm")
        self.assertEqual(right["status"], "completed", right)
        self.assertEqual([(cid, res) for cid, res, _ in dev.bridge.native()], [(GRASP, "right_arm")])
        published = rpc("mhs.devices.get", device_id=dev.device_id)["capabilities"]
        maxima = {(entry["capability_id"], entry["resource"]): entry["x-mhs-effective-limits"]["limits"]["force"]["max"]
                  for entry in published if entry["capability_id"] == GRASP}
        self.assertEqual(maxima, {(GRASP, "left_arm"): 5, (GRASP, "right_arm"): 100})
        listed = rpc("mhs.operations.list", session_id=session)["operations"]
        self.assertEqual([(item["capability_id"], item["resource"]) for item in listed], [(GRASP, "right_arm")])

    def test_an_omitted_resource_with_several_bindings_is_invalid_params(self) -> None:
        dev = pipettes()
        server, rpc, session = serve(dev)
        response = rpc.raw("mhs.command", session_id=session, capability_id=ASPIRATE, input={"volume": 5},
                           command_id=canonical.ulid(), deadline_ms=2000)
        self.assertIn("error", response, response)
        self.assertEqual(error_code(response), "MHS.PROTOCOL.INVALID_PARAMS", response)
        data = response["error"]["data"]
        self.assertEqual(data["details"]["reason"], "resource_required")
        self.assertEqual(sorted(data["details"]["resources"]), ["left", "right"])
        self.assertEqual(dev.bridge.native(), [])

    def test_a_stop_bound_twice_without_resource_points_to_the_estop(self) -> None:
        """A stop is never guessed onto one arm; the error says how to stop both (WP-09 decides fan-out)."""
        dev = grippers()
        server, rpc, session = serve(dev)
        response = rpc.raw("mhs.command", session_id=session, capability_id=STOP, input={},
                           command_id=canonical.ulid(), deadline_ms=2000)
        self.assertEqual(error_code(response), "MHS.PROTOCOL.INVALID_PARAMS", response)
        data = response["error"]["data"]
        self.assertEqual(data["details"]["reason"], "resource_required")
        self.assertIn("mhs.safety.estop", data.get("remediation", ""))
        self.assertEqual(dev.bridge.native(), [])

    def test_schema_get_names_the_binding(self) -> None:
        dev = pipettes()
        server, rpc, session = serve(dev)
        for resource, maximum in (("left", 20), ("right", 1000)):
            got = rpc("mhs.schema.get", ref=ASPIRATE, device_id=dev.device_id, resource=resource)
            self.assertEqual(got["schema"]["input_schema"]["properties"]["volume"]["maximum"], maximum)

    def test_an_estop_class_bound_twice_stops_both_resources(self) -> None:
        estop = "cap.motion.estop.v1"
        dev = make_device("mhs://localhost/bindings/twin-estop",
                          [Resource("left_arm", "robot.arm"), Resource("right_arm", "robot.arm")],
                          [Capability(estop, "left_arm"), Capability(estop, "right_arm"),
                           Capability(MOVE, "left_arm", input_schema=OBJECT)])
        server, rpc, session = serve(dev)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(sorted(res for _, res, _ in dev.bridge.native(estop)), ["left_arm", "right_arm"])
        routed = command(rpc, session, estop, {}, resource="ghost")
        self.assertIn(routed["status"], ("completed", "failed"), "a routed e-stop is never refused for its resource")
        self.assertTrue(server._latched[dev.device_id])
        rpc("mhs.safety.reset", session_id=session, deadline_ms=2000)

    def test_an_omitted_resource_with_one_binding_uses_it(self) -> None:
        dev = pipettes(only_left=True)
        server, rpc, session = serve(dev)
        receipt = command(rpc, session, ASPIRATE, {"volume": 5})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(dev.bridge.native()[0][1], "left")

    def test_a_duplicate_pair_is_refused_at_construction(self) -> None:
        caps = [Capability(ASPIRATE, "left"), Capability(ASPIRATE, "left")]
        for strict in (None, True):
            with self.subTest(strict=strict), self.assertRaises(MHSStrictError) as caught:
                make_device("mhs://localhost/bindings/dup", [Resource("left", "lab.pipette")], caps, strict=strict)
            self.assertIn("capability-duplicate", caught.exception.rules)
            self.assertIsInstance(caught.exception, ValueError)

    def test_strict_mode_serves_one_class_on_two_resources(self) -> None:
        dev = grippers(strict=True)
        server, rpc, session = serve(dev, strict=True)
        self.assertFalse([item for item in server.strict_findings if item["rule"] == "capability-duplicate"])
        left = command(rpc, session, GRASP, {"force": 50}, resource="left_arm")
        self.assertEqual(error_code(left), "MHS.SAFETY.ENVELOPE_VIOLATION", left)
        right = command(rpc, session, GRASP, {"force": 50}, resource="right_arm")
        self.assertEqual(right["status"], "completed", right)

    def test_every_binding_of_a_safe_state_action_runs_on_estop(self) -> None:
        """FIT-ROS-03 refined fix: both arms stop on e-stop."""
        dev = grippers()
        server, rpc, session = serve(dev)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(sorted(res for cid, res, _ in dev.bridge.native(STOP)), ["left_arm", "right_arm"])
        rpc("mhs.safety.reset", session_id=session, deadline_ms=2000)

    def test_a_permit_names_the_binding(self) -> None:
        dev = grippers()
        dev.safety.requires_permit = [GRASP]
        server, rpc, session = serve(dev)
        digest = canonical.digest({"capability_id": GRASP, "resource": "right_arm", "input": {"force": 1}})
        missing = rpc.raw("mhs.safety.permit", session_id=session, capability_id=GRASP, input_digest=digest,
                          input={"force": 1})
        self.assertEqual(error_code(missing), "MHS.PROTOCOL.INVALID_PARAMS", missing)
        self.assertEqual(missing["error"]["data"]["details"]["reason"], "resource_required")
        permit = rpc("mhs.safety.permit", session_id=session, capability_id=GRASP, resource="right_arm",
                     input_digest=digest, input={"force": 1})
        self.assertEqual(permit["resource"], "right_arm")
        other_arm = command(rpc, session, GRASP, {"force": 1}, resource="left_arm", permit_id=permit["permit_id"])
        self.assertEqual(error_code(other_arm), "MHS.SAFETY.PERMIT_INVALID", other_arm)
        self.assertEqual(dev.bridge.native(GRASP), [], "the permit of one arm does not move the other")
        receipt = command(rpc, session, GRASP, {"force": 1}, resource="right_arm", permit_id=permit["permit_id"])
        self.assertEqual(receipt["status"], "completed", receipt)


class ResourceMismatchTests(unittest.TestCase):
    """res_mismatch.py: a binding of 'left' ran on 'right' and on 'ghost'."""

    def test_an_unbound_or_unknown_resource_is_not_bound(self) -> None:
        dev = pipettes(only_left=True)
        server, rpc, session = serve(dev)
        for resource in ("right", "ghost"):
            with self.subTest(resource=resource):
                receipt = command(rpc, session, ASPIRATE, {"volume": 10}, resource=resource)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.CAPABILITY.NOT_BOUND", receipt)
                self.assertEqual(receipt["resource_ids"], [resource])
                self.assertEqual(receipt["capability_id"], ASPIRATE)
                self.assertEqual(details(receipt)["bound_resources"], ["left"])
        over = command(rpc, session, ASPIRATE, {"volume": 500}, resource="left")
        self.assertEqual(over["status"], "rejected", over)
        self.assertEqual(dev.bridge.native(), [], "no call reached the bridge")


class HybridAuthorityTests(unittest.TestCase):
    """hybrid.py: a binding of the model-authority arm drove the hardware-authority arm."""

    RESOURCES = [Resource("sim_arm", "robot.arm", state={}), Resource("real_arm", "robot.arm", state={})]

    def _hybrid(self, bound: tuple[str, ...]) -> Device:
        fidelity = dict(FIDELITY, authority={"sim_arm": "model", "real_arm": "hardware"})
        return make_device("mhs://localhost/bindings/hybrid", copy.deepcopy(self.RESOURCES),
                           [Capability(MOVE, resource, input_schema=OBJECT) for resource in bound],
                           mode="hybrid", fidelity=fidelity)

    def test_a_binding_of_the_model_arm_cannot_drive_the_hardware_arm(self) -> None:
        dev = self._hybrid(("sim_arm",))
        server, rpc, session = serve(dev)
        receipt = command(rpc, session, MOVE, {}, resource="real_arm")
        self.assertEqual(error_code(receipt), "MHS.CAPABILITY.NOT_BOUND", receipt)
        self.assertEqual(dev.bridge.native(), [])
        ok = command(rpc, session, MOVE, {}, resource="sim_arm")
        self.assertEqual(ok["status"], "completed", ok)

    def test_authority_is_evaluated_on_the_targeted_resource(self) -> None:
        dev = self._hybrid(("sim_arm", "real_arm"))
        server, rpc, session = serve(dev)
        refused = command(rpc, session, MOVE, {}, resource="real_arm")
        self.assertEqual(error_code(refused), "MHS.SAFETY.ENVELOPE_VIOLATION", refused)
        self.assertEqual(details(refused)["resource"], "real_arm")
        ok = command(rpc, session, MOVE, {}, resource="sim_arm")
        self.assertEqual(ok["status"], "completed", ok)
        self.assertEqual([res for _, res, _ in dev.bridge.native()], ["sim_arm"])


class GrantScopeTests(unittest.TestCase):
    def test_a_grant_can_name_one_binding(self) -> None:
        dev = grippers()
        server, rpc, _ = serve(dev, session=False)
        opened = rpc("mhs.session.open", device_ids=[dev.device_id], mode="simulated",
                     capabilities=[{"capability_id": GRASP, "resource": "left_arm"}])
        self.assertEqual([(item["capability_id"], item["resource"]) for item in opened["granted"]],
                         [(GRASP, "left_arm")])
        session = opened["session_id"]
        ok = command(rpc, session, GRASP, {"force": 1}, resource="left_arm")
        self.assertEqual(ok["status"], "completed", ok)
        response = rpc.raw("mhs.command", session_id=session, capability_id=GRASP, resource="right_arm",
                           input={"force": 1}, command_id=canonical.ulid(), deadline_ms=2000)
        self.assertEqual(error_code(response), "MHS.SESSION.CAPABILITY_NOT_GRANTED", response)
        self.assertEqual([res for _, res, _ in dev.bridge.native()], ["left_arm"])

    def test_a_grant_for_an_unbound_resource_is_refused(self) -> None:
        dev = grippers()
        server, rpc, _ = serve(dev, session=False)
        response = rpc.raw("mhs.session.open", device_ids=[dev.device_id], mode="simulated",
                           capabilities=[{"capability_id": GRASP, "resource": "ghost"}])
        self.assertEqual(error_code(response), "MHS.CAPABILITY.NOT_BOUND", response)


class RevisionTests(unittest.TestCase):
    """TESTS-04 / SDK-07: only a command that changed the device state advances the revision."""

    def _device(self, **kwargs: Any) -> Device:
        return probe_device(**kwargs)

    def test_the_reference_conveyor_world_state_leaves_the_revision(self) -> None:
        server, rpc, dev, session = conveyor()
        resource = dev.primary_resource.resource_id
        before = revision(rpc, session, resource)
        state = command(rpc, session, "cap.world.state.v1", {})
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual((state["state_revision_before"], state["state_revision_after"]), (before, before))
        self.assertEqual(revision(rpc, session, resource), before)
        step = command(rpc, session, "cap.world.step.v1", {"ticks": 1}, expected_revision=before)
        self.assertEqual(step["status"], "completed", step)
        self.assertEqual(step["state_revision_after"], before + 1)

    def test_a_catalogued_read_never_advances_the_revision(self) -> None:
        dev = self._device()
        server, rpc, session = serve(dev)
        before = revision(rpc, session, "probe")
        receipt = command(rpc, session, TEMPERATURE, {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(dev.bridge.states["probe"].get("reads"), 1)
        self.assertEqual((receipt["state_revision_before"], receipt["state_revision_after"]), (before, before))
        self.assertEqual(revision(rpc, session, "probe"), before)

    def test_only_a_state_change_advances_the_revision(self) -> None:
        dev = self._device()
        server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "probe")
        noop = command(rpc, session, NOOP, {})
        self.assertEqual(noop["status"], "completed", noop)
        self.assertEqual(noop["state_revision_after"], r0, "completed without a state change")
        failed = command(rpc, session, FAIL, {})
        self.assertEqual(failed["status"], "failed", failed)
        self.assertEqual(failed["state_revision_after"], r0, "failed without a state change")
        self.assertEqual(revision(rpc, session, "probe"), r0)
        touched = command(rpc, session, TOUCH, {})
        self.assertEqual((touched["state_revision_before"], touched["state_revision_after"]), (r0, r0 + 1))
        broken = command(rpc, session, FAIL_AFTER, {})
        self.assertEqual(broken["status"], "failed", broken)
        self.assertEqual(broken["state_revision_after"], r0 + 2, "a failed call that changed the state")
        self.assertEqual(revision(rpc, session, "probe"), r0 + 2)

    def test_a_stop_is_not_delayed_by_the_state_read(self) -> None:
        """Regression guard for the revision rule: a bridge read that waits for a
        lock a running call holds must not hold back a stop dispatched beside it."""
        long_call = "x-cap.test.hold.v1"

        class LockingBridge(MultiBridge):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self.lock = threading.Lock()
                self.stop_at: float | None = None

            def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
                with self.lock:
                    return super().read(resource_id, fields, ctx)

            def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
                if capability_id == long_call:
                    with self.lock:
                        time.sleep(1.0)
                    return {"held": True}
                if capability_id == STOP:
                    self.stop_at = time.monotonic()
                return super().call(capability_id, args, ctx)

        bridge = LockingBridge("mhs://localhost/bindings/locking", {"arm": {}})
        dev = make_device("mhs://localhost/bindings/locking", [Resource("arm", "robot.arm")],
                          [Capability(long_call, "arm", input_schema=OBJECT, exclusive=True),
                           Capability(STOP, "arm")], achieved_by=(STOP,), bridge=bridge)
        server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "arm")
        worker = threading.Thread(target=lambda: command(rpc, session, long_call, {}))
        worker.start()
        time.sleep(0.1)
        sent = time.monotonic()
        stop = command(rpc, session, STOP, {})
        self.assertEqual(stop["status"], "completed", stop)
        self.assertLess(bridge.stop_at - sent, 0.5, "the stop reached the bridge at once")
        self.assertGreater(stop["state_revision_after"], r0, "a stop always advances the revision")
        worker.join(5)

    def test_expected_revision_is_rechecked_under_the_device_lock(self) -> None:
        """sdk-core e7.py (a): the revision moved while the interlock was read."""
        dev = self._device()
        dev.bridge.interlock_states["lid"] = "closed"
        dev.bridge.interlock_delay = 0.3
        server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "probe")
        holder: dict[str, Any] = {}
        worker = threading.Thread(target=lambda: holder.setdefault(
            "a", command(rpc, session, GATED, {}, expected_revision=r0)))
        worker.start()
        time.sleep(0.05)
        other = command(rpc, session, TOUCH, {})
        self.assertEqual(other["state_revision_after"], r0 + 1, other)
        worker.join(5)
        receipt = holder["a"]
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.CONFLICT.REVISION", receipt)
        self.assertEqual(receipt["error"].get("current_revision"), r0 + 1, "the true current revision")
        self.assertEqual((receipt["state_revision_before"], receipt["state_revision_after"]), (r0 + 1, r0 + 1))
        self.assertEqual(dev.bridge.native(GATED), [], "nothing ran")

    def test_a_revision_that_moves_before_registration_refuses_and_returns_the_permit(self) -> None:
        """Plan 3.6 step 12: the re-check when the operation is registered (a non-exclusive race)."""
        dev = self._device()
        dev.safety.requires_permit = [TOUCH]
        server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "probe")
        digest = canonical.digest({"capability_id": TOUCH, "resource": "probe", "input": {}})
        permit = rpc("mhs.safety.permit", session_id=session, capability_id=TOUCH, input_digest=digest,
                     input={})["permit_id"]
        original = server._consume_permit

        def consume_then_race(*args: Any, **kwargs: Any) -> None:
            original(*args, **kwargs)
            server._bump_revision(dev)  # another completion lands right after the post-lock check

        server._consume_permit = consume_then_race
        receipt = command(rpc, session, TOUCH, {}, expected_revision=r0, permit_id=permit)
        self.assertEqual(error_code(receipt), "MHS.CONFLICT.REVISION", receipt)
        self.assertEqual(receipt["error"]["current_revision"], r0 + 1)
        self.assertEqual(dev.bridge.native(TOUCH), [])
        self.assertFalse(server._permits[permit].used, "nothing ran: the permit is not spent")
        server._consume_permit = original
        retried = command(rpc, session, TOUCH, {}, expected_revision=r0 + 1, permit_id=permit)
        self.assertEqual(retried["status"], "completed", retried)

    def test_a_refused_command_on_the_replay_device_reports_the_recorded_revision(self) -> None:
        """conformance-verify v_replay.py."""
        from pathlib import Path
        bundle = Path(__file__).resolve().parents[2] / "docs" / "reports" / "replay-bundle-conveyor.json"
        server = build_server(build_endpoint("replay", bundle=str(bundle)), log_ready=False)
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        dev = next(iter(server.devices.values()))
        session = rpc("mhs.session.open", device_ids=[dev.device_id], mode="replay")["session_id"]
        resource = dev.primary_resource.resource_id
        before = rpc("mhs.resource.read", session_id=session, resource_id=resource, deadline_ms=2000)
        receipt = command(rpc, session, "cap.world.state.v1", {})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.MODE.READ_ONLY", receipt)
        self.assertEqual((receipt["state_revision_before"], receipt["state_revision_after"]),
                         (before["revision"], before["revision"]))
        after = rpc("mhs.resource.read", session_id=session, resource_id=resource, deadline_ms=2000)
        self.assertEqual((after["revision"], after["state_hash"]), (before["revision"], before["state_hash"]))


class ConfigureWriteTests(unittest.TestCase):
    """resource.write is served by the cap.device.configure.v1 binding of the target resource."""

    STATE_SCHEMA = {"type": "object", "properties": {
        "setpoint": {"type": "number", "x-mhs-unit": "Cel"},
        "pump": {"type": "number", "x-mhs-unit": "/min"},
        "temperature": {"type": "number", "x-mhs-unit": "Cel", "readOnly": True}}}

    def _bath(self, *, configure: bool = True, envelope: Mapping[str, Any] | None = None,
              bridge: Bridge | None = None, **kwargs: Any) -> Device:
        caps = [Capability(SETPOINT, "bath", verb="write")]
        if configure:
            caps.append(Capability(CONFIGURE, "bath", verb="write"))
        return make_device("mhs://localhost/bindings/bath",
                           [Resource("bath", "thermal.zone", state_schema=copy.deepcopy(self.STATE_SCHEMA))],
                           caps, envelope=envelope, bridge=bridge, risk="R2",
                           states={"bath": {"setpoint": 20.0, "pump": 0, "temperature": 21.0}}, **kwargs)

    def _write(self, rpc: Rpc, session: str, patch: Any, resource: str = "bath", **params: Any) -> dict[str, Any]:
        params.setdefault("deadline_ms", 3000)
        return rpc("mhs.resource.write", session_id=session, resource_id=resource, patch=patch, **params)

    def test_a_write_is_a_configure_command(self) -> None:
        dev = self._bath()
        server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "bath")
        receipt = self._write(rpc, session, {"setpoint": 40.0})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["capability_id"], CONFIGURE)
        self.assertEqual(receipt["resource_ids"], ["bath"])
        self.assertEqual(receipt["output"], {"applied": {"setpoint": 40.0}, "revision": r0 + 1})
        self.assertEqual(receipt["state_revision_after"], r0 + 1)
        self.assertEqual(receipt["input_digest"],
                         canonical.digest({"capability_id": CONFIGURE, "resource": "bath",
                                           "input": {"setpoint": 40.0}}))
        self.assertEqual(dev.bridge.native(), [(CONFIGURE, "bath", {"setpoint": 40.0})])
        same = self._write(rpc, session, {"setpoint": 40.0})
        self.assertEqual(same["status"], "completed", same)
        self.assertEqual(same["output"]["revision"], r0 + 1, "nothing changed: the revision stays")
        self.assertEqual(revision(rpc, session, "bath"), r0 + 1)

    def test_read_only_and_unknown_fields_are_refused(self) -> None:
        """v_write_coupling.py: the measured temperature was written; a stray key reached the bridge."""
        dev = self._bath()
        server, rpc, session = serve(dev)
        read_only = self._write(rpc, session, {"temperature": 5.0})
        self.assertEqual(read_only["status"], "rejected", read_only)
        self.assertEqual(error_code(read_only), "MHS.RESOURCE.NOT_WRITABLE", read_only)
        self.assertEqual(details(read_only)["fields"], ["temperature"])
        unknown = self._write(rpc, session, {"target_temperature": 30.0})
        self.assertEqual(error_code(unknown), "MHS.RESOURCE.FIELD_UNKNOWN", unknown)
        self.assertEqual(details(unknown)["fields"], ["target_temperature"])
        self.assertEqual(unknown["capability_id"], CONFIGURE)
        typed = self._write(rpc, session, {"setpoint": "hot"})
        self.assertEqual(error_code(typed), "MHS.CAPABILITY.INPUT_INVALID", typed)
        empty = self._write(rpc, session, {})
        self.assertEqual(error_code(empty), "MHS.CAPABILITY.INPUT_INVALID", empty)
        self.assertEqual(dev.bridge.native(), [])

    def test_the_configure_class_through_mhs_command_refuses_unknown_keys(self) -> None:
        """4c verifier p11: the 'parameters' form reached the bridge in compatibility mode."""
        dev = self._bath()
        server, rpc, session = serve(dev)
        receipt = command(rpc, session, CONFIGURE, {"parameters": {"setpoint": 1}}, resource="bath")
        self.assertEqual(error_code(receipt), "MHS.RESOURCE.FIELD_UNKNOWN", receipt)
        self.assertEqual(dev.bridge.native(), [])
        ok = command(rpc, session, CONFIGURE, {"pump": 10}, resource="bath")
        self.assertEqual(ok["status"], "completed", ok)
        self.assertEqual(ok["output"]["applied"], {"pump": 10})

    def test_limits_are_keyed_by_state_paths(self) -> None:
        """v_write_coupling.py: {setpoint: 300} completed although the class limit says 80."""
        dev = self._bath(envelope={CONFIGURE: {"setpoint": {"max": 80, "unit": "Cel"}}})
        server, rpc, session = serve(dev)
        receipt = self._write(rpc, session, {"setpoint": 300.0})
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual((details(receipt)["path"], details(receipt)["bound"]), ("setpoint", 80))
        self.assertEqual(dev.bridge.native(), [])

    def test_a_resource_without_a_configure_binding_is_not_writable(self) -> None:
        """The patch is never passed as the input of another write class."""
        dev = self._bath(configure=False)
        server, rpc, session = serve(dev)
        response = rpc.raw("mhs.resource.write", session_id=session, resource_id="bath",
                           patch={"setpoint": 300.0}, deadline_ms=2000)
        self.assertEqual(error_code(response), "MHS.RESOURCE.NOT_WRITABLE", response)
        explicit = rpc.raw("mhs.resource.write", session_id=session, resource_id="bath", capability_id=SETPOINT,
                           patch={"target_temperature": 30.0}, deadline_ms=2000)
        self.assertEqual(error_code(explicit), "MHS.RESOURCE.NOT_WRITABLE", explicit)
        self.assertEqual(dev.bridge.native(), [])

    def test_writes_are_routed_by_resource_and_grant(self) -> None:
        schema = {"type": "object", "properties": {"gain": {"type": "number", "x-mhs-unit": "1"}}}
        dev = make_device("mhs://localhost/bindings/amps",
                          [Resource("left", "device", state_schema=copy.deepcopy(schema)),
                           Resource("right", "device", state_schema=copy.deepcopy(schema))],
                          [Capability(CONFIGURE, "left"), Capability(CONFIGURE, "right")],
                          states={"left": {"gain": 1}, "right": {"gain": 1}})
        server, rpc, _ = serve(dev, session=False)
        session = rpc("mhs.session.open", device_ids=[dev.device_id], mode="simulated",
                      capabilities=[{"capability_id": CONFIGURE, "resource": "right"}])["session_id"]
        receipt = self._write(rpc, session, {"gain": 2}, resource="right")
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(dev.bridge.states, {"left": {"gain": 1}, "right": {"gain": 2}})
        response = rpc.raw("mhs.resource.write", session_id=session, resource_id="left", patch={"gain": 3},
                           deadline_ms=2000)
        self.assertEqual(error_code(response), "MHS.SESSION.CAPABILITY_NOT_GRANTED", response)
        self.assertEqual(dev.bridge.states["left"], {"gain": 1})

    def test_a_bridge_write_method_serves_the_write(self) -> None:
        class PatchBridge(MultiBridge):
            def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
                if capability_id == CONFIGURE:
                    raise unsupported(capability_id)  # what the base Bridge.call does
                return super().call(capability_id, args, ctx)

            def write(self, resource_id, patch, ctx=None):  # noqa: ANN001
                with self._calls_lock:
                    self.calls.append(("write", resource_id, dict(patch)))
                self.states[resource_id].update(patch)
                return {"applied": {key: round(value) for key, value in patch.items()}}

        bridge = PatchBridge("mhs://localhost/bindings/bath", {"bath": {"setpoint": 20.0, "pump": 0}})
        dev = self._bath(bridge=bridge)
        server, rpc, session = serve(dev)
        receipt = self._write(rpc, session, {"setpoint": 40.4})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["applied"], {"setpoint": 40}, "the bridge reports what it applied")
        self.assertEqual(bridge.native(), [("write", "bath", {"setpoint": 40.4})])

    def test_rejected_write_receipts_name_the_configure_class(self) -> None:
        dev = self._bath()
        server, rpc, session = serve(dev)
        rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=2000)
        latched = self._write(rpc, session, {"setpoint": 30.0})
        self.assertEqual(error_code(latched), "MHS.SAFETY.ESTOP_ENGAGED", latched)
        self.assertEqual(latched["capability_id"], CONFIGURE)
        rpc("mhs.safety.reset", session_id=session, deadline_ms=2000)
        bad = self._write(rpc, session, "not an object")
        self.assertEqual(error_code(bad), "MHS.CAPABILITY.INPUT_INVALID", bad)
        self.assertEqual(bad["capability_id"], CONFIGURE)

    def test_a_strict_write_receipt_is_valid_against_the_class_output(self) -> None:
        dev = self._bath(strict=True, envelope={
            CONFIGURE: {"setpoint": {"min": 0, "max": 80, "unit": "Cel"}, "pump": {"min": 0, "max": 100, "unit": "/min"}},
            SETPOINT: {"target_temperature": {"min": 0, "max": 80, "unit": "Cel"}}})
        server, rpc, session = serve(dev, strict=True)
        receipt = self._write(rpc, session, {"pump": 12})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(sorted(receipt["output"]), ["applied", "revision"])


class CallOnlyBridge(Bridge):
    """p1_unreadable.py: a bridge without read() (the base ``Bridge.read`` raises unsupported)."""

    bridge_id = "tests.safety.callonly"

    def __init__(self, device_id: str) -> None:
        super().__init__(device_id=device_id)
        self.position = 0
        self.calls: list[str] = []

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        self.calls.append(capability_id)
        if capability_id == MOVE:
            self.position += int((args or {}).get("delta", 1))
            return {"position": self.position}
        if capability_id == FAIL:
            raise RuntimeError("the native call failed")
        return {"ok": True}


class UnreadableStateTests(unittest.TestCase):
    """Plan 3.7 fails closed: a state hash that cannot be computed is an unknown change, which advances."""

    DEVICE = "mhs://localhost/bindings/callonly"

    def _device(self, bridge: Bridge) -> Device:
        return make_device(self.DEVICE, [Resource("arm", "robot.arm", state={"position": 0})],
                           [Capability(MOVE, "arm", input_schema={
                               "type": "object", "properties": {"delta": {"type": "integer"}}}),
                            Capability(FAIL, "arm", input_schema=OBJECT),
                            Capability(TOUCH, "arm", input_schema=OBJECT)], bridge=bridge)

    def test_a_bridge_without_read_advances_the_revision_and_keeps_expected_revision(self) -> None:
        """p1_unreadable.py: A moved the arm at 0 -> 0, then B with the stale revision 0 moved it again."""
        bridge = CallOnlyBridge(self.DEVICE)
        dev = self._device(bridge)
        server, rpc, session = serve(dev)
        moved = command(rpc, session, MOVE, {"delta": 5})
        self.assertEqual(moved["status"], "completed", moved)
        r0 = moved["state_revision_before"]
        self.assertEqual(moved["state_revision_after"], r0 + 1, "the change is unknown: the revision advances")
        stale = command(rpc, session, MOVE, {"delta": 5}, expected_revision=r0)
        self.assertEqual(stale["status"], "rejected", stale)
        self.assertEqual(error_code(stale), "MHS.CONFLICT.REVISION", stale)
        self.assertEqual(stale["error"]["current_revision"], r0 + 1)
        self.assertEqual(bridge.position, 5, "the stale command never reached the bridge")
        fresh = command(rpc, session, MOVE, {"delta": 1}, expected_revision=r0 + 1)
        self.assertEqual(fresh["status"], "completed", fresh)

    def test_a_read_that_fails_before_and_after_a_failed_call_advances_the_revision(self) -> None:
        class FailingRead(MultiBridge):
            def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
                raise RuntimeError("the device did not answer the state query")

        bridge = FailingRead(self.DEVICE, {"arm": {}})
        dev = self._device(bridge)
        server, rpc, session = serve(dev)
        r0 = server._current_revision(dev)
        failed = command(rpc, session, FAIL, {})
        self.assertEqual(failed["status"], "failed", failed)
        self.assertEqual((failed["state_revision_before"], failed["state_revision_after"]), (r0, r0 + 1),
                         "a failed call whose effect cannot be read is an unknown change")
        stale = command(rpc, session, TOUCH, {}, expected_revision=r0)
        self.assertEqual(error_code(stale), "MHS.CONFLICT.REVISION", stale)

    def test_one_unreadable_resource_makes_the_change_unknown(self) -> None:
        class HalfReadable(MultiBridge):
            def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
                if resource_id == "aux":
                    raise unsupported(resource_id, kind="resource")
                return super().read(resource_id, fields, ctx)

        bridge = HalfReadable("mhs://localhost/bindings/half", {"arm": {}, "aux": {}})
        dev = make_device("mhs://localhost/bindings/half", [Resource("arm", "robot.arm"), Resource("aux", "device")],
                          [Capability(NOOP, "arm", input_schema=OBJECT)], bridge=bridge)
        server, rpc, session = serve(dev)
        r0 = server._current_revision(dev)
        receipt = command(rpc, session, NOOP, {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["state_revision_after"], r0 + 1)

    def test_a_hung_state_read_is_bounded_and_counts_as_a_change(self) -> None:
        """The reads around the call are bounded; a read that does not answer is an unknown change."""
        class HangingRead(MultiBridge):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self.hang = False
                self.release = threading.Event()

            def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
                if self.hang:
                    self.release.wait(5)
                return super().read(resource_id, fields, ctx)

        bridge = HangingRead(self.DEVICE, {"arm": {}})
        dev = self._device(bridge)
        server, rpc, session = serve(dev)
        r0 = server._current_revision(dev)
        bridge.hang = True
        try:
            with mock.patch.object(server_module, "_REVISION_READ_BOUND_S", 0.1, create=True):
                sent = time.monotonic()
                receipt = command(rpc, session, TOUCH, {}, deadline_ms=3000)
                elapsed = time.monotonic() - sent
        finally:
            bridge.release.set()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertLess(elapsed, 1.5, "neither state read held the command")
        self.assertEqual(receipt["state_revision_after"], r0 + 1, "an unanswered read is an unknown change")
        self.assertEqual(bridge.native(TOUCH), [(TOUCH, "arm", {})])


class OverlapBridge(MultiBridge):
    """Records every native call that started while a state read was running (4d r2 ``q2`` / ``q3_standalone``)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.read_delay = 0.0
        #: per-read delays, in the order the reads start (then read_delay)
        self.delays: list[float] = []
        self.in_read = 0
        self.overlaps: list[str] = []
        self.call_times: list[float] = []
        self.hang_after_call = False
        self.hang_reads = False
        self.release = threading.Event()
        self._read_lock = threading.Lock()

    def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
        with self._read_lock:
            self.in_read += 1
            delay = self.delays.pop(0) if self.delays else self.read_delay
        try:
            if self.hang_reads:
                self.release.wait(5)
            elif delay:
                time.sleep(delay)
            return super().read(resource_id, fields, ctx)
        finally:
            with self._read_lock:
                self.in_read -= 1

    def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
        with self._read_lock:
            self.call_times.append(time.monotonic())
            if self.in_read:
                self.overlaps.append(capability_id)
        try:
            return super().call(capability_id, args, ctx)
        finally:
            if self.hang_after_call:
                self.hang_reads = True


class StateReadTimingTests(unittest.TestCase):
    """The revision reads around a command (4d r2 verifier minors): never beside an exclusive call, inside the deadline."""

    DEVICE = "mhs://localhost/bindings/overlap"

    def _device(self, *, exclusive: bool) -> tuple[Device, OverlapBridge, Rpc, str]:
        bridge = OverlapBridge(self.DEVICE, {"psu": {}})
        dev = make_device(self.DEVICE, [Resource("psu", "power.supply")],
                          [Capability(TOUCH, "psu", input_schema=OBJECT, exclusive=exclusive)], bridge=bridge)
        server, rpc, session = serve(dev)
        return dev, bridge, rpc, session

    def test_an_exclusive_call_never_overlaps_a_state_read(self) -> None:
        """q2: the read before the call timed out and kept running while the exclusive call ran."""
        dev, bridge, rpc, session = self._device(exclusive=True)
        # first command: a slow read before its call, a slower one after it;
        # then fast reads.  Every read outlives the 0.1 s bound.
        bridge.delays = [0.3, 0.6]
        with mock.patch.object(server_module, "_REVISION_READ_BOUND_S", 0.1, create=True):
            first = command(rpc, session, TOUCH, {}, deadline_ms=3000)
            # Sent while the first command's read after its call still runs:
            # the device is busy until it returned.
            second = command(rpc, session, TOUCH, {}, deadline_ms=3000)
            time.sleep(0.8)
            third = command(rpc, session, TOUCH, {}, deadline_ms=3000)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(first["state_revision_after"], first["state_revision_before"] + 1,
                         "the read after the call did not answer in time: an unknown change")
        self.assertEqual(second["status"], "rejected", second)
        self.assertEqual(error_code(second), "MHS.DEVICE.BUSY", second)
        self.assertEqual(third["status"], "completed", third)
        self.assertEqual(len(bridge.native(TOUCH)), 2)
        self.assertEqual(bridge.overlaps, [], "an exclusive call started while the server's state read ran")

    def test_the_read_before_the_call_takes_at_most_half_the_budget(self) -> None:
        """A hung pre-call read is capped at half of what is left of the deadline, not at the 1 s bound."""
        dev, bridge, rpc, session = self._device(exclusive=False)
        bridge.hang_reads = True
        try:
            sent = time.monotonic()
            receipt = command(rpc, session, TOUCH, {}, deadline_ms=700)
        finally:
            bridge.release.set()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(bridge.call_times), 1)
        self.assertLess(bridge.call_times[0] - sent, 0.6, "the call waited for the 1 s bound")
        self.assertEqual(receipt["state_revision_after"], receipt["state_revision_before"] + 1,
                         "an unanswered read is an unknown change")

    def test_the_read_after_the_call_answers_within_the_deadline(self) -> None:
        """q3_standalone: a fast call, a slow read after it and a short deadline gave unknown TIMEOUT 0 -> 0."""
        dev, bridge, rpc, session = self._device(exclusive=False)
        bridge.hang_after_call = True
        try:
            sent = time.monotonic()
            receipt = command(rpc, session, TOUCH, {}, deadline_ms=700)
            elapsed = time.monotonic() - sent
        finally:
            bridge.release.set()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertLess(elapsed, 0.7 + 0.2, receipt)
        self.assertEqual(receipt["state_revision_after"], receipt["state_revision_before"] + 1,
                         "the read after the call did not answer: an unknown change")


class EstopBindingRemovedTests(unittest.TestCase):
    """4d r2 blocker (``q1_hw.py``): the e-stop path is the bindings served now, and fails closed."""

    ESTOP = "cap.motion.estop.v1"

    def _arm(self, mode: str) -> tuple[Device, MHSServer, Rpc, str]:
        did = f"mhs://localhost/bindings/estop-{mode}"
        dev = make_device(did, [Resource("arm", "robot.arm")],
                          [Capability(self.ESTOP, "arm", input_schema=OBJECT),
                           Capability(TOUCH, "arm", input_schema=OBJECT)], mode=mode)
        server, rpc, session = serve(dev, **({"armed": True} if mode == "hardware" else {}))
        return dev, server, rpc, session

    def _estop(self, rpc: Rpc, session: str, dev: Device) -> dict[str, Any]:
        return rpc("mhs.safety.estop", session_id=session, device_id=dev.device_id, reason="test",
                   command_id=canonical.ulid(), deadline_ms=2000)

    def test_an_estop_binding_removed_after_start_up_is_not_reported_engaged(self) -> None:
        for mode in ("simulated", "hardware"):
            with self.subTest(mode=mode):
                dev, server, rpc, session = self._arm(mode)
                del dev.capabilities[0]
                receipt = self._estop(rpc, session, dev)
                output = receipt.get("output") or {}
                self.assertNotEqual(output.get("estop"), "engaged", receipt)
                self.assertEqual(dev.bridge.native(), [])
                if mode == "hardware":
                    self.assertEqual(receipt["status"], "failed", receipt)
                    self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
                    self.assertFalse(output.get("safe_state_achieved"), receipt)
                    self.assertEqual(details(receipt)["reason"], "no_stop_path", receipt)
                else:
                    self.assertEqual(receipt["status"], "completed", receipt)
                    self.assertEqual(output.get("estop"), "software_only", receipt)

    def test_the_capability_stop_path_without_a_binding_fails_closed(self) -> None:
        """A capability stop path that finds no binding to call is never 'engaged'."""
        dev, server, rpc, session = self._arm("hardware")
        del dev.capabilities[0]
        with mock.patch.object(MHSServer, "_native_estop_path", return_value="capability"):
            receipt = self._estop(rpc, session, dev)
            output = receipt.get("output") or {}
            self.assertEqual(receipt["status"], "failed", receipt)
            self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
            self.assertEqual(output.get("estop"), "failed", receipt)
            self.assertFalse(output.get("safe_state_achieved"), receipt)
            self.assertEqual(details(receipt)["reason"], "native_failed", receipt)
        self.assertEqual(dev.bridge.native(), [])

    def test_an_estop_binding_added_after_start_up_is_called(self) -> None:
        dev = make_device("mhs://localhost/bindings/estop-late", [Resource("arm", "robot.arm")],
                          [Capability(TOUCH, "arm", input_schema=OBJECT)])
        server, rpc, session = serve(dev)
        dev.capabilities.append(Capability(self.ESTOP, "arm", input_schema=OBJECT))
        receipt = self._estop(rpc, session, dev)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((receipt.get("output") or {}).get("estop"), "engaged", receipt)
        self.assertEqual([item[:2] for item in dev.bridge.native()], [(self.ESTOP, "arm")])


class LateBindingTests(unittest.TestCase):
    """p3_late_dup.py: the binding set is checked again when it changes after construction."""

    def test_a_duplicate_pair_appended_before_the_server_starts_is_refused(self) -> None:
        for strict in (None, True):
            with self.subTest(strict=strict):
                dev = pipettes(only_left=True)
                dev.capabilities.append(Capability(ASPIRATE, "left", limits={"volume": {"max": 20, "unit": "uL"}}))
                with self.assertRaises(MHSStrictError) as caught, warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    MHSServer("mhs://localhost/bindings", [dev], log_ready=False, strict=strict)
                self.assertIn("capability-duplicate", caught.exception.rules)

    def test_a_duplicate_appended_to_a_strict_device_is_refused_at_start_up(self) -> None:
        """4d r2 ``q8_strict_device_dup.py``: the strict branch reused the device's resolution from before."""
        def schema(maximum: int) -> dict[str, Any]:
            return {"type": "object", "properties": {
                "volume": {"type": "number", "minimum": 0, "maximum": maximum, "x-mhs-unit": "uL"}}}

        for server_strict in (None, True):
            with self.subTest(server_strict=server_strict):
                dev = make_device("mhs://localhost/bindings/strict-dup", [Resource("left", "lab.pipette", state={})],
                                  [Capability(ASPIRATE, "left", input_schema=schema(20),
                                              limits={"volume": {"min": 0, "max": 20, "unit": "uL"}})],
                                  strict=True)
                dev.capabilities.append(Capability(ASPIRATE, "left", input_schema=schema(1000),
                                                   limits={"volume": {"min": 0, "max": 1000, "unit": "uL"}}))
                with self.assertRaises(MHSStrictError) as caught, warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    MHSServer("mhs://localhost/bindings", [dev], log_ready=False, strict=server_strict)
                self.assertIn("capability-duplicate", caught.exception.rules)
                self.assertEqual(dev.bridge.native(), [])

    def test_a_duplicate_pair_appended_after_start_up_is_refused(self) -> None:
        dev = pipettes(only_left=True)
        server, rpc, session = serve(dev)
        dev.capabilities.append(Capability(ASPIRATE, "left", limits={"volume": {"max": 1000, "unit": "uL"}}))
        receipt = command(rpc, session, ASPIRATE, {"volume": 10}, resource="left")
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.ADAPTER.MANIFEST_INVALID", receipt)
        self.assertIn("capability-duplicate", str(receipt["error"]))
        self.assertEqual(dev.bridge.native(), [])

    def test_a_binding_replaced_after_start_up_is_served(self) -> None:
        dev = pipettes()
        server, rpc, session = serve(dev)
        ok = command(rpc, session, ASPIRATE, {"volume": 15}, resource="left")
        self.assertEqual(ok["status"], "completed", ok)
        dev.capabilities[0] = Capability(ASPIRATE, "left", limits={"volume": {"min": 0, "max": 10, "unit": "uL"}},
                                         input_schema={"type": "object", "properties": {
                                             "volume": {"type": "number", "minimum": 0, "x-mhs-unit": "uL"}}})
        narrowed = command(rpc, session, ASPIRATE, {"volume": 15}, resource="left")
        self.assertEqual(error_code(narrowed), "MHS.SAFETY.ENVELOPE_VIOLATION", narrowed)
        self.assertEqual(details(narrowed)["bound"], 10)
        dev.capabilities.append(Capability(STOP, "right"))
        session = rpc("mhs.session.open", device_ids=[dev.device_id], mode="simulated")["session_id"]
        stop = command(rpc, session, STOP, {}, resource="right")
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(dev.bridge.native()[-1][:2], (STOP, "right"))


class NestedConfigureTests(unittest.TestCase):
    """p2_write.py: nested state properties follow the same rules as top-level ones."""

    STATE_SCHEMA = {"type": "object", "properties": {
        "ch1": {"type": "object", "properties": {
            "voltage": {"type": "number", "x-mhs-unit": "V"},
            "measured_current": {"type": "number", "x-mhs-unit": "A", "readOnly": True}}},
        "calibration": {"type": "object", "readOnly": True, "properties": {
            "offset": {"type": "number", "x-mhs-unit": "V"}}},
        "channels": {"type": "array", "items": {"type": "object", "properties": {
            "setpoint": {"type": "number", "x-mhs-unit": "V"},
            "reading": {"type": "number", "x-mhs-unit": "V", "readOnly": True}}}},
        "tags": {"type": "object"},
        "serial": {"type": "string", "readOnly": True}}}

    def _psu(self) -> tuple[Device, Rpc, str]:
        dev = make_device("mhs://localhost/bindings/psu",
                          [Resource("psu", "power.supply", state_schema=copy.deepcopy(self.STATE_SCHEMA))],
                          [Capability(CONFIGURE, "psu", verb="write")],
                          states={"psu": {"ch1": {"voltage": 1.0, "measured_current": 0.1}, "serial": "X"}})
        server, rpc, session = serve(dev)
        return dev, rpc, session

    def _write(self, rpc: Rpc, session: str, patch: Any) -> dict[str, Any]:
        return rpc("mhs.resource.write", session_id=session, resource_id="psu", patch=patch, deadline_ms=3000,
                   command_id=canonical.ulid())

    def test_a_nested_read_only_leaf_is_not_writable(self) -> None:
        dev, rpc, session = self._psu()
        for patch, field in (({"ch1": {"measured_current": 9.9}}, "ch1.measured_current"),
                             ({"calibration": {"offset": 0.5}}, "calibration"),
                             ({"channels": [{"setpoint": 1.0}, {"reading": 2.0}]}, "channels[1].reading"),
                             ({"serial": "Y"}, "serial")):
            with self.subTest(patch=patch):
                receipt = self._write(rpc, session, patch)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.RESOURCE.NOT_WRITABLE", receipt)
                self.assertEqual(details(receipt)["fields"], [field])
        self.assertEqual(dev.bridge.native(), [])

    def test_a_nested_unknown_key_is_field_unknown(self) -> None:
        dev, rpc, session = self._psu()
        receipt = self._write(rpc, session, {"ch1": {"voltage": 2.0, "bogus": 1}})
        self.assertEqual(error_code(receipt), "MHS.RESOURCE.FIELD_UNKNOWN", receipt)
        self.assertEqual(details(receipt)["fields"], ["ch1.bogus"])
        element = self._write(rpc, session, {"channels": [{"setpoint": 1.0, "bogus": 1}]})
        self.assertEqual(error_code(element), "MHS.RESOURCE.FIELD_UNKNOWN", element)
        self.assertEqual(details(element)["fields"], ["channels[0].bogus"])
        self.assertEqual(dev.bridge.native(), [])

    def test_nested_writable_parameters_are_written(self) -> None:
        dev, rpc, session = self._psu()
        receipt = self._write(rpc, session, {"ch1": {"voltage": 2.0}})
        self.assertEqual(receipt["status"], "completed", receipt)
        free = self._write(rpc, session, {"tags": {"anything": "goes"}})
        self.assertEqual(free["status"], "completed", free)
        self.assertEqual([args for _, _, args in dev.bridge.native()],
                         [{"ch1": {"voltage": 2.0}}, {"tags": {"anything": "goes"}}])

    COMPOSED_SCHEMA = {"type": "object", "$defs": {
        "meter": {"type": "object", "properties": {
            "range": {"type": "number", "x-mhs-unit": "A"},
            "reading": {"type": "number", "x-mhs-unit": "A", "readOnly": True}}}},
        "properties": {
            "ch1": {"allOf": [{"type": "object", "properties": {
                "voltage": {"type": "number", "x-mhs-unit": "V"},
                "measured": {"type": "number", "x-mhs-unit": "A", "readOnly": True}}}]},
            "ch2": {"anyOf": [{"type": "object", "properties": {"voltage": {"type": "number", "x-mhs-unit": "V"}}},
                              {"type": "object", "properties": {"current": {"type": "number", "x-mhs-unit": "A"}}}]},
            "mode": {"oneOf": [{"type": "string", "readOnly": True}]},
            "meter": {"$ref": "#/$defs/meter"},
            "remote": {"$ref": "https://example.invalid/state.schema.json"},
            "fan": {"type": "object", "properties": {"rpm": {"type": "number"}},
                    "patternProperties": {"^speed_": {"type": "number", "readOnly": True}}}}}

    def _composed_psu(self) -> tuple[Device, Rpc, str]:
        dev = make_device("mhs://localhost/bindings/psu-composed",
                          [Resource("psu", "power.supply", state_schema=copy.deepcopy(self.COMPOSED_SCHEMA))],
                          [Capability(CONFIGURE, "psu", verb="write")], states={"psu": {}})
        server, rpc, session = serve(dev)
        return dev, rpc, session

    def test_read_only_under_composition_and_refs_is_not_writable(self) -> None:
        """4d r2 ``q_probes.py`` q5: readOnly under allOf / anyOf / oneOf / $ref was written."""
        dev, rpc, session = self._composed_psu()
        for patch, field in (({"ch1": {"measured": 3.0}}, "ch1.measured"),
                             ({"mode": "remote"}, "mode"),
                             ({"meter": {"reading": 1.0}}, "meter.reading"),
                             ({"remote": {"anything": 1}}, "remote"),
                             ({"fan": {"speed_1": 3}}, "fan.speed_1")):
            with self.subTest(patch=patch):
                receipt = self._write(rpc, session, patch)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.RESOURCE.NOT_WRITABLE", receipt)
                self.assertEqual(details(receipt)["fields"], [field])
        unknown = self._write(rpc, session, {"ch1": {"voltage": 1.0, "bogus": 1}})
        self.assertEqual(error_code(unknown), "MHS.RESOURCE.FIELD_UNKNOWN", unknown)
        self.assertEqual(details(unknown)["fields"], ["ch1.bogus"])
        self.assertEqual(dev.bridge.native(), [])

    def test_writable_parameters_under_composition_are_written(self) -> None:
        dev, rpc, session = self._composed_psu()
        for patch in ({"ch1": {"voltage": 2.0}}, {"ch2": {"current": 0.5}}, {"fan": {"rpm": 1200}}):
            with self.subTest(patch=patch):
                receipt = self._write(rpc, session, patch)
                self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual([args for _, _, args in dev.bridge.native()],
                         [{"ch1": {"voltage": 2.0}}, {"ch2": {"current": 0.5}}, {"fan": {"rpm": 1200}}])


class PostLockRevisionTests(unittest.TestCase):
    def test_a_stale_expected_revision_is_refused_before_the_permit_is_consumed(self) -> None:
        """Plan 3.6 step 12: the check right after the device lock, on its own (not the registration re-check)."""
        dev = probe_device()
        dev.bridge.interlock_states["lid"] = "closed"
        dev.safety.requires_permit = [GATED]
        server, rpc, session = serve(dev)
        r0 = server._current_revision(dev)
        moved = command(rpc, session, TOUCH, {})
        self.assertEqual(moved["state_revision_after"], r0 + 1, moved)
        digest = canonical.digest({"capability_id": GATED, "resource": "probe", "input": {}})
        permit = rpc("mhs.safety.permit", session_id=session, capability_id=GATED, input_digest=digest,
                     input={})["permit_id"]
        consumed: list[Any] = []
        original = server._consume_permit

        def spy(*args: Any, **kwargs: Any) -> None:
            consumed.append(args)
            original(*args, **kwargs)

        server._consume_permit = spy
        receipt = command(rpc, session, GATED, {}, expected_revision=r0, permit_id=permit)
        self.assertEqual(error_code(receipt), "MHS.CONFLICT.REVISION", receipt)
        self.assertEqual(receipt["error"]["current_revision"], r0 + 1)
        self.assertEqual(consumed, [], "refused before the permit was consumed")
        self.assertEqual(dev.bridge.native(GATED), [])
        retried = command(rpc, session, GATED, {}, expected_revision=r0 + 1, permit_id=permit)
        self.assertEqual(retried["status"], "completed", retried)
        self.assertEqual(len(consumed), 1)



class DispatchRevisionTests(unittest.TestCase):
    """RESIDUAL-B (4d r3 major, ``probes3.py`` / ``test_r3_findings.py``): the revision is re-checked at dispatch.

    ``expected_revision`` was checked after the device lock and when the
    operation was registered, but the worker then read the state before the
    call (up to half the budget; without a bound for an exclusive command).
    A command that completed meanwhile moved the revision, and the stale
    command still ran (SDK-07 / e7 a: ``expected_revision=0 -> completed,
    state_revision_before=1``).
    """

    def _race(self, *, exclusive: bool, permit: bool = False) -> tuple[Any, ...]:
        did = f"mhs://localhost/bindings/window-{int(exclusive)}-{int(permit)}"
        bridge = OverlapBridge(did, {"psu": {}})
        dev = make_device(did, [Resource("psu", "power.supply")],
                          [Capability(TOUCH, "psu", input_schema=OBJECT, exclusive=exclusive),
                           Capability(MOVE, "psu", input_schema=OBJECT)], bridge=bridge)
        if permit:
            dev.safety.requires_permit = [TOUCH]
        server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "psu")
        params: dict[str, Any] = {"deadline_ms": 5000, "expected_revision": r0}
        if permit:
            digest = canonical.digest({"capability_id": TOUCH, "resource": "psu", "input": {}})
            params["permit_id"] = rpc("mhs.safety.permit", session_id=session, capability_id=TOUCH,
                                      input_digest=digest, input={})["permit_id"]
        bridge.delays = [0.8]  # the stale command's state read before its call
        out: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: out.setdefault("a", command(rpc, session, TOUCH, {}, **params)))
        thread.start()
        time.sleep(0.2)
        moved = command(rpc, session, MOVE, {}, deadline_ms=3000)  # r0 -> r0 + 1 meanwhile
        thread.join(10)
        return server, rpc, session, bridge, r0, out["a"], moved, params.get("permit_id")

    def _assert_refused(self, r0: int, stale: Mapping[str, Any], moved: Mapping[str, Any],
                        bridge: OverlapBridge) -> None:
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["state_revision_after"], r0 + 1, moved)
        self.assertEqual(stale["status"], "rejected", stale)
        self.assertEqual(error_code(stale), "MHS.CONFLICT.REVISION", stale)
        self.assertEqual(stale["error"]["current_revision"], r0 + 1, stale)
        self.assertEqual(stale["state_revision_before"], stale["state_revision_after"], "a refusal never bumps")
        self.assertEqual(bridge.native(TOUCH), [], "the stale command reached the bridge")

    def test_a_stale_non_exclusive_command_is_refused_after_its_pre_call_read(self) -> None:
        _server, _rpc, _session, bridge, r0, stale, moved, _permit = self._race(exclusive=False)
        self._assert_refused(r0, stale, moved, bridge)

    def test_a_stale_exclusive_command_is_refused_after_its_pre_call_read(self) -> None:
        _server, _rpc, _session, bridge, r0, stale, moved, _permit = self._race(exclusive=True)
        self._assert_refused(r0, stale, moved, bridge)

    def test_the_permit_of_a_command_refused_at_dispatch_is_given_back(self) -> None:
        server, rpc, session, bridge, r0, stale, moved, permit = self._race(exclusive=False, permit=True)
        self._assert_refused(r0, stale, moved, bridge)
        self.assertFalse(server._permits[permit].used, "nothing ran: the permit is not spent")
        retried = command(rpc, session, TOUCH, {}, expected_revision=r0 + 1, permit_id=permit)
        self.assertEqual(retried["status"], "completed", retried)
        self.assertEqual(len(bridge.native(TOUCH)), 1)

    def test_a_command_refused_at_dispatch_gives_back_its_cumulative_budget(self) -> None:
        """RESIDUAL-B verifier minor (``v_dispatch_budget.py``): ``rejected`` means nothing ran, so nothing is drawn.

        The registration-path refusal released the command's cumulative
        draws, the dispatch-time one kept them: after a ``dose=6`` refused
        stale, a fresh ``dose=6`` was ``MHS.SAFETY.CUMULATIVE_LIMIT`` (10 per
        rolling hour) although nothing had run.
        """
        did = "mhs://localhost/bindings/window-budget"
        bridge = OverlapBridge(did, {"psu": {}})
        dose = {"type": "object", "properties": {"dose": {"type": "number", "x-mhs-unit": "mL"}}}
        dev = make_device(did, [Resource("psu", "power.supply")],
                          [Capability(TOUCH, "psu", input_schema=dose), Capability(MOVE, "psu", input_schema=OBJECT)],
                          bridge=bridge, envelope={TOUCH: {"dose": {"max": 10, "per": "rolling_1h", "unit": "mL"}}})
        _server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "psu")
        bridge.delays = [0.8]
        out: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: out.setdefault("a", command(
            rpc, session, TOUCH, {"dose": 6}, deadline_ms=5000, expected_revision=r0)))
        thread.start()
        time.sleep(0.2)
        moved = command(rpc, session, MOVE, {}, deadline_ms=3000)
        thread.join(10)
        self._assert_refused(r0, out["a"], moved, bridge)
        retried = command(rpc, session, TOUCH, {"dose": 6})
        self.assertEqual(retried["status"], "completed", retried)
        # The retry drew only its own amount: 6 + 4 fits the budget, 6 + 4 + 1 does not.
        self.assertEqual(command(rpc, session, TOUCH, {"dose": 4})["status"], "completed")
        over = command(rpc, session, TOUCH, {"dose": 1})
        self.assertEqual((over["status"], error_code(over)), ("rejected", "MHS.SAFETY.CUMULATIVE_LIMIT"), over)
        self.assertEqual([args for _cap, _res, args in bridge.native(TOUCH)], [{"dose": 6}, {"dose": 4}])

    def test_a_current_expected_revision_still_runs_after_a_slow_pre_call_read(self) -> None:
        """Control: the dispatch re-check refuses only a revision that moved."""
        did = "mhs://localhost/bindings/window-control"
        bridge = OverlapBridge(did, {"psu": {}})
        dev = make_device(did, [Resource("psu", "power.supply")],
                          [Capability(TOUCH, "psu", input_schema=OBJECT)], bridge=bridge)
        _server, rpc, session = serve(dev)
        r0 = revision(rpc, session, "psu")
        bridge.delays = [0.3]
        receipt = command(rpc, session, TOUCH, {}, deadline_ms=5000, expected_revision=r0)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((receipt["state_revision_before"], receipt["state_revision_after"]), (r0, r0 + 1))


class ConfigureReadOnlyGapsTests(unittest.TestCase):
    """RESIDUAL-B (4d r3 minor, ``test_r3_findings.ConfigureReadOnlyGapsTests``): a readOnly state root and the
    draft-07 tuple ``items: [...]`` / ``additionalItems`` (both supported by :mod:`mhs.schema`) were written."""

    def _write(self, schema: Mapping[str, Any], patch: Any) -> tuple[dict[str, Any], list[Any]]:
        dev = make_device("mhs://localhost/bindings/psu-gaps",
                          [Resource("psu", "power.supply", state_schema=copy.deepcopy(dict(schema)))],
                          [Capability(CONFIGURE, "psu", verb="write")], states={"psu": {}})
        _server, rpc, session = serve(dev)
        receipt = rpc("mhs.resource.write", session_id=session, resource_id="psu", patch=patch, deadline_ms=3000,
                      command_id=canonical.ulid())
        return receipt, dev.bridge.native()

    def test_a_read_only_state_root_makes_every_key_not_writable(self) -> None:
        for schema in ({"type": "object", "readOnly": True, "properties": {"x": {"type": "number"}}},
                       {"allOf": [{"readOnly": True}], "type": "object", "properties": {"x": {"type": "number"}}}):
            with self.subTest(schema=schema):
                receipt, native = self._write(schema, {"x": 1})
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.RESOURCE.NOT_WRITABLE", receipt)
                self.assertEqual(details(receipt)["fields"], ["x"])
                self.assertEqual(native, [])

    def test_draft07_tuple_items_follow_their_position(self) -> None:
        schema = {"type": "object", "properties": {"arr": {"type": "array", "items": [
            {"type": "number", "readOnly": True}, {"type": "number"}],
            "additionalItems": {"type": "number", "readOnly": True}}}}
        for patch, fields in (({"arr": [1]}, ["arr[0]"]), ({"arr": [1, 2, 3]}, ["arr[0]", "arr[2]"])):
            with self.subTest(patch=patch):
                receipt, native = self._write(schema, patch)
                self.assertEqual(error_code(receipt), "MHS.RESOURCE.NOT_WRITABLE", receipt)
                self.assertEqual(details(receipt)["fields"], fields)
                self.assertEqual(native, [])

    def test_an_element_or_property_the_schema_forbids_is_refused(self) -> None:
        """Guard: ``additionalItems: false`` / a ``false`` property (the served input refuses it first)."""
        schema = {"type": "object", "properties": {
            "arr": {"type": "array", "items": [{"type": "number"}], "additionalItems": False},
            "gone": False}}
        for patch in ({"arr": [1, 2]}, {"gone": 1}):
            with self.subTest(patch=patch):
                receipt, native = self._write(schema, patch)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertIn(error_code(receipt), ("MHS.CAPABILITY.INPUT_INVALID", "MHS.RESOURCE.FIELD_UNKNOWN"))
                self.assertEqual(native, [])

    def test_writable_tuple_items_are_written(self) -> None:
        """Control: the writable positions of a tuple array are written."""
        receipt, native = self._write({"type": "object", "properties": {"arr": {"type": "array", "items": [
            {"type": "number"}, {"type": "number"}], "additionalItems": {"type": "number"}}}}, {"arr": [1, 2, 3]})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual([args for _, _, args in native], [{"arr": [1, 2, 3]}])



class GateBridge(MultiBridge):
    """``MOVE`` blocks until ``gate`` is set (a command still running on the device)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gate = threading.Event()
        self.entered = threading.Event()

    def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
        if capability_id == MOVE:
            self.entered.set()
            self.gate.wait(5)
        return super().call(capability_id, args, ctx)


class HardwareDeviceLockTests(unittest.TestCase):
    """RESIDUAL-B (4d r3 minor): plan 3.6 step 12, non-read operations on hardware take the device lock by default.

    ``Capability.exclusive`` defaults to False and only an explicit
    ``exclusive=True`` took the lock, so by default concurrent commands ran
    side by side on hardware.  Now a non-read binding of a hardware or hybrid
    device is exclusive unless its concurrency is ``shared``: declared by the
    binding (``constraints.concurrency``) or by its catalogued class, never
    weaker than the class (ADPT-025); ``serialized`` holds the lock too.
    Catalogued reads, stop classes and ``safe_state.achieved_by`` actions
    never wait for the lock (SAFE-029).  Simulated devices keep the declared
    flag.  Full manifests and summaries publish what the runtime applies
    (RESIDUAL-B verifier minor).
    """

    def _device(self, mode: str, *, second: Capability | None = None) -> tuple[Device, GateBridge, Rpc, str]:
        did = f"mhs://localhost/bindings/lock-{mode}"
        bridge = GateBridge(did, {"axis": {}})
        caps = [Capability(MOVE, "axis", input_schema=OBJECT),
                second or Capability(TOUCH, "axis", input_schema=OBJECT),
                Capability(TEMPERATURE, "axis", verb="read", input_schema=OBJECT),
                Capability(STOP, "axis", input_schema=OBJECT)]
        fidelity = dict(FIDELITY, authority={"axis": "model"}) if mode == "hybrid" else None
        dev = make_device(did, [Resource("axis", "motion.axis")], caps, mode=mode, bridge=bridge,
                          achieved_by=(STOP,), fidelity=fidelity)
        _server, rpc, session = serve(dev)
        return dev, bridge, rpc, session

    def _while_running(self, mode: str, capability_id: str, *, second: Capability | None = None
                       ) -> dict[str, Any]:
        dev, bridge, rpc, session = self._device(mode, second=second)
        out: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: out.setdefault("first", command(rpc, session, MOVE, {},
                                                                                 deadline_ms=5000)))
        thread.start()
        try:
            self.assertTrue(bridge.entered.wait(3), "the first command never reached the bridge")
            receipt = command(rpc, session, capability_id, {}, deadline_ms=3000)
        finally:
            bridge.gate.set()
            thread.join(10)
        self.assertEqual(out["first"]["status"], "completed", out["first"])
        return receipt

    def test_a_second_non_read_command_on_hardware_is_busy(self) -> None:
        for mode in ("hardware", "hybrid"):
            with self.subTest(mode=mode):
                receipt = self._while_running(mode, TOUCH)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.DEVICE.BUSY", receipt)

    def test_simulated_devices_keep_the_declared_flag(self) -> None:
        receipt = self._while_running("simulated", TOUCH)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_a_shared_binding_on_hardware_runs_beside_it(self) -> None:
        shared = Capability(TOUCH, "axis", input_schema=OBJECT, constraints={"concurrency": "shared"})
        receipt = self._while_running("hardware", TOUCH, second=shared)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_the_device_summary_publishes_the_lock_the_runtime_applies(self) -> None:
        for mode, expected in (("hardware", {MOVE: True, TOUCH: True, TEMPERATURE: False, STOP: False}),
                               ("hybrid", {MOVE: True, TOUCH: True, TEMPERATURE: False, STOP: False}),
                               ("simulated", {MOVE: False, TOUCH: False, TEMPERATURE: False, STOP: False})):
            with self.subTest(mode=mode):
                dev, _bridge, rpc, _session = self._device(mode)
                for listing in (rpc("mhs.hello", protocol_versions=["1.0"])["devices"],
                                rpc("mhs.devices.list")["devices"]):
                    summary = [item for item in listing if item["device_id"] == dev.device_id][0]
                    self.assertEqual({cap["capability_id"]: cap["exclusive"] for cap in summary["capabilities"]},
                                     expected)

    def test_reads_and_stops_on_hardware_never_wait_for_the_lock(self) -> None:
        for capability_id in (TEMPERATURE, STOP):
            with self.subTest(capability=capability_id):
                receipt = self._while_running("hardware", capability_id)
                self.assertEqual(receipt["status"], "completed", receipt)

    def test_full_manifests_publish_the_concurrency_the_runtime_applies(self) -> None:
        """RESIDUAL-B verifier minor (``v_manifest_concurrency.py``): ``Capability.manifest()`` published
        ``constraints: {"concurrency": "shared"}`` for every binding without constraints, while on hardware the
        summaries said ``exclusive: true`` and the runtime answered ``MHS.DEVICE.BUSY``."""

        lock = {MOVE: "exclusive", TOUCH: "exclusive", TEMPERATURE: "shared", STOP: "shared"}
        for mode, expected in (("hardware", lock), ("hybrid", lock),
                               ("simulated", {MOVE: None, TOUCH: None, TEMPERATURE: None, STOP: None})):
            with self.subTest(mode=mode):
                dev, _bridge, rpc, _session = self._device(mode)
                summary = [item for item in rpc("mhs.devices.list")["devices"] if item["device_id"] == dev.device_id][0]
                exclusive = {cap["capability_id"]: cap["exclusive"] for cap in summary["capabilities"]}
                full = [item for item in rpc("mhs.devices.list", detail="full")["devices"]
                        if item["device_id"] == dev.device_id][0]
                for manifest in (rpc("mhs.devices.get", device_id=dev.device_id), full):
                    published = {cap["capability_id"]: (cap.get("constraints") or {}).get("concurrency")
                                 for cap in manifest["capabilities"]}
                    self.assertEqual(published, expected)  # a simulated manifest invents nothing
                    if mode != "simulated":
                        self.assertEqual({key: value == "exclusive" for key, value in published.items()}, exclusive)

    def test_a_manifest_round_trip_keeps_the_default_lock(self) -> None:
        """The invented ``"shared"`` was the opt-out key: a binding rebuilt from a manifest lost the lock."""

        fields = set(Capability.__dataclass_fields__)
        sim, _bridge, _rpc, _session = self._device("simulated")
        _hw, _bridge, hw_rpc, _session = self._device("hardware")
        for source, entries in (("simulated manifest", sim.manifest()["capabilities"]),
                                ("hardware devices.get", hw_rpc("mhs.devices.get",
                                                                device_id=_hw.device_id)["capabilities"])):
            with self.subTest(source=source):
                entry = [item for item in entries if item["capability_id"] == TOUCH][0]
                rebuilt = Capability(**{key: value for key, value in entry.items() if key in fields})
                receipt = self._while_running("hardware", TOUCH, second=rebuilt)
                self.assertEqual((receipt["status"], error_code(receipt)), ("rejected", "MHS.DEVICE.BUSY"), receipt)

    def test_the_class_concurrency_is_honoured_and_never_weakened(self) -> None:
        """Spec 00 section 6 / ADPT-025: a class declaring ``shared`` runs beside a running command on hardware; a
        binding cannot declare an ``exclusive`` class ``shared``; ``serialized`` holds the device lock."""

        cases = ((Capability("cap.compute.cancel.v1", "axis", input_schema=OBJECT), "completed"),
                 (Capability(GRASP, "axis", input_schema=OBJECT, constraints={"concurrency": "shared"}),
                  "MHS.DEVICE.BUSY"),
                 (Capability("cap.compute.submit.v1", "axis", input_schema=OBJECT), "MHS.DEVICE.BUSY"),
                 (Capability(TOUCH, "axis", input_schema=OBJECT, constraints={"concurrency": "serialized"}),
                  "MHS.DEVICE.BUSY"))
        for capability, expected in cases:
            with self.subTest(capability=capability.capability_id, constraints=capability.constraints):
                receipt = self._while_running("hardware", capability.capability_id, second=capability)
                self.assertEqual(receipt["status"] if expected == "completed" else error_code(receipt), expected,
                                 receipt)


if __name__ == "__main__":
    unittest.main()
