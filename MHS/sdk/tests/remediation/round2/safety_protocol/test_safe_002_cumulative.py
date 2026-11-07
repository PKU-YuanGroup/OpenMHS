"""RE-SAFE-002: cumulative budgets are reserved transactionally.

The concurrent case pauses both requests at the production point where the
current usage has been calculated but not yet reserved, using only a line
trace as the scheduler.  The budget check itself is never patched.
"""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _fixtures import (  # noqa: E402
    add_usage,
    as_dict,
    after_local,
    budget_safety,
    command,
    error_code,
    issue_permit,
    make_device,
    make_server,
    open_session,
    result,
    status_of,
    thread_trace,
    usage_total,
)

CAP = "cap.test.budget.v1"
MULTI = "cap.test.budget_multi.v1"
GATED = "cap.test.budget_gated.v1"


def _budget_device(suffix: str = "budget"):
    return make_device(suffix, safety=budget_safety())


class CumulativeBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device, self.bridge = _budget_device()
        self.server = make_server(self.device)
        self.device_id = self.device.device_id
        self.session = open_session(self.server, [self.device_id])

    def _ticks_usage(self, cap: str = CAP) -> float:
        return usage_total(self.server, self.device_id, cap, "ticks")

    def _command(self, payload: dict, *, cap: str = CAP, **kwargs):
        return command(self.server, self.session, self.device_id, cap, payload, **kwargs)

    # -- required race ---------------------------------------------------
    def test_two_ticks_6_cannot_both_complete_under_max_10(self) -> None:
        barrier = threading.Barrier(2)
        outputs: dict[str, dict] = {}

        def run(name: str, command_id: str) -> None:
            with thread_trace(after_local("_reserve_cumulative", "used", absent="amount"),
                              barrier, timeout=0.75):
                outputs[name] = self._command({"ticks": 6}, command_id=command_id, deadline_ms=2000)

        threads = [
            threading.Thread(target=run, args=("first", "01J8ZQ3V6Y7M2N4P6R8S0T2V7A"), daemon=True),
            threading.Thread(target=run, args=("second", "01J8ZQ3V6Y7M2N4P6R8S0T2V7B"), daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(8.0)
        self.assertTrue(all(not thread.is_alive() for thread in threads), "budget requests did not finish")

        completed = [name for name, response in outputs.items() if status_of(response) == "completed"]
        self.assertEqual(len(completed), 1, outputs)
        rejected = next(name for name in outputs if name not in completed)
        self.assertEqual(status_of(outputs[rejected]), "rejected", outputs[rejected])
        self.assertEqual(error_code(outputs[rejected]), "MHS.SAFETY.CUMULATIVE_LIMIT", outputs[rejected])

        self.assertEqual(self.bridge.state["tick"], 6, "actual effect must not exceed the budget")
        self.assertEqual(self._ticks_usage(), 6.0, "accounted usage must equal the actual effect")
        self.assertLessEqual(self.bridge.state["tick"], 10)
        self.assertEqual(self.server._revisions[self.device_id], 1)

    # -- rollback and release paths --------------------------------------
    def test_multi_field_partial_reservation_is_rolled_back(self) -> None:
        add_usage(self.server, self.device_id, MULTI, "dose", 4.0)
        holder: dict[str, object] = {}

        def run() -> None:
            holder["response"] = self._command(
                {"ticks": 6, "dose": 4}, cap=MULTI, deadline_ms=2000,
                command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7C",
            )

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(3.0)
        self.assertFalse(
            thread.is_alive(),
            "MHS/sdk/src/mhs/server.py deadlocked while releasing a partial multi-field reservation "
            "(_reserve_cumulative holds _cumulative_lock and calls _release_cumulative)",
        )
        response = holder["response"]
        self.assertEqual(status_of(response), "rejected", response)
        self.assertEqual(error_code(response), "MHS.SAFETY.CUMULATIVE_LIMIT", response)
        self.assertEqual(self.bridge.state["tick"], 0)
        self.assertEqual(self.bridge.state["dose"], 0)
        self.assertEqual(self._ticks_usage(MULTI), 0.0, "the ticks reservation leaked")
        self.assertEqual(usage_total(self.server, self.device_id, MULTI, "dose"), 4.0,
                         "the pre-existing dose usage must be untouched")

        legal = self._command({"ticks": 6, "dose": 0}, cap=MULTI, deadline_ms=2000,
                              command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7D")
        self.assertEqual(status_of(legal), "completed", legal)
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(self._ticks_usage(MULTI), 6.0)

    def test_revision_refusal_releases_reservation(self) -> None:
        refused = self._command({"ticks": 6}, expected_revision=99, deadline_ms=2000,
                                command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7E")
        self.assertEqual(status_of(refused), "rejected", refused)
        self.assertEqual(error_code(refused), "MHS.CONFLICT.REVISION", refused)
        self.assertEqual(self._ticks_usage(), 0.0)
        legal = self._command({"ticks": 6}, deadline_ms=2000,
                              command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7F")
        self.assertEqual(status_of(legal), "completed", legal)
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(self._ticks_usage(), 6.0)

    def test_interlock_refusal_releases_reservation(self) -> None:
        self.bridge.state["door"] = "open"
        refused = self._command({"ticks": 6}, deadline_ms=2000,
                                command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7G")
        self.assertEqual(status_of(refused), "rejected", refused)
        self.assertEqual(error_code(refused), "MHS.SAFETY.INTERLOCK_OPEN", refused)
        self.assertEqual(self._ticks_usage(), 0.0)
        self.bridge.state["door"] = "closed"
        legal = self._command({"ticks": 6}, deadline_ms=2000,
                              command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7H")
        self.assertEqual(status_of(legal), "completed", legal)
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(self._ticks_usage(), 6.0)

    def test_permit_refusal_releases_reservation(self) -> None:
        refused = self._command({"ticks": 6}, cap=GATED, deadline_ms=2000,
                                command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7J")
        self.assertEqual(status_of(refused), "rejected", refused)
        self.assertEqual(error_code(refused), "MHS.SAFETY.PERMIT_INVALID", refused)
        self.assertEqual(usage_total(self.server, self.device_id, GATED, "ticks"), 0.0)

        permit = issue_permit(self.server, self.session, self.device_id, GATED, {"ticks": 6},
                              resource="world")
        legal = self._command({"ticks": 6}, cap=GATED, deadline_ms=2000,
                              command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7K",
                              permit_id=result(permit)["permit_id"])
        self.assertEqual(status_of(legal), "completed", legal)
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(usage_total(self.server, self.device_id, GATED, "ticks"), 6.0)

    # -- window / duplicate / session churn -------------------------------
    def test_rolling_window_boundary_prunes_expired_usage_only(self) -> None:
        add_usage(self.server, self.device_id, CAP, "ticks", 6.0, age_s=86_400 + 60)
        legal = self._command({"ticks": 10}, deadline_ms=2000,
                              command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7M")
        self.assertEqual(status_of(legal), "completed", legal)
        self.assertEqual(self.bridge.state["tick"], 10)
        self.assertEqual(self._ticks_usage(), 10.0)

        recent_device, recent_bridge = _budget_device("budget-recent")
        recent_server = make_server(recent_device)
        recent_session = open_session(recent_server, [recent_device.device_id])
        add_usage(recent_server, recent_device.device_id, CAP, "ticks", 6.0, age_s=1)
        refused = command(recent_server, recent_session, recent_device.device_id, CAP,
                          {"ticks": 6}, deadline_ms=2000,
                          command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7N")
        self.assertEqual(status_of(refused), "rejected", refused)
        self.assertEqual(error_code(refused), "MHS.SAFETY.CUMULATIVE_LIMIT")
        self.assertEqual(recent_bridge.state["tick"], 0)
        self.assertEqual(usage_total(recent_server, recent_device.device_id, CAP, "ticks"), 6.0)

    def test_duplicate_request_is_not_double_counted(self) -> None:
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V7P"
        first = self._command({"ticks": 6}, command_id=command_id, deadline_ms=2000)
        self.assertEqual(status_of(first), "completed", first)
        replay = self._command({"ticks": 6}, command_id=command_id, deadline_ms=2000)
        self.assertEqual(status_of(replay), "completed", replay)
        self.assertTrue(result(replay).get("replayed"), replay)
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(self._ticks_usage(), 6.0, "a replay must not reserve the budget twice")

        third = self._command({"ticks": 6}, command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7Q",
                              deadline_ms=2000)
        self.assertEqual(status_of(third), "rejected", third)
        self.assertEqual(error_code(third), "MHS.SAFETY.CUMULATIVE_LIMIT")
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(self._ticks_usage(), 6.0)

    def test_session_churn_does_not_reset_usage(self) -> None:
        first = self._command({"ticks": 6}, deadline_ms=2000,
                              command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7R")
        self.assertEqual(status_of(first), "completed", first)
        close = as_dict(self.server.handle(
            {"jsonrpc": "2.0", "id": "close", "method": "mhs.session.close",
             "params": {"session_id": self.session}}
        ))
        self.assertIn("result", close)
        new_session = open_session(self.server, [self.device_id])
        second = command(self.server, new_session, self.device_id, CAP, {"ticks": 6},
                         deadline_ms=2000, command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7S")
        self.assertEqual(status_of(second), "rejected", second)
        self.assertEqual(error_code(second), "MHS.SAFETY.CUMULATIVE_LIMIT")
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(self._ticks_usage(), 6.0)

    # -- positive control -------------------------------------------------
    def test_legal_first_use_within_budget(self) -> None:
        response = self._command({"ticks": 6}, deadline_ms=2000,
                                 command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V7T")
        self.assertEqual(status_of(response), "completed", response)
        self.assertEqual(self.bridge.state["tick"], 6)
        self.assertEqual(self._ticks_usage(), 6.0)
        self.assertEqual(self.server._revisions[self.device_id], 1)


if __name__ == "__main__":
    unittest.main()
