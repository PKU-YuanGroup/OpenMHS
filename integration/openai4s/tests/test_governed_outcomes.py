"""HOST-003 outcomes the hardened MCP projection returns, on a scripted transport.

``invoke_via`` only needs ``tool_names()`` and ``call(name, arguments)``, so
these tests script the projection's answers and check what the governed
wrapper journals and decides:

* an ``isError`` result whose ``mhs_error`` says ``may_have_effect: true``
  (``MHS.OUTCOME.TIMEOUT``/``UNKNOWN``: the projection sent the command and lost
  the answer) is an UNKNOWN outcome that closes the gate, never a safe retry;
* an ``isError`` result for a call that never ran (a lapsed session the
  projection renewed) stays a retry-safe tool error;
* a ``running`` receipt (plan 3.7 long-running work) is journaled ``in_flight``
  with its operation id; no new command on the device starts until
  ``mhs__operations`` on the same connection shows the operation final;
* the endpoint deadline leaves the transport time to receive the answer.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from mhs import canonical
from mhs.mcp import projection_tool_name

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.host_evidence import HostLedger
from openai4s_mhs.mcp_invoke import (
    CommandJournal,
    MCPInvokeError,
    MCPOutcomeUnknown,
    _endpoint_deadline_ms,
    invoke_via,
)

from .host_remediation_support import write_settings

DEVICE = "mhs://scripted/lab/bath"
CAPABILITY = "cap.thermal.setpoint.v1"


def _result(structured: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "is_error": is_error,
        "text": json.dumps(structured),
        "raw": {"isError": is_error, "structuredContent": structured},
    }


class ScriptedTransport:
    """Answers like ``mhs.mcp`` would; capability answers come from ``script``."""

    def __init__(self, script: list[Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self.tool = projection_tool_name(DEVICE, CAPABILITY)
        self.script = list(script)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.operations: dict[str, dict[str, Any]] = {}

    def tool_names(self) -> set[str]:
        return {self.tool, "mhs__inspect", "mhs__operations", "mhs__evidence"}

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = dict(arguments or {})
        self.calls.append((name, arguments))
        if name == "mhs__inspect":
            return _result({"inspect": {
                "device_id": DEVICE,
                "mode": "simulated",
                "capabilities": [{"capability_id": CAPABILITY, "resource": "bath"}],
            }})
        if name == "mhs__operations":
            operation = self.operations.get(str(arguments.get("operation_id")))
            if operation is None:
                return _result({"receipt": None, "mhs_error": {
                    "mhs_code": "MHS.OPERATION.UNKNOWN", "message": "no such operation"}}, is_error=True)
            return _result({"operations": dict(operation)})
        if name == self.tool:
            return self.script.pop(0)(arguments)
        raise AssertionError(f"unexpected tool {name}")

    def capability_calls(self) -> list[dict[str, Any]]:
        return [arguments for name, arguments in self.calls if name == self.tool]


def receipt(status: str, **extra: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def answer(arguments: dict[str, Any]) -> dict[str, Any]:
        body = {
            "receipt_id": "r_" + canonical.ulid(),
            "command_id": arguments["command_id"],
            "device_id": DEVICE,
            "capability_id": CAPABILITY,
            "status": status,
            **extra,
        }
        structured: dict[str, Any] = {"receipt": body}
        if extra.get("operation_id"):
            structured["operation"] = {"operation_id": extra["operation_id"], "status": status}
        return _result(structured)

    return answer


def tool_error(**payload: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def answer(arguments: dict[str, Any]) -> dict[str, Any]:
        error = {"command_id": arguments["command_id"], **payload}
        return _result({"receipt": None, "mhs_error": error}, is_error=True)

    return answer


class GovernedOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-governed-outcomes-")
        self.addCleanup(self.tmp.cleanup)
        path = write_settings(Path(self.tmp.name), "http://127.0.0.1:9", endpoint_id="lab")
        self.config = MHSConfig.load(path)
        self.journal = CommandJournal(self.config.command_journal_path)

    def _invoke(self, transport: ScriptedTransport, value: float = 40.0, **kwargs: Any) -> Any:
        return invoke_via(
            transport, "lab", DEVICE, CAPABILITY, {"target_temperature": value},
            config=self.config, journal=self.journal, **kwargs,
        )

    def _phases(self, command_id: str) -> list[str]:
        return [item.get("phase") for item in self.journal.for_command(command_id)
                if item.get("kind") == "command_dispatch"]

    # -- isError after dispatch ------------------------------------------
    def test_may_have_effect_error_is_unknown_and_closes_the_gate(self) -> None:
        transport = ScriptedTransport([
            tool_error(mhs_code="MHS.OUTCOME.TIMEOUT", message="no response after send",
                       may_have_effect=True),
        ])
        with self.assertRaises(MCPOutcomeUnknown) as caught:
            self._invoke(transport)
        command_id = caught.exception.command_id
        self.assertFalse(caught.exception.retry_safe)
        self.assertEqual(caught.exception.details["mhs_error"]["mhs_code"], "MHS.OUTCOME.TIMEOUT")
        self.assertEqual(self._phases(command_id)[-1], "unknown")
        self.assertNotIn("tool_error", self._phases(command_id))
        pending = self.journal.unreconciled("lab", DEVICE)
        self.assertEqual([item["command_id"] for item in pending], [command_id])
        outcomes = [item for item in HostLedger(self.config.host_ledger_path).records()
                    if item.get("command_id") == command_id and item.get("kind") == "invoke_outcome"]
        self.assertEqual([item["outcome"] for item in outcomes], ["unknown"])

        # A new command is refused before anything is sent...
        follow = ScriptedTransport([receipt("completed")])
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(follow, 41.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertEqual(follow.capability_calls(), [])
        # ...while the verified same-id retry goes through and settles it.
        retry = ScriptedTransport([receipt("completed", replayed=True)])
        settled = self._invoke(retry, command_id=command_id)
        self.assertEqual(settled["status"], "completed")
        self.assertEqual(retry.capability_calls()[0]["command_id"], command_id)
        self.assertEqual(self.journal.unreconciled("lab", DEVICE), [])

    def test_outcome_unknown_code_without_flag_is_still_unknown(self) -> None:
        transport = ScriptedTransport([tool_error(mhs_code="MHS.OUTCOME.UNKNOWN", message="lost")])
        with self.assertRaises(MCPOutcomeUnknown):
            self._invoke(transport)
        self.assertEqual(len(self.journal.unreconciled("lab", DEVICE)), 1)

    def test_a_call_that_never_ran_stays_a_safe_retry(self) -> None:
        transport = ScriptedTransport([
            tool_error(mhs_code="MHS.SESSION.EXPIRED", message="this call was NOT executed",
                       session_renewed=True, retryable=True),
        ])
        with self.assertRaises(MCPInvokeError) as caught:
            self._invoke(transport)
        self.assertNotIsInstance(caught.exception, MCPOutcomeUnknown)
        self.assertTrue(caught.exception.retry_safe)
        self.assertEqual(self._phases(caught.exception.command_id)[-1], "tool_error")
        self.assertEqual(self.journal.unreconciled("lab", DEVICE), [])

    # -- running receipts ------------------------------------------------
    def test_running_receipt_is_in_flight_until_the_operation_ends(self) -> None:
        transport = ScriptedTransport([receipt("running", operation_id="op_1")])
        started = self._invoke(transport)
        self.assertEqual(started["status"], "running")
        command_id = started["command_id"]
        self.assertEqual(self._phases(command_id)[-1], "in_flight")
        pending = self.journal.unreconciled("lab", DEVICE)
        self.assertEqual(len(pending), 1)
        self.assertEqual((pending[0]["state"], pending[0]["operation_id"]), ("in_flight", "op_1"))
        outcome = [item for item in HostLedger(self.config.host_ledger_path).records()
                   if item.get("kind") == "invoke_outcome"][-1]
        self.assertEqual((outcome["outcome"], outcome["operation_id"]), ("in_flight", "op_1"))

        # Still running: operations.get on the same connection keeps the gate shut.
        transport.operations["op_1"] = {"operation_id": "op_1", "status": "running",
                                        "command_id": command_id}
        transport.script.append(receipt("completed"))
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(transport, 42.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertIn("still running", gate.exception.message)
        self.assertEqual(gate.exception.details["pending_states"][0]["operation_id"], "op_1")
        self.assertEqual(len(transport.capability_calls()), 1)

        # Final: the next command settles it first, then runs.
        transport.operations["op_1"] = {"operation_id": "op_1", "status": "completed",
                                        "command_id": command_id, "receipt_id": "r_final"}
        done = self._invoke(transport, 42.0)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(len(transport.capability_calls()), 2)
        settle = [item for item in self.journal.records() if item.get("kind") == "command_reconcile"]
        self.assertEqual(len(settle), 1)
        self.assertEqual(settle[0]["source"], "operations.get")
        self.assertEqual(settle[0]["resolved_command_ids"], [command_id])
        self.assertEqual(self.journal.unreconciled("lab", DEVICE), [])

    def test_accepted_receipt_is_in_flight_too(self) -> None:
        transport = ScriptedTransport([receipt("accepted", operation_id="op_2")])
        self.assertEqual(self._invoke(transport)["status"], "accepted")
        self.assertEqual(self.journal.unreconciled("lab", DEVICE)[0]["state"], "in_flight")

    # -- deadline -----------------------------------------------------------
    def test_the_endpoint_deadline_is_shorter_than_the_transport_timeout(self) -> None:
        transport = ScriptedTransport([receipt("completed")])
        self._invoke(transport, timeout_s=8.0)
        self.assertEqual(transport.capability_calls()[0]["deadline_ms"], 6400)
        self.assertEqual(_endpoint_deadline_ms(1.0), 750)
        self.assertEqual(_endpoint_deadline_ms(60.0), 48000)
        for seconds in (1.0, 2.5, 60.0, 600.0):
            self.assertLess(_endpoint_deadline_ms(seconds), seconds * 1000)


if __name__ == "__main__":
    unittest.main()
