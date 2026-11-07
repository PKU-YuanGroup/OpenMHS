"""Acceptance run of the RLHT heater package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
STOP_HEATING = "x-cap.uwo-fast.stop_heating.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RlhtHeaterCases(unittest.TestCase):
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

    def test_the_slice_state_is_read(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["state"], "ok")
        self.assertEqual(state["mode"], "closed loop")
        self.assertEqual(state["version"], "RLHT 1.0.0, CRUMBS 0.15.0")
        self.assertFalse(state["estop"])
        self.assertEqual((state["temperature_1"], state["temperature_2"]), (21.5, 20.8))
        self.assertEqual((state["setpoint_1"], state["setpoint_2"]), (0.0, 0.0))

    def test_a_setpoint_is_stored_to_a_tenth(self) -> None:
        client = self.serve()
        receipt = self.configure(client, setpoint_1=42.34)
        self.assertEqual(receipt["status"], "completed")
        self.assertAlmostEqual(self.state(client)["setpoint_1"], 42.3)
        self.assertEqual(self.state(client)["setpoint_2"], 0.0)
        refused = self.configure(client, setpoint_2=3276.8)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.configure(client, setpoint_2=-0.1)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_example_overlay_narrows_both_outputs(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint_1=90)["status"], "completed")
        refused = self.configure(client, setpoint_1=90.1)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.configure(client, setpoint_2=100)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_stop_heating_zeros_both_outputs(self) -> None:
        client = self.serve()
        self.configure(client, setpoint_1=30, setpoint_2=20)
        receipt = client.invoke(STOP_HEATING, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"setpoint_1": 0.0, "setpoint_2": 0.0})
        state = self.state(client)
        self.assertEqual((state["setpoint_1"], state["setpoint_2"]), (0.0, 0.0))

    def test_the_estop_zeros_the_setpoints_and_latches(self) -> None:
        client = self.serve()
        self.configure(client, setpoint_1=30)
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["setpoint_1"], 0.0)
        refused = self.configure(client, setpoint_1=30)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # A safe_state.achieved_by action stays callable while latched (SAFE-029).
        receipt = client.invoke(STOP_HEATING, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"setpoint_1": 0.0, "setpoint_2": 0.0})


if __name__ == "__main__":
    unittest.main()
