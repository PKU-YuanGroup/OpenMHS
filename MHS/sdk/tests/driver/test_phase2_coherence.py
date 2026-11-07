"""Coherence of the phase-2 SDK changes composed together (integration of 2026-11-05).

Each phase-2 change was tested alone by its author. These cases check the combinations the integration named:

* package composition (``extra_resources``, PACKAGE-COMPOSITION.md) with an explicit re-enable or a terminal e-stop
  (RE-ENABLE-AND-TERMINAL-STOP.md): the re-enable may be bound on an extra resource, and one latch covers every
  resource of the device;
* the once-per-e-stop rule of the ROS bridge (RUNTIME-AND-GATE-FIXES.md: a safe-state command whose request the
  e-stop already sent is answered from that request) with TSAFE-001's re-enable ordering, a re-enable in flight when
  the e-stop lands, and the terminal refusal, on a composed ROS device whose power stage carries both commands;
* gate G6's synthesis of an ``operator_required`` path inside an optional container
  (MUJOCO-UNBOUNDED-ACTUATORS.md) on an action bound to an extra resource;
* Gymnasium's asynchronous environments and physics-integrating resets (GYM-LIVE-ROUTES.md) with the step-limit
  precedence of MUJOCO-UNBOUNDED-ACTUATORS.md (a declared rule replaces a derived one only when it narrows it), and
  the MuJoCo bridge's settle hook beside its unranged-actuator limits.

The drivers are test stand-ins; nothing here runs hardware.
"""

from __future__ import annotations

import copy
import threading
import time
import unittest

from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.conformance.inprocess import run_suite_inprocess
from mhs.driver import Action, Driver, DriverFailed, Field, Limit, RosDriver, action, build_device, build_reference
from mhs.driver import build_server, close_server, estop, read
from mhs.driver.behaviour import BehaviourRun
from mhs.driver.build import hardware_device_id
from mhs.driver.check import _Context
from mhs.schema import default_store

from tests.driver import gate_support as gs
from tests.driver import support

MOVE = "x-cap.test.coherence-move.v1"
ENABLE = "x-cap.test.coherence-enable.v1"
LEVEL = "x-cap.test.coherence-level.v1"
TERMINAL = "close() ends the instrument session; the vendor library requires a new initialisation (vendor.py:233)"
ESTOP_ENGAGED = "MHS.SAFETY.ESTOP_ENGAGED"
RESET_REFUSED = "MHS.SAFETY.RESET_REFUSED"


# ---------------------------------------------------------------------------
# stand-ins
# ---------------------------------------------------------------------------


class FakeAxis:
    """An axis whose stop disables its power stage; only ``enable`` powers it again."""

    def __init__(self, **_options):
        self.enabled = True
        self.position = 0.0
        self.calls: list[object] = []

    def disable(self):
        self.calls.append("disable")
        self.enabled = False

    def enable(self):
        self.calls.append("enable")
        self.enabled = True
        return True

    def move(self, position):
        self.calls.append(("move", position))
        if not self.enabled:
            return False
        self.position = float(position)
        return True


class ComposedDrive(Driver):
    """One device, two typed resources: the axis (main) and its power stage, which carries the re-enable."""

    device_id, device_kind, mode, risk = "test/composed-drive", "motion.axis", "hardware", "R1"
    resource_id = "axis"
    extra_resources = {"power": {"kind": "device", "title": "Power stage"}}
    backends = {"fake": FakeAxis}
    safe_state = "the power stage is disabled"

    @read("position", unit="m", description="axis position")
    def position(self):
        return self.native.position

    @action(name=MOVE, input={"position": Field("number", unit="m", description="target position",
                                                limit=Limit(min=0.0, max=1.0, source="upstream_code",
                                                            ref="drive.py:10"))},
            output={"reached": Field("boolean", description="the target was reached")})
    def move(self, position):
        if not self.native.move(position):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the power stage is disabled")
        return {"reached": True}

    @action(name=ENABLE, resource="power", reenable=True,
            output={"enabled": Field("boolean", description="the power stage is enabled")})
    def enable(self):
        return {"enabled": bool(self.native.enable())}

    @estop
    def stop(self):
        self.native.disable()


class FakeSession:
    """An instrument session that ``close()`` ends for good."""

    def __init__(self, **_options):
        self.closed = False
        self.level = 1.0
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        self.closed = True

    def set_level(self, value):
        if self.closed:
            raise RuntimeError("the session is closed")
        self.level = float(value)


class ComposedSession(Driver):
    """A terminal e-stop on a composed device: the closed session ends every resource of the device."""

    device_id, device_kind, mode, risk = "test/composed-session", "instrument", "hardware", "R1"
    resource_id = "session"
    extra_resources = {"source": {"kind": "light.source", "title": "Lamp"}}
    backends = {"fake": FakeSession}
    safe_state = "the instrument session is closed"
    estop_terminal = TERMINAL

    @read("level", unit="1", description="lamp level")
    def level(self):
        return self.native.level

    @action(name=LEVEL, resource="source",
            input={"value": Field("number", unit="1", description="lamp level",
                                  limit=Limit(min=0.0, max=1.0, source="upstream_code", ref="vendor.py:120"))},
            output={"level": Field("number", unit="1", description="lamp level")})
    def set_level(self, value):
        self.native.set_level(value)
        return {"level": self.native.level}

    @estop
    def stop(self):
        self.native.close()


def served(driver_class):
    driver = driver_class(backend="fake")
    server = build_server(driver)
    return driver, server, support.Client(server)


def command(client, capability_id, payload=None, *, resource=None):
    params = {"session_id": client.session_id, "device_id": client.device_id, "capability_id": capability_id,
              "input": dict(payload or {}), "command_id": support.canonical.ulid(), "deadline_ms": 5000}
    if resource is not None:
        params["resource"] = resource
    return client.rpc("mhs.command", params)


def read_resource(client, resource_id):
    return client.rpc("mhs.resource.read", {"session_id": client.session_id, "device_id": client.device_id,
                                            "resource_id": resource_id, "deadline_ms": 5000})


def details(receipt):
    return ((receipt or {}).get("error") or {}).get("details") or {}


def shared_stops(receipt):
    return ((receipt or {}).get("x-vendor") or {}).get("shared_stop_requests") or []


def entry(report, test_id):
    return next(item for item in report["tests"] if item["id"] == test_id)


def suite(driver_class):
    return run_suite_inprocess(lambda: build_server(driver_class(backend="fake")), profile="MHS-Sim", level="CL3")


# ---------------------------------------------------------------------------
# B3 x B2: package composition with a re-enable or a terminal e-stop
# ---------------------------------------------------------------------------


class ComposedRecoveryTests(unittest.TestCase):
    def test_the_reenable_of_an_extra_resource_is_published_and_validates(self):
        store = default_store()
        for cls in (ComposedDrive,):
            with self.subTest(driver=cls.__name__):
                manifest = build_device(cls(backend="fake")).manifest()
                self.assertEqual(manifest["safety"]["estop"]["reenable"], ENABLE)
                self.assertEqual([(r["resource_id"], r["kind"]) for r in manifest["resources"]],
                                 [("axis", "motion.axis"), ("power", "device")])
                self.assertEqual({c["capability_id"]: c["resource"] for c in manifest["capabilities"]}[ENABLE],
                                 "power")
                self.assertEqual(store.validate(manifest, "device.schema.json"), [])
                reference = build_reference(cls(backend="fake"))
                self.assertEqual(reference["safety"]["estop"]["reenable"], ENABLE)
                self.assertEqual(reference["device"]["resources"],
                                 [{"id": "axis", "kind": "motion.axis"},
                                  {"id": "power", "kind": "device", "title": "Power stage"}])
                self.assertEqual(store.validate(reference, "reference.schema.json"), [])

    def test_the_reenable_is_refused_while_latched_and_served_on_its_own_resource_after_the_reset(self):
        driver, server, client = served(ComposedDrive)
        self.addCleanup(close_server, server)
        self.assertEqual(command(client, MOVE, {"position": 0.4})["status"], "completed")
        self.assertEqual(client.estop()["status"], "completed")
        self.assertFalse(driver.native.enabled)
        refused = command(client, ENABLE, resource="power")
        self.assertEqual((refused["status"], support.code(refused)), ("rejected", ESTOP_ENGAGED), refused)
        receipt = client.reset()["result"]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["reenable"], ENABLE)
        self.assertFalse(driver.native.enabled)  # the reset re-armed nothing
        self.assertNotIn("enable", driver.native.calls)
        misrouted = command(client, ENABLE, resource="axis")
        self.assertNotEqual(misrouted["status"], "completed", misrouted)
        self.assertFalse(driver.native.enabled)
        enabled = command(client, ENABLE, resource="power")
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertTrue(driver.native.enabled)
        self.assertEqual(command(client, MOVE, {"position": 0.6})["status"], "completed")
        self.assertEqual(read_resource(client, "power")["state"], {})

    def test_tsafe001_sends_the_reenable_to_the_extra_resource(self):
        report = suite(ComposedDrive)
        case = entry(report, "TSAFE-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn(f"the declared re-enable {ENABLE} was refused while latched and accepted after the reset",
                      case["detail"])

    def test_a_terminal_estop_latches_every_resource_and_refuses_the_reset(self):
        driver, server, client = served(ComposedSession)
        self.addCleanup(close_server, server)
        self.assertEqual(command(client, LEVEL, {"value": 0.5}, resource="source")["status"], "completed")
        self.assertEqual(client.estop()["status"], "completed")
        self.assertTrue(driver.native.closed)
        refused = command(client, LEVEL, {"value": 0.2}, resource="source")
        self.assertEqual((refused["status"], support.code(refused)), ("rejected", ESTOP_ENGAGED), refused)
        receipt = client.reset()["result"]
        self.assertEqual((receipt["status"], support.code(receipt)), ("rejected", RESET_REFUSED), receipt)
        self.assertEqual(details(receipt)["reason"], "terminal_estop")
        self.assertEqual(details(receipt)["terminal"], TERMINAL)
        self.assertEqual(read_resource(client, "source")["state"], {})
        status = client.rpc("mhs.safety.status", {"session_id": client.session_id, "device_id": client.device_id,
                                                  "deadline_ms": 1000})
        self.assertIs(status["estop"]["terminated"], True)

    def test_tsafe001_checks_the_terminal_refusal_of_a_composed_device(self):
        case = entry(suite(ComposedSession), "TSAFE-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn("terminal e-stop declared", case["detail"])


# ---------------------------------------------------------------------------
# S2 x B2 x B3: the ROS once-per-e-stop rule with a re-enable and a terminal e-stop on a composed device
# ---------------------------------------------------------------------------


SWITCH_ON = "x-cap.test.coherence-switch-on.v1"
SWITCH_OFF = "x-cap.test.coherence-switch-off.v1"
SWITCH_ON_SPEC = {"service": "/spine/switch_on", "type": "spine_msgs/srv/SwitchOn",
                  "success": {"path": "success", "equals": True}, "result": {"map": {"switched_on": "success"}}}
SWITCH_OFF_SPEC = {"service": "/spine/switch_off", "type": "spine_msgs/srv/SwitchOff",
                   "success": {"path": "success", "equals": True}, "result": {"map": {"switched_off": "success"}}}


class SpinePeer:
    """A ROS graph stand-in: counts the service calls; a held switch-on is answered only when released."""

    def __init__(self):
        self.state = "SwitchedOn"
        self.counts: dict[str, int] = {}
        self.hold_switch_on = False
        self.held: list[dict] = []
        self.transport = RecordingRosTransport(self.handle)

    def handle(self, message):
        if message.get("op") != "call_service":
            return None
        service = message["service"]
        self.counts[service] = self.counts.get(service, 0) + 1
        if service == "/spine/switch_on" and self.hold_switch_on:
            self.held.append(message)
            return None
        self.state = "SwitchedOn" if service == "/spine/switch_on" else "SwitchedOff"
        return {"op": "service_response", "id": message["id"], "service": service, "result": True,
                "values": {"success": True}}

    def release(self):
        for message in self.held:
            self.state = "SwitchedOn"
            self.transport.feed({"op": "service_response", "id": message["id"], "service": message["service"],
                                 "result": True, "values": {"success": True}})
        self.held = []


def composed_spine(*, terminal=None):
    peer = SpinePeer()
    commands = {SWITCH_OFF: copy.deepcopy(SWITCH_OFF_SPEC)}
    actions = {SWITCH_OFF: Action(name="switch_off", resource="power", safe_state=True,
                                  output={"switched_off": Field("boolean", description="acknowledged")})}
    attributes = {
        "device_id": "ros/composed-spine", "device_kind": "motion.axis", "mode": "hardware", "risk": "R1",
        "resource_id": "axis", "extra_resources": {"power": {"kind": "device", "title": "Power stage"}},
        "safe_state": "the spine is switched off", "safety_bindings": {"estop": copy.deepcopy(SWITCH_OFF_SPEC)},
        "commands": commands, "actions": actions, "backends": {"fake": lambda: peer.transport},
    }
    if terminal is None:
        commands[SWITCH_ON] = copy.deepcopy(SWITCH_ON_SPEC)
        actions[SWITCH_ON] = Action(name="switch_on", resource="power", reenable=True,
                                    output={"switched_on": Field("boolean", description="acknowledged")})
    else:
        attributes["estop_terminal"] = terminal
    return type("ComposedSpine", (RosDriver,), attributes), peer


def wait_for(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        time.sleep(0.01)
    return predicate()


def confirmations(server, stop):
    return [item for item in server.export_evidence()["receipts"]
            if (item.get("output") or {}).get("confirms") == stop["command_id"]]


class RosStopOnceWithRecoveryTests(unittest.TestCase):
    def serve(self, cls):
        driver = cls(backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        return driver, server, support.Client(server)

    def test_the_stop_is_sent_once_and_the_reenable_on_the_power_stage_follows_the_reset(self):
        cls, peer = composed_spine()
        self.assertEqual(cls.driver_model().safety_manifest()["estop"]["reenable"], SWITCH_ON)
        _driver, _server, client = self.serve(cls)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(peer.counts.get("/spine/switch_off"), 1)
        self.assertEqual(stop["x-vendor"]["shared_stop_requests"],
                         [{"capability_id": SWITCH_OFF, "same_request_as": "native"}])
        refused = command(client, SWITCH_ON, resource="power")
        self.assertEqual((refused["status"], support.code(refused)), ("rejected", ESTOP_ENGAGED), refused)
        reset = client.reset()["result"]
        self.assertEqual(reset["output"]["reenable"], SWITCH_ON, reset)
        self.assertEqual((peer.state, peer.counts.get("/spine/switch_on", 0)), ("SwitchedOff", 0))
        self.assertNotEqual(command(client, SWITCH_ON, resource="axis")["status"], "completed")
        self.assertEqual(command(client, SWITCH_ON, resource="power")["status"], "completed")
        self.assertEqual(peer.state, "SwitchedOn")

    def test_tsafe001_passes_for_the_composed_ros_device(self):
        cls, _peer = composed_spine()
        case = entry(suite(cls), "TSAFE-001")
        self.assertEqual(case["status"], "pass", case)
        self.assertIn(f"the declared re-enable {SWITCH_ON}", case["detail"])

    def test_a_terminal_ros_estop_sends_the_stop_once_and_refuses_the_reset(self):
        cls, peer = composed_spine(terminal=TERMINAL)
        _driver, _server, client = self.serve(cls)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(peer.counts.get("/spine/switch_off"), 1)
        reset = client.reset()["result"]
        self.assertEqual((reset["status"], details(reset)["reason"]), ("rejected", "terminal_estop"), reset)
        self.assertEqual(peer.counts.get("/spine/switch_off"), 1)

    def test_an_in_flight_reenable_reruns_the_stop_and_the_confirmation_lists_one_shared_request(self):
        cls, peer = composed_spine()
        _driver, server, client = self.serve(cls)
        peer.hold_switch_on = True
        sender = support.Client(server)
        thread = threading.Thread(target=lambda: command(sender, SWITCH_ON, resource="power"), daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(peer.release)
        self.assertTrue(wait_for(lambda: peer.held))
        stop = client.estop()
        # The re-enable was in flight: the attempt ran the stop path again after it settled (CORE-086). The
        # receipt describes that second run; each safe-state command shared the native request once in it.
        self.assertGreaterEqual(peer.counts.get("/spine/switch_off"), 2)
        self.assertEqual((stop.get("x-vendor") or {}).get("shared_stop_requests"),
                         [{"capability_id": SWITCH_OFF, "same_request_as": "native"}], stop)
        peer.release()
        self.assertTrue(wait_for(lambda: confirmations(server, stop)), stop)
        self.assertEqual(peer.state, "SwitchedOff")  # the stop that confirms came after the late switch-on
        confirmation = confirmations(server, stop)[0]
        self.assertEqual(confirmation["x-vendor"]["shared_stop_requests"],
                         [{"capability_id": SWITCH_OFF, "same_request_as": "native"}], confirmation)


# ---------------------------------------------------------------------------
# S1 x B3: G6 builds an operator_required path inside an optional container on an extra resource
# ---------------------------------------------------------------------------


EXTRA = '''    estop_physical_ref = "MANUAL.md:15"
    extra_resources = {"aux": {"kind": "device", "title": "Auxiliary loop"}}
'''
AUX_ACTION = '''    @action(name="x-cap.openmhs-tutorial.aux_trim.v1", resource="aux", description="Trim the auxiliary loop",
            input={"command": Field("object", description="Auxiliary loop command", properties={
                "trim": Field("number", unit="/min", description="Fan trim", required=False,
                              limit=Limit.operator_required("the manual gives no trim range; the site sets it"))})},
            output={"applied": Field("boolean", description="True once applied")})
    def aux_trim(self, command):
        self.native.set_fan_speed(command.get("trim", 0))
        return {"applied": True}

    @estop'''


class OperatorRequiredOnExtraResourceTests(unittest.TestCase):
    def g6(self, edits):
        directory = gs.broken_copy(self, edits)
        ctx = _Context(directory, "fake", None, None, False)
        self.addCleanup(ctx.close)
        self.assertIsNotNone(ctx.model, ctx.model_error)
        run = BehaviourRun(endpoint=ctx.endpoint, model=ctx.model, hardware_view=ctx.hardware_endpoint,
                           fixtures=None, example_overlay=None, hardware_id=hardware_device_id(ctx.model),
                           recorded=ctx.records_native)
        return [(code, message, severity, path) for code, message, severity, path in run.run()], ctx

    def test_g6_refuses_the_built_path_on_the_extra_resource(self):
        findings, ctx = self.g6([("driver.py", '    estop_physical_ref = "MANUAL.md:15"\n', EXTRA),
                                 ("driver.py", "    @estop", AUX_ACTION)])
        binding = next(b for b in ctx.model.bindings if b.capability_id == "x-cap.openmhs-tutorial.aux_trim.v1")
        self.assertEqual(binding.resource, "aux")
        codes = [code for code, _message, _severity, path in findings if "command.trim" in str(path)]
        self.assertNotIn("G6.NO_INPUT", codes, findings)
        self.assertNotIn("G6.OPERATOR_REQUIRED_NOT_ENFORCED", codes, findings)
        errors = [item for item in findings if item[2] == "error"]
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# B1 x S1: asynchronous and settling Gymnasium environments with the step-limit precedence
# ---------------------------------------------------------------------------


def _gym_step_limits(cls, backend="fake"):
    """The published step limits of a simulator driver (built from an instance, as the family requires)."""
    from mhs.driver import build_manifest

    driver = cls(backend=backend)
    try:
        return next(item for item in build_manifest(driver)["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")["limits"]
    finally:
        driver.close()


def _declared(min_, max_):
    return {"cap.world.step.v1": Action(name="step", limits={"action.values": Limit(
        min=min_, max=max_, source="upstream_code", ref="synthetic-peer.py:1")})}


class GymLiveRoutesWithStepLimitsTests(unittest.TestCase):
    def async_class(self, actions=None):
        from tests.bridges.test_gym_async import STOPPING, AsyncPeer
        from mhs.driver import GymnasiumDriver

        native = AsyncPeer()
        attributes = {"device_id": "coherence/async", "backends": {"fake": lambda: native},
                      "async_by_backend": {"fake": copy.deepcopy(STOPPING)},
                      "safe_state": "the steppable synthetic world is paused and no native work is owned"}
        if actions is not None:
            attributes["actions"] = actions
        return type("AsyncSim", (GymnasiumDriver,), attributes), native

    def test_an_async_environment_keeps_a_narrowing_declared_step_rule_and_refuses_before_the_remote_step(self):
        cls, native = self.async_class(_declared([-0.5, -1.0, -1.0], [0.5, 1.0, 1.0]))
        limits = _gym_step_limits(cls)
        self.assertEqual((limits["action.values"]["max"], limits["action.values"]["source"]),
                         ([0.5, 1.0, 1.0], "upstream_code"), limits)
        driver = cls(backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = support.Client(server)
        refused = client.command("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.8, 0.0, 0.0]}})
        self.assertEqual((refused["status"], support.code(refused)), ("rejected", "MHS.SAFETY.ENVELOPE_VIOLATION"))
        self.assertEqual(native.steps_started, 0)  # refused before the coroutine step ran on the owned loop
        done = client.command("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.4, 0.0, 0.0]}})
        self.assertEqual(done["status"], "completed", done)
        self.assertEqual(native.steps_finished, 1)

    def test_an_async_environment_refuses_a_widening_declared_step_rule(self):
        from mhs.driver import DriverDefinitionError

        cls, _native = self.async_class(_declared([-5.0, -5.0, -5.0], [5.0, 5.0, 5.0]))
        with self.assertRaises(DriverDefinitionError) as caught:
            _gym_step_limits(cls)
        self.assertIn("does not narrow the bound the gymnasium bridge derives", str(caught.exception))

    def test_a_settling_reset_and_a_narrowing_step_rule_compose(self):
        from tests.bridges.test_gymnasium_timing_reset import SETTLING, SettlingEnv
        from mhs.driver import GymnasiumDriver

        native = SettlingEnv(settle=25)
        cls = type("Settling", (GymnasiumDriver,), {
            "device_id": "coherence/settling", "backends": {"sim": lambda: native, "fake": SettlingEnv},
            "timing_by_backend": {"sim": copy.deepcopy(SETTLING)},
            "checkpoint_by_backend": {"sim": {"profile": "none", "reason": "synthetic native state omits its RNG"}},
            "safe_state": "software latch; the synthetic world advances only inside a step or reset"})
        derived = _gym_step_limits(cls, "sim")["action.index"]  # a Discrete(2) space: index 0..1
        self.assertEqual((derived["min"], derived["max"]), (0, 1))
        narrowed = type("SettlingNarrowed", (cls,), {"actions": {"cap.world.step.v1": Action(name="step", limits={
            "action.index": Limit(min=0, max=0, source="upstream_code", ref="synthetic-peer.py:1")})}})
        self.assertEqual(_gym_step_limits(narrowed, "sim")["action.index"]["max"], 0)
        driver = narrowed(backend="sim")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = support.Client(server)
        reset = client.command("cap.world.reset.v1", {})
        self.assertEqual(reset["status"], "completed", reset)
        self.assertIn("openmhs_simulation_timing", reset.get("x-vendor") or {}, reset)  # ticks the reset integrated
        outside = client.command("cap.world.step.v1", {"ticks": 5, "action": {"index": 1}})
        self.assertEqual((outside["status"], support.code(outside)), ("rejected", "MHS.SAFETY.ENVELOPE_VIOLATION"))
        inside = client.command("cap.world.step.v1", {"ticks": 5, "action": {"index": 0}})
        self.assertEqual(inside["status"], "completed", inside)

    def test_the_mujoco_settle_hook_beside_unranged_actuators(self):
        from tests.bridges.test_mujoco_unranged import MixedArm

        limits = _gym_step_limits(MixedArm)
        self.assertIn("operator_required", [rule for rule in limits.values() if not isinstance(rule, dict)])
        server = build_server(MixedArm(backend="fake"))
        self.addCleanup(close_server, server)
        client = support.Client(server)
        bridge = server.devices[client.device_id].bridge
        settle = getattr(getattr(bridge, "inner", bridge), "settle_native_work", None)
        self.assertTrue(callable(settle))
        self.assertTrue(settle(0.1))  # nothing native in flight: settled at once
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)  # the e-stop's settle step passes on an idle model



# ---------------------------------------------------------------------------
# Review S9-11 of RUNTIME-AND-GATE-FIXES: the shared-stop report needs the SDK's own ROS route, per instance too
# ---------------------------------------------------------------------------


class SharedStopRouteTests(unittest.TestCase):
    """A safe-state command answered from the native stop's request is listed only on the SDK's own ROS route."""

    def served_estop(self, driver):
        server = build_server(driver)
        self.addCleanup(close_server, server)
        return support.Client(server).estop()

    def uav_driver(self):
        from tests.safety import test_estop_stop_once as stop_once

        uav = stop_once._Uav()
        driver, _transport = stop_once._ros_driver(uav, estop_spec=stop_once.LAND_SERVICE,
                                                   safe_spec=stop_once.LAND_SERVICE)
        return driver, uav, stop_once

    def test_the_genuine_shared_stop_is_still_listed(self):
        from mhs.server import _sdk_ros_route

        driver, uav, stop_once = self.uav_driver()
        self.assertTrue(_sdk_ros_route(driver))
        stop = self.served_estop(driver)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(uav.count("/uav1/land"), 1)
        self.assertEqual(stop["x-vendor"]["shared_stop_requests"],
                         [{"capability_id": stop_once.LAND, "same_request_as": "native"}])

    def test_an_instance_call_cannot_forge_a_shared_stop_entry(self):
        from mhs.server import _sdk_ros_route

        driver, uav, _stop_once = self.uav_driver()
        original = driver.call

        def forged(capability_id, args=None, ctx=None):
            reports = (getattr(ctx, "extra", None) or {}).get("estop_shared")
            if isinstance(reports, list):  # the probe of the review: claim a shared answer and send nothing
                reports.append({"same_request_as": "native"})
                return {}
            return original(capability_id, args, ctx)

        driver.call = forged
        self.assertFalse(_sdk_ros_route(driver))
        stop = self.served_estop(driver)
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {}, stop)
        self.assertEqual(uav.count("/uav1/land"), 2)  # no report list: the command sent its own request

    def test_instance_attributes_on_the_inner_bridge_or_a_bare_bridge_fail_the_route(self):
        from mhs.bridge.ros import RosBridge
        from mhs.server import _sdk_ros_route

        driver, _uav, _stop_once = self.uav_driver()
        inner = driver.inner
        self.assertTrue(_sdk_ros_route(driver))
        inner.estop = lambda *args, **kwargs: None
        self.assertFalse(_sdk_ros_route(driver))
        bridge = RosBridge({"timeout_s": 1.0, "resources": [{"resource_id": "main", "kind": "instrument"}]},
                           transport=RecordingRosTransport(lambda message: None))
        self.addCleanup(bridge.close)
        self.assertTrue(_sdk_ros_route(bridge))
        bridge.make_bridge = lambda native: None
        self.assertFalse(_sdk_ros_route(bridge))


if __name__ == "__main__":
    unittest.main()
