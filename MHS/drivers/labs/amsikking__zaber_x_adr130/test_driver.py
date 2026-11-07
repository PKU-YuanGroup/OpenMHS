"""Acceptance run of the zaber_x_adr130 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MOVE = "x-cap.amsikking.move_xy.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ZaberXAdr130Cases(unittest.TestCase):
    def serve(self):
        self.driver = load_driver(HERE, backend="fake")
        self.addCleanup(self.driver.close)
        server = build_server(self.driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def test_the_reads_show_the_fake_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["x_mm"], 10.0)           # fake test data, not a device fact
        self.assertEqual(state["y_mm"], 20.0)           # fake test data, not a device fact
        self.assertEqual(state["x_maxspeed"], 50.0)     # fake test data, not a device fact
        self.assertEqual(state["y_maxspeed"], 25.0)     # fake test data, not a device fact

    def test_the_maxspeed_writes_reach_the_fake_and_refuse_the_bounds(self) -> None:
        client = self.serve()
        written = self.configure(client, x_maxspeed=250.0, y_maxspeed=33.3334)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(written["output"]["applied"], {"x_maxspeed": 250.0, "y_maxspeed": 33.333})
        state = self.state(client)
        self.assertEqual((state["x_maxspeed"], state["y_maxspeed"]), (250.0, 33.333))
        for patch in ({"x_maxspeed": 0.005}, {"x_maxspeed": 750.5},
                      {"y_maxspeed": 0.0}, {"y_maxspeed": 751.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual((state["x_maxspeed"], state["y_maxspeed"]), (250.0, 33.333))

    def test_the_move_action_moves_the_fake_and_refuses_the_bounds(self) -> None:
        client = self.serve()
        moved = client.invoke(MOVE, {"x_mm": 30.0, "y_mm": 40.0}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"x_mm": 30.0, "y_mm": 40.0})
        state = self.state(client)
        self.assertEqual((state["x_mm"], state["y_mm"]), (30.0, 40.0))
        for payload in ({"x_mm": -0.5, "y_mm": 40.0}, {"x_mm": 130.5, "y_mm": 40.0},
                        {"x_mm": 30.0, "y_mm": -0.5}, {"x_mm": 30.0, "y_mm": 100.5}):
            refused = client.invoke(MOVE, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        state = self.state(client)
        self.assertEqual((state["x_mm"], state["y_mm"]), (30.0, 40.0))

    def test_the_estop_calls_both_axis_stops_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.driver.native.stop_calls, 0)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertGreaterEqual(self.driver.native.stop_calls, 2)
        refused = client.invoke(MOVE, {"x_mm": 30.0, "y_mm": 40.0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
