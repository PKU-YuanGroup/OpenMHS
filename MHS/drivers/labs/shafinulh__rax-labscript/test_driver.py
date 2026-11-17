"""Acceptance run of the Nuvu camera package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
IMAGE = "cap.sensing.image.v1"
STOP = "x-cap.shafinulh.stop_acquisition.v1"

# The fake's placeholder state (test data, not device facts).
FRAME_SIDE = 8
EXPOSURE_TIME = 20.0
READOUT_MODE = 1
TRIGGER_MODE = 0
SHUTTER_MODE = 1
EM_GAIN = 2
DETECTOR_TEMPERATURE = -55.0
TARGET_DETECTOR_TEMPERATURE = -60.0


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NuvuCameraCases(unittest.TestCase):
    def serve(self, site_limits=None, artifacts=False):
        options = {"artifact_store": LocalArtifactStore()} if artifacts else {}
        self.driver = load_driver(HERE, backend="fake")
        server = build_server(self.driver, site_limits=site_limits, **options)
        self.addCleanup(close_server, server)
        self.server = server
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def site(self):
        return str(HERE / "site-limits.example.json")

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_state_mirrors_the_fake(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertIs(state["acquiring"], False)
        self.assertAlmostEqual(state["exposure_time"], EXPOSURE_TIME)
        self.assertEqual(state["readout_mode"], READOUT_MODE)
        self.assertEqual(state["trigger_mode"], TRIGGER_MODE)
        self.assertEqual(state["shutter_mode"], SHUTTER_MODE)
        self.assertEqual(state["em_gain"], EM_GAIN)
        self.assertAlmostEqual(state["detector_temperature"], DETECTOR_TEMPERATURE)
        self.assertAlmostEqual(state["target_detector_temperature"], TARGET_DETECTOR_TEMPERATURE)

    def test_the_operator_bounds_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"exposure_time": 10}, {"em_gain": 50}):
            refused = client.write("main", patch, **self.ids)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        client = self.serve(self.site())
        applied = client.write("main", {"exposure_time": 10, "em_gain": 50},
                               **self.ids)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertAlmostEqual(state["exposure_time"], 10.0)
        self.assertAlmostEqual(state["target_detector_temperature"], TARGET_DETECTOR_TEMPERATURE)
        self.assertEqual(state["em_gain"], 50)
        for patch in ({"exposure_time": 2000}, {"em_gain": 5000}):
            out_of_range = client.write("main", patch, **self.ids)
            self.assertEqual(out_of_range["error"]["mhs_code"], ENVELOPE, patch)

    def test_temperature_is_read_only_without_a_sourced_unit(self) -> None:
        client = self.serve(self.site())
        refused = client.write("main", {"target_detector_temperature": -40}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertAlmostEqual(self.state(client)["target_detector_temperature"], TARGET_DETECTOR_TEMPERATURE)

    def test_the_enumerated_modes_are_refused_outside_their_set(self) -> None:
        client = self.serve()
        applied = client.write("main", {"readout_mode": 2, "trigger_mode": 3, "shutter_mode": 2}, **self.ids)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["readout_mode"], 2)
        self.assertEqual(state["trigger_mode"], 3)
        self.assertEqual(state["shutter_mode"], 2)
        for patch in ({"readout_mode": 5}, {"trigger_mode": -4}, {"shutter_mode": 9}):
            refused = client.write("main", patch, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_capture_publishes_a_png_artifact(self) -> None:
        client = self.serve(self.site(), artifacts=True)
        receipt = client.invoke(IMAGE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (FRAME_SIDE, FRAME_SIDE))
        self.assertEqual(output["media_type"], "image/png")
        self.assertAlmostEqual(output["exposure_ms"], EXPOSURE_TIME)
        artifact = self.server.read_artifact(output["image_ref"], session_id=self.ids["session_id"])
        self.assertTrue(artifact["data"].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIs(self.state(client)["acquiring"], False)

    def test_capture_applies_an_exposure(self) -> None:
        client = self.serve(self.site(), artifacts=True)
        receipt = client.invoke(IMAGE, {"exposure_ms": 5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertAlmostEqual(receipt["output"]["exposure_ms"], 5.0)
        self.assertAlmostEqual(self.state(client)["exposure_time"], 5.0)

    def test_capture_needs_the_artifact_store(self) -> None:
        client = self.serve(self.site())
        refused = client.invoke(IMAGE, {}, **self.ids)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")

    def test_the_estop_latches_and_the_reset_releases_it(self) -> None:
        client = self.serve(self.site(), artifacts=True)
        client.estop("test", **self.ids)
        refused = client.invoke(IMAGE, {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        client.reset(**self.ids)
        after = client.invoke(IMAGE, {}, **self.ids)
        self.assertEqual(after["status"], "completed", after)

    def test_the_safe_state_action_aborts_acquisition(self) -> None:
        client = self.serve(self.site())
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["acquiring"], False)

    def test_the_safe_state_action_refuses_an_ineffective_abort(self) -> None:
        client = self.serve(self.site())
        self.driver.native.cam_start(1)
        self.driver.native.cam_stop = lambda: None
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt.get("output"))

    def test_the_estop_requires_an_inactive_acquisition_query(self) -> None:
        for state in (1, None):
            with self.subTest(acquisition_state=state):
                client = self.serve(self.site())
                self.driver.native.camIsAcquring = lambda state=state: state
                receipt = client.estop("abort confirmation test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
                refused = client.invoke(IMAGE, {}, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
