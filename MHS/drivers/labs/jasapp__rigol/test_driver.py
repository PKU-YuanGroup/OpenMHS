"""Acceptance run of the RIGOL DP832A package: the gate, plus cases for what is specific to this driver.

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


class RigolCases(unittest.TestCase):
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

    def test_the_three_channels_start_off(self) -> None:
        client = self.serve()
        state = self.state(client)
        for channel in (1, 2, 3):
            self.assertFalse(state[f"output_ch{channel}"])
            self.assertEqual(state[f"voltage_setpoint_ch{channel}"], 0.0)
            self.assertEqual(state[f"current_setpoint_ch{channel}"], 0.0)
            self.assertEqual(state[f"voltage_ch{channel}"], 0.0)
            self.assertEqual(state[f"current_ch{channel}"], 0.0)
            self.assertEqual(state[f"power_ch{channel}"], 0.0)

    def test_a_numeric_write_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, voltage_setpoint_ch1=3.3)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["voltage_setpoint_ch1"], 0.0)  # the fake default, untouched

    def test_the_output_can_be_switched_without_an_overlay(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, output_ch2=True)["status"], "completed")
        self.assertTrue(self.state(client)["output_ch2"])
        self.assertEqual(self.configure(client, output_ch2=False)["status"], "completed")
        self.assertFalse(self.state(client)["output_ch2"])

    def test_the_example_overlay_supplies_the_set_point_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, voltage_setpoint_ch1=3.3)["status"], "completed")
        self.assertEqual(self.configure(client, current_setpoint_ch1=0.5)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["voltage_setpoint_ch1"], 3.3)
        self.assertEqual(state["current_setpoint_ch1"], 0.5)
        for patch in ({"voltage_setpoint_ch1": 5.01}, {"current_setpoint_ch1": 1.01}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_a_measured_value_follows_the_enabled_output(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, voltage_setpoint_ch3=2.0, current_setpoint_ch3=0.25)
        self.assertEqual(self.state(client)["voltage_ch3"], 0.0)          # output still off
        self.configure(client, output_ch3=True)
        state = self.state(client)
        self.assertEqual((state["voltage_ch3"], state["current_ch3"]), (2.0, 0.25))
        self.assertEqual(state["power_ch3"], 0.5)

    def test_the_protection_actions_need_the_site_and_report_the_channel(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.jasapp.set_ovp.v1", {"channel": 2, "voltage": 4.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        with_site = self.serve(str(HERE / "site-limits.example.json"))
        done = with_site.invoke("x-cap.jasapp.set_ovp.v1", {"channel": 2, "voltage": 4.0}, **self.ids)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["output"], {"channel": 2, "voltage": 4.0})
        done = with_site.invoke("x-cap.jasapp.set_ocp.v1", {"channel": 3, "current": 0.5}, **self.ids)
        self.assertEqual(done["output"], {"channel": 3, "current": 0.5})
        refused = with_site.invoke("x-cap.jasapp.set_ocp.v1", {"channel": 4, "current": 0.5}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_turns_every_output_off_and_latches(self) -> None:
        client = self.serve()
        for channel in (1, 2, 3):
            self.configure(client, **{f"output_ch{channel}": True})
        client.estop("test", **self.ids)
        state = self.state(client)
        for channel in (1, 2, 3):
            self.assertFalse(state[f"output_ch{channel}"])
        refused = self.configure(client, output_ch1=True)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
