"""Acceptance run of the Baumer camera package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.pixels import PNG_SIGNATURE
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BaumerCases(unittest.TestCase):
    def serve(self, site_limits=None, artifact_store=None):
        server = load(HERE, backend="fake", site_limits=site_limits, artifact_store=artifact_store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        hello = client.hello()
        device_id = hello["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def test_reads_are_the_camera_settings(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["exposure_time_us"], 10000.0)
        self.assertEqual(state["exposure_time_range_us"], [28.0, 60000000.0])
        self.assertEqual(state["gain"], 1.0)
        self.assertEqual(state["gain_range"], [1.0, 251.1875])
        self.assertEqual(state["pixel_format"], "RGB8")
        self.assertEqual(state["balance_white_auto"], "Off")

    def test_writes_reach_the_native_and_are_read_back(self) -> None:
        client = self.serve()
        receipt = self.configure(client, exposure_time_us=5000.0, gain=8.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertEqual(state["exposure_time_us"], 5000.0)
        self.assertEqual(state["gain"], 8.0)

    def test_every_bound_is_refused_without_a_native_call(self) -> None:
        client = self.serve()
        for patch in ({"exposure_time_us": 27.0}, {"exposure_time_us": 60000001.0},
                      {"gain": 0.5}, {"gain": 252.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        state = self.state(client)
        self.assertEqual(state["exposure_time_us"], 10000.0)
        self.assertEqual(state["gain"], 1.0)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(site_limits=str(HERE / "site-limits.example.json"))
        refused = self.configure(client, exposure_time_us=25000.0)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        receipt = self.configure(client, exposure_time_us=10000.0, gain=32.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = self.configure(client, gain=65.0)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)

    def test_capture_publishes_the_png_as_an_artifact(self) -> None:
        client = self.serve(artifact_store=LocalArtifactStore())
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (4, 4))
        self.assertEqual(output["media_type"], "image/png")
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)
        artifact = client.read_artifact(output["image_ref"], session_id=client.session_id)
        self.assertTrue(artifact["data"].startswith(PNG_SIGNATURE), artifact["descriptor"])

    def test_capture_without_an_artifact_store_refuses_before_the_native_capture(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        client = self.serve()
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY", receipt)
        self.assertEqual(driver.native._capture_calls, 0)

    def test_estop_reaches_the_native_close_and_latches(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertEqual(driver.native._close_calls, 1)
        client = self.serve(artifact_store=LocalArtifactStore())
        client.estop("test", **self.ids)
        refused = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_after_an_estop_the_upstream_camera_object_cannot_capture_again(self) -> None:
        # Model review: close() destroys the acquirer and nothing re-creates it, so with the faithful fake switch the
        # camera refuses reads and captures after the e-stop, and an operator reset does not bring it back.
        server = load(HERE, backend="fake", artifact_store=LocalArtifactStore())
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        bridge = server.devices[device_id]
        native = getattr(bridge, "native", None) or getattr(getattr(bridge, "bridge", None), "native", None)
        native.destroy_on_close = True
        stopped = client.estop("test", **ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(native._close_calls, 1)
        self.assertEqual(client.reset(**ids)["status"], "completed")
        receipt = client.invoke("cap.sensing.image.v1", {}, **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(native._capture_calls, 0)


if __name__ == "__main__":
    unittest.main()
