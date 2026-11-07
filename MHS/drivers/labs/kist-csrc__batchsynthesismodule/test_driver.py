"""Acceptance run of the IKA RET control-visc package: the gate, plus cases for this driver.

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

    def test_the_reads_report_the_fake_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["medium_temperature"], 25.0)
        self.assertEqual(state["hot_plate_temperature"], 24.0)
        self.assertEqual(state["medium_setpoint"], 25.0)
        self.assertEqual(state["hot_plate_setpoint"], 25.0)
        self.assertEqual(state["stir_rate"], 0)
        self.assertEqual(state["stir_rate_setpoint"], 0)
        self.assertEqual(state["ph"], 7.0)
        self.assertEqual(state["weight"], 0.0)

    def test_the_sourced_writes_reach_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, medium_setpoint=80)["status"], "completed")
        self.assertEqual(self.configure(client, stir_rate_setpoint=300)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["medium_setpoint"], 80.0)
        self.assertEqual(state["stir_rate_setpoint"], 300)
        for patch in ({"medium_setpoint": 341}, {"stir_rate_setpoint": 1701},
                      {"stir_rate_setpoint": -1}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_hot_plate_setpoint_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, hot_plate_setpoint=100)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["hot_plate_setpoint"], 25.0)

    def test_the_example_overlay_supplies_the_hot_plate_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, hot_plate_setpoint=100)["status"], "completed")
        self.assertEqual(self.state(client)["hot_plate_setpoint"], 100.0)
        for value in (19.99, 200.01):
            refused = self.configure(client, hot_plate_setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["hot_plate_setpoint"], 100.0)

    def test_the_thermal_action_sets_the_medium_target(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 50}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["setpoint"], 50.0)
        self.assertEqual(self.state(client)["medium_setpoint"], 50.0)

    def test_the_extension_actions_reach_the_fake(self) -> None:
        client = self.serve()
        for capability, key in (("x-cap.kist-csrc.set_heater.v1", "enabled"),
                                ("x-cap.kist-csrc.set_stirrer.v1", "enabled"),
                                ("x-cap.kist-csrc.set_ph_meter.v1", "enabled"),
                                ("x-cap.kist-csrc.set_weighing.v1", "enabled")):
            started = client.invoke(capability, {key: True}, **self.ids)
            self.assertEqual(started["status"], "completed", capability)
            self.assertEqual(started["output"], {key: True})
            stopped = client.invoke(capability, {key: False}, **self.ids)
            self.assertEqual(stopped["status"], "completed", capability)
            self.assertEqual(stopped["output"], {key: False})
        self.assertEqual(client.invoke("x-cap.kist-csrc.reset_hot_plate.v1", {}, **self.ids)["status"],
                         "completed")
        self.assertEqual(client.invoke("x-cap.kist-csrc.stop_heating_and_stirring.v1", {}, **self.ids)["status"],
                         "completed")

    def test_the_estop_latches_the_actuators(self) -> None:
        client = self.serve()
        client.invoke("x-cap.kist-csrc.set_heater.v1", {"enabled": True}, **self.ids)
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke("x-cap.kist-csrc.set_heater.v1", {"enabled": True}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
