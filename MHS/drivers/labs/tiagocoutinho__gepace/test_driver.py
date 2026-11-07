"""Acceptance run of the gepace package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GepaceCases(unittest.TestCase):
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

    def test_the_module_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["idn"], "GE Druck,PACE5000,00000000,FAKE")
        self.assertEqual(state["version"], "FAKE 0.0")
        self.assertEqual(state["pressure_unit"], "BAR")
        self.assertEqual(state["pressure_range"], "0 to 100")
        self.assertTrue(state["pressure_in_limits"])
        self.assertEqual(state["error"], "")
        self.assertEqual(set(state["serial_numbers"]),
                         {"ui", "ctrl1", "ctrl2", "ao1", "ao2", "vfc1", "vfc2"})
        self.assertFalse(state["pressure_control"])

    def test_start_and_stop_change_the_pressure_control_output(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.tiagocoutinho.start_pressure_control.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"enabled": True})
        self.assertTrue(self.state(client)["pressure_control"])
        stopped = client.invoke("x-cap.tiagocoutinho.stop_pressure_control.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"enabled": False})
        self.assertFalse(self.state(client)["pressure_control"])

    def test_set_pressure_control_uses_the_boolean_input(self) -> None:
        client = self.serve()
        enabled = client.invoke("x-cap.tiagocoutinho.set_pressure_control.v1", {"enabled": True}, **self.ids)
        self.assertEqual(enabled["output"], {"enabled": True})
        self.assertTrue(self.state(client)["pressure_control"])
        disabled = client.invoke("x-cap.tiagocoutinho.set_pressure_control.v1", {"enabled": False}, **self.ids)
        self.assertEqual(disabled["output"], {"enabled": False})
        self.assertFalse(self.state(client)["pressure_control"])

    def test_the_estop_disables_the_output_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.tiagocoutinho.start_pressure_control.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["pressure_control"])
        refused = client.invoke("x-cap.tiagocoutinho.set_pressure_control.v1", {"enabled": True}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
