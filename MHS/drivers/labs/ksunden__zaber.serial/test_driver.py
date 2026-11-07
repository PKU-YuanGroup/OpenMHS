"""Acceptance run of the Zaber ASCII axis package: the gate, plus cases specific to this driver.

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
HOME = "x-cap.ksunden.home.v1"
STOP = "x-cap.ksunden.stop.v1"
MOVE_ABS = "x-cap.ksunden.move_abs.v1"
MOVE_REL = "x-cap.ksunden.move_rel.v1"
MOVE_VEL = "x-cap.ksunden.move_vel.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ZaberAxisCases(unittest.TestCase):
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

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_the_motion_waits_for_the_site(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["position"], state["status"]), (0, "IDLE"))
        for capability_id, payload in ((MOVE_ABS, {"position": 1000}),
                                       (MOVE_REL, {"distance": 500}),
                                       (MOVE_VEL, {"speed": 1000})):
            refused = self.invoke(client, capability_id, payload)
            self.assertEqual(refused["status"], "rejected", capability_id)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, capability_id)
        state = self.state(client)
        self.assertEqual((state["position"], state["status"]), (0, "IDLE"))

    def test_home_and_stop_take_no_motion_bound(self) -> None:
        client = self.serve()
        homed = self.invoke(client, HOME)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True})
        stopped = self.invoke(client, STOP)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})
        self.assertEqual(self.state(client)["status"], "IDLE")

    def test_the_example_overlay_moves_the_axis(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.invoke(client, MOVE_ABS, {"position": 1000})
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"position": 1000})
        self.assertEqual(self.state(client)["position"], 1000)
        relative = self.invoke(client, MOVE_REL, {"distance": 500})
        self.assertEqual(relative["status"], "completed")
        self.assertEqual(relative["output"], {"position": 1500})
        self.assertEqual(self.state(client)["position"], 1500)
        for capability_id, payload in ((MOVE_ABS, {"position": 10001}),
                                       (MOVE_ABS, {"position": -10001}),
                                       (MOVE_REL, {"distance": 10001}),
                                       (MOVE_VEL, {"speed": -10001})):
            refused = self.invoke(client, capability_id, payload)
            self.assertEqual(refused["status"], "rejected", (capability_id, payload))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (capability_id, payload))
        self.assertEqual(self.state(client)["position"], 1500)

    def test_continuous_motion_and_the_stop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moving = self.invoke(client, MOVE_VEL, {"speed": 1000})
        self.assertEqual(moving["status"], "completed")
        self.assertEqual(moving["output"], {"moving": True, "speed": 1000})
        self.assertEqual(self.state(client)["status"], "BUSY")
        stopped = self.invoke(client, STOP)
        self.assertEqual(stopped["output"], {"stopped": True})
        self.assertEqual(self.state(client)["status"], "IDLE")

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.invoke(client, MOVE_VEL, {"speed": 1000})
        self.assertEqual(self.state(client)["status"], "BUSY")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["status"], "IDLE")
        refused = self.invoke(client, MOVE_ABS, {"position": 500})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
