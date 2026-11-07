"""Acceptance run of the fibsem-os remote fluorescence microscope package.

The gate, plus cases for what is specific to this driver: the operator-supplied camera bounds, the session channel
label, live-view start/stop, and the e-stop latch.  The check_driver call stays.
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


class RemoteFluorescenceMicroscopeCases(unittest.TestCase):
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

    def test_the_reads_and_the_live_view(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["exposure_time"], state["binning"], state["gain"]), (0.05, 1, 0.5))
        self.assertEqual((state["is_acquiring"], state["is_interactive"]), (False, True))
        self.assertEqual((state["channel_name"], state["channel_color"]), ("DAPI", "#0000FF"))

        started = client.invoke("x-cap.fibsem-os.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"acquiring": True})
        self.assertTrue(self.state(client)["is_acquiring"])

        stopped = client.invoke("x-cap.fibsem-os.stop_acquisition.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"acquiring": False})
        self.assertFalse(self.state(client)["is_acquiring"])
        self.assertEqual(self.state(client)["acquiring_reason"], "")

    def test_the_channel_label_is_writable_without_an_overlay(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel_name="GFP")["status"], "completed")
        self.assertEqual(self.configure(client, channel_color="#00FF00")["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["channel_name"], state["channel_color"]), ("GFP", "#00FF00"))

    def test_the_camera_settings_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, exposure_time=0.2)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["exposure_time"], 0.05)

    def test_the_example_overlay_supplies_the_camera_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, exposure_time=0.2)["status"], "completed")
        self.assertEqual(self.state(client)["exposure_time"], 0.2)
        for value in (0.0005, 20.0):
            refused = self.configure(client, exposure_time=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["exposure_time"], 0.2)
        self.assertEqual(self.configure(client, binning=3)["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.configure(client, binning=4)["status"], "completed")
        self.assertEqual(self.state(client)["binning"], 4)

    def test_the_estop_stops_the_live_view_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.fibsem-os.start_acquisition.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["is_acquiring"])
        refused = client.invoke("x-cap.fibsem-os.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
