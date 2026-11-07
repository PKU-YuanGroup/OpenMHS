"""Acceptance run of the IKA RET Control Visc package: the gate, plus cases for this driver.

The gate call is kept; the cases below exercise the overlay, the operator-required limits, the thermal action and the
e-stop.  The starting values are the fake's placeholders, not facts about any unit.
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


class IKARETControlViscCases(unittest.TestCase):
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

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_the_reads_start_from_the_fake_placeholders(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["medium_temperature"], 21.5)
        self.assertEqual(state["temperature_setpoint"], 25.0)
        self.assertEqual(state["stir_rate"], 0.0)
        self.assertEqual(state["stir_rate_setpoint"], 300.0)
        self.assertEqual(state["ph"], 7.0)

    def test_the_set_points_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"temperature_setpoint": 66.6}, {"stir_rate_setpoint": 400}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        self.assertEqual(self.state(client)["temperature_setpoint"], 25.0)
        self.assertEqual(self.state(client)["stir_rate_setpoint"], 300.0)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, temperature_setpoint=66.6)["status"], "completed")
        self.assertEqual(self.state(client)["temperature_setpoint"], 66.6)
        self.assertEqual(self.configure(client, stir_rate_setpoint=321.9)["status"], "completed")
        self.assertEqual(self.state(client)["stir_rate_setpoint"], 321.0)      # the native setter takes an int()
        for patch in ({"temperature_setpoint": 19.99}, {"temperature_setpoint": 200.01},
                      {"stir_rate_setpoint": 49.9}, {"stir_rate_setpoint": 1200.1}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.state(client)["temperature_setpoint"], 66.6)
        self.assertEqual(self.state(client)["stir_rate_setpoint"], 321.0)

    def test_the_thermal_setpoint_action_sets_and_starts(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.invoke(client, "cap.thermal.setpoint.v1", {"target_temperature": 42.5})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["setpoint"], 42.5)
        self.assertEqual(receipt["output"]["actual_temperature"], 21.5)
        self.assertEqual(self.state(client)["temperature_setpoint"], 42.5)
        refused = self.invoke(client, "cap.thermal.setpoint.v1", {"target_temperature": 250})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_thermal_setpoint_action_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.invoke(client, "cap.thermal.setpoint.v1", {"target_temperature": 42.5})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_heater_and_stirrer_actions(self) -> None:
        client = self.serve()
        self.assertEqual(self.invoke(client, "x-cap.croningp.start_heating.v1")["output"], {"heating": True})
        self.assertEqual(self.invoke(client, "x-cap.croningp.start_stirring.v1")["output"], {"stirring": True})
        self.assertEqual(self.invoke(client, "x-cap.croningp.stop_heating.v1")["output"], {"heating": False})
        self.assertEqual(self.invoke(client, "x-cap.croningp.stop_stirring.v1")["output"], {"stirring": False})
        self.assertEqual(self.invoke(client, "x-cap.croningp.stop_hotplate.v1")["output"],
                         {"heating": False, "stirring": False})

    def test_the_estop_reaches_the_stops_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.croningp.start_stirring.v1")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = self.invoke(client, "x-cap.croningp.start_stirring.v1")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # The safe-state action stays callable while latched by design.
        self.assertEqual(self.invoke(client, "x-cap.croningp.stop_hotplate.v1")["status"], "completed")


if __name__ == "__main__":
    unittest.main()
