"""RE-PROTO-002: command identity is reserved before the bridge is called.

The concurrent cases use bridge gates (controlled blocking) and never patch the
idempotency store or the bridge dispatcher.
"""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _fixtures import (  # noqa: E402
    command,
    error_code,
    make_device,
    make_server,
    open_session,
    result,
    status_of,
    wait_until,
)

IDENTITY = "cap.test.identity.v1"
UNKNOWN = "cap.test.unknown.v1"


class CommandIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device, self.bridge = make_device("identity")
        self.server = make_server(self.device)
        self.device_id = self.device.device_id
        self.session = open_session(self.server, [self.device_id])

    def _count(self, cap: str = IDENTITY) -> int:
        return self.bridge.counts.get(cap, 0)

    def _command(self, cap: str, payload: dict | None = None, **kwargs):
        return command(self.server, self.session, self.device_id, cap, payload or {}, **kwargs)

    def _start(self, cap: str, command_id: str, holder: dict, payload: dict | None = None):
        def run() -> None:
            holder["response"] = self._command(cap, payload, command_id=command_id, deadline_ms=2000)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    # -- concurrent same id / same action ---------------------------------
    def test_concurrent_same_command_id_executes_bridge_once(self) -> None:
        gate = self.bridge.gate(IDENTITY)
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V8A"
        first: dict = {}
        second: dict = {}
        first_thread = self._start(IDENTITY, command_id, first)
        self.assertTrue(wait_until(lambda: self._count() >= 1, timeout=3.0),
                        "the first request never reached the bridge")
        second_thread = self._start(IDENTITY, command_id, second)
        # Buggy code executes the bridge a second time; fixed code answers the
        # in-flight request without entering the bridge.
        observed = wait_until(lambda: self._count() >= 2 or "response" in second, timeout=3.0)
        gate.set()
        first_thread.join(5.0)
        second_thread.join(5.0)
        self.assertFalse(first_thread.is_alive() or second_thread.is_alive(),
                         "same-id requests did not finish")
        self.assertTrue(observed, "the second request neither executed nor returned")
        self.assertEqual(self._count(), 1, "the bridge must execute once for one command_id")

        self.assertEqual(status_of(first["response"]), "completed", first["response"])
        second_response = second["response"]
        if status_of(second_response) == "completed":
            self.assertTrue(result(second_response).get("replayed"), second_response)
            self.assertEqual(result(second_response)["command_id"], command_id)
        else:
            # OP-003: a non-terminal replay returns the current operation state.
            self.assertIn(status_of(second_response), {"accepted", "running"},
                          second_response)
            self.assertTrue(result(second_response).get("replayed"), second_response)
            self.assertEqual(result(second_response).get("command_id"), command_id)
        self.assertEqual(self.server._revisions[self.device_id], 1,
                         "the same command_id must advance the revision exactly once")
        self.assertEqual(self.bridge.state["tick"], 1)

    def test_same_id_different_action_is_a_conflict(self) -> None:
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V8B"
        first = self._command(IDENTITY, {"value": 1}, command_id=command_id)
        self.assertEqual(status_of(first), "completed", first)
        second = self._command(UNKNOWN, {}, command_id=command_id)
        self.assertEqual(status_of(second), "rejected", second)
        self.assertEqual(error_code(second), "MHS.CONFLICT.COMMAND_ID_REUSE", second)
        self.assertEqual(self._count(IDENTITY), 1)
        self.assertEqual(self._count(UNKNOWN), 0)
        self.assertEqual(self.server._revisions[self.device_id], 1)

    # -- restore retry ----------------------------------------------------
    def _snapshot(self) -> dict:
        response = self.server.handle({"jsonrpc": "2.0", "id": "snap", "method": "mhs.snapshot",
                                       "params": {"session_id": self.session,
                                                  "device_id": self.device_id,
                                                  "deadline_ms": 1000}})
        response = response.to_dict() if hasattr(response, "to_dict") else response
        self.assertIn("result", response, response)
        return result(response)

    def _restore(self, snapshot: dict, command_id: str, *, deadline_ms: int = 1000) -> dict:
        params = {"session_id": self.session, "device_id": self.device_id,
                  "snapshot": snapshot, "command_id": command_id, "deadline_ms": deadline_ms}
        response = self.server.handle({"jsonrpc": "2.0", "id": "restore",
                                       "method": "mhs.restore", "params": params})
        return response.to_dict() if hasattr(response, "to_dict") else response

    def test_restore_retry_executes_once_and_advances_revision_once(self) -> None:
        snapshot = self._snapshot()
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V8C"
        first = self._restore(snapshot, command_id)
        self.assertEqual(status_of(first), "completed", first)
        first_receipt = result(first)
        self.assertEqual(self.bridge.counts.get("restore"), 1)
        self.assertEqual(self.server._revisions[self.device_id], 1)

        second = self._restore(snapshot, command_id)
        self.assertEqual(status_of(second), "completed", second)
        self.assertTrue(result(second).get("replayed"), second)
        self.assertEqual(result(second)["receipt_id"], first_receipt["receipt_id"])
        self.assertEqual(self.bridge.counts.get("restore"), 1,
                         "a restore retry must not invoke the bridge twice")
        self.assertEqual(self.server._revisions[self.device_id], 1,
                         "a restore retry must not advance the revision twice")
        self.assertTrue(all(isinstance(key, tuple) for key in self.server._receipts),
                        "every retained receipt must use the (device_id, command_id) key")

    def test_concurrent_restore_retry_executes_once(self) -> None:
        snapshot = self._snapshot()
        gate = self.bridge.gate("restore")
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V8D"
        first: dict = {}
        second: dict = {}

        def run(holder: dict) -> None:
            holder["response"] = self._restore(snapshot, command_id, deadline_ms=3000)

        first_thread = threading.Thread(target=run, args=(first,), daemon=True)
        first_thread.start()
        self.assertTrue(wait_until(lambda: self.bridge.counts.get("restore", 0) >= 1, timeout=3.0))
        second_thread = threading.Thread(target=run, args=(second,), daemon=True)
        second_thread.start()
        observed = wait_until(
            lambda: self.bridge.counts.get("restore", 0) >= 2 or "response" in second,
            timeout=3.0,
        )
        gate.set()
        first_thread.join(5.0)
        second_thread.join(5.0)
        self.assertFalse(first_thread.is_alive() or second_thread.is_alive())
        self.assertTrue(observed)
        self.assertEqual(self.bridge.counts.get("restore"), 1)
        self.assertEqual(self.server._revisions[self.device_id], 1)
        self.assertEqual(status_of(first["response"]), "completed", first["response"])
        second_response = second["response"]
        if status_of(second_response) == "completed":
            self.assertTrue(result(second_response).get("replayed"), second_response)
        elif status_of(second_response) in {"accepted", "running"}:
            pass  # OP-003: the in-flight state is returned instead of re-executing.
        else:
            # A structured "already in flight, may have effect" answer is also
            # acceptable for a concurrent retry: it never executes twice.
            self.assertEqual(error_code(second_response), "MHS.OUTCOME.TIMEOUT", second_response)

    # -- cross device / cross session / UNKNOWN retry ----------------------
    def test_cross_device_is_a_different_idempotency_scope(self) -> None:
        second_device, second_bridge = make_device("identity-b")
        self.server.devices[second_device.device_id] = second_device
        self.server._revisions[second_device.device_id] = 0
        self.server._device_locks[second_device.device_id] = threading.Lock()
        self.server._latched[second_device.device_id] = False
        both = open_session(self.server, [self.device_id, second_device.device_id])
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V8E"
        first = command(self.server, both, self.device_id, IDENTITY, {}, command_id=command_id)
        second = command(self.server, both, second_device.device_id, IDENTITY, {},
                         command_id=command_id)
        self.assertEqual(status_of(first), "completed", first)
        self.assertEqual(status_of(second), "completed", second)
        self.assertFalse(result(second).get("replayed"), second)
        self.assertEqual(self._count(), 1)
        self.assertEqual(second_bridge.counts.get(IDENTITY), 1)
        self.assertEqual(self.server._revisions[self.device_id], 1)
        self.assertEqual(self.server._revisions[second_device.device_id], 1)

    def test_cross_session_same_device_is_a_replay(self) -> None:
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V8F"
        first = self._command(IDENTITY, {}, command_id=command_id)
        self.assertEqual(status_of(first), "completed", first)
        other_session = open_session(self.server, [self.device_id])
        replay = command(self.server, other_session, self.device_id, IDENTITY, {},
                         command_id=command_id)
        self.assertEqual(status_of(replay), "completed", replay)
        self.assertTrue(result(replay).get("replayed"), replay)
        self.assertEqual(self._count(), 1)
        self.assertEqual(self.server._revisions[self.device_id], 1)

    def test_unknown_outcome_retry_does_not_reexecute(self) -> None:
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V8G"
        first = self._command(UNKNOWN, {}, command_id=command_id)
        self.assertEqual(status_of(first), "unknown", first)
        self.assertEqual(error_code(first), "MHS.OUTCOME.UNKNOWN", first)
        self.assertEqual(self._count(UNKNOWN), 1)
        revision = self.server._revisions[self.device_id]

        retry = self._command(UNKNOWN, {}, command_id=command_id)
        self.assertEqual(self._count(UNKNOWN), 1, "an UNKNOWN retry must not re-execute")
        self.assertEqual(status_of(retry), "unknown", retry)
        self.assertTrue(result(retry).get("replayed"), retry)
        self.assertEqual(self.server._revisions[self.device_id], revision,
                         "an UNKNOWN retry must not advance the revision")


if __name__ == "__main__":
    unittest.main()
