"""E2 (companion preflight 2, 2026-11-05): a fresh-sample topic read-back confirms a paused simulator whose paused
flag is reported only on a topic (gz-sim publishes ``WorldStatistics.paused`` on ``/world/<name>/stats``; the reply of
its WorldControl request is true for any queued request, so it confirms nothing).

``safety_bindings.safe_state`` may be ``{topic, type, operation: 'subscribe', success: {path, equals: <boolean>},
fresh: {after_request: true, discard_first: true, consecutive, within_ms, min_interval_ms}}``: after the stop request
returned, a new subscription's first sample is discarded, every later sample must arrive at least ``min_interval_ms``
after the one before it (a replayed history arrives as one burst), and ``consecutive`` samples in a row must hold the
flag within ``within_ms``. Anything else leaves the e-stop unconfirmed (``MHS.SAFETY.SAFE_STATE_UNREACHED``) with the
latch held. The world below is a ROS-free stand-in that publishes its statistics every ``period`` seconds while a
subscription is open and applies a queued pause after the next sample, as gz-sim's runner does (PublishStats at the
start of a step, the world control processed at its end).
"""
from __future__ import annotations

import copy
import threading
import time
import unittest

from mhs import signals
from mhs.bridge import ros
from mhs.bridge.base import BridgeContext
from mhs.bridge.ros import RosBridge, RecordingRosTransport
from mhs.errors import MHSError

CONTROL = {"service": "/world/w/control", "type": "ros_gz_interfaces/srv/ControlWorld",
           "request": {"world_control": {"pause": True}}, "success": {"path": "success", "equals": True},
           "timeout_ms": 400}
STATS = {"topic": "/world/w/stats", "type": "ros_gz_interfaces/msg/WorldStatistics", "operation": "subscribe",
         "success": {"path": "paused", "equals": True},
         "fresh": {"after_request": True, "discard_first": True, "consecutive": 2, "within_ms": 800,
                   "min_interval_ms": 40}}
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class World(RecordingRosTransport):
    """A gz-sim world behind ros_gz: stats every ``period`` s while subscribed; a pause applies after the next sample."""

    def __init__(self, period: float = 0.1) -> None:
        super().__init__(handler=self.handle)
        self.period = period
        self.paused = False
        self.pending: bool | None = None
        self.ignore_pause = False   # another client keeps the world running
        self.silent = False         # no stats bridge: nothing is published
        self.drop_flag = False      # a sample without the paused field
        self.string_flag = False    # a sample whose flag is not a boolean
        self.replay: list[dict] = []  # samples delivered back to back right after the next subscribe
        self.subscribed: set[str] = set()
        self.subscribes = 0
        self.unsubscribes = 0
        self.controls: list[dict] = []
        self.last = 0.0
        self.lock = threading.Lock()

    def handle(self, message):
        op = message.get("op")
        with self.lock:
            if op == "subscribe" and message.get("topic") == "/world/w/stats":
                self.subscribed.add(message["id"])
                self.subscribes += 1
                self.last = time.monotonic()  # the first live sample follows one period later
                replay, self.replay = self.replay, []
                return [{"op": "publish", "topic": "/world/w/stats", "msg": copy.deepcopy(item)} for item in replay]
            if op == "unsubscribe":
                self.subscribed.discard(message.get("id"))
                self.unsubscribes += 1
                return None
            if op == "call_service" and message.get("service") == "/world/w/control":
                self.controls.append(copy.deepcopy(message.get("args")))
                if not self.ignore_pause:
                    self.pending = message["args"]["world_control"]["pause"]
                return {"op": "service_response", "service": message["service"], "result": True,
                        "values": {"success": True}}
        return None

    def sample(self) -> dict:
        msg = {"header": {"stamp": {"sec": 0, "nanosec": 0}, "data": []}, "iterations": 7, "paused": self.paused}
        if self.drop_flag:
            msg.pop("paused")
        if self.string_flag:
            msg["paused"] = "true"
        return msg

    def recv(self, *, timeout_s=None):
        with self.lock:
            now = time.monotonic()
            if self.subscribed and not self.silent and now - self.last >= self.period:
                self.last = now
                message = {"op": "publish", "topic": "/world/w/stats", "msg": self.sample()}
                if self.pending is not None:
                    self.paused, self.pending = self.pending, None
                return message
        return super().recv(timeout_s=min(timeout_s or 0.02, 0.01))


class LateWorld(World):
    """Stats samples at the producer's period, each stamped by the bridge after the read-back's bound (integrator v4).

    The bridge's reader thread stamps every stats sample delivered after the stop request 5 s late (``LateClock``
    below), as if the samples had waited in a delayed batch; the caller's thread keeps the real clock, so the wait
    loop never sees its bound pass on an empty stream and the late batch reaches the per-sample guard.
    """

    def __init__(self) -> None:
        super().__init__()
        self.late = False
        self.reader: int | None = None

    def recv(self, *, timeout_s=None):
        self.reader = threading.get_ident()
        message = super().recv(timeout_s=timeout_s)
        if isinstance(message, dict) and message.get("op") == "publish" and self.controls:
            self.late = True
        return message


class LateClock:
    """``time`` for mhs.bridge.ros: the reader thread's clock runs 5 s ahead once the world's samples are late."""

    def __init__(self, world: LateWorld) -> None:
        self.world = world

    def __getattr__(self, name):
        return getattr(time, name)

    def monotonic(self) -> float:
        now = time.monotonic()
        if self.world.late and threading.get_ident() == self.world.reader:
            return now + 5.0
        return now


def bridge(world: World, *, readback=None, estop=None) -> RosBridge:
    config = {"safety_bindings": {"estop": copy.deepcopy(estop or CONTROL),
                                  "safe_state": copy.deepcopy(readback or STATS)}}
    return RosBridge(config, transport=world)


class TopicReadBackTests(unittest.TestCase):
    def make(self, world: World | None = None, **options):
        world = world or World()
        instance = bridge(world, **options)
        self.addCleanup(instance.close)
        return world, instance

    def unconfirmed(self, instance, *args) -> MHSError:
        with self.assertRaises(MHSError) as raised:
            instance.estop("test", *args)
        self.assertEqual(raised.exception.code, UNREACHED)
        self.assertFalse(instance.safety_status()["safe_state"]["achieved"])
        return raised.exception

    def test_a_paused_world_confirms_the_e_stop_after_the_discarded_first_sample(self) -> None:
        world, instance = self.make()
        result = instance.estop("test")
        self.assertTrue(result["safe_state_achieved"], result)
        self.assertEqual(result["performed"], ["/world/w/control", "/world/w/stats"])
        self.assertEqual(world.controls, [{"world_control": {"pause": True}}])
        self.assertTrue(instance.safety_status()["safe_state"]["achieved"])
        # The subscription was opened after the stop request and closed afterwards; nothing is left behind.
        sent = [message["op"] for message in world.sent]
        self.assertEqual(sent, ["call_service", "subscribe", "unsubscribe"])
        subscribe = world.sent[1]
        self.assertEqual((subscribe["topic"], subscribe["type"], subscribe["queue_length"]),
                         ("/world/w/stats", "ros_gz_interfaces/msg/WorldStatistics", 1))
        self.assertEqual((instance._streams, instance._topic_ids), ({}, {}))

    def test_the_first_sample_never_counts(self) -> None:
        # The first sample (still unpaused: the pause applies after it) is discarded; with the world paused before
        # the request, the first sample would hold the flag but is still not counted: three samples are needed.
        world = World()
        world.paused = True
        world, instance = self.make(world)
        started = time.monotonic()
        self.assertTrue(instance.estop("test")["safe_state_achieved"])
        self.assertGreaterEqual(time.monotonic() - started, 3 * world.period - 0.03)

    def test_a_world_that_keeps_running_is_not_confirmed(self) -> None:
        world = World()
        world.ignore_pause = True
        world, instance = self.make(world)
        started = time.monotonic()
        self.unconfirmed(instance)
        self.assertLess(time.monotonic() - started, 0.8 + 0.4)  # the bound, not the whole budget
        self.assertEqual(world.unsubscribes, 1)

    def test_silence_is_not_confirmed(self) -> None:
        world = World()
        world.silent = True
        _world, instance = self.make(world)
        self.unconfirmed(instance)

    def test_a_replayed_history_alone_never_confirms(self) -> None:
        world = World()
        world.silent = True
        world.replay = [{"paused": True, "iterations": 7}] * 6  # a transient-local history, older than the request
        _world, instance = self.make(world)
        self.unconfirmed(instance)

    def test_a_burst_restarts_the_count_and_live_samples_then_confirm(self) -> None:
        world = World()
        world.paused = True
        world.replay = [{"paused": True, "iterations": 7}] * 6
        world, instance = self.make(world)
        self.assertTrue(instance.estop("test")["safe_state_achieved"])
        # The burst counted nothing: two live samples, each at least min_interval_ms after the previous arrival, did.

    def test_a_failing_sample_restarts_the_count(self) -> None:
        world, instance = self.make()
        flags = iter([False, True, False, True, True])
        world.sample = lambda: {"paused": next(flags, True), "iterations": 7}
        started = time.monotonic()
        self.assertTrue(instance.estop("test")["safe_state_achieved"])
        # discarded, true, false (restart), true, true: five samples one period apart
        self.assertGreaterEqual(time.monotonic() - started, 5 * world.period - 0.05)

    def test_a_sample_without_a_boolean_flag_ends_the_attempt(self) -> None:
        for switch in ("drop_flag", "string_flag"):
            with self.subTest(switch=switch):
                world = World()
                world.paused = True
                setattr(world, switch, True)
                _world, instance = self.make(world)
                started = time.monotonic()
                self.unconfirmed(instance)
                self.assertLess(time.monotonic() - started, 0.5)  # at the second sample, not at the bound

    def test_the_reader_bounds_a_stream_and_remembers_a_lost_sample(self) -> None:
        world = World()
        world.silent = True
        _world, instance = self.make(world)
        stream = ros._Stream()
        with instance._condition:
            instance._streams["probe"] = stream
            instance._topic_ids["/world/w/stats"] = {"probe"}
        for index in range(ros._FRESH_CAPACITY + 6):
            world.feed({"op": "publish", "topic": "/world/w/stats", "msg": {"paused": True, "iterations": index}})
        instance._start_reader()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not world._inbound.empty():
            time.sleep(0.01)
        time.sleep(0.05)
        with instance._condition:
            self.assertTrue(stream.overflowed)
            self.assertEqual(len(stream.items), ros._FRESH_CAPACITY)
            self.assertEqual(stream.items[-1][0]["iterations"], ros._FRESH_CAPACITY + 5)  # the newest are kept
            self.assertNotIn("probe", instance._topics)  # a stream subscription never feeds a one-sample read

    def test_a_lost_sample_ends_the_attempt(self) -> None:
        world = World()
        world.paused = True
        _world, instance = self.make(world)

        class Overflowed(ros._Stream):
            def __init__(self) -> None:
                super().__init__()
                self.overflowed = True

        original = ros._Stream
        ros._Stream = Overflowed
        self.addCleanup(setattr, ros, "_Stream", original)
        started = time.monotonic()
        self.unconfirmed(instance)
        self.assertLess(time.monotonic() - started, 0.5)

    def test_safe_state_alone_repeats_the_read_back_without_a_request(self) -> None:
        world, instance = self.make()
        instance.estop("test")
        self.assertEqual(instance.safe_state(), {"achieved": True, "native": "/world/w/control"})
        self.assertEqual(len(world.controls), 1)  # no second pause request
        self.assertEqual(world.subscribes, 2)
        world.paused = False  # another client unpaused the world
        with self.assertRaises(MHSError) as raised:
            instance.safe_state()
        self.assertEqual(raised.exception.code, UNREACHED)

    def test_every_e_stop_opens_its_own_subscription(self) -> None:
        world, instance = self.make()
        instance.estop("first")
        instance.estop("second")
        self.assertEqual((world.subscribes, len(world.controls)), (2, 2))

    def test_a_failed_stop_request_runs_no_read_back(self) -> None:
        world = World()
        _world, instance = self.make(world, estop=dict(CONTROL, success={"path": "success", "equals": False}))
        self.unconfirmed(instance)
        self.assertEqual(world.subscribes, 0)

    def test_samples_that_arrived_after_the_bound_never_count(self) -> None:
        # integrator v4 (2026-11-05; Claude Sonnet safety lens F2 of p3-companion-3): confirming samples queued in the
        # stream but received after within_ms (a delayed batch) end the attempt unconfirmed, however well spaced.
        world = LateWorld()
        _world, instance = self.make(world)
        self.addCleanup(setattr, ros, "time", ros.time)
        ros.time = LateClock(world)
        error = self.unconfirmed(instance)
        self.assertIn("after its bound", str(error.__cause__ or error.__context__))
        self.assertEqual(world.controls, [{"world_control": {"pause": True}}])
        self.assertTrue(world.late)

    def test_a_short_caller_budget_bounds_the_read_back(self) -> None:
        world = World()
        _world, instance = self.make(world)
        started = time.monotonic()
        self.unconfirmed(instance, BridgeContext(deadline_ms=250))
        self.assertLess(time.monotonic() - started, 0.6)

    def test_cancellation_and_a_closed_bridge_end_the_wait(self) -> None:
        world = World()
        world.silent = True
        _world, instance = self.make(world)
        cancel = threading.Event()
        threading.Timer(0.1, cancel.set).start()
        with self.assertRaises((MHSError, signals.Cancelled)):
            instance.safe_state(BridgeContext(deadline_ms=2000, cancel_event=cancel))
        world2 = World()
        world2.silent = True
        _world2, other = self.make(world2)
        threading.Timer(0.1, other.close).start()
        started = time.monotonic()
        with self.assertRaises(Exception):
            other.safe_state()
        self.assertLess(time.monotonic() - started, 0.6)


class TopicReadBackDeclarationTests(unittest.TestCase):
    def refused(self, safety) -> str:
        with self.assertRaises(MHSError) as raised:
            RosBridge({"safety_bindings": safety}, transport=RecordingRosTransport(handler=lambda message: None))
        self.assertEqual(raised.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")
        return str(raised.exception)

    def test_malformed_read_backs_are_refused(self) -> None:
        fresh = STATS["fresh"]
        cases = {
            "fresh on the stop": {"estop": dict(CONTROL, fresh=fresh), "safe_state": STATS},
            "a missing key": {"estop": CONTROL, "safe_state": {k: v for k, v in STATS.items() if k != "type"}},
            "a service type": {"estop": CONTROL, "safe_state": dict(STATS, type="ros_gz_interfaces/srv/ControlWorld")},
            "a relative topic": {"estop": CONTROL, "safe_state": dict(STATS, topic="stats")},
            "a publication": {"estop": CONTROL, "safe_state": dict(STATS, operation="publish")},
            "a request": {"estop": CONTROL, "safe_state": dict(STATS, request={})},
            "a timeout besides the bound": {"estop": CONTROL, "safe_state": dict(STATS, timeout_ms=500)},
            "a non-boolean flag": {"estop": CONTROL, "safe_state": dict(STATS, success={"path": "paused", "equals": 1})},
            "the whole message": {"estop": CONTROL, "safe_state": dict(STATS, success={"path": "$", "equals": True})},
            "a list-element predicate": {"estop": CONTROL, "safe_state": dict(STATS, success={
                "path": "x", "where": {"name": "a"}, "field": "state", "equals": True})},
            "after_request false": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, after_request=False))},
            "discard_first false": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, discard_first=False))},
            "one sample": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, consecutive=1))},
            "six samples": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, consecutive=6))},
            "a bound too short": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, within_ms=100))},
            "a bound too long": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, within_ms=5001))},
            "no spacing": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, min_interval_ms=0))},
            "a boolean bound": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, within_ms=True))},
            "a bound that cannot hold the samples": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(
                fresh, consecutive=5, within_ms=500, min_interval_ms=100))},
            "an unknown fresh key": {"estop": CONTROL, "safe_state": dict(STATS, fresh=dict(fresh, stale_ms=10))},
        }
        for name, safety in cases.items():
            with self.subTest(name=name):
                self.refused(copy.deepcopy(safety))

    def test_a_read_or_reset_may_not_take_fresh(self) -> None:
        with self.assertRaises(MHSError):
            RosBridge({"safety_bindings": {"estop": CONTROL, "reset": dict(STATS)}},
                      transport=RecordingRosTransport(handler=lambda message: None))
        with self.assertRaises(MHSError):
            RosBridge({"reads": {"main": {"fields": {"paused": dict(STATS, path="paused")}}}},
                      transport=RecordingRosTransport(handler=lambda message: None))

    def test_a_well_formed_read_back_compiles_and_never_enters_the_stop_ledger(self) -> None:
        instance = RosBridge({"safety_bindings": {"estop": CONTROL, "safe_state": STATS}},
                             transport=RecordingRosTransport(handler=lambda message: None))
        self.addCleanup(instance.close)
        spec = instance._safety["safe_state"]
        self.assertEqual((spec["kind"], spec["operation"], spec["timeout"]), ("topic", "subscribe", 0.8))
        self.assertIsNone(RosBridge._stop_request_identity(spec))
        self.assertEqual(instance.estop_native, "/world/w/control")


if __name__ == "__main__":
    unittest.main()
