"""Acceptance run of the thorlabs-pico package: the gate, plus cases for this driver.

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


class PicoStepperCases(unittest.TestCase):
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

    def invoke(self, client, capability_id, payload):
        return client.invoke(capability_id, payload, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_and_the_speed_wait_for_the_site(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["current_rps"], state["target_rps"]), (0.0, 0.0))
        self.assertEqual(state["position_steps"], 0)
        refused = self.configure(client, target_rps=2.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["target_rps"], 0.0)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, target_rps=2.5)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["target_rps"], 2.5)
        for value in (-10.5, 10.5):
            refused = self.configure(client, target_rps=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["target_rps"], 2.5)

    def test_the_motor_actions_reach_the_fake(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        enabled = self.invoke(client, "x-cap.burhankarahasan.enable_motor.v1", {})
        self.assertEqual(enabled["output"], {"enabled": True})
        disabled = self.invoke(client, "x-cap.burhankarahasan.disable_motor.v1", {})
        self.assertEqual(disabled["output"], {"enabled": False})
        ramp = self.invoke(client, "x-cap.burhankarahasan.set_ramp_rate.v1", {"ramp_rate": 120.0})
        self.assertEqual(ramp["output"], {"ramp_rate": 120.0})
        stopped = self.invoke(client, "cap.motion.stop.v1", {})
        self.assertEqual(stopped["output"]["stopped"], True)
        self.assertEqual(stopped["output"]["stopped_position"], {"position_steps": 0})
        self.assertEqual(self.state(client)["target_rps"], 0.0)

    def test_the_out_of_range_ramp_is_refused(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.invoke(client, "x-cap.burhankarahasan.set_ramp_rate.v1", {"ramp_rate": 0.5})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["target_rps"], 0.0)

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.invoke(client, "x-cap.burhankarahasan.enable_motor.v1", {})["status"], "completed")
        self.assertEqual(self.configure(client, target_rps=2.0)["status"], "completed")
        self.assertEqual(self.state(client)["target_rps"], 2.0)
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["target_rps"], 0.0)
        refused = self.invoke(client, "x-cap.burhankarahasan.enable_motor.v1", {})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
