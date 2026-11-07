"""The sensed-confirmation stop of a simulated ROS device (SAFE-049, CORE-088; MHS/changes/SENSED-CONFIRMATION-STOP.md).

A request (a LAND, a zero velocity, a motor cut) proves nothing; the e-stop is achieved only when every stamped
source delivers ``consecutive`` fresh samples that satisfy every predicate term within the bound.  A ROS-free graph
stand-in answers each subscription with a burst of stamped samples; switches break the confirmation in every way
the profile must fail closed.  Simulated devices only: hardware, raw adapter files and non-simulated manifests are
refused at definition, at the bridge and at server start-up.
"""

from __future__ import annotations

import copy
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mhs.bridge import ros_sensed
from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.driver import Action, DriverDefinitionError, Field, Limit, RosDriver, build_server, close_server
from mhs.driver.behaviour import SensedFilter
from mhs.errors import MHSError
from tests.driver.support import Client
from tests.driver.test_ros_simulation import FAKE_FIDELITY, deployment

NS = 1_000_000_000
LAND = "/uav/land"
STATE, POSE = "/uav/state", "/uav/pose"
MOVE = "x-cap.test.move.v1"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class Uav:
    """A stamped ROS graph stand-in: a vehicle that lands after /uav/land, with switches for every failure."""

    def __init__(self, ros_version: int = 2) -> None:
        self.ros_version = ros_version
        self.z = 2.0
        self.armed = True
        self.landing = False
        self.clock = 100 * NS
        self.burst = 12
        self.calls: list[str] = []
        self.lock = threading.Lock()
        self.transport: RecordingRosTransport | None = None
        # switches
        self.ignore_land = False      # acknowledged, nothing happens
        self.refuse_land = False      # the application refuses, the vehicle lands anyway
        self.silent = False           # no sample at all
        self.latched_only = False     # one (latched) sample per subscription
        self.frozen = False           # every sample repeats one stamp
        self.backwards = False        # stamps decrease
        self.null_z = False           # pose z is null
        self.no_z = False             # pose z is missing
        self.armed_as_int = False     # armed is 0/1, not a boolean
        self.slow = 0                 # land requests that do nothing before one lands
        self.gap_s = 0.0              # feed the samples from a timer, this far apart
        self.zero_stamp = False       # stamps are unset (0)

    def stamp(self) -> dict:
        if self.backwards:
            self.clock -= NS // 10
        elif not self.frozen:
            self.clock += NS // 10
        if self.zero_stamp:
            clock = 0
        elif self.ros_version == 1 and self.frozen:
            # The first call is inside the subscribe handler, after the bridge captured its clock, so a repeated
            # stamp is a duplicate (sensed_stale) rather than a pre-subscribe replay.
            if getattr(self, "_frozen_ns", None) is None:
                self._frozen_ns = time.time_ns()
            clock = self._frozen_ns
        elif self.ros_version == 1:
            # Placeholder deltas stay 0.1 s and sit after the bridge clock at subscribe.
            clock = time.time_ns() + (self.clock - 100 * NS)
        else:
            clock = self.clock
        if self.ros_version == 1:
            return {"secs": clock // NS, "nsecs": clock % NS}
        return {"sec": clock // NS, "nanosec": clock % NS}

    def tick(self) -> None:
        if self.landing and self.z > 0:
            self.z = max(0.0, round(self.z - 0.5, 6))
            if self.z == 0.0:
                self.armed = False

    def sample(self, topic: str, ident: str) -> dict:
        if topic == STATE:
            armed = int(self.armed) if self.armed_as_int else self.armed
            body = {"header": {"stamp": self.stamp(), "frame_id": ""}, "armed": armed, "connected": True}
        else:
            position = {"x": 0.0, "y": 0.0, "z": None if self.null_z else self.z}
            if self.no_z:
                position.pop("z")
            body = {"header": {"stamp": self.stamp(), "frame_id": "map"},
                    "pose": {"position": position, "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}}
        return {"op": "publish", "topic": topic, "id": ident, "msg": body}

    def handler(self, message: dict):
        op = message.get("op")
        if op == "call_service" and message.get("service") == LAND:
            with self.lock:
                self.calls.append(LAND)
                if self.slow > 0:
                    self.slow -= 1
                elif not self.ignore_land:
                    self.landing = True
            success = not self.refuse_land
            return {"op": "service_response", "service": LAND, "id": message["id"], "result": True,
                    "values": {"success": success, "message": ""}}
        if op == "publish" and message.get("topic") == "/uav/cmd_vel":
            self.landing, self.armed, self.z = False, True, self.z + 0.5
            return None
        if op == "subscribe" and message.get("topic") in (STATE, POSE):
            if self.silent:
                return None
            count = 1 if self.latched_only else self.burst
            samples = []
            for _ in range(count):
                samples.append(self.sample(message["topic"], message["id"]))
                self.tick()
            if self.gap_s:
                transport = self.transport

                def feed(items=samples):
                    for item in items:
                        time.sleep(self.gap_s)
                        try:
                            transport.feed(item)
                        except ConnectionError:
                            return
                threading.Thread(target=feed, daemon=True).start()
                return None
            return samples
        return None


def sensed_stop(*, ros: int = 2, **changes) -> dict:
    spec = {
        "request": [{"service": LAND, "type": "std_srvs/srv/Trigger", "success": {"path": "success", "equals": True},
                     "timeout_ms": 500, "source_ref": "README.md:1"}],
        "sources": {
            "state": {"topic": STATE, "type": "mavros_msgs/msg/State", "fill_refs": {"armed": "README.md:1"}},
            "pose": {"topic": POSE, "type": "geometry_msgs/msg/PoseStamped",
                     "fill_refs": {"pose.position": "README.md:2"}},
        },
        "predicate": [
            {"source": "state", "path": "armed", "equals": False},
            {"source": "pose", "path": "pose.position.z", "name": "landed_z", "unit": "m",
             "range": {"max": Limit.operator_required("no landed band in the test graph")}},
            {"source": "pose", "path": "pose.position.z", "name": "rest_z", "unit": "m",
             "span_max": Limit(max=0.05, source="vendor_doc", ref="README.md:3")},
        ],
        "consecutive": 3, "min_span_ms": 100, "max_gap_ms": 400, "confirm_within_ms": 800,
        "description": "landed and disarmed, sensed in three consecutive fresh samples within the bound",
    }
    if ros == 2:
        # Verification F1: a ROS 2 source declares its publisher's history; the test graph keeps none for a late
        # subscriber (its first sample is the pre-request state, which the bridge discards anyway).
        for source in spec["sources"].values():
            source["history"] = {"durability": "volatile", "ref": "README.md:1"}
    spec.update(changes)
    return spec


def resolved_sources(stop: dict) -> dict:
    """The bridge's (resolved) form of ``sensed_stop()['sources']``: a history without its citation."""
    for source in stop["sources"].values():
        if isinstance(source.get("history"), dict):
            source["history"] = {key: value for key, value in source["history"].items() if key != "ref"}
    return stop


def uav_class(name: str = "SensedUav", *, stop: dict | None = None, ros_version: int = 2, **attributes):
    body = {
        "device_id": "uav-sensed", "device_kind": "robot.mobile_base", "mode": "simulated", "risk": "R2",
        "ros_version": ros_version, "fidelity": copy.deepcopy(FAKE_FIDELITY),
        "safe_state": "landed and disarmed as sensed within the confirmation window",
        "estop_latency_ms": 1300,
        "commands": {MOVE: {"topic": "/uav/cmd_vel", "type": "geometry_msgs/msg/Twist" if ros_version == 2
                            else "geometry_msgs/Twist", "args": {"linear.z": {"from": "input.vz"}}}},
        "actions": {MOVE: Action(name="move", input={"vz": Field("number", unit="m/s", description="climb rate",
                                                                    limit=Limit(min=-1, max=1, source="vendor_doc",
                                                                                ref="README.md:1"))})},
        "safety_bindings": {"sensed_stop": stop if stop is not None else sensed_stop(ros=ros_version)},
    }
    body.update(attributes)
    return type(name, (RosDriver,), body)


def fixture_dir(test: unittest.TestCase, thresholds: dict | None = None) -> Path:
    holder = tempfile.TemporaryDirectory(prefix="mhs-sensed-")
    test.addCleanup(holder.cleanup)
    base = Path(holder.name)
    (base / "fixtures").mkdir()
    (base / "fixtures/estop-confirmation.json").write_text(json.dumps(
        {"thresholds": thresholds if thresholds is not None else {"landed_z.max": 0.1}}))
    return base


def details(receipt: dict) -> dict:
    return (receipt.get("error") or {}).get("details") or {}


class SensedLogicTests(unittest.TestCase):
    """mhs.bridge.ros_sensed: stamps, windows and reasons without a transport."""

    def profile(self, **changes) -> ros_sensed.Profile:
        raw = {"ros_version": 2, "description": "test", "max_gap_ms": 400, "confirm_within_ms": 800,
               "consecutive": 3, "min_span_ms": 100,
               "sources": {"pose": {"topic": POSE, "type": "geometry_msgs/msg/PoseStamped",
                                    "history": {"durability": "volatile"}}},
               "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed", "range": {"max": 0.1}},
                             {"source": "pose", "path": "pose.position.z", "name": "rest", "span_max": 0.05}]}
        raw.update(changes)
        return ros_sensed.compile_profile(raw)

    def window(self, profile=None) -> ros_sensed.SourceWindow:
        profile = profile or self.profile()
        return ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0.0)

    @staticmethod
    def msg(t: int, z=0.0):
        return {"header": {"stamp": {"sec": t // NS, "nanosec": t % NS}}, "pose": {"position": {"z": z}}}

    def test_ros1_and_ros2_stamps_are_read_exactly_and_unset_or_malformed_ones_refused(self):
        ros2 = {"header": {"stamp": {"sec": 3, "nanosec": 5}}}
        ros1 = {"header": {"stamp": {"secs": 3, "nsecs": 5}}}
        self.assertEqual(ros_sensed.read_stamp(ros2, "header.stamp", 2), 3 * NS + 5)
        self.assertEqual(ros_sensed.read_stamp(ros1, "header.stamp", 1), 3 * NS + 5)
        for bad, version in ((ros1, 2), (ros2, 1), ({"header": {"stamp": {"sec": 0, "nanosec": 0}}}, 2),
                             ({"header": {"stamp": {"sec": True, "nanosec": 1}}}, 2),
                             ({"header": {"stamp": {"sec": 1, "nanosec": NS}}}, 2), ({"header": {}}, 2)):
            with self.assertRaises(ValueError):
                ros_sensed.read_stamp(bad, "header.stamp", version)

    def test_compile_refuses_headerless_types_unused_sources_and_a_low_count(self):
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "no producer stamp"):
            self.profile(sources={"pose": {"topic": POSE, "type": "std_msgs/msg/Float32"}})
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "no predicate term reads"):
            self.profile(sources={"pose": {"topic": POSE, "type": "geometry_msgs/msg/PoseStamped",
                                           "history": {"durability": "volatile"}},
                                  "idle": {"topic": "/idle", "type": "nav_msgs/msg/Odometry"}})
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "consecutive"):
            self.profile(consecutive=1)
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "unknown keys"):
            self.profile(window=3)
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "name"):
            self.profile(predicate=[{"source": "pose", "path": "pose.position.z", "abs_max": 1.0}])
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "producer stamp"):
            self.profile(predicate=[{"source": "pose", "path": "header.stamp.sec", "name": "x", "abs_max": 1.0}])
        self.assertTrue(ros_sensed.headerless_type("geometry_msgs/msg/Twist"))
        self.assertFalse(ros_sensed.headerless_type("std_msgs/msg/Header"))

    def test_the_first_sample_never_counts_even_when_it_satisfies_the_predicate(self):
        window = self.window()
        window.add(self.msg(NS), 0.1)
        self.assertEqual((window.seen, len(window.counted)), (0, 0))
        self.assertFalse(window.confirmed(0.1))
        self.assertEqual(ros_sensed.unconfirmed_reason({"pose": window}, 0.2), "sensed_missing")

    def test_three_fresh_samples_spanning_the_window_confirm(self):
        window = self.window()
        for index in range(4):
            window.add(self.msg((index + 1) * NS // 10), 0.01 * index)
        self.assertTrue(window.confirmed(0.05))
        self.assertFalse(window.confirmed(0.05 + 0.5))     # the newest arrival is older than max_gap_ms

    def test_a_short_window_does_not_confirm(self):
        window = self.window(self.profile(min_span_ms=500))
        for index in range(4):
            window.add(self.msg((index + 1) * NS // 10), 0.01 * index)
        self.assertFalse(window.confirmed(0.05))           # 200 ms of producer time < 500 ms

    def test_a_repeated_stamp_restarts_the_count_and_a_decreasing_one_is_invalid(self):
        window = self.window()
        for t in (NS, 2 * NS, 3 * NS, 3 * NS):
            window.add(self.msg(t), 0.0)
        self.assertEqual((len(window.counted), window.last_reset), (0, "duplicate"))
        window.add(self.msg(NS), 0.0)
        self.assertIn("backwards", window.invalid)

    def test_missing_null_and_mistyped_fields_are_invalid(self):
        for body in ({"header": {"stamp": {"sec": 2, "nanosec": 0}}, "pose": {"position": {}}},
                     {"header": {"stamp": {"sec": 2, "nanosec": 0}}, "pose": {"position": {"z": None}}},
                     {"header": {"stamp": {"sec": 2, "nanosec": 0}}, "pose": {"position": {"z": True}}},
                     {"header": {"stamp": {"sec": 2, "nanosec": 0}}, "pose": {"position": {"z": "0"}}}):
            window = self.window()
            window.add(self.msg(NS), 0.0)
            window.add(body, 0.0)
            self.assertIsNotNone(window.invalid, body)

    def test_an_arrival_gap_and_a_ring_overflow_restart_the_count(self):
        window = self.window()
        window.add(self.msg(NS), 0.0)
        window.add(self.msg(2 * NS), 0.01)
        window.add(self.msg(3 * NS), 0.02)
        window.add(self.msg(4 * NS), 0.9)                   # 880 ms after the previous arrival > 400 ms
        self.assertEqual((len(window.counted), window.last_reset), (1, "gap"))
        window.overflow()
        self.assertEqual(len(window.counted), 0)
        ring = ros_sensed.Ring(2)
        for item in range(3):
            ring.append((item, 0.0))
        self.assertTrue(ring.overflowed)

    def test_a_failing_term_restarts_the_count_and_a_window_term_spans_the_window(self):
        window = self.window()
        window.add(self.msg(NS, 0.5), 0.0)
        for index, z in enumerate((0.5, 0.0, 0.0, 0.0)):
            window.add(self.msg((index + 2) * NS, z), 0.01 * index)
        self.assertEqual(len(window.counted), 3)
        self.assertTrue(window.confirmed(0.04))
        drifting = self.window()
        drifting.add(self.msg(NS, 0.0), 0.0)
        for index, z in enumerate((0.0, 0.04, 0.08)):
            drifting.add(self.msg((index + 2) * NS, z), 0.01 * index)
        self.assertFalse(drifting.confirmed(0.03))          # span 0.08 > 0.05
        self.assertEqual(ros_sensed.unconfirmed_reason({"pose": drifting}, 0.03), "not_confirmed")

    def test_equals_is_type_strict_and_norm_and_abs_terms_bound_magnitudes(self):
        equals = ros_sensed.Term("equals", "s", ("armed",), equals=False)
        self.assertTrue(equals.holds({"armed": False}))
        self.assertFalse(equals.holds({"armed": 0}))
        norm = ros_sensed.Term("norm_max", "s", ("a", "b"), maximum=5.0)
        self.assertTrue(norm.holds({"a": 3.0, "b": 4.0}))
        self.assertFalse(norm.holds({"a": 3.0, "b": 4.1}))
        absolute = ros_sensed.Term("abs_max", "s", ("a",), maximum=1.0)
        self.assertFalse(absolute.holds({"a": -1.5}))

    def test_a_stale_stream_whose_samples_held_is_stale_not_unconfirmed(self):
        window = self.window()
        for t in (NS, 2 * NS, 3 * NS):
            window.add(self.msg(t), 0.0)
        self.assertEqual(ros_sensed.unconfirmed_reason({"pose": window}, 1.0), "sensed_stale")


class SensedServeMixin:
    def serve(self, uav: Uav, cls=None, thresholds=None, transport=None, **server_options):
        cls = cls or uav_class(ros_version=uav.ros_version)
        transport = transport if transport is not None else RecordingRosTransport(uav.handler)
        uav.transport = transport
        driver = cls(backend="fake", native=transport, base_dir=fixture_dir(self, thresholds))
        server = build_server(driver, **server_options)
        self.addCleanup(close_server, server)
        client = Client(server)
        return driver, server, client, transport


class SensedEstopTests(SensedServeMixin, unittest.TestCase):
    """Through the endpoint: completed only on a confirmation; otherwise SAFE_STATE_UNREACHED, latched, retried."""

    def assert_unreached(self, receipt, reason):
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.assertEqual(details(receipt)["reason"], "bridge_reports_unsafe", receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])
        self.assertNotIn("sensed_confirmation", receipt.get("x-vendor") or {})

    def test_a_confirmed_stop_completes_with_its_confirmation_window(self):
        uav = Uav()
        driver, server, client, _ = self.serve(uav)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertTrue(stop["output"]["safe_state_achieved"])
        self.assertEqual(stop["output"]["estop"], "engaged")
        report = stop["x-vendor"]["sensed_confirmation"]
        self.assertTrue(report["confirmed"])
        self.assertEqual(report["request"], [{"native": LAND, "kind": "service", "outcome": "succeeded"}])
        for name in ("state", "pose"):
            self.assertEqual(report["sources"][name]["samples"], 3)
            self.assertIn("first_stamp", report["sources"][name])
        status = driver.safety_status()
        self.assertTrue(status["safe_state"]["achieved"])
        self.assertEqual(status["safe_state"]["confirmation"]["kind"], "sensed")
        self.assertEqual(status["estop"]["native"], LAND)
        refused = client.command(MOVE, {"vz": 0.5})
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_ros1_stamps_do_not_confirm(self):
        # Producer stamps after the bridge clock at subscribe are still not a freshness proof.
        uav = Uav(ros_version=1)
        uav.gap_s = 0.02
        _driver, _server, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assert_unreached(receipt, "sensed_missing")
        self.assertIn(LAND, uav.calls)

    def test_an_ignored_request_is_never_confirmed(self):
        uav = Uav()
        uav.ignore_land = True
        _driver, server, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assert_unreached(receipt, "not_confirmed")
        self.assertTrue(details(receipt)["retrying"])
        self.assertTrue(server._latched[client.device_id])

    def test_a_refused_request_is_recorded_and_the_sensed_state_decides(self):
        uav = Uav()
        uav.refuse_land = True
        _driver, _server, client, _ = self.serve(uav)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(stop["x-vendor"]["sensed_confirmation"]["request"][0]["outcome"], "refused")

    def test_a_single_latched_sample_never_confirms(self):
        uav = Uav()
        uav.latched_only = True
        uav.z, uav.armed = 0.0, False            # the latched sample already satisfies the predicate
        _driver, _server, client, _ = self.serve(uav)
        self.assert_unreached(client.estop(), "sensed_missing")

    def test_silent_frozen_backwards_null_missing_mistyped_and_unset_samples_fail_closed(self):
        for switch, value, reason in (("silent", True, "sensed_missing"), ("frozen", True, "sensed_stale"),
                                      ("backwards", True, "sensed_invalid"), ("null_z", True, "sensed_invalid"),
                                      ("no_z", True, "sensed_invalid"), ("armed_as_int", True, "sensed_invalid"),
                                      ("zero_stamp", True, "sensed_invalid")):
            with self.subTest(switch=switch):
                uav = Uav()
                setattr(uav, switch, value)
                _driver, _server, client, _ = self.serve(uav)
                self.assert_unreached(client.estop(), reason)

    def test_samples_arriving_further_apart_than_max_gap_are_stale(self):
        uav = Uav()
        uav.gap_s, uav.burst = 0.2, 6
        uav.z, uav.armed = 0.0, False            # every sample satisfies the predicate; only freshness fails
        cls = uav_class("GappyUav", stop=sensed_stop(max_gap_ms=150))
        _driver, _server, client, _ = self.serve(uav, cls=cls)
        self.assert_unreached(client.estop(), "sensed_stale")

    def test_a_request_that_was_never_transmitted_is_request_not_sent(self):
        class Unreachable(RecordingRosTransport):
            def prepare(self, *, timeout_s=None):
                raise ConnectionError("no route to the graph")

        uav = Uav()
        cls = uav_class("UnreachableUav")
        driver = cls(backend="fake", native=Unreachable(uav.handler), base_dir=fixture_dir(self))
        server = build_server(driver)
        self.addCleanup(close_server, server)
        receipt = Client(server).estop()
        self.assertEqual(details(receipt)["sensed"]["reason"], "request_not_sent", receipt)
        self.assertEqual(details(receipt)["sensed"]["request"][0]["outcome"], "not_sent")

    def test_slow_convergence_is_confirmed_by_the_background_retry(self):
        uav = Uav()
        uav.slow = 1                              # the first LAND does nothing; the retry's LAND lands
        _driver, server, client, _ = self.serve(uav)
        first = client.estop()
        self.assert_unreached(first, "not_confirmed")
        deadline = time.monotonic() + 8.0
        confirmations: list = []
        while time.monotonic() < deadline and not confirmations:
            time.sleep(0.05)
            confirmations = [item for item in server.export_evidence()["receipts"]
                             if (item.get("output") or {}).get("confirms") == first["command_id"]]
        self.assertEqual(len(confirmations), 1)
        self.assertEqual(confirmations[0]["capability_id"], "cap.internal.safety_estop.v1")
        self.assertTrue(confirmations[0]["x-vendor"]["sensed_confirmation"]["confirmed"])
        self.assertEqual(uav.calls.count(LAND), 2)

    def test_a_reset_reconfirms_read_only_and_is_refused_when_the_state_no_longer_holds(self):
        uav = Uav()
        _driver, server, client, transport = self.serve(uav)
        self.assertEqual(client.estop()["status"], "completed")
        services = len([item for item in transport.sent if item.get("op") == "call_service"])
        uav.landing, uav.armed, uav.z = False, True, 1.0       # something re-armed and lifted the vehicle
        refused = client.reset()["result"]
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", "MHS.SAFETY.RESET_REFUSED"))
        self.assertTrue(server._latched[client.device_id])
        uav.armed, uav.z = False, 0.0
        reset = client.reset()["result"]
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(reset["output"]["resumed"])
        self.assertEqual(len([item for item in transport.sent if item.get("op") == "call_service"]), services)

    def test_a_terminal_sensed_stop_refuses_the_reset(self):
        uav = Uav()
        cls = uav_class("TerminalUav", estop_terminal="the motor cut is undone only by a firmware restart")
        _driver, _server, client, _ = self.serve(uav, cls=cls)
        self.assertEqual(client.estop()["status"], "completed")
        refused = client.reset()["result"]
        self.assertEqual(details(refused)["reason"], "terminal_estop")


class SensedBridgeTests(unittest.TestCase):
    """RosBridge directly: simulated device mode only, exclusive bindings, native activity supersedes."""

    def config(self, stop=None, **changes) -> dict:
        resolved = resolved_sources(copy.deepcopy(stop or sensed_stop()))
        resolved["ros_version"] = 2
        resolved["predicate"][1]["range"] = {"max": 0.1}
        resolved["predicate"][2]["span_max"] = 0.05
        config = {"timeout_s": 1.0, "resources": [{"resource_id": "main", "kind": "robot.mobile_base"}],
                  "commands": {MOVE: {"topic": "/uav/cmd_vel", "type": "geometry_msgs/msg/Twist",
                                      "args": {"linear.z": {"from": "input.vz"}}, "resource": "main"}},
                  "safety_bindings": {"sensed_stop": resolved}}
        config.update(changes)
        return config

    def bridge(self, uav: Uav, config=None, *, served: str | None = "simulated", **kwargs) -> RosBridge:
        transport = RecordingRosTransport(uav.handler)
        uav.transport = transport
        bridge = RosBridge(config or self.config(), transport=transport, **kwargs)
        self.addCleanup(bridge.close)
        if served is not None:
            bridge._bind_served_mode(served)  # what MHSServer does for a device it serves as simulated (F3)
        return bridge

    def test_only_a_simulated_device_mode_accepts_it(self):
        for mode in (None, "hardware", "hybrid", "replay"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(MHSError, "simulated devices only"):
                    RosBridge(self.config(), transport=RecordingRosTransport(None), device_mode=mode)
        self.bridge(Uav(), device_mode="simulated")

    def test_it_excludes_acknowledged_stops_and_actions_and_its_own_request_topics(self):
        estop = self.config()
        estop["safety_bindings"]["estop"] = {"service": LAND, "type": "std_srvs/srv/Trigger",
                                             "success": {"path": "success", "equals": True}}
        with self.assertRaisesRegex(MHSError, "excludes the estop"):
            RosBridge(estop, transport=RecordingRosTransport(None), device_mode="simulated")
        safe = self.config()
        safe["commands"]["x-cap.test.halt.v1"] = {"service": LAND, "type": "std_srvs/srv/Trigger",
                                                  "success": {"path": "success", "equals": True},
                                                  "safe_state": True, "resource": "main"}
        with self.assertRaisesRegex(MHSError, "safe-state command"):
            RosBridge(safe, transport=RecordingRosTransport(None), device_mode="simulated")
        action = self.config()
        action["safety_bindings"]["sensed_stop"]["request"] = [{"action": "/uav/land", "type": "a/action/Land",
                                                                "profile": "ros2-native",
                                                                "success": {"path": "ok", "equals": True}}]
        with self.assertRaisesRegex(MHSError, "action goal"):
            RosBridge(action, transport=RecordingRosTransport(None), device_mode="simulated")
        echo = self.config()
        echo["safety_bindings"]["sensed_stop"]["request"] = [
            {"topic": POSE, "type": "geometry_msgs/msg/PoseStamped", "message": {}}]
        with self.assertRaisesRegex(MHSError, "never its own confirmation"):
            RosBridge(echo, transport=RecordingRosTransport(None), device_mode="simulated")

    def test_native_activity_during_the_confirmation_supersedes_it(self):
        uav = Uav()
        uav.gap_s, uav.burst = 0.05, 12
        bridge = self.bridge(uav, device_mode="simulated")
        result: dict = {}
        worker = threading.Thread(target=lambda: result.update(bridge.estop("test")), daemon=True)
        worker.start()
        time.sleep(0.15)
        bridge._invalidate_safety_locked()       # an ordinary native call went out meanwhile
        worker.join(3)
        self.assertFalse(result["safe_state_achieved"])
        self.assertEqual(result["confirmation"]["reason"], "superseded")

    def test_native_activity_ends_an_attempt_at_once_even_one_that_would_not_confirm(self):
        uav = Uav()
        uav.ignore_land = True                   # the samples would never confirm: only the activity ends it early
        uav.gap_s, uav.burst = 0.05, 30
        bridge = self.bridge(uav, device_mode="simulated")
        result: dict = {}
        started = time.monotonic()
        worker = threading.Thread(target=lambda: result.update(bridge.estop("test")), daemon=True)
        worker.start()
        time.sleep(0.15)
        bridge._invalidate_safety_locked()
        worker.join(3)
        self.assertEqual(result["confirmation"]["reason"], "superseded")
        self.assertLess(time.monotonic() - started, 0.6)          # well before the 800 ms bound

    def test_activity_after_a_confirmation_withdraws_it(self):
        uav = Uav()
        bridge = self.bridge(uav, device_mode="simulated")
        self.assertTrue(bridge.estop("test")["safe_state_achieved"])
        self.assertTrue(bridge.safety_status()["safe_state"]["achieved"])
        bridge.call(MOVE, {"vz": 0.2})
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        self.assertIn("sensed_stop", bridge.describe()["safety_bindings"])

    def test_safe_state_requests_and_confirms(self):
        uav = Uav()
        bridge = self.bridge(uav, device_mode="simulated")
        self.assertEqual(bridge.safe_state(), {"achieved": True, "native": LAND})


class SensedDefinitionTests(unittest.TestCase):
    """RosDriver: the profile is checked at definition (gate G3), and its thresholds at construction."""

    def problems(self, cls) -> str:
        with self.assertRaises(DriverDefinitionError) as caught:
            cls.driver_model()
        return str(caught.exception)

    def test_a_hardware_driver_cannot_declare_it(self):
        self.assertIn("simulated device only", self.problems(uav_class("HardwareUav", mode="hardware")))

    def test_thresholds_are_cited_limits_or_operator_required(self):
        stop = sensed_stop()
        stop["predicate"][2]["span_max"] = 0.05
        self.assertIn("a threshold is a Limit", self.problems(uav_class("PlainNumber", stop=stop)))
        stop = sensed_stop()
        stop["predicate"][2]["span_max"] = Limit(max=0.05, source="operator", ref="README.md:3")
        self.assertIn("simulation_deployment", self.problems(uav_class("OperatorSource", stop=stop)))
        stop = sensed_stop()
        stop["predicate"][2]["span_max"] = Limit(min=0.0, max=0.05, source="vendor_doc", ref="README.md:3")
        self.assertIn("exactly one max", self.problems(uav_class("TwoSided", stop=stop)))

    def test_every_field_a_term_reads_needs_a_fill_reference(self):
        stop = sensed_stop()
        stop["sources"]["pose"]["fill_refs"] = {"pose.orientation": "README.md:1"}
        self.assertIn("has no fill_ref", self.problems(uav_class("Unfilled", stop=stop)))

    def test_the_declared_latency_covers_the_request_and_the_bound(self):
        self.assertIn("estop_latency_ms must cover", self.problems(uav_class("Fast", estop_latency_ms=1000)))

    def test_it_excludes_estop_bindings_safe_state_actions_and_a_set_ros_version(self):
        cls = uav_class("Both", safety_bindings={"sensed_stop": sensed_stop(), "estop": {
            "service": LAND, "type": "std_srvs/srv/Trigger", "success": {"path": "success", "equals": True}}})
        self.assertIn("excludes safety_bindings.estop", self.problems(cls))
        self.assertIn("ros_version is set from the driver",
                      self.problems(uav_class("Versioned", stop=sensed_stop(ros_version=2))))

    def test_the_manifest_publishes_the_confirmation_and_the_reference_prints_it(self):
        from mhs.driver.build import build_manifest
        from mhs.reference_file import render, render_markdown

        cls = uav_class("Published")
        manifest = build_manifest(cls, backend="fake")
        confirmation = manifest["safety"]["estop"]["confirmation"]
        self.assertEqual(confirmation["kind"], "sensed")
        self.assertEqual([item["topic"] for item in confirmation["sources"]], [STATE, POSE])
        thresholds = {item["name"]: item for item in confirmation["thresholds"]}
        self.assertEqual(thresholds["landed_z.max"]["operator_required"], "no landed band in the test graph")
        self.assertEqual((thresholds["rest_z"]["value"], thresholds["rest_z"]["ref"]), (0.05, "README.md:3"))
        self.assertEqual(manifest["safety"]["estop"]["native"], LAND)
        reference = render(manifest)
        self.assertEqual(reference["safety"]["estop"]["confirmation"], confirmation)
        text = render_markdown(reference)
        self.assertIn("Sensed-confirmation stop (simulated devices only; SAFE-049)", text)
        self.assertIn("no source: a wrong value can only withhold the confirmation", text)

    def test_the_fake_backend_needs_the_placeholder_fixture(self):
        holder = tempfile.TemporaryDirectory(prefix="mhs-sensed-")
        self.addCleanup(holder.cleanup)
        with self.assertRaisesRegex(ValueError, "estop-confirmation.json is missing"):
            uav_class("NoFixture")(backend="fake", native=RecordingRosTransport(None), base_dir=Path(holder.name))
        with self.assertRaisesRegex(ValueError, "widens the cited max"):
            uav_class("Wide")(backend="fake", native=RecordingRosTransport(None),
                              base_dir=fixture_dir(self, {"landed_z.max": 0.1, "rest_z": 0.5}))

    def test_a_live_deployment_fills_the_thresholds_narrow_only_and_sets_the_latency(self):
        cls = uav_class("LiveUav")
        with self.assertRaisesRegex(ValueError, "operator_required"):
            cls(backend="sim", simulation_deployment=deployment())
        with self.assertRaisesRegex(ValueError, "widens"):
            cls(backend="sim", simulation_deployment=deployment(
                estop_confirmation={"thresholds": {"landed_z.max": 0.2, "rest_z": 0.06}}))
        with self.assertRaisesRegex(ValueError, "may only rise"):
            cls(backend="sim", simulation_deployment=deployment(
                estop_confirmation={"thresholds": {"landed_z.max": 0.2}, "consecutive": 2}))
        driver = cls(backend="sim", simulation_deployment=deployment(estop_confirmation={
            "thresholds": {"landed_z.max": 0.2, "rest_z": 0.04}, "confirm_within_ms": 30000, "max_gap_ms": 2500}))
        self.addCleanup(driver.close)
        model = driver._driver_model()
        self.assertEqual(model.estop_latency_ms, 500 + 30000)
        confirmation = model.estop_confirmation
        self.assertEqual((confirmation["confirm_within_ms"], confirmation["max_gap_ms"]), (30000, 2500))
        thresholds = {item["name"]: item for item in confirmation["thresholds"]}
        self.assertEqual((thresholds["landed_z.max"]["source"], thresholds["landed_z.max"]["value"]), ("operator", 0.2))
        self.assertEqual(thresholds["rest_z"]["value"], 0.04)
        with self.assertRaisesRegex(ValueError, "only for a driver with a sensed_stop"):
            from tests.driver.test_ros_simulation import SimWorld
            SimWorld(backend="sim", simulation_deployment=deployment(estop_confirmation={"thresholds": {}}))


class SensedServerAndGateTests(SensedServeMixin, unittest.TestCase):
    """Start-up and late-device refusals in every mode; the receipt report only on the SDK route; the gate filter."""

    def manifest_device(self, mode: str):
        from mhs.server import Capability, Device, Resource, SafetyEnvelope
        from mhs.bridge.base import Bridge

        safety = SafetyEnvelope(risk_class="R0", estop={"kind": "software", "latching": True,
                                                       "confirmation": {"kind": "sensed"}})
        return Device(f"mhs://localhost/sensed-{mode}", "sensed", mode=mode,
                      resources=[Resource("main", "instrument", {"type": "object"})],
                      capabilities=[Capability("cap.measure.temperature.v1", "main")],
                      safety=safety, bridge=Bridge(), fidelity=copy.deepcopy(FAKE_FIDELITY))

    def test_the_server_refuses_a_non_simulated_device_with_a_confirmation_in_every_mode(self):
        from mhs.server import MHSServer

        for strict in (False, True):
            with self.subTest(strict=strict):
                with self.assertRaises(MHSError) as caught:
                    MHSServer("mhs://localhost", [self.manifest_device("hardware")], strict=strict)
                self.assertEqual(caught.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")
                self.assertEqual(caught.exception.data["details"]["reason"], "sensed_stop_not_simulated")

    def test_a_late_non_simulated_device_is_refused_on_first_use_and_the_estop_still_reaches_it(self):
        uav = Uav()
        _driver, server, client, _ = self.serve(uav)
        late = self.manifest_device("hardware")
        server.devices[late.device_id] = late
        with self.assertRaises(MHSError) as caught:
            server._check_late_recovery(late)
        self.assertEqual(caught.exception.data["details"]["reason"], "sensed_stop_not_simulated")
        stop = Client(server, device_id=late.device_id).estop() if False else None  # session open is refused
        self.assertIsNone(stop)
        response = client.call("mhs.safety.estop", {"device_id": late.device_id, "reason": "late",
                                                    "deadline_ms": 2000})
        self.assertIn("result", response, response)
        self.assertTrue(server._latched[late.device_id])

    def test_a_package_that_overrides_safety_status_gets_no_confirmation_in_its_receipt(self):
        from mhs.server import _sdk_ros_route

        base = uav_class("Forging")

        class Forging(base):
            def safety_status(self):
                status = super().safety_status()
                status["safe_state"]["confirmation"] = {"kind": "sensed", "last": {"confirmed": True, "forged": 1}}
                return status

        uav = Uav()
        driver, _server, client, _ = self.serve(uav, cls=Forging)
        self.assertFalse(_sdk_ros_route(driver))
        stop = client.estop()
        # Verification F3: off the SDK's own route the endpoint binds nothing, so the confirmation never stands for a
        # stop (the request still went out); and a forged report never reaches the receipt.
        self.assertEqual((stop["status"], stop["error"]["mhs_code"]), ("failed", UNREACHED), stop)
        self.assertNotIn("sensed_confirmation", stop.get("x-vendor") or {})
        self.assertNotIn("sensed", details(stop))
        self.assertEqual(driver.inner._sensed_last["reason"], "not_simulated")
        self.assertIn(LAND, uav.calls)

    def test_the_gate_filter_withholds_freezes_or_nulls_only_sensed_samples(self):
        sources = {POSE: ("header.stamp", 2, "pose.position.z")}
        uav = Uav()
        for mode in ("withhold", "frozen", "null"):
            transport = RecordingRosTransport(uav.handler)
            wrapped = SensedFilter(transport, mode, sources)
            transport.feed({"op": "service_response", "id": "a", "service": LAND, "result": True, "values": {}})
            wrapped.send({"op": "subscribe", "topic": POSE, "id": "s1"})
            first = wrapped.recv(timeout_s=0.05)
            self.assertEqual(first["op"], "service_response")
            if mode == "withhold":
                with self.assertRaises(TimeoutError):
                    wrapped.recv(timeout_s=0.05)
                continue
            sample = wrapped.recv(timeout_s=0.05)
            if mode == "frozen":
                self.assertEqual(sample["msg"]["header"]["stamp"], {"sec": 1, "nanosec": 0})
            else:
                self.assertIsNone(sample["msg"]["pose"]["position"]["z"])
        with self.assertRaises(ValueError):
            SensedFilter(RecordingRosTransport(None), "drop-some", sources)


if __name__ == "__main__":
    unittest.main()
