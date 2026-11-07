"""LEAD-HOST-JOURNAL: reconciliation gate, crash recovery, torn-tail refusal.

Every scenario uses the real connector, the real durable JSONL journal and a
real reference endpoint.  The crash case is a *separate process* that really
exits (``os._exit``) after the endpoint effect and before the host's terminal
record; the parent only has the durable journal left.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mhs import canonical
from mhs.mcp import projection_tool_name
from openai4s_mhs.config import MHSConfig
from openai4s_mhs.host_evidence import HostLedger
from openai4s_mhs.mcp_invoke import (
    CommandJournal,
    MCPConnector,
    MCPInvokeError,
    MCPOutcomeUnknown,
    invoke,
    reconcile,
)

from .hardware_endpoint import start_endpoint
from .host_remediation_support import REPO_ROOT, write_settings
from .support import sdk_projection_available

CAPABILITY = "cap.world.step.v1"
PROXY = Path(__file__).with_name("lost_reply_proxy.py")
CRASH_CHILD = Path(__file__).with_name("crash_after_effect.py")


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    parts = [
        str(REPO_ROOT / "MHS/sdk/src"),
        str(REPO_ROOT / "work/openai4s-src"),
        str(REPO_ROOT / "integration/openai4s"),
    ]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class JournalRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-host-journal-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.endpoint = start_endpoint("conveyor", mode="simulated")
        self.addCleanup(self.endpoint.close)
        self.device_id = str(self.endpoint.devices[0]["device_id"])
        self.endpoint_id = "journal"
        self.settings_path = write_settings(
            self.directory / "settings",
            self.endpoint.url,
            endpoint_id=self.endpoint_id,
        )
        self.config = MHSConfig.load(self.settings_path)
        self.journal_path = self.config.command_journal_path
        self.ledger_path = self.config.host_ledger_path

    # -- helpers -----------------------------------------------------------
    def _journal(self) -> CommandJournal:
        """A newly constructed journal: models a reload in a new object."""
        return CommandJournal(self.journal_path)

    def _observer_journal(self) -> CommandJournal:
        return CommandJournal(self.directory / "observer-journal.jsonl")

    def _revision(self) -> int:
        observed = reconcile(
            self.endpoint_id,
            self.device_id,
            config=self.config,
            journal=self._observer_journal(),
            settle_s=0.0,
        )
        return int(observed["state"]["revision"])

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

    def _lost_reply(self, ticks: int = 3) -> MCPOutcomeUnknown:
        with self.assertRaises(MCPOutcomeUnknown) as caught:
            invoke(
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                {"ticks": ticks},
                config=self.config,
                connector_command=self._proxy_command(),
                timeout_s=1.5,
            )
        return caught.exception

    # -- scenarios ---------------------------------------------------------
    def test_explicit_fresh_ulid_is_blocked_and_same_id_replays_once(self) -> None:
        before = self._revision()
        unknown = self._lost_reply(ticks=3)
        command_id = str(unknown.command_id)
        self.assertTrue(command_id)

        # The endpoint applied the effect; the host saw a lost reply.
        self.assertEqual(self._revision(), before + 1)
        pending = self._journal().unreconciled(self.endpoint_id, self.device_id)
        self.assertEqual([item["command_id"] for item in pending], [command_id])
        self.assertEqual(pending[0]["phase"], "unknown")

        # A caller-supplied fresh ULID is not a way around the gate.
        fresh = canonical.ulid()
        with self.assertRaises(MCPInvokeError) as gate:
            invoke(
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                {"ticks": 4},
                config=self.config,
                command_id=fresh,
            )
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertTrue(gate.exception.reconcile_required)
        self.assertIn(command_id, gate.exception.details["pending_command_ids"])
        self.assertNotIn(
            fresh,
            {
                str(item.get("command_id"))
                for item in self._journal().records()
            },
            "a refused command must not leave an allocated record",
        )

        # Same id, same action, same device: the one permitted replay path.
        retained = self.endpoint.server._receipts[(self.device_id, command_id)][1]
        receipt = invoke(
            self.endpoint_id,
            self.device_id,
            CAPABILITY,
            {"ticks": 3},
            config=self.config,
            command_id=command_id,
        )
        self.assertEqual(receipt["receipt_id"], retained["receipt_id"])
        self.assertTrue(receipt.get("replayed"))
        self.assertEqual(self._revision(), before + 1, "replay must not execute twice")
        self.assertEqual(
            self._journal().unreconciled(self.endpoint_id, self.device_id), []
        )

        # The host ledger recorded the ambiguous outcome and the replay receipt.
        records = HostLedger(self.ledger_path).records()
        outcomes = [item for item in records if item.get("command_id") == command_id]
        self.assertTrue(any(item.get("outcome") == "unknown" for item in outcomes))
        self.assertTrue(any(item.get("outcome") == "receipt" for item in outcomes))
        self.assertTrue(HostLedger(self.ledger_path).verify()["valid"])

    def test_reconcile_records_two_observation_evidence_and_opens_gate(self) -> None:
        unknown = self._lost_reply(ticks=2)
        command_id = str(unknown.command_id)
        observed = reconcile(
            self.endpoint_id,
            self.device_id,
            config=self.config,
            settle_s=0.0,
        )
        report = observed["reconcile"]
        self.assertEqual(report["outcome"], "reconciled")
        self.assertEqual(report["resolved_command_ids"], [command_id])
        self.assertEqual(report["observations"], 2, "one read is not evidence")
        self.assertEqual(report["remaining_command_ids"], [])
        evidence = report["evidence"][command_id]
        self.assertTrue(evidence["resolved"])
        self.assertEqual(evidence["first_operation"]["source"], "endpoint_evidence")
        self.assertEqual(evidence["first_operation"]["status"], "completed")
        self.assertEqual(
            evidence["first_operation"]["receipt_id"],
            evidence["second_operation"]["receipt_id"],
        )

        reconcile_records = [
            item
            for item in self._journal().records()
            if item.get("kind") == "command_reconcile"
        ]
        self.assertEqual(len(reconcile_records), 1)
        record = reconcile_records[0]
        self.assertEqual(record["resolved_command_ids"], [command_id])
        self.assertEqual(len(record["evidence"]["observations"]), 2)
        self.assertIsNotNone(record["evidence"]["state_revision"])
        self.assertTrue(record["evidence"]["observations"][0]["evidence_valid"])

        # The gate is open for a genuinely new command.
        before = self._revision()
        receipt = invoke(
            self.endpoint_id,
            self.device_id,
            CAPABILITY,
            {"ticks": 1},
            config=self.config,
        )
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self._revision(), before + 1)

    def test_inconclusive_reconcile_keeps_the_gate_closed(self) -> None:
        # A dispatching marker whose command never reached this endpoint: no
        # receipt and no operation can prove the outcome, so the gate must stay
        # shut even after a successful read.
        orphan = canonical.ulid()
        journal = self._journal()
        journal.append(
            {
                "kind": "command_dispatch",
                "phase": "dispatching",
                "command_id": orphan,
                "endpoint_id": self.endpoint_id,
                "device_id": self.device_id,
                "capability_id": CAPABILITY,
                "arguments_digest": canonical.digest({"ticks": 9}),
            }
        )
        observed = reconcile(
            self.endpoint_id, self.device_id, config=self.config, settle_s=0.0
        )
        report = observed["reconcile"]
        self.assertEqual(report["outcome"], "inconclusive")
        self.assertEqual(report["resolved_command_ids"], [])
        self.assertIn(orphan, report["remaining_command_ids"])
        self.assertFalse(report["evidence"][orphan]["resolved"])

        with self.assertRaises(MCPInvokeError) as gate:
            invoke(
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                {"ticks": 1},
                config=self.config,
            )
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")

    def test_torn_journal_tail_fails_closed_without_rewriting_bytes(self) -> None:
        receipt = invoke(
            self.endpoint_id,
            self.device_id,
            CAPABILITY,
            {"ticks": 1},
            config=self.config,
        )
        self.assertEqual(receipt["status"], "completed")
        before_tick = self.endpoint.spec.bridges[self.device_id].sim.tick
        with open(self.journal_path, "ab") as handle:
            handle.write(b'{"kind":"command_dispatch","phase":"dispatching"')
        torn_bytes = self.journal_path.read_bytes()

        with self.assertRaises(MCPInvokeError) as corrupt:
            self._journal().records()
        self.assertEqual(corrupt.exception.code, "MHS.HOST.JOURNAL_CORRUPT")

        with self.assertRaises(MCPInvokeError) as refused:
            invoke(
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                {"ticks": 1},
                config=self.config,
            )
        self.assertEqual(refused.exception.code, "MHS.HOST.JOURNAL_CORRUPT")
        self.assertEqual(self.journal_path.read_bytes(), torn_bytes)
        self.assertEqual(self.endpoint.spec.bridges[self.device_id].sim.tick, before_tick)

    def test_corrupt_journal_record_fails_closed(self) -> None:
        receipt = invoke(
            self.endpoint_id,
            self.device_id,
            CAPABILITY,
            {"ticks": 1},
            config=self.config,
        )
        self.assertEqual(receipt["status"], "completed")
        before_tick = self.endpoint.spec.bridges[self.device_id].sim.tick
        with open(self.journal_path, "ab") as handle:
            handle.write(b'{"kind": "command_dispatch", "phase": "dispatching", }\n')
        corrupt_bytes = self.journal_path.read_bytes()
        with self.assertRaises(MCPInvokeError) as corrupt:
            invoke(
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                {"ticks": 2},
                config=self.config,
            )
        self.assertEqual(corrupt.exception.code, "MHS.HOST.JOURNAL_CORRUPT")
        self.assertEqual(self.journal_path.read_bytes(), corrupt_bytes)
        self.assertEqual(self.endpoint.spec.bridges[self.device_id].sim.tick, before_tick)

    def test_crash_window_reopens_as_unknown_in_a_new_process(self) -> None:
        completed = invoke(
            self.endpoint_id,
            self.device_id,
            CAPABILITY,
            {"ticks": 1},
            config=self.config,
        )
        self.assertEqual(completed["status"], "completed")
        before = self._revision()

        child = subprocess.run(
            [
                sys.executable,
                "-B",
                str(CRASH_CHILD),
                str(self.settings_path),
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                "3",
            ],
            env=_child_env(),
            capture_output=True,
            text=True,
            timeout=90,
        )
        self.assertEqual(child.returncode, 17, child.stderr)

        journal = self._journal()
        records = journal.records()
        terminal_by_command: dict[str, set[str]] = {}
        for item in records:
            command = str(item.get("command_id"))
            terminal_by_command.setdefault(command, set()).add(str(item.get("phase")))
        dispatch = [
            item
            for item in records
            if item.get("phase") == "dispatching"
            and not terminal_by_command[str(item.get("command_id"))]
            & {"completed", "receipt", "tool_error", "pre_send_error", "unknown"}
        ]
        self.assertEqual(len(dispatch), 1)
        crashed_id = str(dispatch[0]["command_id"])
        terminal_phases = terminal_by_command[crashed_id]
        self.assertNotIn("completed", terminal_phases)
        self.assertNotIn("unknown", terminal_phases)
        self.assertEqual(self._revision(), before + 1, "the effect happened")

        pending = journal.unreconciled(self.endpoint_id, self.device_id)
        self.assertEqual([item["command_id"] for item in pending], [crashed_id])
        self.assertEqual(pending[0]["phase"], "unknown")
        self.assertEqual(pending[0]["recovered_from"], "dispatching")

        # A brand-new process (and a brand-new journal object in this one)
        # still sees the durable dispatch marker and refuses a new effect.
        with self.assertRaises(MCPInvokeError) as gate:
            invoke(
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                {"ticks": 2},
                config=self.config,
                command_id=canonical.ulid(),
            )
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")

        # Evidence from the endpoint (two consistent observations) reconciles it.
        observed = reconcile(
            self.endpoint_id, self.device_id, config=self.config, settle_s=0.0
        )
        self.assertEqual(observed["reconcile"]["outcome"], "reconciled")
        self.assertEqual(observed["reconcile"]["resolved_command_ids"], [crashed_id])
        receipt = invoke(
            self.endpoint_id,
            self.device_id,
            CAPABILITY,
            {"ticks": 2},
            config=self.config,
        )
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(
            self.endpoint.spec.bridges[self.device_id].sim.tick,
            before + 5,
            "the crashed effect (3) stays applied and the new command (2) applies once",
        )

    def test_command_reuse_with_different_action_is_still_refused(self) -> None:
        receipt = invoke(
            self.endpoint_id,
            self.device_id,
            CAPABILITY,
            {"ticks": 1},
            config=self.config,
        )
        with self.assertRaises(MCPInvokeError) as conflict:
            invoke(
                self.endpoint_id,
                self.device_id,
                CAPABILITY,
                {"ticks": 9},
                config=self.config,
                command_id=receipt["command_id"],
            )
        self.assertEqual(conflict.exception.code, "MHS.CONFLICT.COMMAND_ID_REUSE")


if __name__ == "__main__":
    unittest.main()
