"""Acceptance run of the Velmex VXM package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The gate case fails here: the package is blocked on the missing
native stop (the upstream class has no stop, abort or halt method), which is recorded in RESULT.json.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
MOVE = "cap.motion.cartesian_pose.v1"
HOME = "cap.motion.home.v1"
CONFIGURE = "cap.device.configure.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VelmexCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def read(self, client):
        return client.read("main", **self.ids)["state"]

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def code(self, receipt):
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_fake_starts_at_the_reference_position_and_the_constructor_velocity(self) -> None:
        client = self.serve()
        state = self.read(client)
        self.assertEqual(state["position"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual((state["velocity_x"], state["velocity_y"], state["velocity_z"]), (2000.0, 2000.0, 2000.0))

    def test_the_velocity_write_uses_the_range_the_clone_states(self) -> None:
        client = self.serve()
        for value in (0, 6001):
            self.assertEqual(self.code(self.invoke(client, CONFIGURE, {"velocity_x": value})), ENVELOPE, value)
        for value in (1, 6000):
            self.assertEqual(self.code(self.invoke(client, CONFIGURE, {"velocity_x": value})), "completed", value)
            self.assertEqual(self.read(client)["velocity_x"], float(value))

    def test_the_position_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        refused = self.invoke(client, MOVE, {"position": {"x": 10.0, "y": 5.0, "z": 2.0}})
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.read(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_the_cartesian_move_and_home_reach_the_fake(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.invoke(client, MOVE, {"position": {"x": 10.0, "y": 5.0, "z": 2.0}})
        self.assertEqual(moved["status"], "completed")
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(moved["output"]["position"], {"x": 10.0, "y": 5.0, "z": 2.0})
        self.assertEqual(self.read(client)["position"], {"x": 10.0, "y": 5.0, "z": 2.0})

        homed = self.invoke(client, HOME)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True, "axes": ["X", "Y", "Z"]})
        self.assertEqual(self.read(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_the_example_overlay_refuses_a_move_outside_it(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.invoke(client, MOVE, {"position": {"x": 500.0, "y": 5.0, "z": 2.0}})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.read(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_a_home_can_name_one_axis(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.invoke(client, MOVE, {"position": {"x": 10.0, "y": 5.0, "z": 2.0}})["status"],
                         "completed")
        homed = self.invoke(client, HOME, {"axes": ["X"]})
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True, "axes": ["X"]})
        self.assertEqual(self.read(client)["position"], {"x": 0.0, "y": 5.0, "z": 2.0})


if __name__ == "__main__":
    unittest.main()
