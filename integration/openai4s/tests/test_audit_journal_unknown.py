"""A failed attempt must not hide a later UNKNOWN outcome (HOST-091).

``CommandJournal`` reduces every record of one ``command_id`` together. It used
to treat any ``pre_send_error`` or ``tool_error`` as terminal for the whole id,
ahead of a later ``unknown`` or an unanswered ``dispatching`` marker. A same-id
retry that then lost its reply left ``unreconciled`` empty, so the device gate
stayed open.

HOST-091: a pre-send failure is a safe retry and must be distinguished from the
ambiguous case; a post-send loss is ``MHS.OUTCOME.UNKNOWN`` and blocks a new
command until a definitive receipt or reconciliation. OP-013, OP-014, CORE-091
and SAFE-055 say the same thing: a lost reply is unknown, and the host must
not carry on as if the outcome were settled.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

from mhs import canonical
from mhs.mcp import projection_tool_name

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.mcp_invoke import (
    CommandJournal,
    MCPInvokeError,
    MCPOutcomeUnknown,
    invoke_via,
    reconcile,
)

from .host_remediation_support import write_settings

ENDPOINT = "lab"
DEVICE = "mhs://scripted/lab/bath"
CAPABILITY = "cap.thermal.setpoint.v1"
TOOL = projection_tool_name(DEVICE, CAPABILITY)


def _result(structured: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "is_error": is_error,
        "text": json.dumps(structured),
        "raw": {"isError": is_error, "structuredContent": structured},
    }


class ScriptedTransport:
    """``tool_names`` / ``call`` stand-in. Capability answers come from ``script``."""

    def __init__(
        self,
        script: list[Callable[[dict[str, Any]], dict[str, Any]] | BaseException] | None = None,
        *,
        advertise: bool = True,
    ) -> None:
        self.script = list(script or [])
        self.advertise = advertise
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.operations: dict[str, dict[str, Any]] = {}

    def tool_names(self) -> set[str]:
        names = {"mhs__inspect", "mhs__operations", "mhs__evidence"}
        if self.advertise:
            names.add(TOOL)
        return names

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = dict(arguments or {})
        self.calls.append((name, arguments))
        if name == "mhs__inspect":
            return _result({
                "inspect": {
                    "device_id": DEVICE,
                    "mode": "simulated",
                    "capabilities": [{"capability_id": CAPABILITY, "resource": "bath"}],
                }
            })
        if name == TOOL:
            if not self.script:
                raise AssertionError("unexpected capability call")
            answer = self.script.pop(0)
            if isinstance(answer, BaseException):
                raise answer
            return answer(arguments)
        if name == "mhs__operations":
            return _result({"operations": self.operations.get(str(arguments.get("operation_id")))})
        raise AssertionError(f"unexpected tool {name}")

    def capability_calls(self) -> list[dict[str, Any]]:
        return [arguments for name, arguments in self.calls if name == TOOL]


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
        return _result({"receipt": body})

    return answer


def tool_error(**payload: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def answer(arguments: dict[str, Any]) -> dict[str, Any]:
        error = {"command_id": arguments["command_id"], **payload}
        return _result({"receipt": None, "mhs_error": error}, is_error=True)

    return answer


class JournalUnknownAttemptTests(unittest.TestCase):
    """Reducer and gate: safe failures do not settle an ambiguous attempt."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-audit-journal-unknown-")
        self.addCleanup(self.tmp.cleanup)
        path = write_settings(Path(self.tmp.name), "http://127.0.0.1:9", endpoint_id=ENDPOINT)
        self.config = MHSConfig.load(path)
        self.journal = CommandJournal(self.config.command_journal_path)

    def _record(self, command_id: str, phase: str, **extra: Any) -> None:
        self.journal.append({
            "kind": "command_dispatch",
            "phase": phase,
            "command_id": command_id,
            "endpoint_id": ENDPOINT,
            "device_id": DEVICE,
            "capability_id": CAPABILITY,
            "arguments_digest": extra.pop("arguments_digest", "digest-1"),
            **extra,
        })

    def _phases(self, *phases: str, command_id: str | None = None) -> str:
        command_id = command_id or canonical.ulid()
        for phase in phases:
            self._record(command_id, phase)
        return command_id

    def _pending(self) -> list[dict[str, Any]]:
        return self.journal.unreconciled(ENDPOINT, DEVICE)

    def _invoke(self, transport: ScriptedTransport, value: float = 37.0, **kwargs: Any) -> Any:
        return invoke_via(
            transport,
            ENDPOINT,
            DEVICE,
            CAPABILITY,
            {"target_temperature": value},
            config=self.config,
            journal=self.journal,
            **kwargs,
        )

    def test_presend_error_does_not_hide_a_later_unknown(self) -> None:
        # The audit's probe: one command id, connect-time pre_send_error, then
        # a retry that is dispatched and loses its reply.
        command_id = self._phases(
            "pre_send_error", "allocated", "prepared", "dispatching", "unknown"
        )
        pending = self._pending()
        self.assertEqual([item["command_id"] for item in pending], [command_id])
        self.assertEqual(pending[0]["phase"], "unknown")
        self.assertEqual(pending[0]["state"], "unknown")
        self.assertTrue(pending[0]["reconcile_required"])
        self.assertFalse(pending[0]["retry_safe"])

        blocked = ScriptedTransport([receipt("completed")])
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(blocked, 38.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertTrue(gate.exception.reconcile_required)
        self.assertFalse(gate.exception.retry_safe)
        self.assertEqual(gate.exception.details["pending_command_ids"], [command_id])
        self.assertEqual(blocked.capability_calls(), [])
        self.assertNotIn(
            str(gate.exception.details.get("supplied_command_id")),
            {str(item.get("command_id")) for item in self.journal.records()},
        )

        # An inconclusive observation is not permission to open the gate.
        self.journal.append({
            "kind": "command_reconcile",
            "endpoint_id": ENDPOINT,
            "device_id": DEVICE,
            "command_ids": [command_id],
            "resolved_command_ids": [],
            "outcome": "inconclusive",
        })
        self.assertEqual([item["command_id"] for item in self._pending()], [command_id])

        self.journal.append({
            "kind": "command_reconcile",
            "endpoint_id": ENDPOINT,
            "device_id": DEVICE,
            "command_ids": [command_id],
            "resolved_command_ids": [command_id],
            "outcome": "reconciled",
        })
        self.assertEqual(self._pending(), [])

    def test_tool_error_does_not_hide_a_later_unknown(self) -> None:
        command_id = self._phases(
            "allocated", "prepared", "dispatching", "tool_error",
            "allocated", "prepared", "dispatching", "unknown",
        )
        pending = self._pending()
        self.assertEqual([item["command_id"] for item in pending], [command_id])
        self.assertEqual(pending[0]["state"], "unknown")
        self.assertFalse(pending[0]["retry_safe"])

    def test_safe_failure_does_not_resolve_an_earlier_ambiguous_attempt(self) -> None:
        unknown_id = self._phases(
            "allocated", "prepared", "dispatching", "unknown",
            "allocated", "pre_send_error",
        )
        tool_id = self._phases(
            "allocated", "prepared", "dispatching", "unknown",
            "allocated", "prepared", "dispatching", "tool_error",
        )
        running_id = canonical.ulid()
        for phase in ("allocated", "prepared", "dispatching", "in_flight"):
            extra = {"operation_id": "op_running"} if phase == "in_flight" else {}
            self._record(running_id, phase, **extra)
        for phase in ("allocated", "prepared", "dispatching", "tool_error"):
            self._record(running_id, phase)
        # The dispatch marker was never answered; the later pre_send_error is a
        # connect failure of the retry, not an outcome of that dispatch.
        crashed_id = self._phases(
            "allocated", "prepared", "dispatching",
            "pre_send_error",
        )
        pending = {item["command_id"]: item for item in self._pending()}
        self.assertEqual(set(pending), {unknown_id, tool_id, running_id, crashed_id})
        self.assertEqual(pending[unknown_id]["state"], "unknown")
        self.assertEqual(pending[tool_id]["state"], "unknown")
        self.assertEqual(pending[running_id]["state"], "in_flight")
        self.assertEqual(pending[running_id]["operation_id"], "op_running")
        self.assertEqual(pending[crashed_id]["state"], "dispatching")
        self.assertEqual(pending[crashed_id]["recovered_from"], "dispatching")

    def test_unanswered_dispatch_after_presend_is_reconstructed_as_unknown(self) -> None:
        command_id = self._phases(
            "pre_send_error", "allocated", "prepared", "dispatching"
        )
        pending = self._pending()
        self.assertEqual([item["command_id"] for item in pending], [command_id])
        self.assertEqual(pending[0]["phase"], "unknown")
        self.assertEqual(pending[0]["state"], "dispatching")
        self.assertEqual(pending[0]["recovered_from"], "dispatching")
        self.assertTrue(pending[0]["reconcile_required"])

    def test_later_unknown_after_a_definitive_receipt_reopens_the_gate(self) -> None:
        command_id = self._phases(
            "allocated", "prepared", "dispatching", "completed",
            "allocated", "prepared", "dispatching", "unknown",
        )
        pending = self._pending()
        self.assertEqual([item["command_id"] for item in pending], [command_id])
        self.assertEqual(pending[0]["state"], "unknown")

        blocked = ScriptedTransport([receipt("completed")])
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(blocked, 39.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertEqual(blocked.capability_calls(), [])

    def test_definitive_receipt_settles_an_earlier_unknown(self) -> None:
        command_id = self._phases(
            "allocated", "prepared", "dispatching", "unknown",
            "allocated", "prepared", "dispatching", "completed",
        )
        self.assertEqual(self._pending(), [])

        # A live same-id retry must not hide the unknown that is still open.
        live_id = self._phases(
            "allocated", "prepared", "dispatching", "unknown",
            "allocated", "prepared", "dispatching",
        )
        self.journal.mark_live(live_id)
        self.addCleanup(self.journal.clear_live, live_id)
        pending = self._pending()
        self.assertEqual([item["command_id"] for item in pending], [live_id])
        self.assertEqual(pending[0]["state"], "unknown")
        self.assertNotIn(command_id, {item["command_id"] for item in pending})

    def test_presend_alone_stays_a_safe_retry(self) -> None:
        self._phases("pre_send_error")
        self._phases("allocated", "pre_send_error")
        self._phases("allocated", "prepared", "dispatching", "tool_error")
        self.assertEqual(self._pending(), [])

    def test_rejected_retry_does_not_settle_an_ambiguous_attempt(self) -> None:
        # CORE-090/091: rejected is the retry's refusal, never the retained
        # outcome of the command that may already have taken effect.
        for outcome in ("unknown", "in_flight", "dispatching"):
            with self.subTest(outcome=outcome):
                command_id = self._phases("allocated", "prepared", "dispatching")
                if outcome != "dispatching":
                    self._record(command_id, outcome, operation_id="op_pending")
                self._phases("allocated", "prepared", "dispatching", command_id=command_id)
                self._record(command_id, "receipt", status="rejected")
                pending = {item["command_id"]: item for item in self._pending()}
                self.assertIn(command_id, pending)
                self.assertEqual(pending[command_id]["state"], outcome)

    def test_nonfinal_or_unclassified_receipt_fails_closed(self) -> None:
        for status in ("accepted", "running", "unknown", "", "invalid"):
            with self.subTest(status=status):
                command_id = self._phases("allocated", "prepared", "dispatching")
                self._record(command_id, "receipt", status=status)
                self.assertIn(command_id, {item["command_id"] for item in self._pending()})

    def test_invoke_rejected_retry_does_not_clear_a_lost_reply(self) -> None:
        refused = self._invoke(ScriptedTransport([receipt("rejected")]))
        command_id = refused["command_id"]
        self.assertEqual(self._pending(), [], "a refusal alone remains safe")

        with self.assertRaises(MCPOutcomeUnknown):
            self._invoke(ScriptedTransport([TimeoutError("lost reply")]), command_id=command_id)
        rejected = self._invoke(ScriptedTransport([receipt("rejected")]), command_id=command_id)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual([item["command_id"] for item in self._pending()], [command_id])

        blocked = ScriptedTransport([receipt("completed")])
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(blocked, 45.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertEqual(blocked.capability_calls(), [])

        final = self._invoke(
            ScriptedTransport([receipt("cancelled", replayed=True)]), command_id=command_id
        )
        self.assertEqual(final["status"], "cancelled")
        self.assertEqual(self._pending(), [])
        self.assertEqual(self._invoke(ScriptedTransport([receipt("completed")]), 45.0)["status"],
                         "completed")

    def test_rejected_operation_does_not_settle_in_flight(self) -> None:
        transport = ScriptedTransport([receipt("running", operation_id="op_pending")])
        command_id = self._invoke(transport)["command_id"]
        transport.operations["op_pending"] = {
            "operation_id": "op_pending", "command_id": command_id, "status": "rejected",
        }
        transport.script.append(receipt("completed"))
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(transport, 46.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertEqual(len(transport.capability_calls()), 1)
        self.assertEqual([item["command_id"] for item in self._pending()], [command_id])

        transport.operations["op_pending"]["status"] = "failed"
        self.assertEqual(self._invoke(transport, 46.0)["status"], "completed")
        self.assertEqual(self._pending(), [])

    def test_reconciliation_does_not_accept_rejected_outcomes(self) -> None:
        for source in ("receipts", "operations"):
            with self.subTest(source=source):
                command_id = self._phases("allocated", "prepared", "dispatching", "unknown")
                observation = {
                    "mode": "simulated", "resources": ["bath"], "state": {},
                    "observed_at": "2026-11-18T00:00:00Z",
                    "receipts": [], "operations": [], "evidence_verify": {"valid": True},
                }
                observation[source] = [{
                    "command_id": command_id, "device_id": DEVICE,
                    "capability_id": CAPABILITY, "status": "rejected",
                    "receipt_id": "r_rejected", "operation_id": "op_rejected",
                }]
                # Supply the same trusted, read-only observation twice; the
                # journal gate must still distinguish a refusal from an outcome.
                with patch("openai4s_mhs.mcp_invoke.MCPConnector"), patch(
                    "openai4s_mhs.mcp_invoke._observe_device", return_value=observation
                ):
                    result = reconcile(
                        ENDPOINT, DEVICE, config=self.config, journal=self.journal, settle_s=0.0
                    )
                self.assertEqual(result["reconcile"]["resolved_command_ids"], [])
                self.assertEqual(result["reconcile"]["outcome"], "inconclusive")
                self.assertIn(command_id, {item["command_id"] for item in self._pending()})

    def test_invoke_presend_then_lost_same_id_retry_closes_the_gate(self) -> None:
        blind = ScriptedTransport(advertise=False)
        with self.assertRaises(MCPInvokeError) as presend:
            self._invoke(blind)
        self.assertTrue(presend.exception.retry_safe)
        self.assertNotIsInstance(presend.exception, MCPOutcomeUnknown)
        command_id = str(presend.exception.command_id)
        phases = [
            item.get("phase")
            for item in self.journal.for_command(command_id)
            if item.get("kind") == "command_dispatch"
        ]
        self.assertEqual(phases, ["allocated", "pre_send_error"])
        self.assertEqual(self._pending(), [])

        # The pre-send failure itself does not block a different command.
        other = ScriptedTransport([receipt("completed")])
        done = self._invoke(other, 41.0)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(len(other.capability_calls()), 1)

        lost = ScriptedTransport([TimeoutError("lost reply")])
        with self.assertRaises(MCPOutcomeUnknown) as unknown:
            self._invoke(lost, command_id=command_id)
        self.assertEqual(unknown.exception.command_id, command_id)
        self.assertFalse(unknown.exception.retry_safe)
        self.assertTrue(unknown.exception.reconcile_required)
        pending = self._pending()
        self.assertEqual([item["command_id"] for item in pending], [command_id])
        self.assertEqual(pending[0]["state"], "unknown")

        blocked = ScriptedTransport([receipt("completed")])
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(blocked, 42.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertIn(command_id, gate.exception.details["pending_command_ids"])
        self.assertEqual(blocked.capability_calls(), [])

    def test_invoke_tool_error_then_lost_same_id_retry_closes_the_gate(self) -> None:
        transport = ScriptedTransport([
            tool_error(
                mhs_code="MHS.SESSION.EXPIRED",
                message="this call was NOT executed",
                retryable=True,
            )
        ])
        with self.assertRaises(MCPInvokeError) as failed:
            self._invoke(transport)
        self.assertTrue(failed.exception.retry_safe)
        self.assertNotIsInstance(failed.exception, MCPOutcomeUnknown)
        command_id = str(failed.exception.command_id)
        self.assertEqual(self._pending(), [])

        lost = ScriptedTransport([TimeoutError("lost reply")])
        with self.assertRaises(MCPOutcomeUnknown):
            self._invoke(lost, command_id=command_id)
        self.assertEqual([item["command_id"] for item in self._pending()], [command_id])

        # The retry's own safe tool error still does not settle the lost reply.
        expired = ScriptedTransport([
            tool_error(
                mhs_code="MHS.SESSION.EXPIRED",
                message="this call was NOT executed",
                retryable=True,
            )
        ])
        with self.assertRaises(MCPInvokeError) as again:
            self._invoke(expired, command_id=command_id)
        self.assertTrue(again.exception.retry_safe)
        self.assertEqual([item["command_id"] for item in self._pending()], [command_id])

        blocked = ScriptedTransport([receipt("completed")])
        with self.assertRaises(MCPInvokeError) as gate:
            self._invoke(blocked, 43.0)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertEqual(blocked.capability_calls(), [])

    def test_invoke_same_id_receipt_after_unknown_opens_the_gate(self) -> None:
        lost = ScriptedTransport([TimeoutError("lost reply")])
        with self.assertRaises(MCPOutcomeUnknown) as unknown:
            self._invoke(lost)
        command_id = str(unknown.exception.command_id)
        self.assertEqual([item["command_id"] for item in self._pending()], [command_id])

        settled = ScriptedTransport([receipt("completed", replayed=True)])
        receipt_body = self._invoke(settled, command_id=command_id)
        self.assertEqual(receipt_body["status"], "completed")
        self.assertEqual(settled.capability_calls()[0]["command_id"], command_id)
        self.assertEqual(self._pending(), [])

        follow = ScriptedTransport([receipt("completed")])
        done = self._invoke(follow, 44.0)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(len(follow.capability_calls()), 1)


if __name__ == "__main__":
    unittest.main()
