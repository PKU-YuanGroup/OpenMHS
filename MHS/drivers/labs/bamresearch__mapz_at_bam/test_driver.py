"""Acceptance run of the IKA RCT digital 5 package: the gate, plus cases for this driver.

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


class IkaRctDigital5Cases(unittest.TestCase):
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
        self.assertEqual(state["device_name"], "RCT digital")
        self.assertEqual(state["external_temperature"], 21.5)
        self.assertEqual(state["hotplate_temperature"], 21.0)
        self.assertEqual(state["stirring_speed"], 0.0)
        self.assertEqual(state["viscosity_trend"], 0.0)
        self.assertEqual(state["safety_temperature"], 120.0)

    def test_the_setpoints_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, temperature_setpoint=37.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        refused = self.configure(client, stirring_speed_setpoint=300)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        refused = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 40}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["temperature_setpoint"], 0.0)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, temperature_setpoint=37.5)["status"], "completed")
        self.assertEqual(self.configure(client, stirring_speed_setpoint=300)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["temperature_setpoint"], 37.5)
        self.assertEqual(state["stirring_speed_setpoint"], 300.0)
        for patch in ({"temperature_setpoint": -1}, {"temperature_setpoint": 121},
                      {"stirring_speed_setpoint": -1}, {"stirring_speed_setpoint": 1201}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.state(client)["temperature_setpoint"], 37.5)

    def test_the_thermal_action_sets_the_setpoint(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        done = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 45}, **self.ids)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["output"], {"setpoint": 45.0})
        self.assertEqual(self.state(client)["temperature_setpoint"], 45.0)

    def test_the_stirring_action_sets_the_setpoint(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        done = client.invoke("x-cap.bamresearch.start_stirring.v1", {"stirring_speed": 500}, **self.ids)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["output"], {"stirring_speed_setpoint": 500.0})
        self.assertEqual(self.state(client)["stirring_speed_setpoint"], 500.0)

    def test_the_safe_state_action_resets_both_setpoints(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, temperature_setpoint=45)
        self.configure(client, stirring_speed_setpoint=500)
        done = client.invoke("x-cap.bamresearch.stop_hotplate.v1", {}, **self.ids)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["output"], {"temperature_setpoint": 0.0, "stirring_speed_setpoint": 0.0})

    def test_the_estop_stops_both_actuators_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke("x-cap.bamresearch.start_stirring.v1", {"stirring_speed": 500}, **self.ids)
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertEqual(state["temperature_setpoint"], 0.0)
        self.assertEqual(state["stirring_speed_setpoint"], 0.0)
        refused = client.invoke("x-cap.bamresearch.start_stirring.v1", {"stirring_speed": 500}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
