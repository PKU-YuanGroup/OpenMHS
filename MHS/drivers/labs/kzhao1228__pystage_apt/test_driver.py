"""Acceptance run of the pystage-apt package: the gate, plus cases for what is specific to this driver.

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


class AptStageCases(unittest.TestCase):
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

    def test_the_position_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, position=3)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 1.0)       # the fake's starting test value, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, position=3)["status"], "completed")
        self.assertEqual(self.state(client)["position"], 3.0)
        self.assertEqual(self.configure(client, maximum_velocity=4)["status"], "completed")
        self.assertEqual(self.state(client)["maximum_velocity"], 4.0)
        self.assertEqual(self.configure(client, acceleration=2)["status"], "completed")
        self.assertEqual(self.state(client)["acceleration"], 2.0)
        for patch in ({"position": 6}, {"maximum_velocity": 6}, {"acceleration": 6}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_homing_fields_are_closed_sets(self) -> None:
        client = self.serve()
        for patch in ({"home_direction": 3}, {"home_limit_switch": 2}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.configure(client, home_direction=2)["status"], "completed")
        self.assertEqual(self.state(client)["home_direction"], 2)
        self.assertEqual(self.configure(client, home_limit_switch=4)["status"], "completed")
        self.assertEqual(self.state(client)["home_limit_switch"], 4)

    def test_home_relative_and_stop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("x-cap.kzhao1228.move_relative.v1", {"distance": 0.5}, **self.ids)
        self.assertEqual(moved["output"], {"position": 1.5})
        homed = client.invoke("cap.motion.home.v1", {}, **self.ids)
        self.assertEqual(homed["output"], {"homed": True})
        self.assertEqual(self.state(client)["position"], 0.0)
        stopped = client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["output"]["stopped"], True)

    def test_the_estop_stops_motion_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(client.invoke("cap.motion.home.v1", {}, **self.ids)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["in_motion"])
        refused = self.configure(client, position=2)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
