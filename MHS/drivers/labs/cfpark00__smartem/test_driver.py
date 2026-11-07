"""Acceptance run of the SmartEM Verios package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
DEVICE = "smartem-verios"

# Operator overlay for the cases: the driver refuses every numeric input until the site supplies its bounds.
SITE_LIMITS = {
    "openmhs": "0.9",
    "site": "SmartEM Verios driver test",
    "issued_by": {"id": "operator:test"},
    "devices": {
        "mhs://localhost/smartem-verios": {
            "x-cap.cfpark00.acquire_image.v1": {
                "width": {"min": 1, "max": 4096, "unit": "1", "source": "operator", "reason": "test"},
                "height": {"min": 1, "max": 4096, "unit": "1", "source": "operator", "reason": "test"},
                "dwell_time": {"min": 1e-9, "max": 1e-6, "unit": "s", "source": "operator", "reason": "test"},
                "pixel_size": {"min": 1e-12, "max": 1e-6, "unit": "1", "source": "operator", "reason": "test"},
            },
            "x-cap.cfpark00.move_stage.v1": {
                "x": {"min": -1e-3, "max": 1e-3, "unit": "1", "source": "operator", "reason": "test"},
                "y": {"min": -1e-3, "max": 1e-3, "unit": "1", "source": "operator", "reason": "test"},
                "z": {"min": -1e-3, "max": 1e-3, "unit": "1", "source": "operator", "reason": "test"},
                "r": {"min": -1, "max": 1, "unit": "1", "source": "operator", "reason": "test"},
                "t": {"min": -1, "max": 1, "unit": "1", "source": "operator", "reason": "test"},
            },
        }
    },
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SmartemVeriosCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_image_inputs_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.cfpark00.acquire_image.v1",
                                {"width": 8, "height": 6, "dwell_time": 5e-8, "pixel_size": 4e-9}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_acquire_image_writes_a_pgm(self) -> None:
        client = self.serve(SITE_LIMITS)
        receipt = client.invoke("x-cap.cfpark00.acquire_image.v1",
                                {"width": 8, "height": 6, "dwell_time": 5e-8, "pixel_size": 4e-9}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (8, 6))
        self.assertEqual(output["media_type"], "image/x-portable-graymap")
        data = Path(output["image_ref"]).read_bytes()
        self.assertTrue(data.startswith(b"P5\n8 6\n65535\n"), data[:20])

    def test_move_and_the_two_setup_actions(self) -> None:
        client = self.serve(SITE_LIMITS)
        moved = client.invoke("x-cap.cfpark00.move_stage.v1",
                              {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0, "t": 0.0}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"applied": True})
        focused = client.invoke("x-cap.cfpark00.auto_focus.v1", {}, **self.ids)
        self.assertEqual(focused["status"], "completed", focused)
        self.assertEqual(focused["output"], {"applied": True})
        prepared = client.invoke("x-cap.cfpark00.prepare_acquisition.v1", {}, **self.ids)
        self.assertEqual(prepared["status"], "completed", prepared)
        self.assertEqual(prepared["output"], {"prepared": True})

    def test_release_is_the_safe_state_action(self) -> None:
        client = self.serve()
        released = client.invoke("x-cap.cfpark00.release_microscope.v1", {}, **self.ids)
        self.assertEqual(released["status"], "completed", released)
        self.assertEqual(released["output"], {"released": True})

    def test_the_estop_latches_the_device(self) -> None:
        client = self.serve(SITE_LIMITS)
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.cfpark00.acquire_image.v1",
                                {"width": 8, "height": 6, "dwell_time": 5e-8, "pixel_size": 4e-9}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
