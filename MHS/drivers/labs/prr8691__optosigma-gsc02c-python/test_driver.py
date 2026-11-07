"""Acceptance run of the GSC-02C package: the gate, plus cases for what is specific to this driver.

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


class GSC02CCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def overlay(self):
        return str(HERE / "site-limits.example.json")

    def test_the_reads_start_from_the_fake_position(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position_mm"], 42.5)          # placeholder in fake.py, not a device fact
        self.assertEqual(state["position_pulses"], 42500)     # placeholder in fake.py, not a device fact
        self.assertFalse(state["busy"])
        self.assertIsInstance(state["status"], str)

    def test_the_position_actions_are_refused_without_an_operator_overlay(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.prr8691.move_absolute_mm.v1", {"position_mm": 10}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position_mm"], 42.5)

    def test_the_example_overlay_lets_the_stage_move(self) -> None:
        client = self.serve(self.overlay())
        moved = client.invoke("x-cap.prr8691.move_absolute_mm.v1", {"position_mm": 10}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["position_mm"], 10.0)
        self.assertEqual(moved["output"]["position_pulses"], 10000)
        self.assertEqual(self.state(client)["position_mm"], 10.0)

        stepped = client.invoke("x-cap.prr8691.move_relative_mm.v1", {"distance_mm": 1.5}, **self.ids)
        self.assertEqual(stepped["output"]["position_mm"], 11.5)
        self.assertEqual(stepped["output"]["position_pulses"], 11500)

        refused = client.invoke("x-cap.prr8691.move_absolute_mm.v1", {"position_mm": 85.001}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["position_mm"], 11.5)

    def test_pulse_moves_and_homing(self) -> None:
        client = self.serve(self.overlay())
        moved = client.invoke("x-cap.prr8691.move_relative_pulses.v1", {"pulses": -2500}, **self.ids)
        self.assertEqual(moved["output"]["position_pulses"], 40000)
        self.assertEqual(moved["output"]["position_mm"], 40.0)

        homed = client.invoke("x-cap.prr8691.home.v1", {"direction": "-"}, **self.ids)
        self.assertEqual(homed["output"], {"homed": True, "position_mm": 0.0, "position_pulses": 0})

    def test_the_motion_ramp_is_written_and_reported(self) -> None:
        client = self.serve(self.overlay())
        applied = client.invoke("x-cap.prr8691.configure_motion.v1",
                                {"start_speed_mm_s": 0.5, "max_speed_mm_s": 5.0, "accel_time_ms": 200},
                                **self.ids)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"], {"start_speed_mm_s": 0.5, "max_speed_mm_s": 5.0,
                                             "accel_time_ms": 200})
        refused = client.invoke("x-cap.prr8691.configure_motion.v1",
                                {"start_speed_mm_s": 0.5, "max_speed_mm_s": 5.0, "accel_time_ms": 1001},
                                **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_stop_action_and_the_estop_latch(self) -> None:
        client = self.serve(self.overlay())
        stopped = client.invoke("x-cap.prr8691.stop_motion.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})

        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.prr8691.move_absolute_mm.v1", {"position_mm": 10}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
