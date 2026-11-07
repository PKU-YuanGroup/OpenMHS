"""Acceptance run of the Zaber stage package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The numbers below are test data for the fake, not facts about a
stage.
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


class ZaberStageCases(unittest.TestCase):
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

    def overlay(self):
        return str(HERE / "site-limits.example.json")

    def test_the_initial_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["x_position"], state["y_position"], state["z_position"]), (0.0, 0.0, 0.0))
        self.assertEqual((state["x_travel"], state["y_travel"], state["z_travel"]), (100.0, 100.0, 100.0))
        self.assertEqual((state["x_microstep_size"], state["y_microstep_size"], state["z_microstep_size"]),
                         (1.0, 1.0, 1.0))
        self.assertEqual((state["x_actuator_id"], state["y_actuator_id"], state["z_actuator_id"]),
                         (1001, 1002, 1003))
        self.assertFalse(state["homed"])

    def test_the_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, x_microstep_size=0.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["x_microstep_size"], 1.0)           # the fake default, untouched
        refused = self.configure(client, x_travel=450)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_supplies_the_bounds(self) -> None:
        client = self.serve(self.overlay())
        self.assertEqual(self.configure(client, x_microstep_size=0.5)["status"], "completed")
        self.assertEqual(self.state(client)["x_microstep_size"], 0.5)
        refused = self.configure(client, x_microstep_size=2.0)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.configure(client, x_travel=450)["status"], "completed")
        self.assertEqual(self.state(client)["x_travel"], 450.0)

    def test_the_moves_need_the_site_and_then_change_the_state(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.janelia-python.move_absolute.v1", {"x": 50, "y": 25, "z": 10}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["x_position"], 0.0)
        client = self.serve(self.overlay())
        moved = client.invoke("x-cap.janelia-python.move_absolute.v1", {"x": 50, "y": 25, "z": 10}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"x": 50.0, "y": 25.0, "z": 10.0})
        state = self.state(client)
        self.assertEqual((state["x_position"], state["y_position"], state["z_position"]), (50.0, 25.0, 10.0))
        relative = client.invoke("x-cap.janelia-python.move_relative.v1", {"x": 5, "y": -5, "z": 0}, **self.ids)
        self.assertEqual(relative["status"], "completed")
        self.assertEqual(self.state(client)["x_position"], 55.0)
        self.assertEqual(self.state(client)["y_position"], 20.0)

    def test_stored_positions(self) -> None:
        client = self.serve(self.overlay())
        client.invoke("x-cap.janelia-python.move_absolute.v1", {"x": 40, "y": 20, "z": 10}, **self.ids)
        stored = client.invoke("x-cap.janelia-python.store_position.v1", {"address": 3}, **self.ids)
        self.assertEqual(stored["output"], {"x": 40.0, "y": 20.0, "z": 10.0})
        client.invoke("x-cap.janelia-python.move_relative.v1", {"x": -10, "y": -5, "z": -2}, **self.ids)
        back = client.invoke("x-cap.janelia-python.move_to_stored_position.v1", {"address": 3}, **self.ids)
        self.assertEqual(back["status"], "completed")
        self.assertEqual(back["output"], {"x": 40.0, "y": 20.0, "z": 10.0})
        refused = client.invoke("x-cap.janelia-python.move_to_stored_position.v1", {"address": 16}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_home_and_stop(self) -> None:
        client = self.serve(self.overlay())
        client.invoke("x-cap.janelia-python.move_absolute.v1", {"x": 50, "y": 25, "z": 10}, **self.ids)
        homed = client.invoke("x-cap.janelia-python.home.v1", {}, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True})
        self.assertTrue(self.state(client)["homed"])
        self.assertEqual(self.state(client)["x_position"], 0.0)
        stopped = client.invoke("x-cap.janelia-python.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.janelia-python.home.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
