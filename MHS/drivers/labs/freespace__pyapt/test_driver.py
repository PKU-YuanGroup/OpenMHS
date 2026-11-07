"""Acceptance run of the pyapt package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything here runs on the fake backend; no hardware is used.
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


class PyaptCases(unittest.TestCase):
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

    def test_the_absolute_position_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, position=5.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 1.0)          # the fake's placeholder, untouched

    def test_the_example_overlay_opens_and_bounds_the_position(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, position=5.0)["status"], "completed")
        self.assertEqual(self.state(client)["position"], 5.0)
        refused = self.configure(client, position=50.01)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["position"], 5.0)

    def test_the_velocity_parameters_and_the_soft_limit_switch(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, maximum_velocity=0.5)["status"], "completed")
        self.assertEqual(self.state(client)["maximum_velocity"], 0.5)
        self.assertEqual(self.configure(client, acceleration=0.4)["status"], "completed")
        self.assertEqual(self.state(client)["acceleration"], 0.4)
        self.assertEqual(self.configure(client, soft_limits=False)["status"], "completed")
        self.assertFalse(self.state(client)["soft_limits"])

    def test_the_relative_move_and_the_home(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("x-cap.freespace.move_relative.v1", {"distance": 0.5}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"position": 1.5})
        self.assertEqual(self.state(client)["position"], 1.5)
        homed = client.invoke("cap.motion.home.v1", {}, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True})
        state = self.state(client)
        self.assertTrue(state["homed"])
        self.assertEqual(state["position"], 0.0)

    def test_the_estop_stops_motion_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(client.invoke("x-cap.freespace.move_relative.v1", {"distance": 0.5},
                                       **self.ids)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["moving"])
        refused = self.configure(client, position=2.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
