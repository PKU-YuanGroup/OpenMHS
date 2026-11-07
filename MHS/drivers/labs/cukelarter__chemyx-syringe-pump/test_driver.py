"""Acceptance run of the CHEMYX syringe pump package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Commands(unittest.TestCase):
    """The command text the upstream methods assemble, checked on the lines the fake received."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_setters_assemble_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.set_units("mL/hr")
        driver.set_diameter(20.0)
        driver.set_rate(2.5)
        driver.set_volume(3.0)
        driver.set_delay(0.25)
        driver.set_time(60.0)
        self.assertEqual(driver.native._sent, [
            "set units 1",
            "set diameter 20.0",
            "set rate 2.5",
            "set volume 3.0",
            "set delay 0.25",
            "set time 60.0",
        ])

    def test_the_queries_are_the_query_words_of_the_clone(self) -> None:
        driver = self.driver()
        driver.read("main")
        self.assertEqual(driver.native._sent, [
            "pump status",
            "view parameter",
            "read limit parameter",
            "dispensed volume",
            "elapsed time",
        ])

    def test_start_and_the_estop_send_start_and_stop(self) -> None:
        driver = self.driver()
        driver.start_run()
        driver.estop("test")
        self.assertEqual(driver.native._sent, ["start ", "stop "])
        self.assertEqual(driver.read("main", ["pump_status"]), {"pump_status": "stopped"})


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_numeric_writes_are_operator_required(self) -> None:
        client = self.serve()
        for patch in ({"diameter": 28.6}, {"rate": 1.0}, {"volume": 1.0}, {"delay": 0.5}, {"time": 1.0}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_supplies_and_narrows_the_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"diameter": 60.0}, {"rate": 11.0}, {"volume": 11.0}, {"delay": 601.0},
                      {"time": 3601.0}, {"units": "L/hr"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"units": "mL/min"}, {"diameter": 28.6}, {"rate": 1.0}, {"volume": 1.0},
                      {"delay": 0.5}, {"time": 1.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
