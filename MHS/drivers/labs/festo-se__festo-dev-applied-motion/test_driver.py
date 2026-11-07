"""Acceptance run of the Festo FPosBAPI package: the gate, plus cases for this driver.

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


class FestoGantryCases(unittest.TestCase):
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

    def test_the_speed_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, global_speed=60.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["global_speed"], 50.0)  # the fake start value, untouched

    def test_the_example_overlay_supplies_the_speed_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, global_speed=60.0)["status"], "completed")
        self.assertEqual(self.state(client)["global_speed"], 60.0)
        for value in (0.5, 250.0):
            refused = self.configure(client, global_speed=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["global_speed"], 60.0)

    def test_home_and_the_cartesian_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        homed = client.invoke("x-cap.festo-se.home_axes.v1", {}, **self.ids)
        self.assertEqual(homed["output"], {"homed": True})
        self.assertEqual(self.state(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

        moved = client.invoke("cap.motion.cartesian_pose.v1",
                              {"position": {"x": 100.0, "y": 50.0, "z": 20.0}}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertTrue(moved["output"]["reached"])
        self.assertEqual(moved["output"]["position"], {"x": 100.0, "y": 50.0, "z": 20.0})
        self.assertEqual(self.state(client)["position"], {"x": 100.0, "y": 50.0, "z": 20.0})

    def test_the_move_envelope_is_enforced(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = client.invoke("cap.motion.cartesian_pose.v1",
                                {"position": {"x": 900.0, "y": 50.0, "z": 20.0}}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_the_stop_halts_and_the_estop_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.invoke("x-cap.festo-se.halt_motion.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"stopped": True})
        self.assertEqual(self.state(client)["sys_status"], "HALTED")

        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.festo-se.home_axes.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
