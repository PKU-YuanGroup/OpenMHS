"""HOST-003: durable command ids, UNKNOWN and replay through real MCP.

The lost-reply fixture is a real MCP proxy between OpenAI4S's ``MCPConnection``
and a real ``mhs.mcp`` process: the command reaches the reference endpoint, its
receipt is produced, and the proxy drops that one reply.  The wrapper must not
pretend this is a retryable transport error; it must journal the ambiguous
outcome and a retry with the same command id must replay the retained receipt
with no second effect.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.host_evidence import HostLedger
from openai4s_mhs.mcp_invoke import (
    CommandJournal,
    MCPInvokeError,
    MCPOutcomeUnknown,
    invoke,
    reconcile,
)

from .hardware_endpoint import start_endpoint
from .host_remediation_support import write_settings
from .support import sdk_projection_available

CAPABILITY = "cap.world.step.v1"
PROXY = Path(__file__).with_name("lost_reply_proxy.py")


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class GovernedInvokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-host003-")
        self.addCleanup(self.tmp.cleanup)
        self.endpoint = start_endpoint("conveyor", mode="simulated")
        self.addCleanup(self.endpoint.close)
        self.device_id = str(self.endpoint.devices[0]["device_id"])
        self.settings_path = write_settings(
            Path(self.tmp.name) / "settings",
            self.endpoint.url,
            endpoint_id="sim",
            allow_hardware=False,
        )
        self.config = MHSConfig.load(self.settings_path)
        self.journal = CommandJournal(self.config.command_journal_path)
        self.ledger = HostLedger(self.config.host_ledger_path)
        self.addCleanup(self.ledger.close)

    def _proxy_command(self) -> list[str]:
        return [
            sys.executable,
            str(PROXY),
            "--",
            sys.executable,
            "-m",
            "mhs.mcp",
            "--endpoint",
            self.endpoint.url,
            "--config",
            str(self.settings_path),
        ]

    def _revision(self) -> int:
        return int(reconcile("sim", self.device_id, config=self.config)["state"]["revision"])

    def test_lost_reply_is_unknown_then_same_id_replays_without_second_effect(self) -> None:
        before = self._revision()
        with self.assertRaises(MCPOutcomeUnknown) as caught:
            invoke(
                "sim",
                self.device_id,
                CAPABILITY,
                {"ticks": 3},
                config=self.config,
                journal=self.journal,
                ledger=self.ledger,
                connector_command=self._proxy_command(),
                timeout_s=1.5,
            )
        unknown = caught.exception
        self.assertEqual(unknown.code, "MHS.OUTCOME.UNKNOWN")
        self.assertTrue(unknown.reconcile_required)
        self.assertFalse(unknown.retry_safe)
        self.assertTrue(unknown.command_id)
        command_id = str(unknown.command_id)

        phases = [item.get("phase") for item in self.journal.for_command(command_id)]
        self.assertIn("allocated", phases)
        self.assertIn("dispatching", phases)
        self.assertIn("unknown", phases)

        # A *new* command on this device is blocked until reconciliation; a
        # same-id retry is the only safe way to re-issue the unknown command.
        with self.assertRaises(MCPInvokeError) as gate:
            invoke(
                "sim",
                self.device_id,
                CAPABILITY,
                {"ticks": 4},
                config=self.config,
                journal=self.journal,
                ledger=self.ledger,
            )
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertTrue(gate.exception.reconcile_required)

        after = self._revision()
        self.assertEqual(after, before + 1, "the lost reply's effect was applied")

        retained = self.endpoint.server._receipts[(self.device_id, command_id)][1]
        self.assertEqual(retained["status"], "completed")

        receipt = invoke(
            "sim",
            self.device_id,
            CAPABILITY,
            {"ticks": 3},
            config=self.config,
            command_id=command_id,
            journal=self.journal,
            ledger=self.ledger,
        )
        self.assertEqual(receipt["command_id"], command_id)
        self.assertEqual(receipt["receipt_id"], retained["receipt_id"])
        self.assertTrue(receipt.get("replayed"))
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self._revision(), after, "replay must not execute twice")

        # The host ledger recorded both the intent and the ambiguous outcome.
        outcomes = [
            item
            for item in self.ledger.records()
            if item.get("command_id") == command_id
        ]
        self.assertTrue(any(item.get("outcome") == "unknown" for item in outcomes))
        self.assertTrue(any(item.get("outcome") == "receipt" for item in outcomes))
        self.assertTrue(self.ledger.verify()["valid"])

    def test_presend_failure_is_safe_to_retry_and_has_no_effect(self) -> None:
        before = self._revision()
        bad = [
            sys.executable,
            "-m",
            "mhs.mcp",
            "--endpoint",
            "http://127.0.0.1:1",
            "--config",
            str(self.settings_path),
        ]
        with self.assertRaises(MCPInvokeError) as caught:
            invoke(
                "sim",
                self.device_id,
                CAPABILITY,
                {"ticks": 1},
                config=self.config,
                journal=self.journal,
                ledger=self.ledger,
                connector_command=bad,
                timeout_s=3.0,
            )
        error = caught.exception
        self.assertNotIsInstance(error, MCPOutcomeUnknown)
        self.assertTrue(error.retry_safe)
        self.assertEqual(error.code, "MHS.TRANSPORT.UNAVAILABLE")
        self.assertEqual(self._revision(), before)
        phases = [item.get("phase") for item in self.journal.records()]
        self.assertIn("pre_send_error", phases)

    def test_command_id_reuse_with_different_input_is_refused(self) -> None:
        receipt = invoke(
            "sim",
            self.device_id,
            CAPABILITY,
            {"ticks": 1},
            config=self.config,
            journal=self.journal,
            ledger=self.ledger,
        )
        with self.assertRaises(MCPInvokeError) as caught:
            invoke(
                "sim",
                self.device_id,
                CAPABILITY,
                {"ticks": 99},
                config=self.config,
                command_id=receipt["command_id"],
                journal=self.journal,
                ledger=self.ledger,
            )
        self.assertEqual(caught.exception.code, "MHS.CONFLICT.COMMAND_ID_REUSE")

    def test_successful_invoke_and_reconcile(self) -> None:
        before = self._revision()
        receipt = invoke(
            "sim",
            self.device_id,
            CAPABILITY,
            {"ticks": 2},
            config=self.config,
            journal=self.journal,
            ledger=self.ledger,
        )
        self.assertEqual(receipt["status"], "completed")
        state = reconcile("sim", self.device_id, config=self.config)
        self.assertEqual(state["state"]["revision"], before + 1)
        self.assertEqual(state["state"]["state"]["tick"], 2)
        self.assertIsInstance(state["operations"], (list, dict, type(None)))


if __name__ == "__main__":
    unittest.main()
