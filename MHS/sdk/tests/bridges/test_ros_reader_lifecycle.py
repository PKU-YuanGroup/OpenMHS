"""Receiver startup/close scheduling, without ROS or a network connection.

The Thread.start seam controls both sides of native thread startup. Raising
after the real start is adversarial injection, not a stdlib behavior claim.
All native action/service owners and wire guards are the production bridge.
"""
from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.ros import RosBridge
from tests.bridges.test_ros_action_safety import (
    FrankaPeer, MOVE, READ, STOP_NAME, config,
)


class _ReaderLifecycle:
    profile: str

    def make_bridge(self):
        peer = FrankaPeer(self.profile, automatic_stop=False)
        bridge = RosBridge(config(self.profile), transport=peer.transport)
        self.addCleanup(bridge.close)
        return bridge, peer

    def worker(self, call):
        result = {}
        def run():
            try:
                result["value"] = call()
            except BaseException as exc:
                result["error"] = exc
        thread = threading.Thread(target=run, name="test-ros-owner", daemon=True)
        thread.start()
        return thread, result

    def joined(self, thread):
        thread.join(1)
        self.assertFalse(thread.is_alive(), "controlled owner did not finish")

    def close_bounded(self, bridge):
        # Run close independently so a broken unbounded-lock fix cannot hang
        # the test. The caller releases the startup barrier in its finally.
        before = time.monotonic()
        thread, result = self.worker(bridge.close)
        thread.join(0.4)
        elapsed = time.monotonic() - before
        return thread, result, elapsed

    def assert_closed(self, bridge, peer, sent_count):
        before = len(peer.transport.sent)
        bridge.close()
        bridge.close()
        with self.assertRaises(Exception):
            bridge.call(READ, {}, BridgeContext(deadline_ms=20))
        with self.assertRaises(Exception):
            bridge.call(MOVE, {}, BridgeContext(deadline_ms=20))
        self.assertEqual(len(peer.transport.sent), before)
        self.assertEqual(before, sent_count)
        self.assertFalse(peer.cancels)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        if bridge._reader is not None and bridge._reader.ident is not None:
            bridge._reader.join(1)
            self.assertFalse(bridge._reader.is_alive())

    def delayed_start_case(self, *, real_start_first=False):
        bridge, peer = self.make_bridge()
        entered, release = threading.Event(), threading.Event()
        native_start = threading.Thread.start
        starts, receives = [], []
        original_recv = peer.transport.recv
        def receive(*args, **kwargs):
            receives.append(bridge.closed)
            return original_recv(*args, **kwargs)
        peer.transport.recv = receive
        def start(thread):
            if thread.name != "mhs-ros-receiver":
                return native_start(thread)
            starts.append(thread)
            if real_start_first:
                native_start(thread)
            entered.set()
            if not release.wait(2):
                raise TimeoutError("test startup barrier was not released")
            if not real_start_first:
                native_start(thread)
        with patch.object(threading.Thread, "start", start):
            owner, result = self.worker(lambda: bridge.safe_state(BridgeContext(deadline_ms=1200)))
            try:
                self.assertTrue(entered.wait(1))
                self.assertIs(bridge._reader, starts[0], "startup ownership must be retained")
                sent_count = len(peer.transport.sent)
                closer, close_result, elapsed = self.close_bounded(bridge)
                self.assertFalse(closer.is_alive(), "close waited for a delayed startup")
                self.assertLess(elapsed, 0.5)
                self.assertNotIn("error", close_result)
            finally:
                release.set()
                self.joined(owner)
                if "closer" in locals():
                    self.joined(closer)
        self.assertIn("error", result)
        self.assertEqual(len(starts), 1)
        if not real_start_first:
            self.assertEqual(receives, [])
        self.assertNotIn(True, receives)
        self.assertEqual(len(peer.named_goals(STOP_NAME)), 0 if self.profile == "ros1-actionlib" else 1)
        self.assert_closed(bridge, peer, sent_count)

    def test_close_before_native_start_is_bounded_and_retains_owner(self):
        self.delayed_start_case()

    def test_close_after_native_start_before_start_returns_is_bounded(self):
        self.delayed_start_case(real_start_first=True)

    def test_close_before_first_start_prevents_receiver_creation(self):
        bridge, peer = self.make_bridge()
        bridge.close()
        with patch.object(threading.Thread, "start", side_effect=AssertionError("late receiver start")):
            bridge._start_reader()
        self.assertIsNone(bridge._reader)
        self.assert_closed(bridge, peer, 0)

    def concurrent_start_case(self, *, close_while_starting):
        bridge, peer = self.make_bridge()
        entered, release, second_entered = threading.Event(), threading.Event(), threading.Event()
        native_start = threading.Thread.start
        starts, receives = [], []
        original_recv = peer.transport.recv
        def receive(*args, **kwargs):
            receives.append(bridge.closed)
            return original_recv(*args, **kwargs)
        peer.transport.recv = receive
        def start(thread):
            if thread.name == "mhs-ros-receiver":
                starts.append(thread)
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("test concurrent-start barrier was not released")
            return native_start(thread)
        def another_start():
            second_entered.set()
            bridge._start_reader()
        with patch.object(threading.Thread, "start", start):
            first, first_result = self.worker(bridge._start_reader)
            try:
                self.assertTrue(entered.wait(1))
                second, second_result = self.worker(another_start)
                self.assertTrue(second_entered.wait(1))
                if close_while_starting:
                    closer, close_result, elapsed = self.close_bounded(bridge)
                    self.assertFalse(closer.is_alive())
                    self.assertNotIn("error", close_result)
                    self.assertLess(elapsed, 0.5)
            finally:
                release.set()
                self.joined(first)
                if "second" in locals():
                    self.joined(second)
                if "closer" in locals():
                    self.joined(closer)
        self.assertNotIn("error", first_result)
        self.assertNotIn("error", second_result)
        self.assertEqual(len(starts), 1)
        if close_while_starting:
            self.assertEqual(receives, [])
        bridge.close()
        self.assert_closed(bridge, peer, 0)

    def test_concurrent_starters_create_one_reader(self):
        self.concurrent_start_case(close_while_starting=False)

    def test_concurrent_starters_and_close_do_not_deadlock_or_restart(self):
        self.concurrent_start_case(close_while_starting=True)

    def start_failure_case(self, *, after_real_start, operation="safe"):
        bridge, peer = self.make_bridge()
        native_start = threading.Thread.start
        starts, receives = [], []
        received, release_receive = threading.Event(), threading.Event()
        original_recv = peer.transport.recv
        fault = RuntimeError("injected receiver startup failure")
        def receive(*args, **kwargs):
            receives.append(bridge.closed)
            received.set()
            if after_real_start and not release_receive.wait(2):
                raise TimeoutError("test receive barrier was not released")
            return original_recv(*args, **kwargs)
        peer.transport.recv = receive
        def start(thread):
            if thread.name != "mhs-ros-receiver":
                return native_start(thread)
            starts.append(thread)
            if after_real_start:
                native_start(thread)
                if not received.wait(1):
                    raise AssertionError("partial startup did not enter production receive loop")
            raise fault
        call = (lambda: bridge.safe_state(BridgeContext(deadline_ms=200))) if operation == "safe" else (
            lambda: bridge.call(READ, {}, BridgeContext(deadline_ms=200)))
        try:
            with patch.object(threading.Thread, "start", start):
                with self.assertRaises(Exception):
                    call()
                self.assertIs(bridge._reader, starts[0], "failed startup handle must remain owned")
                self.assertIs(bridge._fatal, fault)
                self.assertTrue(bridge._stop_reader.is_set())
                sent_count = len(peer.transport.sent)
                # Failure poisons the connection before another request/setup,
                # regardless of whether a native goal had already been sent.
                with self.assertRaises(Exception):
                    bridge.call(READ, {}, BridgeContext(deadline_ms=25))
                with self.assertRaises(Exception):
                    bridge.safe_state(BridgeContext(deadline_ms=25))
                bridge._start_reader()
                self.assertEqual(len(starts), 1)
                self.assertEqual(len(peer.transport.sent), sent_count)
                closer, close_result, elapsed = self.close_bounded(bridge)
                self.assertFalse(closer.is_alive())
                self.assertNotIn("error", close_result)
                self.assertLess(elapsed, 0.5)
                if after_real_start:
                    # An intentionally held recv may outlive bounded close,
                    # but the sole actual thread must remain reachable.
                    self.assertTrue(starts[0].is_alive())
        finally:
            release_receive.set()
            if starts and starts[0].ident is not None:
                starts[0].join(1)
            # Before the repair this call can raise for a never-started thread;
            # unittest retains that failure instead of suppressing it.
        self.assertEqual(len(receives), 1 if after_real_start else 0)
        self.assertNotIn(True, receives)
        self.assert_closed(bridge, peer, sent_count)

    def test_failed_start_before_native_thread_fences_safety_and_reads(self):
        self.start_failure_case(after_real_start=False)

    def test_partial_start_failure_keeps_live_reader_owned_until_exit(self):
        self.start_failure_case(after_real_start=True)

    def test_service_start_failure_has_no_reconnect_or_replay(self):
        self.start_failure_case(after_real_start=False, operation="read")

    def test_normal_service_reader_and_repeated_close_control(self):
        bridge, peer = self.make_bridge()
        self.assertEqual(bridge.call(READ, {}, BridgeContext(deadline_ms=500)), {})
        reader = bridge._reader
        self.assertIsNotNone(reader)
        self.assertTrue(reader.is_alive())
        self.assertEqual(len(peer.transport.sent), 1)
        bridge.close()
        self.assertFalse(reader.is_alive())
        self.assert_closed(bridge, peer, 1)


class Ros1ReaderLifecycleTests(_ReaderLifecycle, unittest.TestCase):
    profile = "ros1-actionlib"


class Ros2ReaderLifecycleTests(_ReaderLifecycle, unittest.TestCase):
    profile = "ros2-native"


if __name__ == "__main__":
    unittest.main()
