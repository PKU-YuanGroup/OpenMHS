"""Acceptance run of the SCILA package: the gate, plus cases for what is specific to this driver.

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


class ScilaCases(unittest.TestCase):
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

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["device_name"], "SCILA fake")               # fake placeholder
        self.assertEqual(state["firmware_version"], "FAKE-0.0")            # fake placeholder
        self.assertEqual(state["state"], "Idle")                           # fake placeholder
        self.assertEqual((state["current_temperature"], state["target_temperature"]), (37.0, 37.0))
        self.assertTrue(state["temperature_control"])
        self.assertFalse(state["auto_boost_co2"])
        self.assertEqual(state["boost_state"], "Idle")                     # fake placeholder
        self.assertEqual(state["co2_flow_status"], "Off")                  # fake placeholder
        self.assertEqual(state["liquid_level"], "OK")                      # fake placeholder
        self.assertEqual(state["door_status"],
                         "drawer1=Closed; drawer2=Closed; drawer3=Closed; drawer4=Closed")
        self.assertEqual(state["valve_status"], "gas_boost=Closed; gas_normal=Open; h2o=Closed")

    def test_the_boolean_write_reaches_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, auto_boost_co2=True)["status"], "completed")
        self.assertTrue(self.state(client)["auto_boost_co2"])
        self.assertEqual(self.state(client)["boost_state"], "Boost")       # fake placeholder
        self.assertEqual(self.configure(client, auto_boost_co2=False)["status"], "completed")
        self.assertFalse(self.state(client)["auto_boost_co2"])

    def test_the_catalogue_temperature_measurement(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.measure.temperature.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["temperature"], 37.0)           # fake placeholder
        self.assertIn("sampled_at", receipt["output"])

    def test_the_set_point_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 37}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["target_temperature"], 37.0)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        completed = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 36.5}, **self.ids)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"]["setpoint"], 36.5)
        state = self.state(client)
        self.assertEqual(state["target_temperature"], 36.5)
        self.assertTrue(state["temperature_control"])
        for value in (19.9, 40.1):
            refused = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": value}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)

    def test_the_estop_stops_the_outputs_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, auto_boost_co2=True)["status"], "completed")
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertFalse(state["temperature_control"])
        self.assertFalse(state["auto_boost_co2"])
        refused = self.configure(client, auto_boost_co2=True)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
