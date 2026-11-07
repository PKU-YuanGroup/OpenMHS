"""Acceptance run of the tekinstr MDO3000 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every number below is a placeholder of fake.py, not a fact.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"

#: The fake placeholders (fake.py): the state of a freshly opened in-memory oscilloscope.
START = {
    "sample_rate": 1000000000.0,  # placeholder
    "record_length": 10000,  # placeholder
    "horizontal_scale": 1e-06,  # placeholder
    "horizontal_delay_mode": "pretrigger_percent",  # placeholder
    "acquisition_mode": "SAMPLE",  # placeholder
    "acquisition_count": 0,  # placeholder
    "num_averages": 2,  # placeholder
    "acquisition_state": "STOP",  # placeholder
    "single_acquisition": False,  # placeholder
    "trigger_state": "READY",  # placeholder
}


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

    def test_the_state_of_a_fresh_scope(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client), START)

    def test_a_write_changes_the_state_it_reports(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, acquisition_mode="AVERAGE"), "completed")
        self.assertEqual(self.configure(client, record_length=1000000), "completed")
        self.assertEqual(self.configure(client, num_averages=64), "completed")
        self.assertEqual(self.configure(client, acquisition_state="RUN"), "completed")
        self.assertEqual(self.configure(client, single_acquisition=True), "completed")
        self.assertEqual(self.configure(client, horizontal_delay_mode="delay_time"), "completed")
        state = self.state(client)
        self.assertEqual(state["acquisition_mode"], "AVERAGE")
        self.assertEqual(state["record_length"], 1000000)  # placeholder
        self.assertEqual(state["num_averages"], 64)  # placeholder
        self.assertEqual(state["acquisition_state"], "RUN")  # placeholder
        self.assertTrue(state["single_acquisition"])
        self.assertEqual(state["horizontal_delay_mode"], "delay_time")

    def test_the_front_panel_sets_are_the_envelope(self) -> None:
        client = self.serve()
        for patch in (
            {"acquisition_mode": "SINE"},
            {"record_length": 2000},
            {"num_averages": 3},
            {"horizontal_delay_mode": "center"},
            {"acquisition_state": "PAUSE"},
        ):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in (
            {"acquisition_mode": "PEAKDETECT"},
            {"record_length": 5000000},
            {"num_averages": 512},
            {"horizontal_delay_mode": "pretrigger_percent"},
            {"acquisition_state": "STOP"},
        ):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_operator_supplies_the_horizontal_scale(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, horizontal_scale=1e-06), LIMITS_UNSET)
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, horizontal_scale=1e-06), "completed")
        self.assertEqual(self.state(client, ["horizontal_scale"])["horizontal_scale"], 1e-06)  # placeholder
        for value in (5e-10, 1.5):
            self.assertEqual(self.configure(client, horizontal_scale=value), ENVELOPE, value)

    def test_the_force_trigger_action_reports_the_trigger_state(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.l-johnston.force_trigger.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"trigger_state": "TRIGGER"})  # placeholder
        self.assertEqual(self.state(client, ["trigger_state"])["trigger_state"], "TRIGGER")  # placeholder


class Safety(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_estop_stops_the_acquisition(self) -> None:
        driver = self.driver()
        driver.write("main", {"acquisition_state": "RUN"})
        self.assertEqual(driver.read("main", ["acquisition_state"])["acquisition_state"], "RUN")  # placeholder
        driver.estop("test")
        self.assertEqual(driver.read("main", ["acquisition_state"])["acquisition_state"], "STOP")  # placeholder


if __name__ == "__main__":
    unittest.main()
