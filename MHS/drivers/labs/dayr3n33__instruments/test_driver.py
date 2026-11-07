"""Acceptance run of the Ismatec package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The package is blocked (model review, 2026-11-05): nothing confirms
the upstream stop, so the e-stop reports SAFE_STATE_UNREACHED and the gate fails G3 (SAFE-045); test_gate fails while
the package is blocked, by design.  The other cases describe the blocked package as it is.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
START = "x-cap.dayr3n33.start_pump.v1"
STOP = "x-cap.dayr3n33.stop_pump.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class IsmatecCases(unittest.TestCase):
    def serve(self, site_limits=None, **options):
        driver = load_driver(HERE, backend="fake", options=options)
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.fake = driver.native
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_setpoint_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, setpoint=42)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["rate"], 0.0)      # the fake's placeholder start speed
        self.assertNotIn("1S00042\r", self.fake.written)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=42.9)["status"], "completed")
        self.assertEqual(self.state(client)["setpoint"], 42)   # the upstream's int() conversion
        self.assertIn("1S00042\r", self.fake.written)          # '1S' + str(int(val)).zfill(5), ismatec.py:50-53
        for value in (-1, 101):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["setpoint"], 42)

    def test_start_and_stop_report_only_the_written_command(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=42)["status"], "completed")
        started = client.invoke(START, {}, **self.ids)
        self.assertEqual(started["output"], {"written": True}, started)
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["output"], {"written": True}, stopped)
        self.assertLess(self.fake.written.index("1H\r"), self.fake.written.index("1I\r"))
        # The clone does not say what the pump answers to '1S' after a stop; the fake keeps the set speed, so a
        # read after a stop is no evidence that the pump stopped.
        self.assertEqual(self.state(client)["rate"], 42.0)

    def test_the_estop_is_unconfirmed_and_stays_latched(self) -> None:
        # Model review (2026-11-05): the upstream reads no reply to 1I and has no run-state query, so the e-stop
        # queues 1I and still reports SAFE_STATE_UNREACHED with the latch held.
        client = self.serve()
        self.assertEqual(client.invoke(START, {}, **self.ids)["status"], "completed")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertFalse(stopped["output"]["safe_state_achieved"], stopped)
        self.assertEqual(stopped["output"]["safe_state"]["achieved_by"], [], stopped)
        self.assertIn("1I\r", self.fake.written)               # the stop was still sent as a best effort
        self.assertTrue(client.safety_status(device_id=self.ids["device_id"])["estop"]["engaged"])
        for capability in (START, STOP):
            refused = client.invoke(capability, {}, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_after_the_worker_ends_the_stop_is_never_written(self) -> None:
        # An empty reply (the pump did not answer within timeout=0.5) makes float() raise in the upstream worker,
        # which ends its thread; stop() still returns normally and the stop stays queued for ever.
        client = self.serve(reply="")
        self.fake.get_flowrate()
        self.assertFalse(self.fake.worker_alive)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertNotIn("1I\r", self.fake.written)
        self.assertIn({"command": "stop"}, self.fake.pending)

    def test_a_read_after_the_worker_ended_is_unknown(self) -> None:
        # The pump answers only '*', which strip('*') turns into '' (ismatec.py:57): the worker ends and the
        # driver's bounded wait for the callback reports an unknown outcome (about 5 s).
        driver = load_driver(HERE, backend="fake", options={"reply": "*\r\n"})
        self.addCleanup(driver.close)
        with self.assertRaises(MHSError) as caught:
            driver.read("main")
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")
        self.assertFalse(driver.native.worker_alive)

    def test_a_non_finite_speed_reply_fails(self) -> None:
        driver = load_driver(HERE, backend="fake", options={"reply": "nan\r\n"})
        self.addCleanup(driver.close)
        with self.assertRaises(MHSError) as caught:
            driver.read("main")
        self.assertEqual(caught.exception.code, "MHS.DEVICE.FAULTED")


if __name__ == "__main__":
    unittest.main()
