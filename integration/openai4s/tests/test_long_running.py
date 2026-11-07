"""HOST-003 with long-running work, end to end through a real ``mhs.mcp`` child.

A long-running capability answers ``running`` with an ``operation_id`` at its
deadline and keeps executing (plan 3.7).  The governed wrapper journals that
receipt as ``in_flight``; no new command starts on the device until the
operation is settled -- through ``mhs__operations`` on the same connection, or
by :func:`reconcile` from the endpoint evidence after a reconnect.
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.mcp_invoke import (
    CommandJournal,
    MCPConnector,
    MCPInvokeError,
    _ConnectorTransport,
    invoke,
    invoke_via,
    reconcile,
)

from .host_remediation_support import write_settings
from .long_running_endpoint import JOB, start_job_endpoint
from .support import sdk_projection_available

#: Transport timeout 3 s -> endpoint deadline 2.4 s; the job outlives both.
TIMEOUT_MS = 3000
JOB_MS = 3500


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class LongRunningGovernedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoint = start_job_endpoint()
        self.addCleanup(self.endpoint.close)
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-long-running-")
        self.addCleanup(self.tmp.cleanup)
        path = write_settings(Path(self.tmp.name), self.endpoint.url, endpoint_id="job",
                              extra={"command_timeout_ms": TIMEOUT_MS})
        self.config = MHSConfig.load(path)
        self.journal = CommandJournal(self.config.command_journal_path)
        self.device_id = self.endpoint.device_id

    def _wait_done(self, count: int) -> None:
        deadline = time.monotonic() + 10.0
        while self.endpoint.bridge.done < count:
            if time.monotonic() > deadline:
                self.fail("the job did not finish")
            time.sleep(0.05)

    def test_running_receipt_blocks_until_reconciled_from_evidence(self) -> None:
        started = invoke("job", self.device_id, JOB, {"ms": JOB_MS}, config=self.config,
                         journal=self.journal)
        self.assertEqual(started["status"], "running", started)
        self.assertTrue(started["operation_id"])
        pending = self.journal.unreconciled("job", self.device_id)
        self.assertEqual([(item["state"], item["operation_id"]) for item in pending],
                         [("in_flight", started["operation_id"])])

        with self.assertRaises(MCPInvokeError) as gate:
            invoke("job", self.device_id, JOB, {"ms": 10}, config=self.config, journal=self.journal)
        self.assertEqual(gate.exception.code, "MHS.HOST.RECONCILE_REQUIRED")
        self.assertEqual(self.endpoint.bridge.done, 0, "nothing new was sent")

        self._wait_done(1)
        observed = reconcile("job", self.device_id, config=self.config, journal=self.journal,
                             settle_s=0.1)
        self.assertEqual(observed["reconcile"]["outcome"], "reconciled", observed["reconcile"])
        evidence = observed["reconcile"]["evidence"][started["command_id"]]
        self.assertEqual(evidence["first_operation"]["status"], "completed")
        self.assertEqual(evidence["first_operation"]["source"], "endpoint_evidence")

        after = invoke("job", self.device_id, JOB, {"ms": 10}, config=self.config,
                       journal=self.journal)
        self.assertEqual(after["status"], "completed")
        self.assertEqual(self.endpoint.bridge.done, 2)

    def test_same_connection_settles_through_operations_get(self) -> None:
        with MCPConnector("job", self.config) as connector:
            transport = _ConnectorTransport(connector)
            started = invoke_via(transport, "job", self.device_id, JOB, {"ms": JOB_MS},
                                 config=self.config, journal=self.journal)
            self.assertEqual(started["status"], "running", started)
            self._wait_done(1)
            after = invoke_via(transport, "job", self.device_id, JOB, {"ms": 10},
                               config=self.config, journal=self.journal)
        self.assertEqual(after["status"], "completed", after)
        settled = [item for item in self.journal.records() if item.get("kind") == "command_reconcile"]
        self.assertEqual(len(settled), 1)
        self.assertEqual(settled[0]["source"], "operations.get")
        self.assertEqual(settled[0]["evidence"]["operation_id"], started["operation_id"])
        self.assertEqual(settled[0]["evidence"]["status"], "completed")
        self.assertEqual(self.journal.unreconciled("job", self.device_id), [])


if __name__ == "__main__":
    unittest.main()
