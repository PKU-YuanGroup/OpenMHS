"""HOST-004: append-only host ledger and portable package verification.

The invocation and the endpoint bundle both come from the real MCP path.  The
package is verified offline; altering one host record or one endpoint receipt
must invalidate it, and an ambiguous timeout must be recorded as ``unknown``.
"""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.host_evidence import (
    HostLedger,
    HostLedgerError,
    export_package,
    verify_package,
)
from openai4s_mhs.mcp_invoke import (
    CommandJournal,
    MCPConnector,
    MCPInvokeError,
    MCPOutcomeUnknown,
    export_evidence,
    invoke,
    reconcile,
)

from .hardware_endpoint import start_endpoint
from .host_remediation_support import write_settings
from .support import sdk_projection_available

CAPABILITY = "cap.world.step.v1"
PROXY = Path(__file__).with_name("lost_reply_proxy.py")


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class HostEvidencePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-host004-")
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

    def _manifest(self) -> dict:
        with MCPConnector("sim", self.config) as connector:
            response = connector.call("mhs__inspect", {"device_id": self.device_id})
        self.assertFalse(response["is_error"], response)
        return dict(response["raw"]["structuredContent"]["inspect"])

    def _package(self) -> dict:
        evidence = export_evidence("sim", config=self.config)
        return export_package(
            self.ledger,
            [evidence["bundle"]],
            manifests=[self._manifest()],
            transcript=[{"role": "test", "text": "HOST-004 package"}],
        )

    def test_package_is_valid_and_tamper_evident(self) -> None:
        receipt = invoke(
            "sim",
            self.device_id,
            CAPABILITY,
            {"ticks": 1},
            config=self.config,
            journal=self.journal,
            ledger=self.ledger,
            approvals=[{"principal": "human:test", "method": "human_click"}],
        )
        self.assertEqual(receipt["status"], "completed")
        package = self._package()
        report = verify_package(package)
        self.assertTrue(report["valid"], report)
        self.assertTrue(report["host_chain"]["valid"])
        self.assertTrue(report["endpoint_bundles"][0]["valid"])

        tampered_host = copy.deepcopy(package)
        tampered_host["host_ledger"][1]["capability_id"] = "cap.tampered.v1"
        host_report = verify_package(tampered_host)
        self.assertFalse(host_report["valid"])
        self.assertTrue(
            any(item["mhs_code"] == "MHS.EVIDENCE.CHAIN_BROKEN" for item in host_report["errors"])
        )

        tampered_endpoint = copy.deepcopy(package)
        tampered_endpoint["endpoint_bundles"][0]["receipts"][0]["status"] = "failed"
        endpoint_report = verify_package(tampered_endpoint)
        self.assertFalse(endpoint_report["valid"])
        self.assertFalse(endpoint_report["endpoint_bundles"][0]["valid"])

    def test_unknown_timeout_is_recorded_and_replay_stays_valid(self) -> None:
        before = int(reconcile("sim", self.device_id, config=self.config)["state"]["revision"])
        proxy = [
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
        with self.assertRaises(MCPOutcomeUnknown) as caught:
            invoke(
                "sim",
                self.device_id,
                CAPABILITY,
                {"ticks": 2},
                config=self.config,
                journal=self.journal,
                ledger=self.ledger,
                connector_command=proxy,
                timeout_s=1.5,
            )
        command_id = str(caught.exception.command_id)
        records = [item for item in self.ledger.records() if item.get("command_id") == command_id]
        self.assertTrue(any(item.get("outcome") == "unknown" for item in records))
        self.assertTrue(any(item.get("reconcile_required") for item in records))
        after = int(reconcile("sim", self.device_id, config=self.config)["state"]["revision"])
        self.assertEqual(after, before + 1)

        replayed = invoke(
            "sim",
            self.device_id,
            CAPABILITY,
            {"ticks": 2},
            config=self.config,
            command_id=command_id,
            journal=self.journal,
            ledger=self.ledger,
        )
        self.assertTrue(replayed.get("replayed"))
        self.assertEqual(self._revision(), after)
        package = self._package()
        report = verify_package(package)
        self.assertTrue(report["valid"], report)

    def _revision(self) -> int:
        return int(reconcile("sim", self.device_id, config=self.config)["state"]["revision"])

    def test_durable_store_failure_is_visible_and_blocks_dispatch(self) -> None:
        before = self._revision()
        with mock.patch.object(
            self.ledger,
            "append",
            side_effect=HostLedgerError(
                "MHS.HOST.EVIDENCE_WRITE_FAILED", "simulated disk full"
            ),
        ):
            with self.assertRaises(MCPInvokeError) as caught:
                invoke(
                    "sim",
                    self.device_id,
                    CAPABILITY,
                    {"ticks": 1},
                    config=self.config,
                    journal=self.journal,
                    ledger=self.ledger,
                )
        self.assertEqual(caught.exception.code, "MHS.HOST.EVIDENCE_WRITE_FAILED")
        self.assertFalse(caught.exception.retry_safe)
        self.assertEqual(self._revision(), before)


if __name__ == "__main__":
    unittest.main()
