"""Acceptance run of the SMC100 package: the gate, plus cases for what is specific to this driver.

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


class Smc100Cases(unittest.TestCase):
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

    def test_the_initial_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position"], 0.0)                 # placeholder start position of the fake
        self.assertEqual(state["state"], "READY from HOMING")    # placeholder start state of the fake
        self.assertEqual(state["errors"], [])
        self.assertEqual(state["velocity"], 1.0)                 # placeholder start velocity of the fake

    def test_velocity_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, velocity=2)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["velocity"], 1.0)    # untouched placeholder

    def test_the_example_overlay_bounds_the_velocity(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, velocity=2.5)["status"], "completed")
        self.assertEqual(self.state(client)["velocity"], 2.5)
        refused = self.configure(client, velocity=10.01)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["velocity"], 2.5)

    def test_absolute_and_relative_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("x-cap.jieunboy0516.move_absolute.v1", {"position": 4.0}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["position"], 4.0)
        self.assertEqual(self.state(client)["position"], 4.0)
        relative = client.invoke("x-cap.jieunboy0516.move_relative.v1", {"offset": -1.5}, **self.ids)
        self.assertEqual(relative["output"]["position"], 2.5)
        refused = client.invoke("x-cap.jieunboy0516.move_absolute.v1", {"position": -0.01}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["position"], 2.5)

    def test_home_then_stop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke("x-cap.jieunboy0516.move_absolute.v1", {"position": 4.0}, **self.ids)
        homed = client.invoke("x-cap.jieunboy0516.start_home.v1", {}, **self.ids)
        self.assertEqual(homed["output"], {"started": True})
        self.assertEqual(self.state(client)["position"], 0.0)
        stopped = client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke("x-cap.jieunboy0516.start_home.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.jieunboy0516.move_absolute.v1", {"position": 4.0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
