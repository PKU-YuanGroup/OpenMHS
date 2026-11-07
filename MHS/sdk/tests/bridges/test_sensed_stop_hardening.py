"""Hardening of the sensed-confirmation stop after the phase-3 verification (lens safety-path; SAFE-049, CORE-088).

F1: a source whose new subscription replays more than one pre-request sample (a ROS 2 transient-local history deeper
than one) must not confirm the stop. Only samples provably published after the subscription was opened count: the
bridge discards every ROS 1 stamp sample (no proven producer-clock offset) and the declared publisher history on ROS 2
(cited, or operator_required and then stated by the fake's fixture or the live deployment, never lower than a cited
one), by arrival ordinal numbered before its ring drops anything. Every test here replays a deep history.

F3: the simulated-only restriction is bound to what the endpoint serves. A sensed confirmation commits a safe state
only on a RosBridge that :class:`mhs.server.MHSServer` bound after it checked the served manifest (mode
``simulated``, the confirmation declared) on the SDK's own ROS route; the constructor's ``device_mode`` can refuse
but never grant it, so a package's own bridge built with ``device_mode="simulated"`` never confirms.
"""

from __future__ import annotations

import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from mhs.bridge import ros_sensed
from mhs.bridge.base import Bridge
from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.driver import DriverDefinitionError, Limit, build_server, close_server
from mhs.errors import MHSError
from tests.bridges.test_ros_sensed_stop import (LAND, MOVE, NS, POSE, STATE, UNREACHED, SensedServeMixin, Uav,
                                                details, fixture_dir, resolved_sources, sensed_stop, uav_class)
from tests.driver.support import Client
from tests.driver.test_ros_simulation import FAKE_FIDELITY, deployment


class ReplayUav(Uav):
    """A ROS 2 graph stand-in whose new subscriptions first replay a deep pre-request history.

    The history (``depth`` samples, older stamps) shows the vehicle landed and disarmed; what is published after the
    subscription (``live`` samples) shows the vehicle as it is now. This is the verifier's probe p1.py generalised:
    a transient-local publisher keeps ``depth`` samples and replays them to every new subscription.
    """

    def __init__(self, depth: int = 5, live: int = 0, ros_version: int = 2) -> None:
        super().__init__(ros_version)
        self.depth, self.live = depth, live

    def handler(self, message: dict):
        if message.get("op") == "subscribe" and message.get("topic") in (STATE, POSE):
            replay = []
            history_clock = self.clock - (self.depth + 1) * (NS // 10)
            for index in range(self.depth):
                history_clock += NS // 10
                sample = self.sample(message["topic"], message["id"])
                stamp = {"sec": history_clock // NS, "nanosec": history_clock % NS} if self.ros_version == 2 else {
                    "secs": history_clock // NS, "nsecs": history_clock % NS}
                sample["msg"]["header"]["stamp"] = stamp
                if message["topic"] == STATE:
                    sample["msg"]["armed"] = False
                else:
                    sample["msg"]["pose"]["position"]["z"] = 0.0
                replay.append(sample)
            live = []
            for _ in range(self.live):
                live.append(self.sample(message["topic"], message["id"]))
                self.tick()
            return replay + live
        return super().handler(message)


def deep_stop(depth: int, *, ros: int = 2, **changes) -> dict:
    """``sensed_stop()`` whose two sources declare a transient-local history of ``depth`` samples."""
    stop = sensed_stop(ros=ros, **changes)
    if ros == 2:
        for source in stop["sources"].values():
            source["history"] = {"durability": "transient_local", "depth": depth, "ref": "README.md:4"}
    return stop


class ReplayLogicTests(unittest.TestCase):
    """mhs.bridge.ros_sensed: the replay bound, the ring's ordinals and the window's discard."""

    def profile(self, history=None, ros_version: int = 2):
        source = {"topic": POSE, "type": "geometry_msgs/msg/PoseStamped"}
        if history is not None:
            source["history"] = history
        return ros_sensed.compile_profile({
            "ros_version": ros_version, "description": "test", "max_gap_ms": 400, "confirm_within_ms": 800,
            "consecutive": 3, "min_span_ms": 100, "sources": {"pose": source},
            "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed", "range": {"max": 0.1}}]})

    @staticmethod
    def msg(t: int, z: float = 0.0) -> dict:
        return {"header": {"stamp": {"sec": t // NS, "nanosec": t % NS}}, "pose": {"position": {"z": z}}}

    def test_the_replay_bound_of_each_generation(self):
        self.assertEqual(ros_sensed.replay_bound({"durability": "volatile"}, where="h"), 0)
        self.assertEqual(ros_sensed.replay_bound({"durability": "transient_local", "depth": 7}, where="h"), 7)
        for bad in (None, {}, {"durability": "latched"}, {"durability": "volatile", "depth": 1},
                    {"durability": "transient_local"}, {"durability": "transient_local", "depth": 0},
                    {"durability": "transient_local", "depth": True}, {"durability": "transient_local", "depth": 1.0},
                    {"durability": "transient_local", "depth": ros_sensed.MAX_HISTORY_DEPTH + 1}):
            with self.subTest(bad=bad), self.assertRaises(ros_sensed.SensedConfigError):
                ros_sensed.replay_bound(bad, where="h")
        self.assertEqual(self.profile({"durability": "volatile"}).sources["pose"].skip, 1)
        self.assertEqual(self.profile({"durability": "transient_local", "depth": 9}).sources["pose"].skip, 9)
        self.assertEqual(self.profile(ros_version=1).sources["pose"].skip, 1)

    def test_a_ros2_source_without_a_history_and_a_ros1_source_with_one_are_refused(self):
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "declares its publisher's history"):
            self.profile()
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "ROS 2 durability"):
            self.profile({"durability": "volatile"}, ros_version=1)

    def test_a_deep_replay_is_discarded_whatever_it_shows(self):
        profile = self.profile({"durability": "transient_local", "depth": 5})
        window = ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0.0)
        for index in range(5):               # the replay: landed, stamps increasing, all at one instant
            window.add(self.msg((index + 1) * NS // 10), 0.05)
        self.assertEqual((window.seen, len(window.counted), window.discarded), (0, 0, 5))
        self.assertFalse(window.confirmed(0.05))
        self.assertEqual(ros_sensed.unconfirmed_reason({"pose": window}, 0.9), "sensed_missing")
        self.assertEqual(window.last_stamp, 5 * NS // 10)   # the newest replayed stamp is the baseline
        window.add(self.msg(5 * NS // 10), 0.06)             # a live sample must be newer than every replayed one
        self.assertEqual((window.last_reset, len(window.counted)), ("duplicate", 0))

    def test_the_ring_numbers_every_sample_so_a_lossy_replay_is_discarded_exactly(self):
        profile = self.profile({"durability": "transient_local", "depth": 20})
        ring = ros_sensed.Ring(4)
        for index in range(20):              # a 20-sample replay into a 4-sample ring: 16 are lost
            ring.append((self.msg((index + 1) * NS // 10), 0.05))
        self.assertEqual((ring.total, ring.overflowed, [item[2] for item in ring.items]), (20, True, [17, 18, 19, 20]))
        window = ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0.0)
        for sample, received_at, ordinal, continuation in ring.items:
            window.add(sample, received_at, ordinal, continuation=continuation)
        self.assertEqual((window.seen, len(window.counted), window.received), (0, 0, 20))
        for index in range(4):               # live samples after the replay count
            window.add(self.msg((21 + index) * NS // 10), 0.06 + 0.01 * index, 21 + index)
        self.assertEqual(len(window.counted), 3)
        self.assertTrue(window.confirmed(0.1))


class ReplayEstopTests(SensedServeMixin, unittest.TestCase):
    """Through the endpoint: a deep replay never confirms; live samples after it still can."""

    def assert_unreached(self, receipt, reason):
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], reason, receipt)
        self.assertTrue(receipt["output"]["latched"])

    def test_the_verifier_probe_no_longer_confirms(self):
        # p1.py: five replayed samples show the vehicle landed and disarmed; it is at 5 m and armed, and the LAND is
        # acknowledged but does nothing. The declared transient-local depth of 5 discards the whole replay.
        uav = ReplayUav(depth=5, live=0)
        uav.z, uav.armed, uav.ignore_land = 5.0, True, True
        _driver, server, client, _ = self.serve(uav, cls=uav_class("Replay5", stop=deep_stop(5)))
        receipt = client.estop()
        self.assert_unreached(receipt, "sensed_missing")
        self.assertTrue(server._latched[client.device_id])
        for name in ("state", "pose"):
            self.assertEqual(details(receipt)["sensed"]["sources"][name]["seen"], 0)

    def test_a_deep_replay_then_live_airborne_samples_is_not_confirmed(self):
        uav = ReplayUav(depth=6, live=8)
        uav.z, uav.armed, uav.ignore_land = 5.0, True, True
        _driver, _server, client, _ = self.serve(uav, cls=uav_class("Replay6", stop=deep_stop(6)))
        self.assert_unreached(client.estop(), "not_confirmed")

    def test_a_deep_replay_then_live_landed_samples_confirms(self):
        uav = ReplayUav(depth=6, live=12)    # the LAND works: the live samples descend and land
        _driver, _server, client, _ = self.serve(uav, cls=uav_class("Replay6Lands", stop=deep_stop(6)))
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        for name in ("state", "pose"):
            self.assertEqual(stop["x-vendor"]["sensed_confirmation"]["sources"][name]["samples"], 3)

    def test_a_replay_deeper_than_the_ring_is_still_discarded(self):
        # 40 replayed samples overflow the 16-sample ring; the ring's ordinals keep them uncounted.
        uav = ReplayUav(depth=40, live=0)
        uav.z, uav.armed, uav.ignore_land = 5.0, True, True
        _driver, _server, client, _ = self.serve(uav, cls=uav_class("Replay40", stop=deep_stop(40)))
        self.assert_unreached(client.estop(), "sensed_missing")

    def test_the_declared_history_is_the_trusted_bound(self):
        # The trust boundary, pinned: a declaration that understates the replay (volatile, while this graph keeps
        # five) lets the replay count. The cited QoS line is what makes the bound true: gate G7 checks that it shows
        # the declared durability and depth, and the reviewer that it is the source's publisher (REVIEW.md item 5).
        uav = ReplayUav(depth=5, live=0)
        uav.z, uav.armed, uav.ignore_land = 5.0, True, True
        _driver, _server, client, _ = self.serve(uav, cls=uav_class("Understated"))
        self.assertEqual(client.estop()["status"], "completed")

    def test_a_ros1_latched_replay_is_one_sample(self):
        uav = ReplayUav(depth=1, live=0, ros_version=1)
        uav.z, uav.armed, uav.ignore_land = 5.0, True, True
        _driver, _server, client, _ = self.serve(uav, cls=uav_class("Ros1Latched", ros_version=1))
        self.assert_unreached(client.estop(), "sensed_missing")


class LossyReplayBridgeTests(unittest.TestCase):
    """The bridge numbers samples before its ring drops any: a lossy deep replay is discarded exactly, and the live
    samples after it count (a window that counted only what it saw would discard them too and never confirm)."""

    def test_live_samples_after_a_replay_the_ring_lost_still_confirm(self):
        import time

        depth, live = 20, 12   # 32 samples per subscription into a 16-sample ring: it overflows before it is read

        class InjectingBridge(RosBridge):
            """Stands in for the receiver: every subscription's samples are in its ring before the bridge reads it."""

            clock = 100 * NS

            def _send(self, message, deadline, context, epoch, **kwargs):
                super()._send(message, deadline, context, epoch, **kwargs)
                if message.get("op") != "subscribe":
                    return
                with self._condition:
                    ring = self._sensed_rings.get(message["id"])
                    now = time.monotonic()
                    for index in range(depth + live):
                        InjectingBridge.clock += NS // 10
                        stamp = {"sec": self.clock // NS, "nanosec": self.clock % NS}
                        body = ({"header": {"stamp": stamp}, "armed": False, "connected": True}
                                if message["topic"] == STATE else
                                {"header": {"stamp": stamp}, "pose": {"position": {"x": 0.0, "y": 0.0, "z": 0.0}}})
                        ring.append((body, now))
                    self._condition.notify_all()

        stop = resolved_sources(deep_stop(depth))
        stop["ros_version"] = 2
        stop["predicate"][1]["range"] = {"max": 0.1}
        stop["predicate"][2]["span_max"] = 0.05
        uav = Uav()
        uav.silent = True    # the graph stand-in answers the request only; the samples come from the ring above
        transport = RecordingRosTransport(uav.handler)
        bridge = InjectingBridge({"timeout_s": 1.0, "resources": [{"resource_id": "main", "kind": "robot.mobile_base"}],
                                  "safety_bindings": {"sensed_stop": stop}}, transport=transport,
                                 device_mode="simulated")
        self.addCleanup(bridge.close)
        bridge._bind_served_mode("simulated")
        result = bridge.estop("lossy replay")
        self.assertTrue(result["safe_state_achieved"], result)
        for name in ("state", "pose"):
            report = result["confirmation"]["sources"][name]
            self.assertEqual((report["samples"], report["seen"]), (3, live), report)


class HistoryDeclarationTests(unittest.TestCase):
    """RosDriver: the history is cited or operator_required; the fake's fixture or the deployment states the latter."""

    def problems(self, cls) -> str:
        with self.assertRaises(DriverDefinitionError) as caught:
            cls.driver_model()
        return str(caught.exception)

    def test_a_ros2_source_declares_its_history_and_a_ros1_source_none(self):
        stop = sensed_stop()
        del stop["sources"]["pose"]["history"]
        self.assertIn("declares its publisher's history", self.problems(uav_class("NoHistory", stop=stop)))
        ros1 = sensed_stop(ros=1)
        ros1["sources"]["pose"]["history"] = {"durability": "volatile", "ref": "README.md:1"}
        self.assertIn("ROS 2 durability", self.problems(uav_class("Ros1History", stop=ros1, ros_version=1)))
        for bad, text in (({"durability": "volatile"}, "ref must be"),
                          ({"durability": "transient_local", "ref": "README.md:1"}, "states its depth"),
                          ({"operator_required": ""}, "operator_required history"),
                          ({"operator_required": "x", "durability": "volatile"}, "operator_required history"),
                          ("volatile", "must be")):
            with self.subTest(bad=bad):
                stop = sensed_stop()
                stop["sources"]["pose"]["history"] = bad
                self.assertIn(text, self.problems(uav_class("BadHistory", stop=stop)))

    def operator_stop(self) -> dict:
        stop = deep_stop(3)
        stop["sources"]["state"]["history"] = {"operator_required": "the state publisher is outside the clone"}
        return stop

    def fixture(self, history) -> Path:
        holder = tempfile.TemporaryDirectory(prefix="mhs-sensed-")
        self.addCleanup(holder.cleanup)
        base = Path(holder.name)
        (base / "fixtures").mkdir()
        document = {"thresholds": {"landed_z.max": 0.1}}
        if history is not None:
            document["history"] = history
        (base / "fixtures/estop-confirmation.json").write_text(json.dumps(document))
        return base

    def test_the_fake_backend_reads_an_operator_required_history_from_its_fixture(self):
        cls = uav_class("OperatorHistory", stop=self.operator_stop())
        with self.assertRaisesRegex(ValueError, "operator_required"):
            cls(backend="fake", native=RecordingRosTransport(None), base_dir=self.fixture(None))
        with self.assertRaisesRegex(ValueError, "fewer than the cited history"):
            cls(backend="fake", native=RecordingRosTransport(None), base_dir=self.fixture(
                {"state": {"durability": "volatile"}, "pose": {"durability": "transient_local", "depth": 2}}))
        driver = cls(backend="fake", native=RecordingRosTransport(None), base_dir=self.fixture(
            {"state": {"durability": "transient_local", "depth": 4}}))
        self.addCleanup(driver.close)
        sources = driver.inner._sensed.sources
        self.assertEqual((sources["state"].replay, sources["pose"].replay), (4, 3))

    def test_a_live_deployment_states_an_operator_required_history_and_may_only_raise_a_cited_one(self):
        cls = uav_class("LiveHistory", stop=self.operator_stop())
        thresholds = {"landed_z.max": 0.2, "rest_z": 0.04}
        with self.assertRaisesRegex(ValueError, "history of source 'state' is operator_required"):
            cls(backend="sim", simulation_deployment=deployment(estop_confirmation={"thresholds": thresholds}))
        with self.assertRaisesRegex(ValueError, "fewer than the cited history"):
            cls(backend="sim", simulation_deployment=deployment(estop_confirmation={
                "thresholds": thresholds, "history": {"state": {"durability": "volatile"},
                                                      "pose": {"durability": "volatile"}}}))
        with self.assertRaisesRegex(ValueError, "not a ROS 2 source"):
            cls(backend="sim", simulation_deployment=deployment(estop_confirmation={
                "thresholds": thresholds, "history": {"state": {"durability": "volatile"},
                                                      "odom": {"durability": "volatile"}}}))
        driver = cls(backend="sim", simulation_deployment=deployment(estop_confirmation={
            "thresholds": thresholds, "history": {"state": {"durability": "volatile"},
                                                  "pose": {"durability": "transient_local", "depth": 10}}}))
        self.addCleanup(driver.close)
        sources = {item["name"]: item for item in driver._driver_model().estop_confirmation["sources"]}
        self.assertEqual(sources["state"]["history"], {"durability": "volatile", "source": "operator"})
        self.assertEqual(sources["pose"]["history"], {"durability": "transient_local", "depth": 10,
                                                      "source": "operator"})
        self.assertEqual(driver.inner._sensed.sources["pose"].replay, 10)

    def test_the_manifest_and_the_reference_publish_each_ros2_history(self):
        from mhs.driver.build import build_manifest
        from mhs.reference_file import render, render_markdown

        manifest = build_manifest(uav_class("PublishedHistory", stop=self.operator_stop()), backend="fake")
        sources = {item["name"]: item for item in manifest["safety"]["estop"]["confirmation"]["sources"]}
        self.assertEqual(sources["state"]["history"], {"operator_required": "the state publisher is outside the clone"})
        self.assertEqual(sources["pose"]["history"], {"durability": "transient_local", "depth": 3, "ref": "README.md:4"})
        text = render_markdown(render(manifest))
        self.assertIn("Publisher history of `/uav/pose` (a new subscription's replay, discarded before any sample "
                      "counts): transient_local, depth 3, cited `README.md:4`.", text)
        self.assertIn("operator_required (the state publisher is outside the clone)", text)
        ros1 = build_manifest(uav_class("Ros1Published", ros_version=1), backend="fake")
        self.assertFalse(any("history" in item for item in ros1["safety"]["estop"]["confirmation"]["sources"]))


class HistoryGateTests(unittest.TestCase):
    """Gate G7: a cited history shows the QoS it claims; gate G3: the fixture's placeholders."""

    def findings(self, history: dict, text: str) -> list[str]:
        from mhs.driver.check import Gate
        from mhs.driver.ros_check import _check_history_refs

        tree = SimpleNamespace(read_text=lambda path: text if path == "src/node.cpp" else None)
        gate = Gate("G7", "Native surface")
        _check_history_refs(SimpleNamespace(tree=tree), gate, {"sources": {"pose": {"history": history}}})
        return [finding.code for finding in gate.findings]

    def test_a_cited_history_must_show_its_qos(self):
        volatile = {"durability": "volatile", "ref": "src/node.cpp:1"}
        latched = {"durability": "transient_local", "depth": 5, "ref": "src/node.cpp:1"}
        for history, text, ok in (
                (volatile, 'pub_ = create_publisher<Odometry>("odom", 10);', True),
                (volatile, "rclcpp::QoS(10).durability_volatile()", True),
                (volatile, 'pub_ = create_publisher<Odometry>("odom", rclcpp::QoS(5).transient_local());', False),
                (volatile, "# the odometry topic", False),
                (latched, 'create_publisher<Odometry>("odom", rclcpp::QoS(5).transient_local());', True),
                (latched, "QoSProfile(depth=5, durability=DurabilityPolicy.TRANSIENT_LOCAL)", True),
                (latched, 'create_publisher<Odometry>("odom", rclcpp::QoS(50).transient_local());', False),
                (latched, 'create_publisher<Odometry>("odom", 5);', False)):
            with self.subTest(text=text, durability=history["durability"]):
                codes = self.findings(history, text)
                self.assertEqual(codes == [], ok, codes)
                if not ok:
                    self.assertEqual(codes, ["G7.ROS_HISTORY_NOT_SHOWN"])
        self.assertEqual(self.findings({"operator_required": "outside the clone"}, ""), [])
        self.assertIn("G7.ROS_REF_MISSING", self.findings(dict(volatile, ref="src/other.cpp:1"), ""))


class ServedBindingTests(SensedServeMixin, unittest.TestCase):
    """F3: only the endpoint, from what it serves, lets a sensed confirmation stand for a stop."""

    def raw_bridge(self, uav: Uav) -> RosBridge:
        transport = RecordingRosTransport(uav.handler)
        uav.transport = transport
        config = {"timeout_s": 1.0, "resources": [{"resource_id": "main", "kind": "robot.mobile_base"}],
                  "safety_bindings": {"sensed_stop": resolved_sources(copy.deepcopy(sensed_stop()))}}
        stop = config["safety_bindings"]["sensed_stop"]
        stop["ros_version"] = 2
        stop["predicate"][1]["range"] = {"max": 0.1}
        stop["predicate"][2]["span_max"] = 0.05
        bridge = RosBridge(config, transport=transport, device_mode="simulated")
        self.addCleanup(bridge.close)
        return bridge

    def test_the_constructor_argument_never_grants_the_stop(self):
        uav = Uav()
        bridge = self.raw_bridge(uav)
        result = bridge.estop("unbound")
        self.assertFalse(result["safe_state_achieved"])
        self.assertEqual(result["confirmation"]["reason"], "not_simulated")
        self.assertEqual(result["performed"], [LAND])             # the request still went out
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        bridge._bind_served_mode("hardware")
        self.assertEqual(bridge.estop("hardware")["confirmation"]["reason"], "not_simulated")
        bridge._bind_served_mode("simulated")
        self.assertTrue(bridge.estop("served simulated")["safe_state_achieved"])

    def test_an_unbound_reset_is_refused(self):
        uav = Uav()
        bridge = self.raw_bridge(uav)
        bridge._bind_served_mode("simulated")
        self.assertTrue(bridge.estop("bound")["safe_state_achieved"])
        bridge._bind_served_mode(None)
        with self.assertRaises(MHSError) as caught:
            bridge.reset()
        self.assertEqual(caught.exception.data["details"]["sensed_reason"], "not_simulated")

    def test_the_server_binds_the_sdk_route_and_a_driver_without_a_server_never_confirms(self):
        uav = Uav()
        driver, _server, client, _ = self.serve(uav)
        self.assertEqual(driver.__dict__.get("_mhs_served_mode"), "simulated")
        self.assertEqual(client.estop()["status"], "completed")
        self.assertEqual(driver.inner._served_mode, "simulated")
        alone = uav_class()(backend="fake", native=RecordingRosTransport(Uav().handler), base_dir=fixture_dir(self))
        self.addCleanup(alone.close)
        result = alone.estop("no endpoint")
        self.assertFalse(result["safe_state_achieved"])
        self.assertEqual(result["confirmation"]["reason"], "not_simulated")

    def test_a_late_device_is_bound_on_first_use(self):
        uav = Uav()
        _driver, server, _client, _ = self.serve(uav)
        late_uav = Uav()
        transport = RecordingRosTransport(late_uav.handler)
        late_uav.transport = transport
        late = uav_class("LateUav", device_id="uav-late")(backend="fake", native=transport, base_dir=fixture_dir(self))
        self.addCleanup(late.close)
        from mhs.driver.build import build_device

        device = build_device(late)
        server.devices[device.device_id] = device
        self.assertIsNone(late.__dict__.get("_mhs_served_mode"))
        server._check_late_recovery(device)
        self.assertEqual(late.__dict__.get("_mhs_served_mode"), "simulated")

    def test_a_package_s_own_hardware_bridge_with_device_mode_simulated_gets_no_sensed_stop(self):
        # The verifier's F3: a hand-written hardware Driver builds RosBridge(..., device_mode="simulated") with a
        # sensed_stop config; its manifest declares no confirmation, so the start-up check cannot see it. The endpoint
        # binds nothing off the SDK's route, so the confirmation never commits and the e-stop fails, latched.
        from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

        uav = Uav()
        inner = self.raw_bridge(uav)

        class HandWritten(Bridge):
            def estop(self, reason: str = "", ctx=None):
                self._engage_estop()
                return inner.estop(reason, ctx)

            def safety_status(self):
                return inner.safety_status()

        device = Device("mhs://localhost/hand-written", "hand-written", mode="hardware",
                        resources=[Resource("main", "instrument", {"type": "object"})],
                        capabilities=[Capability("cap.measure.temperature.v1", "main")],
                        safety=SafetyEnvelope(risk_class="R2", estop={"kind": "software", "latching": True}),
                        bridge=HandWritten(), fidelity=copy.deepcopy(FAKE_FIDELITY))
        server = MHSServer("mhs://localhost", [device])
        self.addCleanup(server.close)
        self.assertIsNone(inner._served_mode)
        receipt = Client(server).estop()
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.assertEqual(inner._sensed_last["reason"], "not_simulated")
        self.assertIn(LAND, uav.calls)
        self.assertTrue(server._latched[device.device_id])

    def test_a_rosdriver_off_the_sdk_route_is_never_bound_and_gate_g3_says_why(self):
        from mhs.driver.check import Gate, _g3_sensed_served

        base = uav_class("OffRoute")

        class OffRoute(base):
            def make_bridge(self, native):
                return super().make_bridge(native)

        uav = Uav()
        driver, _server, client, _ = self.serve(uav, cls=OffRoute)
        self.assertIsNone(driver.__dict__.get("_mhs_served_mode"))
        receipt = client.estop()
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.assertEqual(driver.inner._sensed_last["reason"], "not_simulated")
        gate = Gate("G3", "Definition")
        _g3_sensed_served(SimpleNamespace(instance=None, cls=OffRoute, backend="fake"), gate)
        self.assertEqual([finding.code for finding in gate.findings], ["G3.SENSED_ROUTE"])
        gate = Gate("G3", "Definition")
        _g3_sensed_served(SimpleNamespace(instance=None, cls=base, backend="fake"), gate)
        self.assertEqual(gate.findings, [])

    def test_an_instance_that_builds_its_own_bridge_is_never_bound(self):
        # An instance attribute make_bridge decides which bridge is built: the endpoint grants nothing then, even when
        # the attribute only calls the SDK's own method (the gate's phase windows wrap estop and friends, never this).
        import types

        cls = uav_class("InstanceBuilder")
        transport = RecordingRosTransport(Uav().handler)
        driver = cls(backend="fake", native=transport, base_dir=fixture_dir(self))
        driver.make_bridge = types.MethodType(cls.make_bridge, driver)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.assertIsNone(driver.__dict__.get("_mhs_served_mode"))
        receipt = Client(server).estop()
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.assertEqual(driver.inner._sensed_last["reason"], "not_simulated")

    def test_gate_g3_checks_the_served_manifest_as_the_server_does(self):
        from mhs.driver import build as build_module
        from mhs.driver.check import Gate, _g3_sensed_served

        cls = uav_class("ServedHardware")
        manifest = build_module.build_manifest(cls, backend="fake")
        for mode, expected in (("hardware", ["G3.SENSED_SERVED"]), ("simulated", [])):
            with self.subTest(mode=mode):
                served = dict(copy.deepcopy(manifest), mode=mode)
                with mock.patch.object(build_module, "build_manifest", return_value=served):
                    gate = Gate("G3", "Definition")
                    _g3_sensed_served(SimpleNamespace(instance=None, cls=cls, backend="fake"), gate)
                self.assertEqual([finding.code for finding in gate.findings], expected)


HOLD = "/uav/hold"


def hold_stop() -> dict:
    """A landed vehicle whose request publishes a hold the exclusion watch reads."""
    stop = sensed_stop()
    stop["request"] = [{
        "topic": HOLD, "type": "std_msgs/msg/Float64", "timeout_ms": 500, "source_ref": "README.md:1",
        "message": {"kp": 0.0, "kd": 0.0},
    }]
    stop["exclusion"] = {
        "topic": HOLD, "type": "std_msgs/msg/Float64", "source_ref": "README.md:4",
        "paths": ["kp", "kd"],
    }
    return stop


class HoldUav(Uav):
    """Already landed. ``overflow`` queues one non-passive hold, then 128 passive samples, before evaluation."""

    def __init__(self, overflow: bool) -> None:
        super().__init__(2)
        self.overflow = overflow
        self.z = 0.0
        self.armed = False
        self.gain_kp = 0.0
        self.gain_kd = 0.0
        self.observed: list = []
        self.snapshot: tuple[int, bool] | None = None

    def handler(self, message: dict):
        operation = message.get("op")
        if operation == "publish" and message.get("topic") == HOLD:
            if self.overflow:
                # The competing controller keeps its gains. The passive request does not clear them.
                self.gain_kp, self.gain_kd = 50.0, 1.0
            return None
        if operation == "subscribe" and message.get("topic") == HOLD:
            passive = {"op": "publish", "topic": HOLD, "id": message["id"], "msg": {"kp": 0.0, "kd": 0.0}}
            if not self.overflow:
                return passive
            active = {"op": "publish", "topic": HOLD, "id": message["id"],
                      "msg": {"kp": self.gain_kp, "kd": self.gain_kd}}
            frames = [active] + [copy.deepcopy(passive) for _ in range(128)]
            for frame in frames:
                self.transport.feed(frame)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and (not self.observed or self.observed[-1].total < 129):
                time.sleep(0.001)
            if self.observed:
                ring = self.observed[-1]
                self.snapshot = (ring.total, ring.overflowed)
            return None
        return super().handler(message)


class ExclusionOverflowTests(SensedServeMixin, unittest.TestCase):
    """A lost exclusion sample is an observer fault. One passive sample still confirms."""

    def _serve(self, overflow: bool):
        observed: list = []
        original = ros_sensed.Ring

        class ObservedRing(original):
            def __init__(self, capacity: int) -> None:
                super().__init__(capacity)
                observed.append(self)

        ros_sensed.Ring = ObservedRing
        self.addCleanup(setattr, ros_sensed, "Ring", original)
        uav = HoldUav(overflow)
        uav.observed = observed
        cls = uav_class("HoldUav", stop=hold_stop())
        return self.serve(uav, cls=cls) + (uav,)

    def test_a_dropped_non_passive_sample_refuses_confirmation(self):
        _driver, _server, client, _transport, uav = self._serve(True)
        receipt = client.estop()
        self.assertIsNotNone(uav.snapshot)
        self.assertGreaterEqual(uav.snapshot[0], 129)
        self.assertTrue(uav.snapshot[1])
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", UNREACHED), receipt)
        self.assertEqual(details(receipt)["sensed"]["reason"], "not_confirmed", receipt)
        self.assertEqual((uav.gain_kp, uav.gain_kd), (50.0, 1.0))

    def test_one_passive_exclusion_sample_still_confirms(self):
        _driver, _server, client, _transport, uav = self._serve(False)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        self.assertEqual((uav.gain_kp, uav.gain_kd), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
