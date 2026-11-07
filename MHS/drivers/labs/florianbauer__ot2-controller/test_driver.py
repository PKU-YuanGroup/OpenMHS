"""Acceptance run of the OT-2 controller package: the gate plus cases for this driver's own paths.

The gate call is required and is never removed.  The other cases use only the fake backend and in-process
transport; nothing here talks to an OT-2 or opens a network connection.

Model review (2026-11-05): the package is blocked because the upstream has no stop for a running protocol, so the
stock gate case fails (G3 SAFE-045) until a source-backed stop exists; the e-stop case expects
SAFE_STATE_UNREACHED with the latch held.
"""

import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
RUN = "cap.process.run.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
UNKNOWN = "MHS.OUTCOME.UNKNOWN"
FAULTED = "MHS.DEVICE.FAULTED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Ot2ControllerCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def start(self, client, payload):
        # A short deadline makes a long run answer "running" at once instead of blocking the caller to its end.
        return client.invoke(RUN, payload, deadline_ms=300, **self.ids)

    def settle(self, client, receipt, timeout=10.0):
        """Poll a long-running run until it leaves accepted/running (``unknown`` included, which wait() skips)."""
        deadline = time.monotonic() + timeout
        while receipt.get("status") in ("accepted", "running") and time.monotonic() < deadline:
            time.sleep(0.02)
            receipt = client.get_operation(receipt["operation_id"], session_id=self.ids["session_id"])
        return receipt

    def run_to_end(self, client, payload):
        return self.settle(client, self.start(client, payload))

    def wait_started(self, fake, count=1, timeout=5.0):
        deadline = time.monotonic() + timeout
        while len(fake._runs) < count and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(len(fake._runs), count, fake._runs)

    def test_reads_follow_the_upstream(self) -> None:
        client, _fake = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertIn("Device IP:", state["connection"])
        # The upstream filter tests "demo_protocol.py\n" before stripping it, so nothing is listed (line 54).
        self.assertEqual(state["available_protocols"], [])

    def test_a_simulated_run_with_status_zero_completes(self) -> None:
        client, fake = self.serve()
        receipt = self.run_to_end(client, {"recipe_ref": "demo_protocol.py", "dry_run": True})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["exit_code"], 0)
        self.assertEqual(fake._runs, [("demo_protocol.py", True)])

    def test_an_executed_run_with_a_nonzero_status_fails_with_the_native_code(self) -> None:
        client, fake = self.serve()
        fake._exit_status = 1                            # placeholder: a protocol that raised
        receipt = self.run_to_end(client, {"recipe_ref": "demo_protocol.py"})
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED), receipt)
        self.assertEqual(receipt["error"]["details"]["native_code"], 1)
        self.assertEqual(fake._runs, [("demo_protocol.py", False)])

    def test_a_simulation_the_upstream_reports_unsuccessful_fails(self) -> None:
        client, fake = self.serve()
        fake._exit_status = 2                            # placeholder; the upstream raises ValueError (130-131)
        receipt = self.run_to_end(client, {"recipe_ref": "demo_protocol.py", "dry_run": True})
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("failed", FAULTED), receipt)

    def test_a_run_whose_channel_closes_without_a_status_is_unknown(self) -> None:
        client, fake = self.serve()
        fake._run_seconds = 5.0                          # placeholder: long enough to drop the link mid-run
        receipt = self.start(client, {"recipe_ref": "demo_protocol.py"})
        self.assertEqual(receipt["status"], "running", receipt)
        self.wait_started(fake)
        fake.ssh.close()                                 # the link drops without an e-stop
        receipt = self.settle(client, receipt)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", UNKNOWN), receipt)
        self.assertEqual(receipt["error"]["details"]["native_code"], -1)

    def test_a_run_that_raises_after_it_started_is_unknown_not_a_failed_simulation(self) -> None:
        # UnicodeDecodeError is a ValueError subclass: reading undecodable remote output while opentrons.execute
        # runs must not be taken for the upstream's "simulation not successful" ValueError (lines 130-131).
        for dry_run in (False, True):
            client, fake = self.serve()
            fake._fail = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "placeholder")
            receipt = self.run_to_end(client, {"recipe_ref": "demo_protocol.py", "dry_run": dry_run})
            self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", UNKNOWN),
                             (dry_run, receipt))

    def test_protocol_names_outside_the_plain_file_pattern_are_refused_before_the_native_call(self) -> None:
        client, fake = self.serve()
        for name in ("demo_protocol.py; reboot", "../demo_protocol.py", "-demo_protocol.py", "demo protocol.py",
                     "demo_protocol.py && rm x.py", "$(reboot).py", "demo_protocol.sh"):
            receipt = self.start(client, {"recipe_ref": name})
            self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("rejected", INPUT_INVALID),
                             (name, receipt))
        self.assertEqual(fake._runs, [])

    def test_a_running_protocol_cannot_be_cancelled(self) -> None:
        client, fake = self.serve()
        fake._run_seconds = 1.0                          # placeholder
        receipt = self.start(client, {"recipe_ref": "demo_protocol.py", "dry_run": True})
        self.assertEqual(receipt["status"], "running", receipt)
        self.wait_started(fake)
        # No line of the clone stops a running protocol, so a cancel request is refused rather than answered
        # "cancelled" for a run that goes on.
        with self.assertRaises(MHSError) as refused:
            client.cancel(receipt["operation_id"], session_id=self.ids["session_id"])
        self.assertEqual(refused.exception.code, "MHS.OPERATION.NOT_CANCELLABLE")
        self.assertEqual(self.settle(client, receipt)["status"], "completed")

    def test_the_estop_is_unreached_and_keeps_the_latch(self) -> None:
        client, fake = self.serve()
        stopped = client.estop("unit test", **self.ids)
        self.assertEqual((stopped["status"], stopped["error"]["mhs_code"]), ("failed", UNREACHED), stopped)
        self.assertIs(stopped["output"]["safe_state_achieved"], False, stopped)
        self.assertTrue(fake.ssh.closed)                 # the e-stop still closed this driver's channel
        refused = self.start(client, {"recipe_ref": "demo_protocol.py", "dry_run": True})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP), refused)
        self.assertEqual(fake._runs, [])

    def test_an_estop_during_a_run_leaves_the_run_unknown(self) -> None:
        for dry_run in (False, True):
            client, fake = self.serve()
            fake._run_seconds = 5.0                      # placeholder
            receipt = self.start(client, {"recipe_ref": "demo_protocol.py", "dry_run": dry_run})
            self.assertEqual(receipt["status"], "running", receipt)
            self.wait_started(fake)
            stopped = client.estop("unit test", **self.ids)
            self.assertEqual((stopped["status"], stopped["error"]["mhs_code"]), ("failed", UNREACHED), stopped)
            receipt = self.settle(client, receipt)
            # Not completed and not cancelled: the remote opentrons process is not shown to stop.
            self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", UNKNOWN),
                             (dry_run, receipt))
            refused = self.start(client, {"recipe_ref": "demo_protocol.py"})
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP), refused)
            self.assertEqual(len(fake._runs), 1)


if __name__ == "__main__":
    unittest.main()
