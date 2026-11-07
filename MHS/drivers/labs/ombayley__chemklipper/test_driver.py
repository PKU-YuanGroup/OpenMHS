"""Acceptance run of the ChemKlipper gantry package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MOVE = "x-cap.ombayley.move_cartesian.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ChemKlipperGantryCases(unittest.TestCase):
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

    def test_the_reads_describe_the_gantry(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertTrue(state["connected"])
        self.assertEqual(set(state["position"]), {"x", "y", "z"})
        self.assertEqual(set(state["target_position"]), {"x", "y", "z"})
        self.assertIsInstance(state["status"], str)

    def test_home_moves_the_axes_to_zero(self) -> None:
        client = self.serve()
        homed = client.invoke("x-cap.ombayley.home_gantry.v1", {}, wait=True, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True})
        position = self.state(client)["position"]
        self.assertEqual(position, {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_the_move_waits_for_the_operator_workspace(self) -> None:
        client = self.serve()
        refused = client.invoke(MOVE, {"x": 10.0, "y": 20.0, "z": 5.0}, wait=True, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_the_example_overlay_supplies_the_workspace(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke(MOVE, {"x": 12.5, "y": 34.0, "z": 5.5}, wait=True, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(moved["output"]["position"], {"x": 12.5, "y": 34.0, "z": 5.5})
        self.assertEqual(self.state(client)["position"], {"x": 12.5, "y": 34.0, "z": 5.5})
        refused = client.invoke(MOVE, {"x": 300.1, "y": 34.0, "z": 5.5}, wait=True, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_the_stop_action_reports_the_stop(self) -> None:
        client = self.serve()
        stopped = client.invoke("x-cap.ombayley.stop_motion.v1", {}, wait=True, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertTrue(stopped["output"]["stopped"])
        self.assertEqual(set(stopped["output"]["stopped_position"]), {"x", "y", "z"})

    def test_the_estop_latches_the_motion(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.ombayley.home_gantry.v1", {}, wait=True, **self.ids)["status"], "completed")
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.ombayley.home_gantry.v1", {}, wait=True, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
