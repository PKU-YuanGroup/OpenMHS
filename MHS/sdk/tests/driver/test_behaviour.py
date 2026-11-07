"""Gate G6 (mhs.driver.behaviour) against endpoints that misbehave in one way each.

The SDK server always enforces the latch, the operator-only reset, cancellation
on e-stop and operator_required limits, so no driver package can make these
checks fail; here the session of an otherwise correct endpoint (the tutorial)
lies about one outcome, and the check must notice.
"""

from __future__ import annotations

import copy
import unittest
from typing import Any, Callable

from mhs.driver.behaviour import BehaviourRun, Session
from mhs.driver.build import hardware_device_id
from mhs.driver.check import _Context

from tests.driver import gate_support as gs

_LATCHED = "MHS.SAFETY.ESTOP_ENGAGED"
_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class LyingSession:
    """A session proxy whose receipts pass through ``lie(method, result)``."""

    def __init__(self, session: Any, lie: Callable[[str, Any], Any]):
        self._session = session
        self._lie = lie

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    def command(self, *args: Any, **kwargs: Any) -> Any:
        return self._lie("command", self._session.command(*args, **kwargs))

    def write(self, *args: Any, **kwargs: Any) -> Any:
        return self._lie("write", self._session.write(*args, **kwargs))

    def read(self) -> Any:
        return self._lie("read", self._session.read())

    def reset(self) -> Any:
        return self._lie("reset", self._session.reset())


def _code(receipt: Any) -> Any:
    return ((receipt or {}).get("error") or {}).get("mhs_code") if isinstance(receipt, dict) else None


def completed(receipt: dict) -> dict:
    out = {key: value for key, value in receipt.items() if key != "error"}
    out["status"] = "completed"
    out.setdefault("output", {})
    return out


class ScriptedSession(Session):
    """A session whose ``mhs.operations.get`` answers come from a list (no server)."""

    def __init__(self, answers: list[dict[str, Any]]):          # noqa: super().__init__ would open a server session
        self.session_id, self.calls, self.answers = "session", [], list(answers)

    def rpc(self, method: str, params: Any) -> Any:
        self.calls.append(method)
        return self.answers.pop(0)


class SettledReceiptTests(unittest.TestCase):
    """A failing transport ends its operation as ``unknown``; polling that for the whole bound cost 15 s a check."""

    UNKNOWN = {"status": "unknown", "operation_id": "op_1", "error": {"mhs_code": "MHS.OUTCOME.UNKNOWN"}}

    def test_an_unknown_outcome_is_final(self) -> None:
        session = ScriptedSession([])
        self.assertEqual(session._final(dict(self.UNKNOWN), timeout_s=60.0), self.UNKNOWN)
        self.assertEqual(session.calls, [])                          # not a single poll

    def test_an_unknown_timeout_and_a_running_operation_are_polled(self) -> None:
        done = {"status": "completed", "operation_id": "op_1"}
        for waiting in ({"status": "unknown", "operation_id": "op_1", "error": {"mhs_code": "MHS.OUTCOME.TIMEOUT"}},
                        {"status": "running", "operation_id": "op_1"}):
            session = ScriptedSession([done])
            self.assertEqual(session._final(waiting, timeout_s=60.0), done)
            self.assertEqual(session.calls, ["mhs.operations.get"])

    def test_a_failed_or_operationless_receipt_is_not_polled(self) -> None:
        for receipt in ({"status": "failed", "operation_id": "op_1"}, {"status": "accepted"}):
            session = ScriptedSession([])
            self.assertEqual(session._final(receipt, timeout_s=60.0), receipt)
            self.assertEqual(session.calls, [])


class BehaviourLieTests(unittest.TestCase):
    def run_with(self, lie: Callable[[str, Any], Any]) -> list[str]:
        directory = gs.copy_tutorial(self)
        ctx = _Context(directory, "fake", None, None, False)
        self.addCleanup(ctx.close)

        def lying(factory: Callable[..., Any]) -> Callable[..., Any]:
            def make(**options: Any) -> Any:
                endpoint = factory(**options)
                endpoint.session = LyingSession(endpoint.session, lie)
                return endpoint

            return make

        run = BehaviourRun(endpoint=lying(ctx.endpoint), model=ctx.model, hardware_view=lying(ctx.hardware_endpoint),
                           fixtures=None, example_overlay=None, hardware_id=hardware_device_id(ctx.model),
                           recorded=ctx.records_native)
        return [code for code, _message, severity, _path in run.run() if severity == "error"]

    def test_the_honest_tutorial_has_no_error(self) -> None:
        self.assertEqual(self.run_with(lambda method, result: result), [])

    def test_an_action_accepted_while_latched_is_found(self) -> None:
        def lie(method: str, result: Any) -> Any:
            return completed(result) if method in ("command", "write") and _code(result) == _LATCHED else result

        self.assertIn("G6.LATCH_NOT_ENFORCED", self.run_with(lie))

    def test_an_agent_reset_accepted_on_hardware_is_found(self) -> None:
        def lie(method: str, result: Any) -> Any:
            return {"jsonrpc": "2.0", "id": 1, "result": {"status": "completed"}} if method == "reset" else result

        self.assertIn("G6.AGENT_RESET_ACCEPTED", self.run_with(lie))

    def test_an_action_the_estop_does_not_cancel_is_found(self) -> None:
        def lie(method: str, result: Any) -> Any:
            if method == "command" and isinstance(result, dict) and result.get("status") == "cancelled":
                return completed(result)
            return result

        self.assertIn("G6.ESTOP_NOT_CANCELLED", self.run_with(lie))

    def test_operator_required_accepted_without_an_overlay_is_found(self) -> None:
        def lie(method: str, result: Any) -> Any:
            return completed(result) if method in ("command", "write") and _code(result) == _UNSET else result

        self.assertIn("G6.OPERATOR_REQUIRED_NOT_ENFORCED", self.run_with(lie))

    def test_a_state_that_breaks_its_schema_is_found(self) -> None:
        def lie(method: str, result: Any) -> Any:
            if method == "read" and isinstance(result, dict) and isinstance(result.get("state"), dict):
                result = copy.deepcopy(result)
                result["state"]["temperature"] = "hot"
            return result

        self.assertIn("G6.READ_INVALID", self.run_with(lie))

    def test_an_out_of_limit_input_that_completes_is_found(self) -> None:
        def lie(method: str, result: Any) -> Any:
            if method in ("command", "write") and _code(result) == "MHS.SAFETY.ENVELOPE_VIOLATION":
                return completed(result)
            return result

        self.assertIn("G6.ENVELOPE_NOT_ENFORCED", self.run_with(lie))


if __name__ == "__main__":
    unittest.main()
