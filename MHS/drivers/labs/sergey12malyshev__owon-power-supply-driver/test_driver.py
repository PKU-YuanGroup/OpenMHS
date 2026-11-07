"""Acceptance run of the OWON package: the gate, plus cases for what is specific to this driver.

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


class OwonCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def write(self, client, **patch):
        return client.write("main", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_numeric_bounds_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"voltage_setpoint": 12.0}, {"current_setpoint": 1.0},
                      {"voltage_limit": 12.0}, {"current_limit": 1.0}):
            refused = self.write(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        state = self.state(client)
        self.assertEqual(state["voltage_setpoint"], 5.0)        # placeholder, untouched
        self.assertEqual(state["current_setpoint"], 0.5)        # placeholder, untouched
        self.assertEqual(state["voltage_limit"], 10.0)          # placeholder, untouched
        self.assertEqual(state["current_limit"], 2.0)           # placeholder, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.write(client, voltage_setpoint=12.5)["status"], "completed")
        self.assertEqual(self.write(client, current_setpoint=1.0)["status"], "completed")
        self.assertEqual(self.write(client, voltage_limit=12.0)["status"], "completed")
        self.assertEqual(self.write(client, current_limit=1.0)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["voltage_setpoint"], 12.5)
        self.assertEqual(state["current_setpoint"], 1.0)
        self.assertEqual(state["voltage_limit"], 12.0)
        self.assertEqual(state["current_limit"], 1.0)

        for patch in ({"voltage_setpoint": 30.5}, {"current_setpoint": 5.5},
                      {"voltage_limit": 0.5}, {"current_limit": 5.5}):
            refused = self.write(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual(state["voltage_setpoint"], 12.5)
        self.assertEqual(state["current_setpoint"], 1.0)
        self.assertEqual(state["voltage_limit"], 12.0)
        self.assertEqual(state["current_limit"], 1.0)

    def test_the_output_switch_changes_the_measurements(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.write(client, voltage_setpoint=12.5)
        self.write(client, current_setpoint=1.0)
        self.assertEqual(self.write(client, output_enabled=True)["status"], "completed")
        state = self.state(client)
        self.assertTrue(state["output_enabled"])
        self.assertEqual(state["voltage"], 12.5)
        self.assertEqual(state["current"], 1.0)
        self.assertEqual(state["power"], 12.5)
        self.assertEqual(self.write(client, output_enabled=False)["status"], "completed")
        state = self.state(client)
        self.assertFalse(state["output_enabled"])
        self.assertEqual((state["voltage"], state["current"], state["power"]), (0.0, 0.0, 0.0))

    def test_reset_returns_the_fake_to_its_placeholders(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.write(client, voltage_setpoint=12.5)
        self.write(client, output_enabled=True)
        receipt = client.invoke("x-cap.sergey12malyshev.reset_config.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"reset": True})
        state = self.state(client)
        self.assertEqual(state["voltage_setpoint"], 5.0)        # placeholder
        self.assertFalse(state["output_enabled"])

    def test_the_estop_disables_the_output_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.write(client, voltage_setpoint=12.5)
        self.write(client, output_enabled=True)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["output_enabled"])
        refused = self.write(client, output_enabled=True)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
