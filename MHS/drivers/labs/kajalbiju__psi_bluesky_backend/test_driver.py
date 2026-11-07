"""Acceptance run of the Mercury iTC package: the gate, plus cases for what is specific to this driver.

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


class MercuryITCCases(unittest.TestCase):
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

    def test_the_setpoints_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, temperature_setpoint=300)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["temperature_setpoint"], 295.0)   # the fake's starting value

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, temperature_setpoint=300)["status"], "completed")
        self.assertEqual(self.state(client)["temperature_setpoint"], 300.0)
        refused = self.configure(client, temperature_setpoint=500)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["temperature_setpoint"], 300.0)
        self.assertEqual(self.configure(client, heater_setpoint=50, p_value=5)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["heater_setpoint"], state["p_value"]), (50.0, 5.0))

    def test_the_estop_writes_the_heater_setpoint_zero_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, heater_setpoint=50)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["heater_setpoint"], 0.0)
        self.assertEqual(self.state(client)["temperature_setpoint"], 0.0)  # the PID loop no longer heats
        refused = self.configure(client, temperature_setpoint=300)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_heater_off_action_is_the_safe_state(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, heater_setpoint=50)["status"], "completed")
        receipt = client.invoke("x-cap.kajalbiju.heater_off.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"heater_setpoint": 0.0})
        self.assertEqual(self.state(client)["heater_setpoint"], 0.0)


if __name__ == "__main__":
    unittest.main()
