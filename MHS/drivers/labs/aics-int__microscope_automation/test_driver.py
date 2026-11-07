"""Acceptance run of the ZEN microscope package: the gate, plus cases for this driver.

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


class ZenMicroscopeCases(unittest.TestCase):
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

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["stage_x"], state["stage_y"]), (60000.0, 40000.0))
        self.assertEqual(state["objective_name"], "Dummy Objective")
        self.assertEqual(state["objective_position"], 0)
        self.assertEqual(state["microscope_name"], "ZEN blue simulation")
        self.assertFalse(state["live"])

    def test_live_mode_and_the_snapshot(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.aics-int.live_mode_start.v1", {"experiment": "test.czexp"}, **self.ids)
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"]["live"], True)
        self.assertEqual(started["output"]["experiment"], "test.czexp")
        self.assertTrue(self.state(client)["live"])

        snapped = client.invoke("x-cap.aics-int.snap_image.v1", {"experiment": "test.czexp"}, **self.ids)
        self.assertEqual(snapped["status"], "completed")
        self.assertEqual(snapped["output"]["acquired"], True)

        stopped = client.invoke("x-cap.aics-int.live_mode_stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"live": False})
        self.assertFalse(self.state(client)["live"])

    def test_the_estop_stops_live_mode_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.aics-int.live_mode_start.v1", {}, **self.ids)
        self.assertTrue(self.state(client)["live"])
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["live"])
        refused = client.invoke("x-cap.aics-int.live_mode_start.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
