"""Acceptance run of the Prior ProScan III package: the gate, plus cases for this driver.

The package is blocked: the upstream class has no stop, abort or position query, and close() only closes the
serial connection.  The cases below exercise the move contract on the fake and the honest e-stop failure; the
model review (2026-11-05) added the unknown outcome of a reply other than R, the failure of a move on a closed port
and the terminal refusal of a reset after the e-stop.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.vstevensf.move_xy.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
UNKNOWN = "MHS.OUTCOME.UNKNOWN"
SHIM_FAILED = "MHS.ADAPTER.SHIM_FAILED"
RESET_REFUSED = "MHS.SAFETY.RESET_REFUSED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PriorProScanCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def overlay(self):
        return str(HERE / "site-limits.example.json")

    def test_a_move_waits_for_the_site(self) -> None:
        client, fake = self.serve()
        refused = client.invoke(MOVE, {"x": 10, "y": 20}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, refused)
        self.assertEqual(fake._moves, 0)

    def test_the_example_overlay_reaches_the_fake(self) -> None:
        client, fake = self.serve(site_limits=self.overlay())
        moved = client.invoke(MOVE, {"x": 10, "y": -20}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"x": 10.0, "y": -20.0}, moved)
        self.assertEqual(fake._moves, 1)
        self.assertEqual(fake._last_target, {"x": 10.0, "y": -20.0})

    def test_out_of_envelope_is_refused_without_a_native_move(self) -> None:
        client, fake = self.serve(site_limits=self.overlay())
        for target in ({"x": 1001, "y": 0}, {"x": 0, "y": -1001}):
            refused = client.invoke(MOVE, target, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        self.assertEqual(fake._moves, 0)

    def test_the_estop_reports_unreached_and_latches(self) -> None:
        client, fake = self.serve(site_limits=self.overlay())
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertTrue(fake._closed)
        self.assertGreaterEqual(fake._close_calls, 1)
        refused = client.invoke(MOVE, {"x": 10, "y": -20}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(fake._moves, 0)

    def test_a_move_after_the_fake_close_raises(self) -> None:
        # Fake-only: OSError is the fake's placeholder for the serial library's closed-port error (outside the clone).
        _client, fake = self.serve()
        fake.close()
        with self.assertRaises(OSError):
            fake.move_to({"x": 1, "y": 2})

    def test_a_reply_other_than_r_is_an_unknown_outcome(self) -> None:
        # validate_response raises RuntimeError only after writing the command (proscan.py:79-115): E,2 is a reply
        # the upstream names (proscan.py:99-100), and b"" stands for a read that returned nothing.
        for reply in (b"E,2\r", b""):
            client, fake = self.serve(site_limits=self.overlay())
            fake._reply = reply
            moved = client.invoke(MOVE, {"x": 10, "y": -20}, **self.ids)
            self.assertEqual(moved["status"], "unknown", moved)
            self.assertEqual(moved["error"]["mhs_code"], UNKNOWN, moved)
            self.assertEqual(fake._moves, 1)

    def test_a_move_on_a_closed_port_fails_without_a_write(self) -> None:
        client, fake = self.serve(site_limits=self.overlay())
        fake.close()
        moved = client.invoke(MOVE, {"x": 10, "y": -20}, **self.ids)
        self.assertEqual(moved["status"], "failed", moved)
        self.assertEqual(moved["error"]["mhs_code"], SHIM_FAILED, moved)
        self.assertEqual(fake._moves, 0)

    def test_a_reset_after_the_estop_is_refused_as_terminal(self) -> None:
        client, fake = self.serve(site_limits=self.overlay())
        client.estop("test", **self.ids)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "rejected", reset)
        self.assertEqual(reset["error"]["mhs_code"], RESET_REFUSED, reset)
        self.assertEqual(reset["error"]["details"]["reason"], "terminal_estop", reset)
        refused = client.invoke(MOVE, {"x": 10, "y": -20}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(fake._moves, 0)


if __name__ == "__main__":
    unittest.main()
