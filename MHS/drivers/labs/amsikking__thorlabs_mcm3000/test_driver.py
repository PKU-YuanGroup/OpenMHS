"""Acceptance run of the Thorlabs MCM3000 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MOVE = "x-cap.amsikking.move_channel.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Mcm3000Cases(unittest.TestCase):
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

    def move(self, client, channel, position_um, relative=False):
        return client.invoke(MOVE, {"channel": channel, "position_um": position_um, "relative": relative},
                             **self.ids)

    def test_the_three_channel_positions_are_read(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        state = driver.read("main")
        self.assertEqual((state["position_ch0"], state["position_ch1"], state["position_ch2"]),
                         (0.0, 0.0, 0.0))                       # the fake's placeholder start positions

    def test_a_move_without_the_site_overlay_is_refused(self) -> None:
        client = self.serve()
        refused = self.move(client, 0, 10.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position_ch0"], 0.0)

    def test_the_example_overlay_moves_a_channel(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        done = self.move(client, 0, 10.0)
        self.assertEqual(done["status"], "completed", done)
        self.assertTrue(done["output"]["reached"])
        self.assertEqual(done["output"]["channel"], 0)
        self.assertAlmostEqual(done["output"]["measured_position_um"], 10.0, places=9)
        self.assertAlmostEqual(self.state(client)["position_ch0"], 10.0, places=9)

    def test_a_relative_move_adds_the_offset(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.move(client, 0, 10.0)["status"], "completed")
        done = self.move(client, 0, 5.0, relative=True)
        self.assertEqual(done["status"], "completed", done)
        self.assertAlmostEqual(done["output"]["target_position_um"], 15.0, places=9)
        self.assertAlmostEqual(self.state(client)["position_ch0"], 15.0, places=9)

    def test_a_channel_outside_the_three_ports_is_refused(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.move(client, 3, 0.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_stop_action_completes(self) -> None:
        client = self.serve()
        stopped = client.invoke("cap.motion.stop.v1", {"deceleration": 2.0}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_sends_the_vendor_stop_frames(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertEqual(driver.native.received[-3:],
                         [b"\x65\x04\x00\x01\x00\x00",
                          b"\x65\x04\x01\x01\x00\x00",
                          b"\x65\x04\x02\x01\x00\x00"])

    def test_the_estop_latches_and_refuses_a_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        refused = self.move(client, 0, 10.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
