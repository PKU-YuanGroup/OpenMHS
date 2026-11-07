"""Acceptance run of the DG4202 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"

#: The fake placeholders (fake.py): a channel of the generator in its power-on-like state.
START = {"identity": "RIGOL TECHNOLOGIES,DG4202,FAKE000000,00.01.00", "output": False, "function": "SIN",
         "frequency": 1000.0, "amplitude": 1.0, "amplitude_unit": "VPP", "duty_cycle": 50.0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def state(self, client, fields=None):
        return client.read("main", fields=fields, **self.ids)["state"]

    def test_the_state_of_the_served_channel(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client), START)

    def test_a_write_changes_the_state_it_reports(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, output=True), "completed")
        self.assertEqual(self.configure(client, function="SQU"), "completed")
        self.assertEqual(self.configure(client, duty_cycle=25.0), "completed")
        state = self.state(client)
        self.assertEqual((state["output"], state["function"], state["duty_cycle"]), (True, "SQU", 25.0))
        self.assertEqual(self.configure(client, output=False), "completed")
        self.assertFalse(self.state(client, ["output"])["output"])

    def test_the_bounds_of_the_upstream_code(self) -> None:
        client = self.serve()
        for patch in ({"duty_cycle": -0.5}, {"duty_cycle": 100.5}, {"function": "TRI"}, {"function": "USER"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"duty_cycle": 12.5}, {"function": "RAMP"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_operator_supplies_the_frequency_and_amplitude_ranges(self) -> None:
        client = self.serve()
        for patch in ({"frequency": 1000.0}, {"amplitude": 0.5}):
            self.assertEqual(self.configure(client, **patch), LIMITS_UNSET, patch)
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"frequency": 1000.0}, {"amplitude": 0.5}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        state = self.state(client)
        self.assertEqual((state["frequency"], state["amplitude"]), (1000.0, 0.5))
        for patch in ({"frequency": 0.5}, {"frequency": 20000001.0}, {"amplitude": -0.5}, {"amplitude": 2.5}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        self.assertEqual(self.state(client, ["frequency", "amplitude"]),
                         {"frequency": 1000.0, "amplitude": 0.5})


class Safety(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_estop_switches_both_channels_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True})
        driver.write("main", {"duty_cycle": 25.0})
        self.assertTrue(driver.read("main", ["output"])["output"])
        driver.estop("test")
        self.assertFalse(driver.read("main", ["output"])["output"])
        self.assertEqual([driver.native._state[channel]["output"] for channel in (1, 2)], ["OFF", "OFF"])
        self.assertEqual(driver.native._state[1]["square_duty_cycle_percent"], 25.0)

    def test_the_identity_is_the_generator_of_this_driver(self) -> None:
        driver = self.driver()
        self.assertTrue(driver.read("main", ["identity"])["identity"].startswith("RIGOL TECHNOLOGIES,DG4202,"))


if __name__ == "__main__":
    unittest.main()
