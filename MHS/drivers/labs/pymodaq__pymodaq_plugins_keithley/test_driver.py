"""Acceptance run of the Keithley 2100 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NativeCalls(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_call_the_upstream_methods(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["identification"], "Keithley Instruments,2100,0000000,1.0")
        self.assertEqual(state["card"], "NONE")
        self.assertEqual(state["error"], '0,"No error"')
        self.assertEqual(state["reading"], 1.0)
        self.assertEqual(state["mode"], "unknown")
        self.assertEqual(driver.native.read_calls, 1)

    def test_a_mode_write_reaches_set_mode_and_the_state(self) -> None:
        driver = self.driver()
        driver.write("main", {"mode": "VAC"})
        self.assertEqual(driver.native.written_modes[-1], "VAC")
        self.assertEqual(driver.read("main")["mode"], "VAC")

    def test_the_native_reset_is_the_stop(self) -> None:
        driver = self.driver()
        driver.write("main", {"mode": "VDC"})
        driver.estop("test")
        self.assertGreaterEqual(driver.native.reset_calls, 1)
        self.assertEqual(driver.read("main")["mode"], "unknown")


class Capabilities(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def test_the_documented_mode_set_is_enforced(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"mode": "OHM"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        for mode in ("VDC", "VAC", "IDC", "IAC", "R2W", "R4W"):
            receipt = client.invoke("cap.device.configure.v1", {"mode": mode}, **self.ids)
            self.assertEqual(receipt["status"], "completed", receipt)

    def test_the_reset_action_reports_the_native_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.pymodaq.keithley2100_reset.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"reset": True})
        state = client.read("main", **self.ids)
        self.assertEqual(state["state"]["mode"], "unknown")

    def test_the_example_overlay_narrows_the_mode_set(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = client.invoke("cap.device.configure.v1", {"mode": "IAC"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        accepted = client.invoke("cap.device.configure.v1", {"mode": "VDC"}, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)


if __name__ == "__main__":
    unittest.main()
