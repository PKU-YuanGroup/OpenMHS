"""Acceptance run of the Cetoni package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PUMP = "cap.actuation.pump.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DirectState(unittest.TestCase):
    """The setters and getters of the driver on the fake, without the runtime's limit layer."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_reads_and_writes_are_observable(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["current_position"], 0)
        self.assertEqual(state["target_position"], 0)
        self.assertEqual(state["status"], 1079)                 # placeholder ready state
        self.assertEqual(state["valve_position"], "closed")

        driver.write("main", {"velocity": 1000})
        self.assertEqual(driver.read("main", ["velocity"]), {"velocity": 1000})

        driver.write("main", {"flow_rate": 25.0})
        flow = driver.read("main", ["flow_rate"])["flow_rate"]
        self.assertAlmostEqual(flow, 25.0, places=6)

        driver.write("main", {"target_position": 10})
        self.assertEqual(driver.read("main", ["target_position"]), {"target_position": 10})

        driver.write("main", {"valve_position": "output"})
        self.assertEqual(driver.read("main", ["valve_position"]), {"valve_position": "output"})
        driver.write("main", {"valve_position": "input"})
        self.assertEqual(driver.read("main", ["valve_position"]), {"valve_position": "input"})


class RuntimeCases(unittest.TestCase):
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

    def test_the_numeric_bounds_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, velocity=1000)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

        refused = client.invoke(PUMP, {"flow_rate": 25.0, "direction": "forward", "volume": 100.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(client.read("main", **self.ids)["state"]["current_position"], 0)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, velocity=1000)["status"], "completed")
        self.assertEqual(self.configure(client, flow_rate=25.0)["status"], "completed")
        self.assertEqual(self.configure(client, target_position=10)["status"], "completed")
        self.assertEqual(self.configure(client, valve_position="input")["status"], "completed")
        for patch in ({"velocity": 0}, {"velocity": 1000001}, {"flow_rate": 4.0}, {"flow_rate": 51.0},
                      {"target_position": -1000001}, {"target_position": 1000001}, {"valve_position": "closed"}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_pump_moves_the_fake_and_reports_the_volume(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        aspirated = client.invoke(PUMP, {"flow_rate": 25.0, "direction": "reverse", "volume": 100.0}, **self.ids)
        self.assertEqual(aspirated["status"], "completed")
        self.assertEqual(aspirated["output"]["dispensed_volume"], 100.0)
        self.assertLess(client.read("main", **self.ids)["state"]["current_position"], 0)

        dispensed = client.invoke(PUMP, {"flow_rate": 10.0, "direction": "forward", "volume": 50.0}, **self.ids)
        self.assertEqual(dispensed["status"], "completed")
        self.assertEqual(dispensed["output"]["dispensed_volume"], 50.0)

    def test_the_estop_disables_the_drive_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(client.invoke(PUMP, {"flow_rate": 25.0, "direction": "forward", "volume": 50.0},
                                       **self.ids)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke(PUMP, {"flow_rate": 25.0, "direction": "forward", "volume": 50.0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
