"""Acceptance run of the Kinesis package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class KinesisCases(unittest.TestCase):
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

    def test_the_state_comes_from_the_controller(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position"], 0.0)
        self.assertEqual((state["moving"], state["homed"]), (False, False))
        self.assertEqual(state["max_velocity"], 1000.0)
        self.assertEqual(state["controller_model"], "KDC101")
        self.assertEqual(state["channel_count"], 1)
        self.assertIn("connected", state["status"])

    def test_the_velocity_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"max_velocity": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["max_velocity"], 1000.0)        # untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        written = client.invoke("cap.device.configure.v1", {"max_velocity": 500}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(self.state(client)["max_velocity"], 500.0)

    def test_the_move_the_home_and_the_stop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("x-cap.alexshkarin.move_to_absolute.v1", {"target_position": 1200}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"]["position"], 1200.0)
        self.assertEqual(self.state(client)["position"], 1200.0)
        homed = client.invoke("x-cap.alexshkarin.home_axis.v1", {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertEqual(homed["output"], {"homed": True})
        self.assertTrue(self.state(client)["homed"])
        stopped = client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_stops_the_axis_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke("x-cap.alexshkarin.move_to_absolute.v1", {"target_position": 10}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["moving"])
        refused = client.invoke("x-cap.alexshkarin.home_axis.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
