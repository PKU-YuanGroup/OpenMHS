"""A confirmed ROS stop request is not sent again in the same e-stop (CORE-074, RUNTIME-AND-GATE-FIXES).

The e-stop runs the native stop and then every ``safe_state.achieved_by`` action.  When a ROS safe-state command sends
the same request as the bridge's own stop (the hector LAND of coppolam/ros_mav_swarm_simulator was bound both as
``safety_bindings.estop`` and as a ``safe_state=True`` action, and a second LAND re-enables the motors), the ROS bridge
answers the command from that request's response once it was confirmed successful; the command still checks it against
its own output contract.  After a failed, timed-out or unconfirmed request, or one still unanswered once the command
must send to keep time for its own request, the command sends its own request: a repeated stop is harmless, a lost
safe-state path is not.  The latch, the background retry (SAFE-040, a new attempt sends the stop again) and the
receipts stay as they were; the receipt lists the commands that shared a request (``x-vendor``).  A direct driver's
``@estop`` method and its ``safe_state=True`` actions are still all called: the runtime cannot see which native calls
a method makes (found, not fixed).
"""

from __future__ import annotations

import threading
import time
import unittest

from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.driver import Action, Driver, Field, RosDriver, action, close_server, estop
from tests.driver.support import serve

LAND = "x-cap.test.land.v1"
DISARM = "x-cap.test.disarm.v1"
MOVE = "x-cap.test.move.v1"
SAFE = "x-cap.test.halt.v1"
LAND_SERVICE = {"service": "/uav1/land", "type": "std_srvs/srv/Trigger", "success": {"path": "success", "equals": True}}
LAND_ACTION = {"action": "/uav1/action/landing", "type": "hector_uav_msgs/action/Landing", "profile": "ros2-native",
               "success": {"path": "success", "equals": True}}
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


def _wait(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)
    return predicate()


class _Uav:
    """A ROS graph stand-in: counts service calls and action goals per name and answers ``answer``.

    With ``delay`` the answer comes that many seconds after the request (from a timer thread).  ``script`` overrides
    the next requests in order: ``{"values": ...}`` another answer, ``{"result": False}`` a failed service call,
    ``{"silent": True}`` no answer, each with an optional ``delay``.  ``times`` records when each request arrived.
    """

    def __init__(self, delay: float = 0.0) -> None:
        self.calls: dict[str, int] = {}
        self.times: list[float] = []
        self.answer = {"success": True}
        self.delay = delay
        self.script: list[dict] = []
        self.lock = threading.Lock()
        self.transport: RecordingRosTransport | None = None

    def count(self, name: str) -> int:
        with self.lock:
            return self.calls.get(name, 0)

    def handler(self, message):
        op = message.get("op")
        if op not in ("call_service", "send_action_goal"):
            return None
        name = message["service"] if op == "call_service" else message["action"]
        with self.lock:
            self.calls[name] = self.calls.get(name, 0) + 1
            self.times.append(time.monotonic())
            step = self.script.pop(0) if self.script else {}
        if step.get("silent"):
            return None
        values = dict(step.get("values", self.answer))
        result = step.get("result", True)
        if op == "call_service":
            reply = {"op": "service_response", "id": message["id"], "service": name, "result": result,
                     "values": values}
        else:
            reply = {"op": "action_result", "action": name, "id": message["id"], "status": 4, "result": result,
                     "values": values}
        delay = step.get("delay", self.delay)
        if not delay:
            return reply
        transport = self.transport
        threading.Timer(delay, lambda: transport.feed(reply)).start()
        return None


def _ros_driver(uav: _Uav, *, estop_spec, safe_spec=None, safe_state_binding=None, extra_commands=None,
                body=None, name="Uav"):
    transport = RecordingRosTransport(uav.handler)
    uav.transport = transport
    commands = {MOVE: {"topic": "/uav1/cmd_vel", "type": "geometry_msgs/msg/Twist",
                       "args": {"linear.x": {"from": "input.x"}}}}
    actions = {MOVE: Action(name="move", input={"x": Field("number", unit="m/s", description="forward speed")})}
    if safe_spec is not None:
        commands[LAND] = dict(safe_spec)
        actions[LAND] = Action(name="land", safe_state=True, output={})
    for capability_id, (spec, output) in (extra_commands or {}).items():
        commands[capability_id] = dict(spec)
        actions[capability_id] = Action(name=capability_id.split(".")[-2], safe_state=True, output=output)
    safety = {"estop": dict(estop_spec)}
    if safe_state_binding is not None:
        safety["safe_state"] = dict(safe_state_binding)
    attributes = {"device_id": "uav-stop-once", "device_kind": "instrument", "risk": "R0",
                  "backends": {"fake": lambda: transport}, "commands": commands, "actions": actions,
                  "safety_bindings": safety}
    attributes.update(body or {})
    cls = type(name, (RosDriver,), attributes)
    return cls(backend="fake"), transport


def _failed(stop, capability_id):
    return [item for item in (stop.get("error") or {}).get("details", {}).get("failed_actions") or []
            if item.get("capability_id") == capability_id]


class RosStopOnceTests(unittest.TestCase):
    def serve(self, driver):
        server, client = serve(driver)
        self.addCleanup(close_server, server)
        return client

    def test_a_service_bound_as_estop_and_safe_state_action_is_called_once_per_estop(self):
        uav = _Uav()
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=LAND_SERVICE)
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertTrue(stop["output"]["safe_state_achieved"], stop)
        self.assertEqual(uav.count("/uav1/land"), 1)
        self.assertEqual(stop["x-vendor"]["shared_stop_requests"], [{"capability_id": LAND, "same_request_as": "native"}])
        # The latch holds: an effectful command is refused and sends nothing.
        refused = client.command(MOVE, {"x": 0.5})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        # Every e-stop sends the stop once more (it is a new e-stop), never twice.
        client.reset()
        again = client.estop()
        self.assertEqual(again["status"], "completed", again)
        self.assertEqual(uav.count("/uav1/land"), 2)

    def test_an_action_goal_bound_twice_is_sent_once_per_estop(self):
        uav = _Uav()
        driver, _transport = _ros_driver(uav, estop_spec=LAND_ACTION, safe_spec=LAND_ACTION)
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(uav.count("/uav1/action/landing"), 1)
        self.assertEqual(stop["x-vendor"]["shared_stop_requests"], [{"capability_id": LAND, "same_request_as": "native"}])

    def test_identical_estop_and_safe_state_bindings_are_one_request(self):
        uav = _Uav()
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_state_binding=LAND_SERVICE)
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(uav.count("/uav1/land"), 1)
        self.assertTrue(driver.inner.safety_status()["safe_state"]["achieved"])

    def test_a_different_request_is_still_sent(self):
        uav = _Uav()
        disarm = {"service": "/uav1/disarm", "type": "std_srvs/srv/Trigger", "success": {"path": "success", "equals": True}}
        other_land = {**LAND_SERVICE, "request": {"hover_first": True}}
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, extra_commands={
            DISARM: (disarm, {}), "x-cap.test.land_hover.v1": (other_land, {})})
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(uav.count("/uav1/disarm"), 1)
        self.assertEqual(uav.count("/uav1/land"), 2)  # the native LAND and the one with another request
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {})

    def test_a_different_success_predicate_is_a_different_request(self):
        # Each binding's acceptance is part of the request: a command that accepts another answer sends its own.
        uav = _Uav()
        uav.answer = {"success": True, "landed": True}
        stricter = {**LAND_SERVICE, "success": {"path": "landed", "equals": True}}
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=stricter)
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(uav.count("/uav1/land"), 2)
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {})

    def test_a_command_with_another_timeout_sends_its_own_request_even_after_a_success(self):
        # The timeout is part of the request's identity (S9-04): another wait is another request, so the command
        # sends its own even though the native stop was confirmed.
        uav = _Uav()
        driver, _transport = _ros_driver(uav, estop_spec={**LAND_SERVICE, "timeout_ms": 200},
                                         safe_spec={**LAND_SERVICE, "timeout_ms": 5000})
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(uav.count("/uav1/land"), 2)
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {})

    def test_a_command_with_a_longer_timeout_sends_its_own_request(self):
        # S9-04: the native stop gives up after 200 ms, the command may wait 5 s. It must not take the native
        # stop's timeout failure: it sends its own request and waits within its own budget.
        uav = _Uav(delay=0.5)
        native = {**LAND_SERVICE, "timeout_ms": 200}
        patient = {**LAND_SERVICE, "timeout_ms": 5000}
        driver, _transport = _ros_driver(uav, estop_spec=native, safe_spec=patient)
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "failed", stop)
        self.assertEqual(stop["error"]["details"]["reason"], "native_failed")
        self.assertEqual(uav.count("/uav1/land"), 2)
        self.assertEqual(_failed(stop, LAND), [])  # the command itself was confirmed
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {})

    def test_the_safe_state_action_still_checks_its_own_output_contract(self):
        uav = _Uav()
        uav.answer = {"success": True, "status": "landing"}
        safe = {**LAND_SERVICE, "result": {"map": {"status": "output.status"}}}
        transport = RecordingRosTransport(uav.handler)
        cls = type("UavContract", (RosDriver,), {
            "device_id": "uav-contract", "device_kind": "instrument", "risk": "R0",
            "backends": {"fake": lambda: transport}, "commands": {LAND: safe},
            "actions": {LAND: Action(name="land", safe_state=True, output={
                "status": Field("object", properties={"landed": Field("boolean")})})},
            "safety_bindings": {"estop": dict(LAND_SERVICE)},
        })
        driver = cls(backend="fake")
        client = self.serve(driver)
        stop = client.estop()
        # The shared answer does not satisfy the action's output contract: the e-stop is not confirmed, the latch
        # holds, and the request was still sent once.
        self.assertEqual(stop["status"], "failed", stop)
        self.assertFalse(stop["output"]["safe_state_achieved"])
        self.assertEqual(stop["error"]["mhs_code"], UNREACHED)
        self.assertEqual(uav.count("/uav1/land"), 1)
        self.assertEqual([item["error"].get("mhs_code") for item in _failed(stop, LAND)],
                         ["MHS.CAPABILITY.OUTPUT_INVALID"])

    def _stop_after_a_bad_native_land(self, step, *, spec=LAND_SERVICE, name="Uav"):
        # The native LAND meets ``step``; every later request is answered with success.
        uav = _Uav()
        uav.script = [step]
        driver, _transport = _ros_driver(uav, estop_spec=spec, safe_spec=spec, name=name)
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "failed", stop)
        details = stop["error"]["details"]
        self.assertEqual(details["reason"], "native_failed")
        self.assertTrue(details["retrying"])
        # The command did not take the native request's outcome: it sent its own request once more, which was
        # confirmed, and nothing was shared.
        self.assertEqual(uav.count("/uav1/land"), 2)
        self.assertEqual(_failed(stop, LAND), [])
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {})
        return uav, client, stop

    def test_a_failed_identical_request_is_sent_again_by_the_command(self):
        uav, client, stop = self._stop_after_a_bad_native_land({"result": False})
        # The native stop failed, so the attempt is not confirmed; the background retry (SAFE-040) is a new
        # attempt: its native LAND succeeds and the command shares it (one LAND in that attempt).
        state = client.server._estop_state[client.device_id]
        self.assertTrue(_wait(lambda: state.get("confirmed") is True, timeout=6.0))
        self.assertEqual(uav.count("/uav1/land"), 3)
        confirmations = [item for item in client.server.export_evidence()["receipts"]
                         if (item.get("output") or {}).get("confirms") == stop["command_id"]]
        self.assertEqual(len(confirmations), 1)
        self.assertEqual(confirmations[0]["x-vendor"]["shared_stop_requests"],
                         [{"capability_id": LAND, "same_request_as": "native"}])

    def test_a_timed_out_identical_request_is_sent_again_by_the_command(self):
        # The native LAND is never answered and gives up after its 200 ms timeout.
        self._stop_after_a_bad_native_land({"silent": True}, spec={**LAND_SERVICE, "timeout_ms": 200},
                                           name="DeafUav")

    def test_an_unconfirmed_identical_request_is_sent_again_by_the_command(self):
        # The native LAND is answered, but its success predicate does not hold.
        self._stop_after_a_bad_native_land({"values": {"success": False}}, name="RefusingUav")

    def test_an_action_waits_for_the_identical_request_still_in_flight(self):
        # The native stop answers after the e-stop budget (400 ms): the safe-state actions start meanwhile (CORE-074),
        # each with a budget of its own, and the identical one waits for that answer (up to half its budget) instead
        # of sending a second LAND beside it.
        uav = _Uav(delay=0.45)
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=LAND_SERVICE,
                                         body={"estop_latency_ms": 400}, name="SlowUav")
        client = self.serve(driver)
        stop = client.estop()
        # The receipt answers at the budget, before the stop: the latch holds and the attempt goes on.
        self.assertEqual(stop["status"], "failed", stop)
        self.assertEqual(stop["error"]["details"]["reason"], "timeout")
        state = client.server._estop_state[client.device_id]
        self.assertTrue(_wait(lambda: state.get("confirmed") is True, timeout=6.0))
        self.assertEqual(uav.count("/uav1/land"), 1)
        confirmation = [item for item in client.server.export_evidence()["receipts"]
                        if (item.get("output") or {}).get("confirms") == stop["command_id"]]
        self.assertEqual(confirmation[0]["x-vendor"]["shared_stop_requests"],
                         [{"capability_id": LAND, "same_request_as": "native"}])

    def test_an_identical_request_still_unanswered_is_sent_again_within_the_budget(self):
        # The native LAND is answered only after a second. The command waits for it while it can still give its own
        # request time (half its 400 ms budget), then sends its own LAND, which is confirmed at once.
        uav = _Uav()
        uav.script = [{"delay": 1.0}]
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=LAND_SERVICE,
                                         body={"estop_latency_ms": 400}, name="LateUav")
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "failed", stop)
        self.assertEqual(stop["error"]["details"]["reason"], "timeout")
        state = client.server._estop_state[client.device_id]
        self.assertTrue(_wait(lambda: state.get("confirmed") is True, timeout=6.0))
        self.assertEqual(uav.count("/uav1/land"), 2)
        with uav.lock:
            first, second = uav.times[:2]
        # Sent after the wait (the actions start at 400 ms and wait 200 ms), and while the native LAND was still
        # unanswered (it is answered at 1 s): in this attempt, not by a retry.
        self.assertGreaterEqual(second - first, 0.5)
        self.assertLess(second - first, 0.95)
        confirmation = [item for item in client.server.export_evidence()["receipts"]
                        if (item.get("output") or {}).get("confirms") == stop["command_id"]]
        self.assertEqual(len(confirmation), 1)
        self.assertNotIn("shared_stop_requests", confirmation[0].get("x-vendor") or {})

    def test_the_wait_spends_the_command_budget(self):
        # The command's own LAND is sent after the wait (at about 600 ms) with what is left of its 400 ms budget; it
        # is answered only after that budget, so the command fails, and the background retry (a new attempt, whose
        # native LAND succeeds and is shared) confirms the stop.
        uav = _Uav()
        uav.script = [{"delay": 1.0}, {"delay": 0.35}]
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=LAND_SERVICE,
                                         body={"estop_latency_ms": 400}, name="SlowerUav")
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["error"]["details"]["reason"], "timeout")
        state = client.server._estop_state[client.device_id]
        self.assertTrue(_wait(lambda: state.get("confirmed") is True, timeout=8.0))
        self.assertEqual(uav.count("/uav1/land"), 3)
        confirmation = [item for item in client.server.export_evidence()["receipts"]
                        if (item.get("output") or {}).get("confirms") == stop["command_id"]]
        self.assertEqual(confirmation[0]["x-vendor"]["shared_stop_requests"],
                         [{"capability_id": LAND, "same_request_as": "native"}])

    def test_native_work_after_an_identical_request_makes_a_fresh_stop_due(self):
        # S9-05 / BL-03: _shared_stop (bridge/ros.py) reuses a confirmed identical request only while
        # flight.stamp still equals the command's stamp. An interrupted goal's terminal is native work
        # after the native LAND was recorded, so the safe-state action must send LAND again and must
        # not report shared_stop_requests. The goal is planted on the bridge; no command thread owns it,
        # so the server's cancel path does not call safe_state on its own.
        from mhs.bridge.ros_actions import PendingAction

        uav = _Uav()
        driver, transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=LAND_SERVICE,
                                        body={"estop_latency_ms": 4000}, name="InterruptedUav")
        client = self.serve(driver)
        bridge = driver.inner
        bridge._start_reader()
        self.assertTrue(bridge._reader_entered.wait(2), "ROS reader did not start")
        goal = PendingAction(ident="mhs-action-interrupted", name="/uav1/action/go",
                             action_type="test_msgs/action/Go", profile="ros2-native", sent=True)
        with bridge._condition:
            bridge._actions[goal.ident] = goal
            before = bridge._native_activity
        rose = {"ok": False}
        original = transport.handler

        def feeding(message):
            if (not rose["ok"] and message.get("op") == "call_service" and message.get("service") == "/uav1/land"):
                transport.feed({"op": "action_result", "action": "/uav1/action/go", "id": goal.ident,
                                "status": 5, "result": True, "values": {}})
                deadline = time.monotonic() + 1.5
                while time.monotonic() < deadline:
                    with bridge._condition:
                        if bridge._native_activity != before:
                            rose["ok"] = True
                            break
                    time.sleep(0.005)
            return original(message)

        transport.handler = feeding
        stop = client.estop()
        self.assertTrue(rose["ok"], "the goal terminal did not invalidate the stamp before the native LAND returned")
        self.assertEqual(goal.response["status"], 5)
        self.assertIsNone(goal.error)
        self.assertEqual(bridge._native_activity, before + 1)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertTrue(stop["output"]["safe_state_achieved"], stop)
        self.assertEqual(uav.count("/uav1/land"), 2)
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {})

    def test_an_explicit_call_of_the_safe_state_action_still_sends(self):
        uav = _Uav()
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=LAND_SERVICE)
        client = self.serve(driver)
        client.estop()
        self.assertEqual(uav.count("/uav1/land"), 1)
        receipt = client.command(LAND, {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(uav.count("/uav1/land"), 2)

    def test_a_package_that_overrides_the_call_path_gets_no_report_and_no_sharing(self):
        # Only the SDK's own call path receives the report list: a package that wraps call() (or make_bridge) is
        # served as before (the stop goes out twice) and cannot write into the receipt.
        def call(self, capability_id, args=None, ctx=None):
            report = getattr(ctx, "extra", {}).get("estop_shared") if ctx is not None else None
            if isinstance(report, list):
                report.append({"same_request_as": "native"})
            return RosDriver.call(self, capability_id, args, ctx)

        uav = _Uav()
        driver, _transport = _ros_driver(uav, estop_spec=LAND_SERVICE, safe_spec=LAND_SERVICE,
                                         body={"call": call}, name="WrappedUav")
        client = self.serve(driver)
        stop = client.estop()
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(uav.count("/uav1/land"), 2)
        self.assertNotIn("shared_stop_requests", stop.get("x-vendor") or {})


class SharedReportTests(unittest.TestCase):
    def test_the_route_check_never_imports_on_the_estop_path(self):
        # An import on the e-stop worker can outlast the stop's budget (the reference conveyor's e-stop failed that
        # way): without the ROS modules loaded, nothing can be a ROS route and nothing is imported.
        import sys
        from unittest import mock
        from mhs.server import _sdk_ros_route

        with mock.patch.dict(sys.modules):
            for name in ("mhs.bridge.ros", "mhs.driver.families"):
                sys.modules.pop(name, None)
            self.assertFalse(_sdk_ros_route(object()))
            self.assertNotIn("mhs.bridge.ros", sys.modules)
            self.assertNotIn("mhs.driver.families", sys.modules)

    def test_only_a_known_sender_is_recorded_and_nothing_raises(self):
        from mhs.server import _shared_stop_entry

        achieved_by = [LAND, DISARM]
        self.assertEqual(_shared_stop_entry([{"same_request_as": "native"}], LAND, achieved_by),
                         {"capability_id": LAND, "same_request_as": "native"})
        self.assertEqual(_shared_stop_entry([{"same_request_as": DISARM}], LAND, achieved_by),
                         {"capability_id": LAND, "same_request_as": DISARM})
        for report in ([], [{"same_request_as": "x-cap.test.nothing.v1"}], [{"same_request_as": 7}], [1, "native"],
                       [{"same_request_as": object()}], None, "native", [{"capability_id": LAND}]):
            with self.subTest(report=repr(report)[:40]):
                self.assertIsNone(_shared_stop_entry(report, LAND, achieved_by))


class _Motor:
    def __init__(self, **_options):
        self.halts = 0

    def halt(self):
        self.halts += 1


class DirectDriverTests(unittest.TestCase):
    def test_a_direct_driver_safe_state_action_is_still_called_after_its_estop(self):
        # Found, not fixed: the runtime cannot see which native calls a method makes, so an @estop method and a
        # safe_state=True action that reach one native method both run (the fake sees it twice per e-stop). A
        # driver gets no report list and cannot claim a shared request in the receipt.
        def stop(self):
            self.native.halt()

        def halt_motion(self):
            report = (self.ctx.extra or {}).get("estop_shared") if self.ctx is not None else None
            if isinstance(report, list):
                report.append({"same_request_as": "native"})
            self.native.halt()

        cls = type("TwiceMotor", (Driver,), {
            "device_id": "twice-motor", "device_kind": "instrument", "risk": "R1", "mode": "simulated",
            "fidelity": {"engine": "test fake", "fidelity_level": "F0",
                         "determinism": {"kind": "seeded", "seed_control": "none"}, "timestep_ms": 0,
                         "realtime_factor": 0, "reset": "full", "snapshot_restore": False, "gaps": ["test only"]},
            "backends": {"fake": _Motor}, "stop": estop(stop),
            "halt_motion": action(name=SAFE, safe_state=True, output={})(halt_motion),
        })
        driver = cls(backend="fake")
        server, client = serve(driver)
        self.addCleanup(close_server, server)
        stop_receipt = client.estop()
        self.assertEqual(stop_receipt["status"], "completed", stop_receipt)
        self.assertEqual(driver.native.halts, 2)
        self.assertNotIn("shared_stop_requests", stop_receipt.get("x-vendor") or {})


if __name__ == "__main__":
    unittest.main()
