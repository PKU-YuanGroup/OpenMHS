"""E1 (companion preflight 2, 2026-11-05): a stall read-back confirms a paused simulator by a value that no longer
advances, for a stack that has no service reporting its paused flag (ROS 2 gazebo_ros: ``get_model_list`` stamps its
answer with the world's sim time, which advances only while the world steps).

``safety_bindings.safe_state`` (a fixed service call) may add ``stall: {path, samples, interval_ms, unchanged: true}``:
the read-back is called ``samples`` times, each call at least ``interval_ms`` after the previous answer, every answer
must satisfy the success predicate, and the value at ``path`` must not change. Anything else leaves the e-stop
unconfirmed (``MHS.SAFETY.SAFE_STATE_UNREACHED``) with the latch held.
"""
from __future__ import annotations

import copy
import threading
import time
import unittest

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.ros import RosBridge, RecordingRosTransport, _stall_sample_ok
from mhs.errors import MHSError

PAUSE = {"service": "/pause_physics", "type": "std_srvs/srv/Empty", "request": {},
         "success": {"path": "$", "equals": {}}, "timeout_ms": 400}
READBACK = {"service": "/get_model_list", "type": "gazebo_msgs/srv/GetModelList", "request": {},
            "success": {"path": "success", "equals": True}, "timeout_ms": 300,
            "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 150, "unchanged": True}}


class World:
    """A ROS-free stand-in of a gazebo_ros world: sim time advances on every answer unless paused."""

    def __init__(self) -> None:
        self.paused = False
        self.sim_ns = 5_000_000
        self.calls: list[tuple[str, float]] = []
        self.answers: list[float] = []
        self.success = True
        self.drop_stamp = False
        self.advance_after_pause = False
        self.lock = threading.Lock()

    def handler(self, message):
        if message.get("op") != "call_service":
            return None
        service = message["service"]
        with self.lock:
            self.calls.append((service, time.monotonic()))
            if service == "/pause_physics":
                self.paused = True
                values = {}
            elif service == "/unpause_physics":
                self.paused = False
                values = {}
            else:
                if not self.paused or self.advance_after_pause:
                    self.sim_ns += 1_000_000
                stamp = {"sec": self.sim_ns // 1_000_000_000, "nanosec": self.sim_ns % 1_000_000_000}
                values = {"header": {"stamp": stamp, "frame_id": ""}, "model_names": ["ground_plane", "go1"],
                          "success": self.success}
                if self.drop_stamp:
                    values["header"].pop("stamp")
            self.answers.append(time.monotonic())
        return {"op": "service_response", "service": service, "result": True, "values": values}


def bridge(world: World, *, readback=None, estop=None) -> RosBridge:
    config = {"safety_bindings": {"estop": copy.deepcopy(estop or PAUSE),
                                  "safe_state": copy.deepcopy(readback or READBACK)}}
    return RosBridge(config, transport=RecordingRosTransport(handler=world.handler))


class StallReadBackTests(unittest.TestCase):
    def make(self, **options):
        world = World()
        instance = bridge(world, **options)
        self.addCleanup(instance.close)
        return world, instance

    def test_a_paused_world_confirms_the_e_stop(self) -> None:
        world, instance = self.make()
        result = instance.estop("test")
        self.assertTrue(result["safe_state_achieved"], result)
        services = [service for service, _when in world.calls]
        self.assertEqual(services, ["/pause_physics", "/get_model_list", "/get_model_list"])
        first_answer, second_sent = world.answers[1], world.calls[2][1]
        self.assertGreaterEqual(second_sent - first_answer, 0.15 - 0.005)
        self.assertTrue(instance.safety_status()["safe_state"]["achieved"])

    def test_a_world_that_still_advances_is_not_confirmed(self) -> None:
        world, instance = self.make()
        world.advance_after_pause = True
        with self.assertRaises(MHSError) as raised:
            instance.estop("test")
        self.assertEqual(raised.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(instance.safety_status()["safe_state"]["achieved"])

    def test_a_change_on_a_later_sample_and_a_failed_or_stampless_answer(self) -> None:
        stall = dict(READBACK["stall"], samples=3, interval_ms=100)
        world, instance = self.make(readback=dict(READBACK, stall=stall))
        original = world.handler

        def third_moves(message):
            response = original(message)
            if message.get("service") == "/get_model_list" and sum(
                    1 for service, _ in world.calls if service == "/get_model_list") == 3:
                response["values"]["header"]["stamp"]["nanosec"] += 1
            return response

        instance._transport.handler = third_moves
        with self.assertRaises(MHSError):
            instance.estop("test")
        self.assertEqual(sum(1 for service, _ in world.calls if service == "/get_model_list"), 3)
        for switch in ("success", "drop_stamp"):
            with self.subTest(switch=switch):
                world, instance = self.make()
                setattr(world, switch, False if switch == "success" else True)
                with self.assertRaises(MHSError) as raised:
                    instance.estop("test")
                self.assertEqual(raised.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_safe_state_alone_repeats_the_stall_check(self) -> None:
        world, instance = self.make()
        instance.estop("test")
        world.calls.clear()
        self.assertEqual(instance.safe_state(), {"achieved": True, "native": "/pause_physics"})
        self.assertEqual([service for service, _ in world.calls], ["/get_model_list", "/get_model_list"])
        world.paused = False  # another client unpaused the world
        with self.assertRaises(MHSError):
            instance.safe_state()

    def test_a_budget_that_cannot_hold_the_next_sample_fails(self) -> None:
        world, instance = self.make()
        context = BridgeContext(deadline_ms=300)  # the interval (150) and the read-back timeout (300) do not fit
        with self.assertRaises(MHSError) as raised:
            instance.estop("test", context)
        self.assertEqual(raised.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(sum(1 for service, _ in world.calls if service == "/get_model_list"), 1)

    def test_cancellation_between_samples_stops_the_wait(self) -> None:
        world, instance = self.make(readback=dict(READBACK, stall=dict(READBACK["stall"], interval_ms=2000)))
        event = threading.Event()
        context = BridgeContext(cancel_event=event)
        threading.Timer(0.1, event.set).start()
        started = time.monotonic()
        with self.assertRaises((MHSError, signals.Cancelled)):
            instance.estop("test", context)
        self.assertLess(time.monotonic() - started, 1.5)

    def test_one_answer_never_stands_for_a_stall_read_back(self) -> None:
        _world, instance = self.make()
        plain = dict(READBACK)
        plain.pop("stall")
        other = RosBridge({"safety_bindings": {"estop": PAUSE, "safe_state": plain}},
                          transport=RecordingRosTransport(handler=World().handler))
        self.addCleanup(other.close)
        self.assertNotEqual(instance._stop_request_identity(instance._safety["safe_state"]),
                            other._stop_request_identity(other._safety["safe_state"]))
        self.assertEqual(other._safety["safe_state"]["stall"], None)


class StallSampleKindTests(unittest.TestCase):
    """Integrator edit (Claude Sonnet safety F1 of p3-companion-2): only a finite number or a ROS time confirms.

    Every value below is the same on every sample, so the comparison alone would confirm the stop; each kind that
    cannot show a running clock must leave the e-stop unconfirmed with the latch held.
    """

    BAD = (("null", None), ("empty string", ""), ("string", "12.5"), ("empty list", []), ("list", [1, 2]),
           ("true", True), ("false", False), ("empty object", {}), ("other object", {"t": 1}),
           ("half a stamp", {"sec": 1}), ("stamp with an extra member", {"sec": 1, "nanosec": 0, "frame": 0}),
           ("mixed stamp keys", {"sec": 1, "nsecs": 0}), ("string seconds", {"sec": "1", "nanosec": 0}),
           ("float seconds", {"sec": 1.0, "nanosec": 0}), ("boolean seconds", {"sec": True, "nanosec": 0}),
           ("null nanoseconds", {"sec": 1, "nanosec": None}), ("nanoseconds overflow", {"sec": 1, "nanosec": 10 ** 9}),
           ("negative nanoseconds", {"secs": 1, "nsecs": -1}), ("infinity", float("inf")), ("nan", float("nan")))
    GOOD = (("integer", 7), ("float", 2.5), ("zero", 0), ("ROS 2 stamp", {"sec": 5, "nanosec": 1000}),
            ("ROS 1 stamp", {"secs": 5, "nsecs": 1000}))

    def run_with(self, value):
        world = World()
        original = world.handler

        def fixed(message):
            response = original(message)
            if message.get("service") == "/get_model_list":
                response["values"]["header"]["stamp"] = copy.deepcopy(value)
            return response

        instance = RosBridge({"safety_bindings": {"estop": copy.deepcopy(PAUSE),
                                                  "safe_state": copy.deepcopy(READBACK)}},
                             transport=RecordingRosTransport(handler=fixed))
        self.addCleanup(instance.close)
        return world, instance

    def test_values_that_cannot_show_a_clock_fail_closed(self) -> None:
        for name, value in self.BAD:
            with self.subTest(value=name):
                world, instance = self.run_with(value)
                with self.assertRaises(MHSError) as raised:
                    instance.estop("test")
                self.assertEqual(raised.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")
                self.assertFalse(instance.safety_status()["safe_state"]["achieved"])
                self.assertTrue(world.paused)  # the pause itself was sent; only its confirmation is refused

    def test_numbers_and_ros_times_still_confirm(self) -> None:
        for name, value in self.GOOD:
            with self.subTest(value=name):
                _world, instance = self.run_with(value)
                result = instance.estop("test")
                self.assertTrue(result["safe_state_achieved"], result)

    def test_the_sample_rule_itself(self) -> None:
        # A non-finite number never crosses the strict JSON transport (it fails the connection), so the rule is
        # checked directly as well: it must refuse every bad kind on its own.
        for name, value in self.BAD:
            with self.subTest(value=name):
                self.assertFalse(_stall_sample_ok(value))
        for name, value in self.GOOD:
            with self.subTest(value=name):
                self.assertTrue(_stall_sample_ok(value))


class StallValidationTests(unittest.TestCase):
    def refused(self, config) -> None:
        with self.assertRaises(MHSError) as raised:
            RosBridge(config, transport=RecordingRosTransport(handler=World().handler))
        self.assertEqual(raised.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")

    def test_only_the_safe_state_read_back_takes_a_stall(self) -> None:
        stall = READBACK["stall"]
        self.refused({"safety_bindings": {"estop": dict(PAUSE, stall=stall), "safe_state": READBACK}})
        self.refused({"safety_bindings": {"estop": PAUSE, "safe_state": READBACK, "reset": dict(PAUSE, stall=stall)}})
        self.refused({"commands": {"x-cap.a.b.v1": dict(READBACK)}})

    def test_malformed_stalls_are_refused(self) -> None:
        stall = READBACK["stall"]
        for name, bad in (("samples 1", dict(stall, samples=1)), ("samples 5", dict(stall, samples=5)),
                          ("samples bool", dict(stall, samples=True)), ("interval 50", dict(stall, interval_ms=50)),
                          ("interval 3000", dict(stall, interval_ms=3000)), ("unchanged false", dict(stall, unchanged=False)),
                          ("unchanged 1", dict(stall, unchanged=1)), ("path $", dict(stall, path="$")),
                          ("extra key", dict(stall, tolerance=0)), ("missing key", {"path": "header.stamp"})):
            with self.subTest(name=name):
                self.refused({"safety_bindings": {"estop": PAUSE, "safe_state": dict(READBACK, stall=bad)}})
        no_success = dict(READBACK)
        no_success.pop("success")
        self.refused({"safety_bindings": {"estop": PAUSE, "safe_state": no_success}})


if __name__ == "__main__":
    unittest.main()
