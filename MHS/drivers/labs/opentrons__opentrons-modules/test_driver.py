"""Acceptance run of the Opentrons Temp Deck Gen 3 package: the gate, plus cases for this driver.

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


class TempdeckCases(unittest.TestCase):
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

    def test_the_reads_are_the_fake_values(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["plate_temperature_1"], 22.0)
        self.assertEqual(state["plate_temperature_2"], 22.0)
        self.assertEqual(state["heatsink_temperature"], 24.0)
        self.assertEqual(state["peltier_current"], 0.0)
        self.assertEqual(state["fan_speed"], 0.0)
        self.assertEqual(state["peltier_power"], 0.0)
        self.assertEqual(state["fan_power"], 0.0)

    def test_the_fan_pwm_is_a_bounded_write(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, fan_power=0.5)["status"], "completed")
        self.assertEqual(self.state(client)["fan_power"], 0.5)
        for value in (-0.01, 1.01):
            refused = self.configure(client, fan_power=value)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["fan_power"], 0.5)

    def test_the_target_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 37}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_supplies_the_target_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        done = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 37}, **self.ids)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["output"], {"setpoint": 37.0})
        self.assertNotEqual(self.state(client)["peltier_power"], 0.0)   # the fake's placeholder response
        for value in (3.99, 95.01):
            refused = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": value}, **self.ids)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)

    def test_the_safe_state_action_deactivates(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, fan_power=0.5)["status"], "completed")
        done = client.invoke("x-cap.opentrons.deactivate.v1", {}, **self.ids)
        self.assertEqual(done["output"], {"deactivated": True})
        state = self.state(client)
        self.assertEqual(state["fan_power"], 0.0)
        self.assertEqual(state["peltier_power"], 0.0)

    def test_the_estop_clears_the_thermal_system_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, fan_power=0.5)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["fan_power"], 0.0)
        refused = self.configure(client, fan_power=0.3)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
