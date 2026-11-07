"""Stop retries survive evidence failure; close ends background publication."""
from __future__ import annotations

import threading
import unittest

from mhs import canonical

from ._support import NativeStopBridge, open_session, stub_server, wait_until


class RetrySucceeds(NativeStopBridge):
    def estop(self, reason="", ctx=None):
        self._record("estop")
        if self.count("estop") == 1:
            raise RuntimeError("controlled first stop failure")
        return {"estop": "engaged"}


class ConfirmationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.uncaught = []
        previous = threading.excepthook

        def capture(args):
            if args.thread.name.startswith("mhs-estop-retry-"):
                self.uncaught.append(args.exc_value)
            else:
                previous(args)

        threading.excepthook = capture
        self.addCleanup(setattr, threading, "excepthook", previous)

    def make(self, bridge=None):
        server, rpc, device, bridge = stub_server(bridge or RetrySucceeds())
        self.addCleanup(server.close)
        return server, rpc, device, bridge, open_session(rpc, device)

    def test_failed_confirmation_keeps_command_unconfirmed_until_receipt_recovers(self):
        server, rpc, device, bridge, session = self.make()
        failed_attempt = threading.Event()
        allow_write = threading.Event()
        self.addCleanup(allow_write.set)
        append = server._evidence.append_receipt
        confirm = server._confirm_estop

        def reject(record):
            if (record.get("output") or {}).get("confirms") and not allow_write.is_set():
                raise OSError("controlled evidence failure before append")
            return append(record)

        def observe(*args, **kwargs):
            try:
                return confirm(*args, **kwargs)
            finally:
                if not allow_write.is_set():
                    failed_attempt.set()

        server._evidence.append_receipt = reject
        server._confirm_estop = observe
        with self.assertLogs("mhs.server", level="ERROR"):
            first = rpc("mhs.safety.estop", session_id=session, reason="recording test", deadline_ms=1000)
            self.assertEqual(first["status"], "failed", first)
            self.assertTrue(failed_attempt.wait(2))
            state = server._estop_state[device.device_id]
            self.assertFalse(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["confirmed"])
            self.assertIn(first["command_id"], state["unconfirmed"])
            self.assertTrue(state["supervisor"].is_alive())
            self.assertEqual([r for r in server.export_evidence()["receipts"]
                              if (r.get("output") or {}).get("confirms") == first["command_id"]], [])
            allow_write.set()
            self.assertTrue(wait_until(lambda: state.get("confirmed") is True, timeout=3))
        self.assertEqual(self.uncaught, [])
        confirmations = [r for r in server.export_evidence()["receipts"]
                         if (r.get("output") or {}).get("confirms") == first["command_id"]]
        self.assertEqual(len(confirmations), 1)
        self.assertNotIn(first["command_id"], state["unconfirmed"])
        self.assertTrue(server._latched[device.device_id])
        self.assertGreaterEqual(bridge.count("estop"), 3)

    def test_close_during_confirmation_write_never_commits_or_escapes_thread_error(self):
        server, rpc, device, bridge, session = self.make()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        append = server._evidence.append_receipt

        def blocked_append(record):
            if (record.get("output") or {}).get("confirms"):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("controlled confirmation release timeout")
            return append(record)

        server._evidence.append_receipt = blocked_append
        first = rpc("mhs.safety.estop", session_id=session, reason="close while recording", deadline_ms=1000)
        self.assertEqual(first["status"], "failed", first)
        self.assertTrue(entered.wait(2))
        supervisor = server._estop_state[device.device_id]["supervisor"]
        server.close()
        release.set()
        supervisor.join(1)
        state = server._estop_state[device.device_id]
        self.assertFalse(supervisor.is_alive())
        self.assertFalse(state["confirmed"])
        self.assertIn(first["command_id"], state["unconfirmed"])
        self.assertIsNone(state["supervisor"])
        self.assertEqual(self.uncaught, [])

    def test_close_ends_retry_without_dispatching_a_new_attempt(self):
        class AlwaysFails(NativeStopBridge):
            def estop(self, reason="", ctx=None):
                self._record("estop")
                raise RuntimeError("controlled failed stop")

        server, rpc, device, bridge, session = self.make(AlwaysFails())
        first = rpc("mhs.safety.estop", session_id=session, reason="close before retry", deadline_ms=1000)
        self.assertEqual(first["status"], "failed", first)
        supervisor = server._estop_state[device.device_id]["supervisor"]
        server.close()
        supervisor.join(1)
        self.assertFalse(supervisor.is_alive())
        self.assertIsNone(server._estop_state[device.device_id]["supervisor"])
        self.assertEqual(bridge.count("estop"), 1)
        self.assertEqual(self.uncaught, [])

    def test_close_while_native_stop_is_pending_does_not_claim_late_confirmation(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        class Pending(NativeStopBridge):
            def estop(self, reason="", ctx=None):
                self._record("estop")
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("controlled native release timeout")
                return {"estop": "engaged"}

        server, rpc, device, bridge, session = self.make(Pending())
        first = rpc("mhs.safety.estop", session_id=session, reason="pending stop", deadline_ms=1000)
        self.assertEqual(first["status"], "failed", first)
        self.assertTrue(entered.is_set())
        state = server._estop_state[device.device_id]
        supervisor, attempt = state["supervisor"], state["attempt"]
        server.close()
        release.set()
        self.assertTrue(attempt.done.wait(1))
        supervisor.join(1)
        self.assertFalse(supervisor.is_alive())
        self.assertFalse(state["confirmed"])
        self.assertIn(first["command_id"], state["unconfirmed"])
        self.assertIsNone(state["supervisor"])
        self.assertEqual(self.uncaught, [])

    def test_failed_initial_receipt_does_not_lose_native_retry(self):
        server, rpc, device, bridge, session = self.make()
        append = server._evidence.append_receipt
        command_id = canonical.ulid()

        def reject_initial(record):
            if record.get("command_id") == command_id:
                raise OSError("controlled initial receipt failure")
            return append(record)

        server._evidence.append_receipt = reject_initial
        response = rpc.raw("mhs.safety.estop", session_id=session,
                           command_id=command_id, reason="initial recording failed", deadline_ms=1000)
        self.assertEqual(response["error"]["data"]["mhs_code"], "MHS.INTERNAL.ERROR")
        state = server._estop_state[device.device_id]
        self.assertTrue(wait_until(lambda: state.get("confirmed") is True, timeout=3))
        self.assertGreaterEqual(bridge.count("estop"), 2)
        self.assertNotIn(command_id, state["unconfirmed"])
        receipts = server.export_evidence()["receipts"]
        self.assertFalse(any(r["command_id"] == command_id for r in receipts))
        confirmations = [r for r in receipts if (r.get("output") or {}).get("confirms") == command_id]
        self.assertEqual(len(confirmations), 1)
        self.assertTrue(server._latched[device.device_id])
        self.assertEqual(self.uncaught, [])

    def test_native_success_diagnostic_does_not_claim_receipt_durability(self):
        server, rpc, device, bridge, session = self.make(NativeStopBridge())
        append = server._evidence.append_receipt

        def reject_initial(record):
            if record.get("capability_id") == "cap.internal.safety_estop.v1":
                raise OSError("controlled initial receipt failure")
            return append(record)

        server._evidence.append_receipt = reject_initial
        response = rpc.raw("mhs.safety.estop", session_id=session, reason="native succeeded", deadline_ms=1000)
        self.assertEqual(response["error"]["data"]["mhs_code"], "MHS.INTERNAL.ERROR")
        self.assertTrue(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["confirmed"])
        self.assertIsNone(server._estop_state[device.device_id].get("supervisor"))
        self.assertEqual(bridge.count("estop"), 1)
        self.assertFalse(any(r["capability_id"] == "cap.internal.safety_estop.v1"
                             for r in server.export_evidence()["receipts"]))

    def test_close_before_initial_stop_answers_does_not_publish_confirmation(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        class Pending(NativeStopBridge):
            def estop(self, reason="", ctx=None):
                self._record("estop")
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("controlled release timeout")
                return {"estop": "engaged"}

        server, rpc, device, bridge, session = self.make(Pending())
        device.safety.estop["latency_ms"] = 1000
        holder = {}
        thread = threading.Thread(target=lambda: holder.update(response=rpc.raw(
            "mhs.safety.estop", session_id=session, reason="close during initial stop", deadline_ms=2000)))
        thread.start()
        self.assertTrue(entered.wait(1))
        server.close()
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(holder["response"]["error"]["data"]["mhs_code"], "MHS.TRANSPORT.CLOSED")
        self.assertFalse(server._estop_state[device.device_id]["confirmed"])
        self.assertTrue(server._latched[device.device_id])
        self.assertEqual(bridge.count("estop"), 1)
        self.assertEqual(self.uncaught, [])

    def _close_during_reset_reassertion(self, *, close_before_reassert, reassert_fails=False):
        class Controlled(NativeStopBridge):
            def __init__(self):
                super().__init__()
                self.reset_enter = threading.Event()
                self.reset_release = threading.Event()
                self.reassert_enter = threading.Event()
                self.reassert_release = threading.Event()

            def estop(self, reason="", ctx=None):
                self._record("estop")
                if self.count("estop") == 3:
                    self.reassert_enter.set()
                    if not self.reassert_release.wait(3):
                        raise RuntimeError("controlled reassert release timeout")
                    if reassert_fails:
                        raise RuntimeError("controlled reassert failure")
                return {"estop": "engaged"}

            def reset(self, ctx=None):
                self._record("reset")
                self.reset_enter.set()
                if not self.reset_release.wait(3):
                    raise RuntimeError("controlled reset release timeout")
                return {"reset": True}

        bridge = Controlled()
        self.addCleanup(bridge.reset_release.set)
        self.addCleanup(bridge.reassert_release.set)
        server, rpc, device, bridge, session = self.make(bridge)
        holder = {}
        first = rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
        self.assertEqual(first["status"], "completed")
        thread = threading.Thread(target=lambda: holder.update(response=rpc.raw(
            "mhs.safety.reset", session_id=session, deadline_ms=2000)))
        thread.start()
        self.assertTrue(bridge.reset_enter.wait(1))
        second = rpc("mhs.safety.estop", session_id=session, reason="during reset", deadline_ms=1000)
        self.assertEqual(second["status"], "completed")
        if close_before_reassert:
            server.close()
            self.assertEqual(bridge.count("estop"), 2)
        bridge.reset_release.set()
        self.assertTrue(bridge.reassert_enter.wait(1))
        with server._lock:
            state = server._estop_state[device.device_id]
            self.assertFalse(state["confirmed"])
        server.close()
        bridge.reassert_release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(holder["response"]["error"]["data"]["mhs_code"], "MHS.TRANSPORT.CLOSED")
        self.assertFalse(state["confirmed"])
        self.assertTrue(server._latched[device.device_id])
        self.assertEqual(bridge.count("estop"), 3)
        self.assertIsNone(state.get("supervisor"))
        self.assertEqual(self.uncaught, [])

    def test_close_during_reset_reassertion_prevents_late_confirmation(self):
        self._close_during_reset_reassertion(close_before_reassert=False)

    def test_admitted_reset_keeps_final_protective_stop_after_close(self):
        self._close_during_reset_reassertion(close_before_reassert=True)

    def test_failed_final_protective_stop_after_close_does_not_restart_supervisor(self):
        self._close_during_reset_reassertion(close_before_reassert=True, reassert_fails=True)


if __name__ == "__main__":
    unittest.main()
