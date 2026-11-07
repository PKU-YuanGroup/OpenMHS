"""Arrival freshness (no producer stamp) and the ROS 1 stamp proof (BL-17).

Arrival is ROS 2 only, from a cited volatile publisher: the first sample is discarded, a later sample closer than
``min_interval_ms`` restarts the count, and ``min_span_ms`` is arrival time. A malformed field ends the attempt
even inside that interval. A transient-local history is refused. On ROS 1 a producer stamp is not a freshness
proof: the bridge has no proven clock offset, so every stamp sample is discarded and does not refresh a counted
sample. A stamp one second ahead, a ROS simulation clock, a delayed latch, and a fixed lead are the same refusal.
A queue flag is not that proof. These window tests pass explicit times. The bridge cases use stamps from before
the request and stamps from a producer clock ahead of the bridge.
"""

from __future__ import annotations

import copy
import math
import threading
import time
import unittest

from mhs.bridge import ros_sensed
from mhs.driver import DriverDefinitionError, Limit
from mhs.driver.behaviour import SensedFilter
from mhs.bridge.ros_transport import RecordingRosTransport
from tests.bridges.test_ros_sensed_stop import (NS, POSE, STATE, SensedServeMixin, Uav, fixture_dir, sensed_stop,
                                                uav_class)
from tests.driver.support import Client

_LAND = "/uav/land"


def _arrival_raw(**changes) -> dict:
    raw = {"ros_version": 2, "description": "arrival test", "max_gap_ms": 400, "confirm_within_ms": 800,
           "consecutive": 3, "min_span_ms": 40,
           "sources": {"twist": {"topic": "/ucat/state", "type": "gazebo_msgs/msg/EntityState",
                                 "freshness": "arrival", "min_interval_ms": 20,
                                 "history": {"durability": "volatile"}}},
           "predicate": [{"source": "twist", "path": "twist.linear.x", "name": "still", "abs_max": 0.01}]}
    raw.update(changes)
    return raw


class ArrivalCompileTests(unittest.TestCase):
    def test_arrival_accepts_a_headerless_volatile_source_and_refuses_the_rest(self):
        profile = ros_sensed.compile_profile(_arrival_raw())
        source = profile.sources["twist"]
        self.assertEqual((source.freshness, source.stamp_path, source.min_interval_ms, source.skip),
                         ("arrival", "", 20, 1))
        headerless = _arrival_raw()
        headerless["sources"]["twist"]["type"] = "std_msgs/msg/Float64MultiArray"
        ros_sensed.compile_profile(headerless)
        transient = _arrival_raw()
        transient["sources"]["twist"]["history"] = {"durability": "transient_local", "depth": 4}
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "volatile"):
            ros_sensed.compile_profile(transient)
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "ROS 2 only"):
            ros_sensed.compile_profile(_arrival_raw(ros_version=1))
        stamped = _arrival_raw()
        stamped["sources"]["twist"]["stamp_path"] = "header.stamp"
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "no stamp_path"):
            ros_sensed.compile_profile(stamped)
        missing = _arrival_raw()
        del missing["sources"]["twist"]["min_interval_ms"]
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "min_interval_ms"):
            ros_sensed.compile_profile(missing)
        plain = {"ros_version": 2, "description": "stamp", "max_gap_ms": 400, "confirm_within_ms": 800,
                 "consecutive": 3, "min_span_ms": 0,
                 "sources": {"pose": {"topic": POSE, "type": "std_msgs/msg/Float64MultiArray",
                                      "history": {"durability": "volatile"}}},
                 "predicate": [{"source": "pose", "path": "data.0", "name": "v", "abs_max": 1.0}]}
        with self.assertRaisesRegex(ros_sensed.SensedConfigError, "no producer stamp"):
            ros_sensed.compile_profile(plain)

    def test_a_driver_refuses_arrival_without_a_cited_volatile_history(self):
        stop = sensed_stop()
        stop["sources"] = {"twist": {"topic": "/ucat/state", "type": "gazebo_msgs/msg/EntityState",
                                     "freshness": "arrival", "min_interval_ms": 20,
                                     "history": {"durability": "transient_local", "depth": 2, "ref": "README.md:1"},
                                     "fill_refs": {"twist.linear.x": "README.md:1"}}}
        stop["predicate"] = [{"source": "twist", "path": "twist.linear.x", "name": "still", "unit": "m/s",
                              "abs_max": Limit.operator_required("test")}]
        with self.assertRaises(DriverDefinitionError) as caught:
            uav_class("ArrivalBad", stop=stop).driver_model()
        self.assertIn("cited volatile", str(caught.exception))


class ArrivalWindowTests(unittest.TestCase):
    def window(self, **changes):
        profile = ros_sensed.compile_profile(_arrival_raw(**changes))
        return ros_sensed.SourceWindow(profile.sources["twist"], profile.terms_of("twist"), profile, 0.0)

    @staticmethod
    def msg(x: float = 0.0):
        return {"twist": {"linear": {"x": x, "y": 0.0, "z": 0.0}}}

    def test_the_first_sample_does_not_count_and_a_burst_restarts(self):
        window = self.window()
        window.add(self.msg(0.0), 0.10)             # discarded, even though it already holds
        self.assertEqual((window.seen, len(window.counted)), (0, 0))
        window.add(self.msg(0.0), 0.11)             # 10 ms < 20 ms: burst, not counted
        self.assertEqual((window.last_reset, len(window.counted), window.seen), ("burst", 0, 1))
        self.assertFalse(window.confirmed(0.11))
        for index, at in enumerate((0.14, 0.17, 0.20)):
            window.add(self.msg(0.0), at)
        self.assertEqual(len(window.counted), 3)
        self.assertTrue(window.confirmed(0.20))
        self.assertEqual(ros_sensed.unconfirmed_reason({"twist": self.window()}, 1.0), "sensed_missing")

    def test_a_missing_or_non_finite_field_fails_closed(self):
        window = self.window()
        window.add(self.msg(0.0), 0.0)
        window.add({"twist": {"linear": {}}}, 0.05)
        self.assertIn("missing", window.invalid or "")
        other = self.window()
        other.add(self.msg(0.0), 0.0)
        other.add({"twist": {"linear": {"x": float("nan")}}}, 0.05)
        self.assertIn("finite", other.invalid or "")
        self.assertFalse(other.confirmed(0.05))

    def test_min_span_uses_arrival_time(self):
        window = self.window(min_span_ms=100)
        window.add(self.msg(), 0.0)
        for at in (0.03, 0.06, 0.09):       # span 60 ms < 100 ms
            window.add(self.msg(), at)
        self.assertEqual(len(window.counted), 3)
        self.assertFalse(window.confirmed(0.09))
        window.add(self.msg(), 0.20)        # span from 0.06 to 0.20 is 140 ms; the window keeps the last 3
        self.assertTrue(window.confirmed(0.20))

    def test_a_malformed_field_inside_the_burst_interval_ends_the_attempt(self):
        # The burst return used to run before validation, so a null inside min_interval_ms left invalid unset
        # and three later valid samples confirmed (CORE-088).
        for body, text in (({"twist": {"linear": {"x": None}}}, "finite"),
                           ({"twist": {"linear": {}}}, "missing"),
                           ({"twist": {"linear": {"x": True}}}, "finite"),
                           ({"twist": {"linear": {"x": float("nan")}}}, "finite")):
            window = self.window()
            window.add(self.msg(0.0), 0.10)          # the discarded prefix is not validated
            window.add(body, 0.11)                   # 10 ms < 20 ms, and the field is unusable
            self.assertIn(text, window.invalid or "", body)
            for at in (0.14, 0.17, 0.20):
                window.add(self.msg(0.0), at)
            self.assertFalse(window.confirmed(0.20))


class LatchClusterTests(unittest.TestCase):
    def window(self, fresh_after_ns: int = 10 * NS):
        profile = ros_sensed.compile_profile({
            "ros_version": 1, "description": "ros1", "max_gap_ms": 500, "confirm_within_ms": 1500,
            "consecutive": 3, "min_span_ms": 100,
            "sources": {"pose": {"topic": POSE, "type": "geometry_msgs/PoseStamped"}},
            "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed", "range": {"max": 0.1}}]})
        return ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0.0,
                                       fresh_after_ns=fresh_after_ns)

    @staticmethod
    def msg(t: int, z: float = 0.0):
        return {"header": {"stamp": {"secs": t // NS, "nsecs": t % NS}}, "pose": {"position": {"z": z}}}

    def test_stamps_at_or_before_subscribe_are_discarded_even_when_spaced(self):
        window = self.window()
        for index in range(4):                  # four publishers, landed, spaced, stamps still before subscribe
            window.add(self.msg((index + 1) * NS), 0.01 + 0.03 * index, continuation=index > 0)
        self.assertEqual((window.seen, len(window.counted), window.discarded, window.last_stamp), (0, 0, 4, None))
        window.add(self.msg(4 * NS), 0.20)      # a later stamp is still not a freshness proof
        self.assertEqual((window.seen, window.discarded, window.last_reset, window.last_arrival), (0, 5, None, None))
        self.assertFalse(window.confirmed(0.20))
        repeated = self.window(fresh_after_ns=0)
        repeated.add(self.msg(5 * NS), 0.05)
        repeated.add(self.msg(5 * NS), 0.10)    # equal stamps are discarded before the duplicate rule
        self.assertEqual((len(repeated.counted), repeated.last_reset, repeated.last_stamp), (0, None, None))
        fresh = self.window()
        for index in range(4):
            fresh.add(self.msg((index + 1) * NS), 0.01)
        for index in range(3):
            fresh.add(self.msg((11 + index) * NS), 0.05 + 0.05 * index)
        self.assertEqual((fresh.seen, len(fresh.counted), fresh.replay_discarded), (0, 0, 7))
        self.assertFalse(fresh.confirmed(0.20))
        self.assertIsNone(fresh.last_arrival)

    def test_a_post_subscribe_burst_does_not_count_without_a_clock_proof(self):
        window = self.window(fresh_after_ns=1 * NS)
        window.add(self.msg(1 * NS), 0.01, continuation=True)
        window.add(self.msg(2 * NS), 0.04, continuation=False)
        window.add(self.msg(3 * NS), 0.04, continuation=True)
        window.add(self.msg(4 * NS), 0.04, continuation=True)
        self.assertEqual((window.seen, window.replay_discarded), (0, 4))
        self.assertFalse(window.confirmed(0.05))


class _OldStamps(Uav):
    """ROS 1 stamps on the placeholder 100 s clock, which is before any bridge subscribe clock."""

    def __init__(self) -> None:
        super().__init__(ros_version=1)

    def stamp(self) -> dict:
        if not self.frozen:
            self.clock += NS // 10
        clock = self.clock
        return {"secs": clock // NS, "nsecs": clock % NS}


class _DelayedLatches(_OldStamps):
    """Four safe samples cached before the request, then replayed 30 ms apart. The vehicle stays airborne."""

    def __init__(self) -> None:
        super().__init__()
        self.gap_s = 0.03
        self.burst = 4
        self.ignore_land = True
        self.z, self.armed = 0.0, False
        self.cached = {topic: [self.sample(topic, "cached") for _ in range(4)] for topic in (STATE, POSE)}
        self.z, self.armed = 2.0, True

    def handler(self, message: dict):
        if message.get("op") == "subscribe" and message.get("topic") in getattr(self, "cached", {}):
            items = self.cached[message["topic"]]
            for item in items:
                item["id"] = message["id"]
            transport = self.transport

            def feed(frames=items):
                for frame in frames:
                    time.sleep(self.gap_s)
                    try:
                        transport.feed(frame)
                    except ConnectionError:
                        return

            threading.Thread(target=feed, daemon=True).start()
            return None
        return super().handler(message)


class _NoBuffered(RecordingRosTransport):
    """A transport whose ``buffered`` attribute is absent."""

    def __getattribute__(self, name: str):
        if name == "buffered":
            raise AttributeError(name)
        return super().__getattribute__(name)


class LatchClusterBridgeTests(SensedServeMixin, unittest.TestCase):
    def test_a_synchronous_burst_of_pre_subscribe_stamps_never_confirms(self):
        uav = _OldStamps()
        uav.z, uav.armed = 0.0, False
        _driver, _server, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "failed", receipt)
        sensed = (receipt.get("error") or {}).get("details", {}).get("sensed") or {}
        self.assertEqual(sensed.get("reason"), "sensed_missing", receipt)
        for name in ("state", "pose"):
            self.assertEqual(sensed["sources"][name]["seen"], 0, receipt)

    def test_spaced_live_samples_after_subscribe_do_not_confirm(self):
        uav = Uav(ros_version=1)
        uav.gap_s = 0.02
        _driver, _server, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "failed", receipt)
        sensed = (receipt.get("error") or {}).get("details", {}).get("sensed") or {}
        self.assertEqual(sensed.get("reason"), "sensed_missing", receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])

    def test_delayed_pre_request_latches_do_not_confirm_while_the_vehicle_stays_armed(self):
        uav = _DelayedLatches()
        _driver, _server, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertEqual(receipt["status"], "failed", receipt)
        sensed = (receipt.get("error") or {}).get("details", {}).get("sensed") or {}
        self.assertEqual(sensed.get("reason"), "sensed_missing", receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertEqual((uav.z, uav.armed), (2.0, True))

    def test_old_stamps_are_discarded_without_a_buffer_probe(self):
        for transport_cls in (_NoBuffered,):
            uav = _DelayedLatches()
            transport = transport_cls(uav.handler)
            _driver, _server, client, _ = self.serve(uav, transport=transport)
            receipt = client.estop()
            self.assertEqual(receipt["status"], "failed", receipt)
            sensed = (receipt.get("error") or {}).get("details", {}).get("sensed") or {}
            self.assertEqual(sensed.get("reason"), "sensed_missing", receipt)
            self.assertEqual((uav.z, uav.armed), (2.0, True))

        class AlwaysEmpty(RecordingRosTransport):
            def buffered(self) -> bool:
                return False

        uav = _DelayedLatches()
        _driver, _server, client, _ = self.serve(uav, transport=AlwaysEmpty(uav.handler))
        receipt = client.estop()
        self.assertEqual((receipt["status"], (receipt.get("error") or {}).get("details", {}).get("sensed", {}).get("reason")),
                         ("failed", "sensed_missing"), receipt)
        self.assertEqual((uav.z, uav.armed), (2.0, True))


class ArrivalBridgeTests(SensedServeMixin, unittest.TestCase):
    def arrival_stop(self) -> dict:
        return {"request": [{"service": _LAND, "type": "std_srvs/srv/Trigger",
                             "success": {"path": "success", "equals": True}, "timeout_ms": 500,
                             "source_ref": "README.md:1"}],
                "sources": {"pose": {"topic": POSE, "type": "geometry_msgs/msg/Pose",
                                     "freshness": "arrival", "min_interval_ms": 15,
                                     "history": {"durability": "volatile", "ref": "README.md:1"},
                                     "fill_refs": {"pose.position.z": "README.md:2"}}},
                "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed_z", "unit": "m",
                               "range": {"max": Limit.operator_required("test band")}}],
                "consecutive": 3, "min_span_ms": 20, "max_gap_ms": 400, "confirm_within_ms": 800,
                "description": "landed, sensed from arrival times of an unstamped pose"}

    def test_spaced_arrival_samples_confirm_and_a_burst_does_not(self):
        stop = self.arrival_stop()
        cls = uav_class("ArrivalUav", stop=stop)
        uav = Uav()
        uav.gap_s = 0.03
        uav.z = 0.0
        _driver, _server, client, _ = self.serve(uav, cls=cls, thresholds={"landed_z.max": 0.1})
        stop_receipt = client.estop()
        self.assertEqual(stop_receipt["status"], "completed", stop_receipt)
        report = stop_receipt["x-vendor"]["sensed_confirmation"]["sources"]["pose"]
        self.assertEqual(report["samples"], 3)
        self.assertNotIn("first_stamp", report)

        burst = Uav()
        burst.z = 0.0
        _driver, _server, client, _ = self.serve(burst, cls=cls, thresholds={"landed_z.max": 0.1})
        receipt = client.estop()
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual((receipt.get("error") or {}).get("details", {}).get("sensed", {}).get("reason"),
                         "sensed_stale", receipt)

    def test_the_frozen_filter_does_not_let_an_arrival_source_confirm(self):
        stop = self.arrival_stop()
        cls = uav_class("ArrivalFrozen", stop=stop)
        uav = Uav()
        uav.gap_s = 0.03
        uav.z = 0.0
        transport = RecordingRosTransport(uav.handler)
        uav.transport = transport
        sources = {POSE: ("", 2, "pose.position.z", "arrival")}
        wrapped = SensedFilter(transport, "frozen", sources)
        driver = cls(backend="fake", native=wrapped, base_dir=fixture_dir(self, {"landed_z.max": 0.1}))
        from mhs.driver import build_server, close_server
        server = build_server(driver)
        self.addCleanup(close_server, server)
        receipt = Client(server).estop()
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])


class FrozenContradictionTests(unittest.TestCase):
    def test_boolean_and_other_equals_values_are_rewritten(self):
        from mhs.driver import check as gate_check

        self.assertIs(gate_check._frozen_contradiction({"equals": True}), False)
        self.assertIs(gate_check._frozen_contradiction({"equals": False}), True)
        self.assertEqual(gate_check._frozen_contradiction({"equals": "hold"}), "hold ")
        self.assertEqual(gate_check._frozen_contradiction({"equals": ""}), "frozen")
        self.assertEqual(gate_check._frozen_contradiction({"equals": 3}), 4)
        self.assertEqual(gate_check._frozen_contradiction({"equals": 1.5}), math.nextafter(1.5, math.inf))
        self.assertEqual(gate_check._frozen_contradiction({"equals": float("nan")}), 0.0)
        self.assertIs(gate_check._frozen_contradiction({"path": "data", "abs_max": 0.1}), True)

        def one(value, poison):
            transport = RecordingRosTransport(
                lambda message, sent=value: {"op": "publish", "topic": "/flag", "msg": {"data": sent}}
                if message.get("op") == "subscribe" else None)
            wrapped = SensedFilter(transport, "frozen", {"/flag": ("", 2, "data", "arrival", poison)})
            wrapped.send({"op": "subscribe", "topic": "/flag", "id": "1"})
            return wrapped.recv(timeout_s=0.05)["msg"]["data"]

        self.assertIs(one(True, False), False)
        self.assertEqual(one("hold", "hold "), "hold ")
        self.assertEqual(one(3, 4), 4)

        raw = {"ros_version": 2, "description": "bool", "max_gap_ms": 400, "confirm_within_ms": 800,
               "consecutive": 3, "min_span_ms": 20,
               "sources": {"flag": {"topic": "/flag", "type": "std_msgs/msg/Bool", "freshness": "arrival",
                                    "min_interval_ms": 10, "history": {"durability": "volatile"}}},
               "predicate": [{"source": "flag", "path": "data", "equals": True}]}
        profile = ros_sensed.compile_profile(raw)

        def confirmed(value) -> bool:
            window = ros_sensed.SourceWindow(profile.sources["flag"], profile.terms_of("flag"), profile, 0.0)
            window.add({"data": value}, 0.0)
            for index in range(3):
                window.add({"data": value}, 0.02 + 0.02 * index)
            return window.confirmed(0.08)

        self.assertTrue(confirmed(True))
        self.assertFalse(confirmed(False))

        text = ros_sensed.compile_profile({
            "ros_version": 2, "description": "text", "max_gap_ms": 400, "confirm_within_ms": 800,
            "consecutive": 3, "min_span_ms": 20,
            "sources": {"flag": {"topic": "/flag", "type": "std_msgs/msg/String", "freshness": "arrival",
                                 "min_interval_ms": 10, "history": {"durability": "volatile"}}},
            "predicate": [{"source": "flag", "path": "data", "equals": "hold"}]})
        window = ros_sensed.SourceWindow(text.sources["flag"], text.terms_of("flag"), text, 0.0)
        window.add({"data": "hold "}, 0.0)
        for index in range(3):
            window.add({"data": "hold "}, 0.02 + 0.02 * index)
        self.assertFalse(window.confirmed(0.08))
        self.assertEqual(window.last_reset, "term")

    def test_g6_frozen_must_contradict_a_large_finite_float(self):
        from mhs.driver import check as gate_check

        poison = gate_check._frozen_contradiction({"equals": 1e20})
        self.assertNotEqual(poison, 1e20)
        self.assertIsInstance(poison, float)
        profile = ros_sensed.compile_profile({
            "ros_version": 2, "description": "float filter", "max_gap_ms": 400,
            "confirm_within_ms": 800, "consecutive": 3, "min_span_ms": 20,
            "sources": {"flag": {"topic": "/flag", "type": "std_msgs/msg/Float64", "freshness": "arrival",
                                 "min_interval_ms": 10, "history": {"durability": "volatile"}}},
            "predicate": [{"source": "flag", "path": "data", "equals": 1e20}],
        })
        window = ros_sensed.SourceWindow(profile.sources["flag"], profile.terms_of("flag"), profile, 0)
        target = RecordingRosTransport(lambda _: [
            {"op": "publish", "topic": "/flag", "msg": {"data": 1e20}} for _ in range(4)
        ])
        self.addCleanup(target.close)
        wrapped = SensedFilter(target, "frozen", {
            "/flag": ("", 2, "data", "arrival", poison)
        })
        wrapped.send({"op": "subscribe", "topic": "/flag", "id": "1"})
        for index in range(4):
            window.add(wrapped.recv(timeout_s=0.05)["msg"], 0.02 * index)
        self.assertFalse(window.confirmed(0.08))


class RecordingBufferTests(unittest.TestCase):
    def test_a_handler_list_is_queued_before_the_reader_can_see_a_gap(self):
        seen = []

        def handler(message):
            if message.get("op") == "subscribe":
                return [{"op": "publish", "topic": "/t", "msg": {"n": index}} for index in range(4)]
            return None

        transport = RecordingRosTransport(handler)
        transport.send({"op": "subscribe", "topic": "/t", "id": "1"})
        first = transport.recv(timeout_s=0.05)
        self.assertTrue(transport.buffered())
        seen.append(first["msg"]["n"])
        while transport.buffered() or True:
            try:
                seen.append(transport.recv(timeout_s=0.01)["msg"]["n"])
            except TimeoutError:
                break
        self.assertEqual(seen, [0, 1, 2, 3])


def _pose(stamp: int, z: float) -> dict:
    return {"header": {"stamp": {"secs": stamp // NS, "nsecs": stamp % NS}},
            "pose": {"position": {"z": z}}}


class _FutureCached(Uav):
    """Pre-request samples from a producer five seconds ahead. The vehicle never lands."""

    def __init__(self):
        super().__init__(ros_version=1)
        self.ignore_land = True
        self.z, self.armed = 0.0, False
        self.cache_ns = time.time_ns() + 5 * NS
        self.cache = {topic: [self.sample(topic, "cached") for _ in range(4)] for topic in (STATE, POSE)}
        self.z, self.armed = 2.0, True

    def stamp(self):
        self.cache_ns += NS // 10
        return {"secs": self.cache_ns // NS, "nsecs": self.cache_ns % NS}

    def handler(self, message):
        if message.get("op") == "subscribe" and message.get("topic") in self.cache:
            frames = self.cache[message["topic"]]
            for item in frames:
                item["id"] = message["id"]

            def feed():
                for frame in frames:
                    time.sleep(0.03)
                    try:
                        self.transport.feed(frame)
                    except ConnectionError:
                        return

            threading.Thread(target=feed, daemon=True).start()
            return None
        return super().handler(message)


class _OldReplayAfterFresh(Uav):
    """The state source expires, then an old replay must not keep it fresh for the pose source."""

    def __init__(self):
        super().__init__(ros_version=1)
        self.ignore_land = True
        self.z, self.armed = 0.0, True
        self.old_frame = self.sample(STATE, "cached-before-request")
        self.armed = False

    def stamp(self):
        stamp = time.time_ns()
        return {"secs": stamp // NS, "nsecs": stamp % NS}

    def handler(self, message):
        if message.get("op") == "subscribe" and message.get("topic") in (STATE, POSE):
            topic, ident = message["topic"], message["id"]
            start = time.monotonic()

            def feed():
                schedule = ((0.03, 0.085, 0.14, 0.55, 0.58, 0.61, 0.64, 0.67, 0.70, 0.73) if topic == STATE
                            else (0.60, 0.655, 0.71))
                for at in schedule:
                    time.sleep(max(0.0, start + at - time.monotonic()))
                    old = topic == STATE and at >= 0.55
                    if old:
                        self.armed = True
                    frame = copy.deepcopy(self.old_frame) if old else self.sample(topic, ident)
                    frame["id"] = ident
                    try:
                        self.transport.feed(frame)
                    except ConnectionError:
                        return

            threading.Thread(target=feed, daemon=True).start()
            return None
        return super().handler(message)


class _SimClock(Uav):
    """ROS simulation time parked five seconds ahead of the bridge, replayed without buffered()."""

    def __init__(self):
        super().__init__(ros_version=1)
        self.ignore_land = True
        self.z, self.armed = 0.0, True
        self.sim_ns = time.time_ns() + 5 * NS

    def stamp(self):
        self.sim_ns += NS // 10
        return {"secs": self.sim_ns // NS, "nsecs": self.sim_ns % NS}

    def handler(self, message):
        if message.get("op") != "subscribe":
            return super().handler(message)
        frames = [self.sample(message["topic"], message["id"]) for _ in range(4)]
        transport = self.transport

        def feed():
            for frame in frames:
                time.sleep(0.03)
                try:
                    transport.feed(frame)
                except ConnectionError:
                    return

        threading.Thread(target=feed, daemon=True).start()
        return None


class RoundTwoFreshnessTests(SensedServeMixin, unittest.TestCase):
    def test_pre_request_latches_from_an_ahead_clock_must_not_confirm(self):
        uav = _FutureCached()
        _, _, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertEqual((uav.z, uav.armed), (2.0, True))
        self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)

    def test_a_discarded_old_replay_must_not_refresh_the_counted_window(self):
        profile = ros_sensed.compile_profile({
            "ros_version": 1, "description": "fresh sample timeout", "max_gap_ms": 400,
            "confirm_within_ms": 1500, "consecutive": 3, "min_span_ms": 100,
            "sources": {"pose": {"topic": "/pose", "type": "geometry_msgs/PoseStamped"}},
            "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed", "range": {"max": 0.1}}],
        })
        window = ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0,
                                         fresh_after_ns=10 * NS)
        for index in range(3):
            window.add(_pose(11 * NS + index * NS // 10, 0), 0.05 * index)
        self.assertFalse(window.confirmed(0.7))
        window.add(_pose(9 * NS, 2), 0.7)
        self.assertFalse(window.confirmed(0.7), window.report())
        self.assertIsNone(window.last_arrival)
        self.assertEqual(window.seen, 0)

    def test_a_replay_between_counted_samples_does_not_hide_the_gap(self):
        profile = ros_sensed.compile_profile({
            "ros_version": 1, "description": "gap across a replay", "max_gap_ms": 400,
            "confirm_within_ms": 1500, "consecutive": 3, "min_span_ms": 100,
            "sources": {"pose": {"topic": "/pose", "type": "geometry_msgs/PoseStamped"}},
            "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed", "range": {"max": 0.1}}],
        })
        window = ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0,
                                         fresh_after_ns=10 * NS)
        window.add(_pose(11 * NS, 0), 0.0)
        window.add(_pose(11 * NS + NS // 10, 0), 0.05)
        window.add(_pose(9 * NS, 2), 0.10)  # a stamp between others is still not counted
        window.add(_pose(11 * NS + 2 * NS // 10, 0), 0.70)
        self.assertIsNone(window.last_reset)
        self.assertIsNone(window.last_arrival)
        self.assertEqual(window.seen, 0)
        self.assertFalse(window.confirmed(0.70))

    def test_old_replays_must_not_combine_an_expired_source_with_a_later_source(self):
        uav = _OldReplayAfterFresh()
        _, _, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertTrue(uav.armed)
        self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)

    def test_simulation_time_ahead_of_the_bridge_does_not_confirm(self):
        uav = _SimClock()
        _, _, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertTrue(uav.armed)
        self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)

    def test_a_wall_clock_stamp_inside_or_outside_a_fixed_lead_does_not_count(self):
        profile = ros_sensed.compile_profile({
            "ros_version": 1, "description": "no fixed lead", "max_gap_ms": 400,
            "confirm_within_ms": 1500, "consecutive": 3, "min_span_ms": 100,
            "sources": {"pose": {"topic": "/pose", "type": "geometry_msgs/PoseStamped"}},
            "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed", "range": {"max": 0.1}}],
        })
        fresh = time.time_ns()
        window = ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0,
                                         fresh_after_ns=fresh)
        window.add(_pose(fresh + 5 * NS, 0), 0.0)
        window.add(_pose(fresh + 100_000_000, 0), 0.05)
        window.add(_pose(fresh + NS, 0), 0.10)
        self.assertEqual(window.seen, 0)
        self.assertEqual(window.replay_discarded, 3)
        self.assertIsNone(window.last_stamp)
        self.assertIsNone(window.last_arrival)

    def test_a_one_second_ahead_cache_does_not_confirm(self):
        uav = _FutureCached()
        for frames in uav.cache.values():
            for frame in frames:
                frame["msg"]["header"]["stamp"]["secs"] -= 4
        _, _, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertEqual((uav.z, uav.armed), (2.0, True))
        self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)
        sensed = (receipt.get("error") or {}).get("details", {}).get("sensed") or {}
        self.assertEqual(sensed.get("reason"), "sensed_missing", receipt)

    def test_simulation_time_one_second_ahead_does_not_confirm(self):
        uav = _SimClock()
        uav.sim_ns -= 4 * NS
        _, _, client, _ = self.serve(uav)
        receipt = client.estop()
        self.assertTrue(uav.armed)
        self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)
        sensed = (receipt.get("error") or {}).get("details", {}).get("sensed") or {}
        self.assertEqual(sensed.get("reason"), "sensed_missing", receipt)

    def test_a_paused_simulation_clock_is_not_after_subscribe(self):
        profile = ros_sensed.compile_profile({
            "ros_version": 1, "description": "paused sim time", "max_gap_ms": 400,
            "confirm_within_ms": 1500, "consecutive": 3, "min_span_ms": 100,
            "sources": {"pose": {"topic": "/pose", "type": "geometry_msgs/PoseStamped"}},
            "predicate": [{"source": "pose", "path": "pose.position.z", "name": "landed", "range": {"max": 0.1}}],
        })
        window = ros_sensed.SourceWindow(profile.sources["pose"], profile.terms_of("pose"), profile, 0,
                                         fresh_after_ns=time.time_ns())
        window.add(_pose(100 * NS, 0), 0.0)
        self.assertEqual(window.seen, 0)
        self.assertEqual(window.replay_discarded, 1)


if __name__ == "__main__":
    unittest.main()
