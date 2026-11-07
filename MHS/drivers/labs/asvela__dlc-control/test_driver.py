"""Acceptance run of the DLCpro package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DlcControlCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_wavelength_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, wavelength_setpoint=1550)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["wavelength_setpoint"], 1550.0)   # the fake's placeholder, untouched

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        completed = self.configure(client, wavelength_setpoint=1550.5)
        self.assertEqual(completed["status"], "completed", completed)
        self.assertEqual(self.state(client)["wavelength_setpoint"], 1550.5)
        for value in (1499.99, 1600.01):
            refused = self.configure(client, wavelength_setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["wavelength_setpoint"], 1550.5)

    def test_the_scan_frequency_uses_the_wrapper_bound(self) -> None:
        client = self.serve()
        for value in (0.019, 400.1):
            refused = self.configure(client, scan_frequency=value)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.configure(client, scan_frequency=50)["status"], "completed")
        self.assertEqual(self.state(client)["scan_frequency"], 50.0)

    def test_the_safe_state_action_disables_the_diode_current(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, current_enabled=True)["status"], "completed")
        self.assertTrue(self.state(client)["current_enabled"])
        self.assertTrue(self.state(client)["emission"])
        stopped = client.invoke("x-cap.asvela.emission_off.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"current_enabled": False})
        self.assertFalse(self.state(client)["current_enabled"])
        self.assertFalse(self.state(client)["emission"])

    def test_the_estop_disables_the_current_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, current_enabled=True)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["current_enabled"])
        refused = self.configure(client, scan_enabled=True)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_reads_carry_the_wrapper_limits_and_user_level(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["scan_output_channel"], "PC")
        self.assertEqual(state["user_level"], 3)
        self.assertEqual(state["device_limits"]["fmin"], 0.02)
        self.assertEqual(state["device_limits"]["fmax"], 400.0)


if __name__ == "__main__":
    unittest.main()
