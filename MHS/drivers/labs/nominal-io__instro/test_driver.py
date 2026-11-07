"""Acceptance run of the Siglent SPD3303 package: the gate, plus cases for what is specific to this driver.

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


class SiglentSPD3303Cases(unittest.TestCase):
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

    def test_the_numeric_set_points_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, voltage_setpoint_ch1=5.0, current_setpoint_ch1=0.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        state = self.state(client)
        self.assertEqual((state["voltage_setpoint_ch1"], state["current_setpoint_ch1"]), (0.0, 0.0))
        enabled = self.configure(client, output_enabled_ch1=True)
        self.assertEqual(enabled["status"], "completed")
        self.assertTrue(self.state(client)["output_enabled_ch1"])

    def test_the_example_overlay_bounds_the_set_points(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, voltage_setpoint_ch1=12.345, current_setpoint_ch1=1.5)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["voltage_setpoint_ch1"], state["current_setpoint_ch1"]), (12.345, 1.5))
        for patch in ({"voltage_setpoint_ch1": 30.01}, {"voltage_setpoint_ch1": -0.01},
                      {"current_setpoint_ch2": 3.01}, {"current_setpoint_ch2": -0.01}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual((state["voltage_setpoint_ch1"], state["current_setpoint_ch1"]), (12.345, 1.5))

    def test_the_measurements_follow_the_output(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, voltage_setpoint_ch2=10.0)["status"], "completed")
        self.assertEqual(self.state(client)["voltage_ch2"], 0.0)
        self.assertEqual(self.configure(client, output_enabled_ch2=True)["status"], "completed")
        self.assertEqual(self.state(client)["voltage_ch2"], 10.0)
        self.assertEqual(self.configure(client, output_enabled_ch2=False)["status"], "completed")
        self.assertEqual(self.state(client)["voltage_ch2"], 0.0)

    def test_the_output_off_action_and_the_estop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, output_enabled_ch1=True, output_enabled_ch2=True)
        state = self.state(client)
        self.assertEqual((state["output_enabled_ch1"], state["output_enabled_ch2"]), (True, True))
        stopped = client.invoke("x-cap.nominal-io.output_off.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"output_enabled_ch1": False, "output_enabled_ch2": False})
        state = self.state(client)
        self.assertEqual((state["output_enabled_ch1"], state["output_enabled_ch2"]), (False, False))
        self.configure(client, output_enabled_ch1=True)
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertEqual((state["output_enabled_ch1"], state["output_enabled_ch2"]), (False, False))
        refused = self.configure(client, output_enabled_ch1=True)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
