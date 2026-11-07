"""RE-PROTO-004: every blocking method honours one monotonic deadline.

A bridge gate blocks indefinitely (not a sleep); the caller must return a
structured timeout/UNKNOWN promptly.  The gate is released only after the
caller has returned, so a late synchronous bridge call is detectable.
"""
from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _fixtures import (  # noqa: E402
    as_dict,
    command,
    error_code,
    make_device,
    make_server,
    open_session,
    result,
    status_of,
    wait_no_threads,
    wait_until,
)

TOLERANCE_S = 0.20
DEADLINE_MS = 10
EXCLUSIVE = "cap.test.exclusive_identity.v1"


def structured_timeout(response: dict) -> bool:
    """True when the response is a timeout/UNKNOWN, never a success payload."""
    response = as_dict(response)
    if "error" in response:
        return error_code(response) in {"MHS.OUTCOME.TIMEOUT", "MHS.OUTCOME.UNKNOWN"}
    res = response.get("result")
    if not isinstance(res, dict):
        return False
    if res.get("status") in {"unknown", "accepted", "running"}:
        return True
    return error_code(response) in {"MHS.OUTCOME.TIMEOUT", "MHS.OUTCOME.UNKNOWN"}


class DeadlineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device, self.bridge = make_device("deadline")
        self.server = make_server(self.device)
        self.device_id = self.device.device_id
        self.session = open_session(self.server, [self.device_id])

    def tearDown(self) -> None:
        self.bridge.release()
        wait_no_threads("mhs-bounded-", timeout=3.0)
        wait_no_threads("mhs-op-", timeout=3.0)

    # -- helpers ---------------------------------------------------------
    def _call(self, method: str, params: dict, *, timeout: float = 2.0) -> tuple[dict, float]:
        holder: dict = {}

        def run() -> None:
            started = time.monotonic()
            holder["response"] = self.server.handle(
                {"jsonrpc": "2.0", "id": "deadline", "method": method, "params": params}
            )
            holder["elapsed"] = time.monotonic() - started

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            self.bridge.release()
            thread.join(3.0)
            self.fail(f"{method} did not return within {timeout}s despite deadline_ms={DEADLINE_MS}")
        return holder["response"], holder["elapsed"]

    def _assert_bounded(self, method: str, response: dict, elapsed: float) -> None:
        self.assertLess(elapsed, TOLERANCE_S,
                        f"{method} returned after {elapsed * 1000:.1f} ms for deadline_ms={DEADLINE_MS}")
        self.assertTrue(structured_timeout(response),
                        f"{method} reported late success instead of a structured timeout: {response}")

    def _common(self) -> dict:
        return {"session_id": self.session, "device_id": self.device_id, "deadline_ms": DEADLINE_MS}

    @staticmethod
    def _details(response: dict) -> dict:
        response = as_dict(response)
        if isinstance(response.get("error"), dict):
            return dict((response["error"].get("data") or {}).get("details") or {})
        res = response.get("result")
        if isinstance(res, dict) and isinstance(res.get("error"), dict):
            return dict(res["error"].get("details") or {})
        return {}

    # -- one case per blocking bridge method ------------------------------
    def test_resource_read_deadline(self) -> None:
        self.bridge.gate("read")
        response, elapsed = self._call("mhs.resource.read", {**self._common(), "resource_id": "world"})
        self._assert_bounded("mhs.resource.read", response, elapsed)
        self.bridge.release("read")
        self.assertTrue(wait_no_threads("mhs-bounded-", timeout=3.0))

    def test_snapshot_deadline(self) -> None:
        self.bridge.gate("snapshot")
        response, elapsed = self._call("mhs.snapshot", self._common())
        self._assert_bounded("mhs.snapshot", response, elapsed)
        self.bridge.release("snapshot")
        self.assertTrue(wait_no_threads("mhs-bounded-", timeout=3.0))

    def test_safety_status_deadline(self) -> None:
        self.bridge.gate("safety_status")
        response, elapsed = self._call("mhs.safety.status", self._common())
        self._assert_bounded("mhs.safety.status", response, elapsed)
        self.bridge.release("safety_status")
        status = self.server.handle({"jsonrpc": "2.0", "id": "status", "method": "mhs.safety.status",
                                    "params": {**self._common(), "deadline_ms": 1000}})
        status = status.to_dict() if hasattr(status, "to_dict") else status
        self.assertEqual(result(status)["device_id"], self.device_id)

    def test_restore_deadline_is_truthful_and_reconcilable(self) -> None:
        snapshot = result(self.server.handle(
            {"jsonrpc": "2.0", "id": "snap", "method": "mhs.snapshot",
             "params": {**self._common(), "deadline_ms": 1000}}
        ))
        self.bridge.gate("restore")
        response, elapsed = self._call("mhs.restore", {**self._common(), "snapshot": snapshot})
        self._assert_bounded("mhs.restore", response, elapsed)
        command_id = self._details(response).get("command_id")
        self.assertIsInstance(command_id, str, response)
        self.bridge.release("restore")
        self.assertTrue(
            wait_until(lambda: (self.device_id, command_id) in self.server._receipts, timeout=3.0),
            "the accepted restore attempt is not traceable by command_id",
        )
        receipt = self.server._receipts[(self.device_id, command_id)][1]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.server._revisions[self.device_id], 1)
        self.assertFalse(self.server._device_locks[self.device_id].locked())

    def test_estop_deadline_keeps_the_safety_path_traceable(self) -> None:
        # WP-04 4a1 (SAFE-040): the e-stop latches before its native stop and
        # answers within the deadline with a failed SAFE_STATE_UNREACHED
        # receipt (never a bare timeout); the stop path keeps running and its
        # late success is recorded as a confirmation receipt.
        self.bridge.gate("estop")
        response, elapsed = self._call("mhs.safety.estop", {**self._common(), "reason": "round2"})
        self.assertLess(elapsed, TOLERANCE_S,
                        f"mhs.safety.estop returned after {elapsed * 1000:.1f} ms")
        self.assertTrue(self.server._latched[self.device_id],
                        "the emergency stop was not engaged before the native stop returned")
        receipt = result(response)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        command_id = receipt["command_id"]
        self.assertIn((self.device_id, command_id), self.server._receipts,
                      "the e-stop attempt is not traceable by command_id")
        self.bridge.release("estop")
        self.assertTrue(
            wait_until(lambda: self.server._estop_state[self.device_id]["confirmed"] is True, timeout=3.0),
            "the native stop completed but was never confirmed",
        )
        self.assertEqual(self.server._receipts[(self.device_id, command_id)][1]["status"], "failed",
                         "a final receipt is immutable")
        confirmations = [
            stored for _digest, stored in self.server._receipts.values()
            if (stored.get("output") or {}).get("confirms") == command_id
        ]
        self.assertEqual(len(confirmations), 1, confirmations)
        status = result(self.server.handle(
            {"jsonrpc": "2.0", "id": "status", "method": "mhs.safety.status",
             "params": {**self._common(), "deadline_ms": 1000}}
        ))
        self.assertTrue(status["estop_engaged"], status)
        self.assertTrue(status["estop"]["confirmed"], status)

    def test_reset_deadline_is_truthful_and_reconcilable(self) -> None:
        self.bridge.state["latched"] = True
        self.bridge.gate("reset")
        response, elapsed = self._call("mhs.safety.reset", self._common())
        self._assert_bounded("mhs.safety.reset", response, elapsed)
        command_id = self._details(response).get("command_id")
        self.assertIsInstance(command_id, str, response)
        self.bridge.release("reset")
        self.assertTrue(
            wait_until(lambda: (self.device_id, command_id) in self.server._receipts, timeout=3.0),
            "the accepted reset attempt is not traceable by command_id",
        )
        receipt = self.server._receipts[(self.device_id, command_id)][1]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(self.bridge.state["latched"])

    def test_command_deadline_returns_unknown_operation_and_stays_queryable(self) -> None:
        self.bridge.gate(EXCLUSIVE)
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V9A"
        response, elapsed = self._call(
            "mhs.command",
            {**self._common(), "capability_id": EXCLUSIVE, "input": {"value": 1},
             "command_id": command_id},
        )
        self._assert_bounded("mhs.command", response, elapsed)
        receipt = result(response)
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.OUTCOME.TIMEOUT", receipt)
        operation_id = receipt.get("operation_id")
        self.assertIsInstance(operation_id, str, receipt)
        self.assertTrue(self.server._device_locks[self.device_id].locked(),
                        "the worker should still hold the exclusive lease while blocked")
        self.bridge.release(EXCLUSIVE)
        self.assertTrue(wait_no_threads("mhs-op-", timeout=3.0),
                        "the command worker leaked after the deadline")
        self.assertTrue(wait_until(lambda: not self.server._device_locks[self.device_id].locked(),
                                   timeout=2.0), "the exclusive device lease leaked")
        queried, query_elapsed = self._call(
            "mhs.operations.get",
            {"session_id": self.session, "device_id": self.device_id,
             "operation_id": operation_id, "deadline_ms": 1000},
        )
        self.assertLess(query_elapsed, TOLERANCE_S)
        self.assertEqual(result(queried)["status"], "completed", queried)
        self.assertEqual(self.server._revisions[self.device_id], 1)

    # -- remaining blocking methods: prompt structured responses -----------
    def test_operations_and_subscribe_are_bounded(self) -> None:
        command_response = command(self.server, self.session, self.device_id, EXCLUSIVE,
                                   {"value": 2}, deadline_ms=1000,
                                   command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V9B")
        self.assertEqual(status_of(command_response), "completed", command_response)
        operation_id = result(command_response)["operation_id"]

        started = time.monotonic()
        got = self.server.handle({"jsonrpc": "2.0", "id": "op", "method": "mhs.operations.get",
                                  "params": {"session_id": self.session, "device_id": self.device_id,
                                             "operation_id": operation_id, "deadline_ms": 1000}})
        got = got.to_dict() if hasattr(got, "to_dict") else got
        self.assertLess(time.monotonic() - started, TOLERANCE_S)
        self.assertEqual(status_of(got), "completed", got)

        started = time.monotonic()
        cancelled = self.server.handle({"jsonrpc": "2.0", "id": "cancel",
                                        "method": "mhs.operations.cancel",
                                        "params": {"session_id": self.session,
                                                   "operation_id": operation_id,
                                                   "deadline_ms": 1000}})
        cancelled = cancelled.to_dict() if hasattr(cancelled, "to_dict") else cancelled
        self.assertLess(time.monotonic() - started, TOLERANCE_S)
        self.assertEqual(status_of(cancelled), "completed", cancelled)

        started = time.monotonic()
        subscribed = self.server.handle({"jsonrpc": "2.0", "id": "sub", "method": "mhs.subscribe",
                                         "params": {"session_id": self.session,
                                                    "device_id": self.device_id,
                                                    "streams": ["state"], "deadline_ms": 10}})
        subscribed = subscribed.to_dict() if hasattr(subscribed, "to_dict") else subscribed
        self.assertLess(time.monotonic() - started, TOLERANCE_S)
        self.assertIn("subscription_id", result(subscribed))

    def test_cancel_of_a_running_operation_is_bounded(self) -> None:
        # Exercise the cancellation wait, rather than the non-cancellable refusal.
        # Set the declaration before the command captures its admitted binding.
        binding = self.device.capability(EXCLUSIVE, "world")
        binding.constraints = {**(binding.constraints or {}), "cancellable": True}
        self.assertTrue(binding.cancellable)
        gate = self.bridge.gate(EXCLUSIVE)
        holder: dict = {}

        def run() -> None:
            holder["response"] = command(
                self.server, self.session, self.device_id, EXCLUSIVE, {"value": 3},
                deadline_ms=3000, command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V9C",
            )

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            self.assertTrue(wait_until(lambda: bool(self.server._operations), timeout=3.0))
            # WP-04 4a1: an operation cancelled before its worker reached the
            # bridge is receipted cancelled without a bridge call; this test is
            # about an operation that is already inside the (gated) bridge call.
            self.assertTrue(wait_until(lambda: self.bridge.counts.get(EXCLUSIVE, 0) >= 1, timeout=3.0))
            operation_id = next(iter(self.server._operations))
            started = time.monotonic()
            cancelled = self.server.handle({"jsonrpc": "2.0", "id": "cancel",
                                            "method": "mhs.operations.cancel",
                                            "params": {"session_id": self.session,
                                                       "operation_id": operation_id,
                                                       "deadline_ms": 10}})
            cancelled = cancelled.to_dict() if hasattr(cancelled, "to_dict") else cancelled
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, TOLERANCE_S)
            if status_of(cancelled) is None:
                self.assertIn(error_code(cancelled), {"MHS.OUTCOME.TIMEOUT", "MHS.OUTCOME.UNKNOWN"},
                              cancelled)
            else:
                self.assertIn(status_of(cancelled), {"running", "unknown"}, cancelled)
        finally:
            gate.set()
            thread.join(5.0)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
