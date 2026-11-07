"""Acceptance run of the PAL3 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PalCases(unittest.TestCase):
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

    def test_the_reads_start_at_the_fake_placeholders(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["x_mm"], state["y_mm"], state["z_mm"]), (100.0, 100.0, 100.0))
        self.assertEqual(state["gripper_distance_mm"], 15.0)

    def test_the_absolute_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.motion.cartesian_pose.v1",
                                {"position": {"x": 300, "y": 0, "z": 250}}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["x_mm"], 100.0)             # the fake was not moved

        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("cap.motion.cartesian_pose.v1",
                              {"position": {"x": 300, "y": 0, "z": 250}}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"]["position"], {"x": 300.0, "y": 0.0, "z": 250.0})
        self.assertEqual((self.state(client)["x_mm"], self.state(client)["y_mm"],
                          self.state(client)["z_mm"]), (300.0, 0.0, 250.0))

    def test_the_transfer_moves_the_placeholder_source(self) -> None:
        client = self.serve()
        moved = client.invoke("x-cap.ad-sdl.transfer_vial.v1",
                              {"source": "Tray Holder 1:Slot1:1",
                               "target": "Tray Holder 1:Slot1:3"}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"moved": True, "source": "Tray Holder 1:Slot1:1",
                                           "target": "Tray Holder 1:Slot1:3"})
        self.assertEqual(self.state(client)["gripper_distance_mm"], 4.2)   # the fake modelled a grip

    def test_the_e_stop_disconnects_but_never_reports_a_safe_state(self) -> None:
        # Model review (2026-11-05): stop_remote_service only disconnects the remote service and the clone has no
        # motion stop, so the e-stop sends the disconnect and still reports SAFE_STATE_UNREACHED with the latch held.
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        stopped = client.estop("test", **ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertFalse(stopped["output"]["safe_state_achieved"], stopped)
        self.assertEqual(stopped["output"]["safe_state"]["achieved_by"], [], stopped)
        self.assertFalse(driver.native.remote_service.IsConnected)       # the disconnect was sent
        self.assertTrue(client.safety_status(device_id=device_id)["estop"]["engaged"])
        for capability, payload in (("x-cap.ad-sdl.reconnect.v1", {}), ("x-cap.ad-sdl.home_axes.v1", {})):
            refused = client.invoke(capability, payload, **ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_disconnect_is_an_ordinary_action_and_the_re_enable_reconnects(self) -> None:
        client = self.serve()
        disconnected = client.invoke("x-cap.ad-sdl.disconnect.v1", {}, **self.ids)
        self.assertEqual(disconnected["status"], "completed", disconnected)
        self.assertTrue(disconnected["output"]["disconnected"])
        self.assertFalse(client.safety_status(device_id=self.ids["device_id"])["estop"]["engaged"])
        reconnected = client.invoke("x-cap.ad-sdl.reconnect.v1", {}, **self.ids)
        self.assertEqual(reconnected["status"], "completed", reconnected)
        self.assertTrue(reconnected["output"]["connected"])


if __name__ == "__main__":
    unittest.main()
