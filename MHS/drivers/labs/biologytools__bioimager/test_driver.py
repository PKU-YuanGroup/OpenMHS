"""Acceptance run of the Cobolt laser package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CoboltLaserCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    def test_the_power_setpoint_is_bounded(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["power_setpoint"], 0.0)
        applied = self.configure(client, power_setpoint=0.5)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["power_setpoint"], 0.5)
        for value in (1.5, -0.1):
            refused = self.configure(client, power_setpoint=value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["power_setpoint"], 0.5)

    def test_the_emission_and_the_safe_state_action(self) -> None:
        client = self.serve()
        self.assertFalse(self.state(client)["emission"])
        self.assertEqual(len(self.state(client)["status"]), 5)
        turned_on = self.configure(client, emission=True)
        self.assertEqual(turned_on["status"], "completed")
        self.assertTrue(self.state(client)["emission"])
        disabled = client.invoke("x-cap.biologytools.disable_laser.v1", {}, **self.ids)
        self.assertEqual(disabled["status"], "completed")
        self.assertEqual(disabled["output"], {"emission": False})
        self.assertFalse(self.state(client)["emission"])

    def test_the_estop_turns_the_emission_off_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, emission=True)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["emission"])
        refused = self.configure(client, emission=True)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
