"""Acceptance run of the Andor SDK3 camera package: the gate, plus cases for this driver."""

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


class AndorCameraCases(unittest.TestCase):
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

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["sensor_width"], state["sensor_height"]), (1024, 1024))
        self.assertEqual((state["roi_width"], state["roi_height"]), (1024, 1024))
        self.assertEqual(state["serial_number"], "SIM-0000")
        self.assertEqual(state["integration_time"], 10.0)
        self.assertEqual(state["actual_exposure_time"], 0.01)
        self.assertEqual(state["sensor_temperature"], -40.0)
        self.assertTrue(state["sensor_cooling"])
        self.assertEqual(state["temperature_status"], "idle")
        self.assertEqual(state["temperature_control"], "-40.00")
        self.assertEqual(state["frame_rate"], 10.0)
        self.assertFalse(state["overlap"])

    def test_the_integration_time_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, integration_time=12.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["integration_time"], 10.0)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, integration_time=12.5)["status"], "completed")
        self.assertEqual(self.state(client)["integration_time"], 12.5)
        for value in (0.5, 1000.5):
            refused = self.configure(client, integration_time=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["integration_time"], 12.5)

    def test_the_estop_stops_acquisition_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = self.configure(client, integration_time=12.5)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["integration_time"], 10.0)


if __name__ == "__main__":
    unittest.main()
