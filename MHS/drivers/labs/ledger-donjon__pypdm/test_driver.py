"""Acceptance run of the PDM package: the gate, plus cases for what is specific to this driver.

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


class PdmCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **inputs):
        return client.invoke("x-cap.ledger-donjon.configure_pulse.v1", inputs, **self.ids)

    def test_the_initial_state_reports_the_device(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["address"], 1)                       # the fake's placeholder address
        self.assertEqual(state["protocol_version"], "3.7")          # the fake's placeholder version
        self.assertFalse(state["activation"])
        self.assertTrue(state["interlock_closed"])                  # CLOSED is 0, the laser can pulse
        self.assertEqual((state["operating_mode"], state["current_source"], state["sync_source"], state["delay_line_type"]),
                         ("pulsed", "numeric", "internal", "none"))
        self.assertEqual(state["maximum_current"], 500.0)           # the fake's placeholder maximum current
        self.assertEqual(state["current"], 100.0)                   # 20 percent of 500 mA

    def test_the_configuration_is_written_applied_and_read_back(self) -> None:
        client = self.serve()
        receipt = self.configure(client, frequency=5000, current_percentage=40, offset_current=30)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"frequency": 5000, "current_percentage": 40.0, "offset_current": 30.0})
        state = self.state(client)
        self.assertEqual((state["frequency"], state["current_percentage"], state["offset_current"]),
                         (5000, 40.0, 30.0))
        self.assertEqual(state["current"], 200.0)                   # 40 percent of 500 mA

    def test_the_configuration_envelope_is_enforced(self) -> None:
        client = self.serve()
        cases = (
            {"frequency": 0, "current_percentage": 20, "offset_current": 0},
            {"frequency": 250000001, "current_percentage": 20, "offset_current": 0},
            {"frequency": 1000, "current_percentage": -0.1, "offset_current": 0},
            {"frequency": 1000, "current_percentage": 100.1, "offset_current": 0},
            {"frequency": 1000, "current_percentage": 20, "offset_current": -1.0},
            {"frequency": 1000, "current_percentage": 20, "offset_current": 151.0},
        )
        for inputs in cases:
            refused = client.invoke("x-cap.ledger-donjon.configure_pulse.v1", inputs, **self.ids)
            self.assertEqual(refused["status"], "rejected", inputs)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, inputs)
        self.assertEqual(self.state(client)["frequency"], 1000)     # nothing was applied

    def test_the_disable_emission_action_is_the_safe_state(self) -> None:
        client = self.serve()
        stopped = client.invoke("x-cap.ledger-donjon.disable_emission.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"activation": False})
        self.assertFalse(self.state(client)["activation"])

    def test_the_estop_clears_the_activation_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["activation"])
        refused = self.configure(client, frequency=5000, current_percentage=40, offset_current=30)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
