"""Integrator edits on p3-hardening-3 (integrator-v4, claude-opus-5-5, a model; 2026-11-05), from the Claude Sonnet
review of that change:

* S1 (edit I9): gate G3's static scan refuses package code that names a private member of the endpoint's served-mode
  binding or the bridge's safe-state commit, so a package cannot grant itself a sensed confirmation (SAFE-049);
* S4 (edit I10): a companion read-back's state line that reads the request (``res.x = req.x``) is not state, and the
  acknowledgement rule covers status, done, code, sent and completed style fields;
* S5 (edit I11): a cited ROS 2 publisher history counts no word in a comment, and a ``volatile`` claim whose QoS is a
  variable the cited lines do not define shows nothing;
* R-V4-15 (join): the assignment rule reads a protobuf setter (``msg.set_paused(...)``), the form of p3-companion-3's
  gz-sim read-back lines;
* S2 (edit I12): ``mhs.server._bind_sensed_route`` itself refuses a device whose served mode is not ``simulated``,
  also for a late device;
* E3 (edit I12): the two served-mode guards of a sensed attempt are each needed: an unbound bridge opens no
  confirmation (no subscription), and a bridge rebound away from ``simulated`` during an attempt never commits.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
import unittest

from mhs import server as server_module
from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.driver.check import Gate, static_findings
from mhs.driver.ros_check import _assigned_from_state, _check_history_refs

from tests.bridges.test_ros_sensed_stop import LAND, POSE, STATE, SensedServeMixin, Uav, resolved_sources, sensed_stop
from tests.driver import gate_support as gs
from tests.driver import test_companion_sources as companion_tests  # a module, so its test classes are not re-run here
from tests.driver.test_companion_sources import API_CPP, ALIAS, VERSION_TXT, companion_repo

# The companion fixture of the read-back tests, with lines that echo the request or report a request status:
# line 15 echoes it, 16 reads it inside a larger value, 17 reports the world's flag, 18 and 19 report what became
# of the request.
API_CPP_S4 = API_CPP + """res.pause = req.pause;  // echoes the request
response->pause = request->pause && world_->IsPaused();
res.pause = world_->IsPaused();
res.status = world_->IsPaused();
res.done = world_->IsPaused();
"""


class PrivateBindingScanTests(unittest.TestCase):
    """S1: package code never names the served-mode binding or the safe-state commit (G3 FORBIDDEN)."""

    def scan(self, code: str) -> list[str]:
        directory = gs.temp_root(self)
        (directory / "driver.py").write_text(code, encoding="utf-8")
        return [message for _code, message, _path in static_findings(directory, {})]

    def test_every_spelling_is_refused(self):
        refused = {
            "def f(bridge):\n    bridge._bind_served_mode('simulated')\n": "_bind_served_mode",
            "def f(driver):\n    driver._grant_served_mode('simulated')\n": "_grant_served_mode",
            "def f(bridge):\n    bridge._served_mode = 'simulated'\n": "_served_mode",
            "def f(bridge):\n    setattr(bridge, '_served_mode', 'simulated')\n": "_served_mode",
            "def f(driver):\n    driver.__dict__['_mhs_served_mode'] = 'simulated'\n": "_mhs_served_mode",
            "def f(driver):\n    vars(driver)['_mhs_served_mode'] = 'simulated'\n": "_mhs_served_mode",
            "def f(bridge, stamp):\n    return bridge._commit_safe_state_locked(stamp)\n": "_commit_safe_state_locked",
            "def f(bridge):\n    bridge._safe_state_achieved = True\n": "_safe_state_achieved",
            "def f(bridge):\n    bridge._safe_stamp = (0, 0)\n": "_safe_stamp",
            "def f(bridge):\n    return getattr(bridge, '_bind_' + 'served_mode')\n": "_bind_served_mode",
            "def f(bridge):\n    return getattr(bridge, f'_bind_{\"served\"}_mode')\n": "_bind_served_mode",
            "from x import _bind_sensed_route\n": "_bind_sensed_route",
        }
        for code, name in refused.items():
            with self.subTest(code=code):
                messages = self.scan(code)
                self.assertTrue(any(name in message for message in messages), messages)

    def test_ordinary_names_are_allowed(self):
        for code in ("def f(bridge):\n    return bridge.safety_status()['safe_state']['achieved']\n",
                     "served_mode = 'simulated'\n", "def f(x):\n    x._served = 1\n",
                     "def f(bridge):\n    return bridge.estop('test')\n"):
            with self.subTest(code=code):
                self.assertEqual(self.scan(code), [])
        self.assertEqual(static_findings(gs.TUTORIAL), [])


class ReadbackRequestEchoTests(companion_tests.CompanionReadBackMeaningTests):
    """S4: a state line that reads the request is no state; status-style fields are acknowledgements."""

    def setUp(self) -> None:
        from mhs.driver.upstream import UpstreamTree, companion_sources
        from tests.driver.test_companion_sources import card_entry

        root = gs.temp_root(self)
        _clone, commit = companion_repo(self, root, files={"src/api.cpp": API_CPP_S4, "VERSION.txt": VERSION_TXT})
        (root / "pkg").mkdir()
        (root / "pkg" / "node.cpp").write_text('pub = nh.advertise<std_msgs::Float64>("level", 1);\n')
        self.tree = UpstreamTree(root / "pkg", use_git=False)
        self.companions, problems = companion_sources({"package_id": "gh.acme/th1",
                                                       "companions": [card_entry(commit)]}, root)
        self.assertEqual(problems, [])

    # the inherited tests ask for the F2 fixture's lines; this class asks only its own
    test_the_shipped_form_still_passes = None
    test_an_acknowledgement_field_never_confirms_the_stop = None
    test_the_verifier_probe_is_refused = None
    test_the_read_back_is_in_the_stop_s_world = None
    test_the_state_ref_line_assigns_the_field_from_the_stopped_state = None
    test_the_assignment_reader = None

    def test_a_state_line_that_reads_the_request_is_refused(self):
        for line, accepted in ((15, False), (16, False), (17, True)):
            with self.subTest(line=line):
                messages = self.readback_messages(self.stop(safe_state={
                    "state_ref": f"companion:{ALIAS}/src/api.cpp:{line}"}))
                self.assertEqual(not any("from the stopped state" in message for message in messages), accepted,
                                 messages)

    def test_status_style_fields_are_acknowledgements(self):
        for path, line in (("status", 18), ("done", 19)):
            with self.subTest(path=path):
                messages = self.readback_messages(self.stop(safe_state={
                    "success": {"path": path, "equals": True},
                    "state_ref": f"companion:{ALIAS}/src/api.cpp:{line}"}))
                self.assertTrue(any("acknowledgement of the request" in message for message in messages), messages)

    def test_the_reader_refuses_request_values(self):
        for text in ("res.pause = req.pause;", "response->pause = request->pause;", "res.pause = (*req).pause;",
                     "res.pause = static_cast<bool>(req->pause);", "res['pause'] = goal->pause",
                     "pause=request.pause)", "res.pause = req_.pause;"):
            with self.subTest(text=text):
                self.assertFalse(_assigned_from_state("pause", text))
        for text in ("res.pause = world_->IsPaused();", "res.pause = paused; // req.pause is ignored",
                     "res.pause = required_pause_;", "res.pause = request_count_ > 0;"):
            with self.subTest(text=text):
                self.assertTrue(_assigned_from_state("pause", text))

    def test_a_protobuf_setter_assigns_its_field(self):
        # R-V4-15: p3-companion-3's fresh read-back of gz-sim WorldStatistics.paused cites the setter line
        # (SimulationRunner.cc: msg.set_paused(this->currentInfo.paused);); p3-hardening-3's assignment rule reads it
        for text in ("  msg.set_paused(this->currentInfo.paused);", "msg->set_paused(paused_);",
                     "msg.set_paused (world.paused);"):
            with self.subTest(text=text):
                self.assertTrue(_assigned_from_state("paused", text))
        for text in ("msg.set_paused(true);", "msg.set_paused(req->pause);", "msg.reset_paused(x);",
                     "msg.set_paused_flag(x);"):
            with self.subTest(text=text):
                self.assertFalse(_assigned_from_state("paused", text))


class HistoryCommentAndVariableTests(unittest.TestCase):
    """S5: a cited history counts no comment; a volatile claim shows its QoS on the cited lines."""

    def findings(self, history: dict, text: str) -> list[str]:
        tree = SimpleNamespace(read_text=lambda path: text if path == "src/node.cpp" else None)
        gate = Gate("G7", "Native surface")
        _check_history_refs(SimpleNamespace(tree=tree), gate, {"sources": {"pose": {"history": history}}})
        return [finding.code for finding in gate.findings]

    def test_comments_and_hidden_qos(self):
        lines = len
        cases = (
            ("volatile", 'pub_ = create_publisher<Odometry>("odom", qos_);', False),
            ("volatile", 'auto qos_ = rclcpp::QoS(10);\npub_ = create_publisher<Odometry>("odom", qos_);', True),
            ("volatile", "self.pub = self.create_publisher(Odometry, 'odom', qos_profile_sensor_data)", True),
            ("volatile", 'pub_ = create_publisher<Odometry>("odom", rclcpp::SystemDefaultsQoS());', True),
            ("volatile", 'pub_ = create_publisher<Odometry>("odom", latched_qos);  // volatile', False),
            ("volatile", 'pub_ = create_publisher<Odometry>(\n    "odom",', False),
            ("volatile", 'pub = self.create_publisher(\n    topic_type, self.cf_dict[uri] + "/" + prefix, 10)', True),
            ("volatile", 'pub_ = create_publisher<Odometry>("odom", 10);  /* transient_local elsewhere */', True),
            ("transient_local", 'pub_ = create_publisher<Odometry>("odom", qos);  // transient_local, depth 5', False),
            ("transient_local", 'create_publisher<Odometry>("odom", rclcpp::QoS(5).transient_local());', True),
        )
        for durability, text, ok in cases:
            with self.subTest(text=text):
                history = {"durability": durability, "ref": f"src/node.cpp:1-{lines(text.splitlines())}"}
                if durability == "transient_local":
                    history["depth"] = 5
                codes = self.findings(history, text)
                self.assertEqual(codes == [], ok, codes)
                if not ok:
                    self.assertEqual(codes, ["G7.ROS_HISTORY_NOT_SHOWN"])


class ServedBindingRouteTests(SensedServeMixin, unittest.TestCase):
    """S2 and E3: the route binding's own mode check, and both served-mode guards of an attempt."""

    def raw_bridge(self, uav: Uav, handler=None) -> RosBridge:
        transport = RecordingRosTransport(handler or uav.handler)
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

    def device(self, bridge, mode):
        return SimpleNamespace(device_id="uav", mode=mode, bridge=bridge,
                               safety=SimpleNamespace(estop={"confirmation": {"kind": "sensed"}}))

    def test_the_route_binding_refuses_a_device_not_served_as_simulated(self):
        bridge = self.raw_bridge(Uav())
        for mode in ("hardware", "hybrid", None):
            with self.subTest(mode=mode):
                self.assertFalse(server_module._bind_sensed_route(self.device(bridge, mode)))
                self.assertIsNone(bridge._served_mode)
        self.assertFalse(bridge.estop("hardware served")["safe_state_achieved"])
        self.assertTrue(server_module._bind_sensed_route(self.device(bridge, "simulated")))
        self.assertEqual(bridge._served_mode, "simulated")

    def test_a_late_hardware_device_is_never_bound(self):
        uav = Uav()
        _driver, server, _client, _ = self.serve(uav)
        bridge = self.raw_bridge(Uav())
        late = SimpleNamespace(device_id="uav-late-hardware", mode="hardware", bridge=bridge,
                               safety=SimpleNamespace(estop={"confirmation": {"kind": "sensed"}}))
        self.assertFalse(server_module._bind_sensed_route(late))
        server.devices[late.device_id] = late
        with self.assertRaises(Exception):
            server._check_late_recovery(late)  # refused: a sensed stop on a hardware device (SAFE-049)
        self.assertIsNone(bridge._served_mode)

    def test_an_unbound_bridge_opens_no_confirmation(self):
        uav = Uav()
        bridge = self.raw_bridge(uav)
        result = bridge.estop("unbound")
        self.assertEqual(result["confirmation"]["reason"], "not_simulated")
        self.assertEqual(result["performed"], [LAND])
        sent = uav.transport.sent
        self.assertEqual([message for message in sent if message.get("op") == "subscribe"], [],
                         "an unbound bridge must not subscribe to its sources")

    def test_a_bridge_rebound_away_from_simulated_during_an_attempt_never_commits(self):
        uav = Uav()
        holder = {}

        def rebinding(message):
            if message.get("op") == "subscribe" and message.get("topic") == POSE:
                holder["bridge"]._bind_served_mode("hardware")  # another endpoint path rebinds mid-attempt
            return uav.handler(message)

        bridge = self.raw_bridge(uav, rebinding)
        holder["bridge"] = bridge
        bridge._bind_served_mode("simulated")
        result = bridge.estop("rebound")
        self.assertFalse(result["safe_state_achieved"])
        self.assertEqual(result["confirmation"]["reason"], "not_simulated")
        self.assertIn(STATE, [message.get("topic") for message in uav.transport.sent if message.get("op") == "subscribe"])


if __name__ == "__main__":
    unittest.main()
