"""Acceptance run of the PI GCS2 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PIControllerCases(unittest.TestCase):
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

    def move_absolute(self, client, axis, position):
        return client.invoke("x-cap.pymodaq.pi_move_absolute.v1",
                             {"axis": axis, "position": position}, **self.ids)

    def test_the_reads_of_the_stand_in(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertIn("fake PI GCS2 controller", state["identity"])
        self.assertEqual(state["axis_names"], ["1", "2"])
        self.assertEqual(state["axis_units"], ["um", "um"])
        self.assertEqual(state["positions"], [12.5, -3.0])
        self.assertEqual(state["referenced"], [True, False])
        self.assertEqual(state["servo_enabled"], [True, False])

    def test_every_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.move_absolute(client, "1", 10.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["positions"], [12.5, -3.0])

    def test_the_example_overlay_permits_a_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move_absolute(client, "1", 10.0)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"axis": "1", "position": 10.0})
        self.assertEqual(self.state(client)["positions"], [10.0, -3.0])

    def test_the_relative_move_and_home(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("x-cap.pymodaq.pi_move_relative.v1",
                              {"axis": "1", "delta": 5.0}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"axis": "1", "position": 17.5})
        homed = client.invoke("x-cap.pymodaq.pi_home_axis.v1", {"axis": "2"}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertEqual(homed["output"], {"axis": "2", "referenced": True})
        self.assertEqual(self.state(client)["positions"], [17.5, 0.0])

    def test_the_stop_action_and_the_estop_latch(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.invoke("x-cap.pymodaq.pi_stop_motion.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": True})
        client.estop("test", **self.ids)
        latched = self.move_absolute(client, "1", 10.0)
        self.assertEqual(latched["status"], "rejected")
        self.assertEqual(latched["error"]["mhs_code"], ESTOP)

    def test_an_unknown_axis_is_refused_without_a_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.move_absolute(client, "9", 10.0)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.state(client)["positions"], [12.5, -3.0])


if __name__ == "__main__":
    unittest.main()
