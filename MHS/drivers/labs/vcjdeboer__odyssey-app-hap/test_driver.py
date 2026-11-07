"""Acceptance run of the LI-COR Odyssey Classic package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
CONTROL = "x-cap.vcjdeboer.odyssey_control_scan.v1"
SAFE_STOP = "x-cap.vcjdeboer.odyssey_safe_stop.v1"
IMAGE = "cap.sensing.image.v1"
CONFIGURE = "cap.device.configure.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OdysseyCases(unittest.TestCase):
    def serve(self, site_limits=None, **server_options):
        server = load(HERE, backend="fake", site_limits=site_limits, **server_options)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def invoke(self, client, capability, payload=None):
        return client.invoke(capability, payload or {}, **self.ids)

    def test_initial_state_is_the_next_configuration_and_the_idle_status(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["scan_name"], "scan")
        self.assertEqual(state["scan_group"], "odyssey")
        self.assertEqual(state["resolution"], "169")
        self.assertEqual(state["quality"], "medium")
        self.assertAlmostEqual(state["intensity_700"], 5.0)
        self.assertAlmostEqual(state["intensity_800"], 5.0)
        self.assertTrue(state["channel_700"])
        self.assertTrue(state["channel_800"])
        self.assertEqual((state["origin_x_cm"], state["origin_y_cm"]), (0, 0))
        self.assertEqual((state["width_cm"], state["height_cm"]), (10, 10))
        self.assertAlmostEqual(state["focus_offset_mm"], 0.0)
        self.assertEqual(state["state"], "Idle")
        self.assertAlmostEqual(state["progress_percent"], 0.0)
        self.assertFalse(state["lid_open"])
        self.assertIn("placeholder", state["instrument_info"])

    def test_a_write_reaches_the_fake_and_is_read_back(self) -> None:
        client = self.serve()
        receipt = self.invoke(client, CONFIGURE, {"resolution": "84", "intensity_700": 2.5})
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertEqual(state["resolution"], "84")
        self.assertAlmostEqual(state["intensity_700"], 2.5)
        self.assertEqual(state["state"], "Configured")

    def test_the_sourced_envelope_refuses_before_the_native_call(self) -> None:
        client = self.serve()
        for patch in ({"resolution": "5"}, {"quality": "ultra"}, {"intensity_700": 0.25},
                      {"origin_x_cm": 26}, {"focus_offset_mm": -0.1}):
            refused = self.invoke(client, CONFIGURE, patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", patch)
        state = self.state(client)
        self.assertEqual(state["resolution"], "169")
        self.assertAlmostEqual(state["intensity_700"], 5.0)

    def test_width_and_height_need_the_operator_overlay(self) -> None:
        client = self.serve()
        for patch in ({"width_cm": 12}, {"height_cm": 12}):
            refused = self.invoke(client, CONFIGURE, patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", patch)
        client = self.serve(site_limits=str(HERE / "site-limits.example.json"))
        receipt = self.invoke(client, CONFIGURE, {"width_cm": 12, "height_cm": 8})
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertEqual((state["width_cm"], state["height_cm"]), (12, 8))

    def test_scan_control_walks_the_fake_state_machine(self) -> None:
        client = self.serve()
        expected = (("start", "Scanning"), ("pause", "Paused"), ("stop", "Stopped"), ("cancel", "Idle"))
        for command, state_name in expected:
            receipt = self.invoke(client, CONTROL, {"command": command})
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"]["state"], state_name)
            self.assertEqual(self.state(client)["state"], state_name)

    def test_capture_publishes_the_jpeg_preview_artifact(self) -> None:
        client = self.serve(artifact_store=LocalArtifactStore())
        receipt = self.invoke(client, IMAGE)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (8, 6))
        self.assertEqual(output["media_type"], "image/jpeg")
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)
        artifact = client.read_artifact(output["image_ref"], session_id=self.ids["session_id"])
        self.assertTrue(artifact["data"].startswith(b"\xff\xd8"))

    def test_capture_without_a_store_refuses_before_the_native_preview(self) -> None:
        client = self.serve()
        receipt = self.invoke(client, IMAGE)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY", receipt)

    def test_estop_calls_the_status_stop_and_latches(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertGreaterEqual(driver.native._stop_from_status_calls, 1)
        client = self.serve()
        safe = self.invoke(client, SAFE_STOP)
        self.assertEqual(safe["status"], "completed", safe)
        self.assertTrue(safe["output"]["stopped"])
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = self.invoke(client, CONTROL, {"command": "start"})
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)

    def test_estop_during_a_scan_is_confirmed_by_the_status_page(self) -> None:
        # Model review: the stop holds only when a fresh status read reports Idle or Stopped.
        client = self.serve()
        self.assertEqual(self.invoke(client, CONTROL, {"command": "start"})["status"], "completed")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["state"], "Stopped")

    def test_a_stop_the_status_page_does_not_confirm_is_unreached_and_latched(self) -> None:
        # Model review: stop_from_status returns its response unchecked; a scanner still reporting Scanning after
        # the Stop is SAFE_STATE_UNREACHED with the latch held, never a completed e-stop or safe state.
        client = self.serve(options={"stop_ignored": True})
        self.assertEqual(self.invoke(client, CONTROL, {"command": "start"})["status"], "completed")
        safe = self.invoke(client, SAFE_STOP)
        self.assertEqual(safe["status"], "failed", safe)
        self.assertEqual(safe["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", safe)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        refused = self.invoke(client, CONTROL, {"command": "start"})
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)


if __name__ == "__main__":
    unittest.main()
