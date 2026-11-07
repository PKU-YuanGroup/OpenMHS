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

    def test_the_initial_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["is_on"], state["enabled"]), (False, False))
        self.assertEqual((state["power"], state["measured_power"]), (0.0, 0.0))
        self.assertEqual(len(state["status"]), 5)                    # the five queries of get_status

    def test_the_power_set_point_is_written_and_read_back(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, power=0.5)["status"], "completed")
        self.assertEqual(self.state(client)["power"], 0.5)
        self.assertEqual(self.state(client)["measured_power"], 0.0)  # emission is off, so nothing is measured

    def test_the_power_envelope_is_enforced(self) -> None:
        client = self.serve()
        for value in (-0.1, 1.5):
            refused = self.configure(client, power=value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["power"], 0.0)

    def test_enable_emission_and_disable_emission(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.python-microscope.enable_emission.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"is_on": True})
        self.assertTrue(self.state(client)["is_on"])
        self.assertEqual(self.configure(client, power=0.5)["status"], "completed")
        self.assertEqual(self.state(client)["measured_power"], 0.5)
        stopped = client.invoke("x-cap.python-microscope.disable_emission.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"is_on": False})
        self.assertFalse(self.state(client)["is_on"])
        # the Cobolt disable override leaves the Device.enabled flag alone (microscope/lights/cobolt.py:133-135)
        self.assertTrue(self.state(client)["enabled"])

    def test_the_estop_turns_emission_off_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.python-microscope.enable_emission.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["is_on"])
        refused = self.configure(client, power=0.5)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
