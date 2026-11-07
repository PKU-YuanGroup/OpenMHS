"""Acceptance run of the Runze SY01B package: the gate, plus cases for what is specific to this driver.

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
MOVE = "x-cap.allenneuraldynamics.runze_move_to_percent.v1"
ASPIRATE = "x-cap.allenneuraldynamics.runze_aspirate.v1"
DISPENSE = "x-cap.allenneuraldynamics.runze_dispense.v1"
VALVE = "x-cap.allenneuraldynamics.runze_select_valve_port.v1"
SPEED = "x-cap.allenneuraldynamics.runze_set_speed.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RunzeSY01BCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def invoke(self, client, capability_id, payload):
        return client.invoke(capability_id, payload, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_start_at_the_fake_home_position(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position_steps"], 0)
        self.assertEqual(state["position_percent"], 0.0)
        self.assertEqual(state["position_ul"], 0.0)
        self.assertEqual(state["address"], 0)
        self.assertEqual(state["firmware_version"], 0.0)
        self.assertEqual(state["rs232_baudrate"], 9600)
        self.assertEqual(state["motor_status"], 0)
        self.assertFalse(state["busy"])

    def test_the_move_is_bounded_and_reaches_the_fake(self) -> None:
        client = self.serve()
        moved = self.invoke(client, MOVE, {"position": 25})
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"position_percent": 25.0})
        self.assertEqual(self.state(client)["position_steps"], 1500)
        refused = self.invoke(client, MOVE, {"position": 100.5})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["position_steps"], 1500)

    def test_the_speed_is_bounded(self) -> None:
        client = self.serve()
        changed = self.invoke(client, SPEED, {"percent": 25})
        self.assertEqual(changed["status"], "completed")
        self.assertEqual(changed["output"], {"speed_percent": 25.0})
        refused = self.invoke(client, SPEED, {"percent": -1})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_volume_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.invoke(client, ASPIRATE, {"volume": 1000})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position_steps"], 0)

    def test_the_example_overlay_enables_the_volume_and_valve(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        aspirated = self.invoke(client, ASPIRATE, {"volume": 1000})
        self.assertEqual(aspirated["status"], "completed")
        self.assertEqual(aspirated["output"]["aspirated_volume"], 1000.0)
        self.assertEqual(aspirated["output"]["position_ul"], 1000.0)
        dispensed = self.invoke(client, DISPENSE, {"volume": 400})
        self.assertEqual(dispensed["status"], "completed")
        self.assertEqual(dispensed["output"]["dispensed_volume"], 400.0)
        self.assertEqual(dispensed["output"]["position_ul"], 600.0)
        selected = self.invoke(client, VALVE, {"port": 3})
        self.assertEqual(selected["status"], "completed")
        self.assertEqual(selected["output"], {"port": 3})
        refused = self.invoke(client, VALVE, {"port": 13})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_latches_and_refuses_the_motion(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = self.invoke(client, MOVE, {"position": 25})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["position_steps"], 0)


if __name__ == "__main__":
    unittest.main()
