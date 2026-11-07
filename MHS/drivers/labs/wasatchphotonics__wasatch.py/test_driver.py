"""Acceptance run of the Wasatch package: the gate, plus cases for this driver.

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


class WasatchCases(unittest.TestCase):
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
        self.assertEqual(state["integration_time_ms"], 100)
        self.assertEqual(state["detector_temperature_degC"], 25.0)
        self.assertEqual(state["detector_tec_setpoint_degC"], -10.0)
        self.assertFalse(state["tec_enabled"])
        self.assertFalse(state["laser_enabled"])
        self.assertEqual(state["ambient_temperature_degC"], 22.0)

    def test_the_integration_time_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, integration_time_ms=50)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["integration_time_ms"], 100)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, integration_time_ms=50)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["integration_time_ms"], 50)
        for value in (0, 60001):
            refused = self.configure(client, integration_time_ms=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["integration_time_ms"], 50)

    def test_the_spectrum_uses_the_integration_time(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        first = client.invoke("x-cap.wasatchphotonics.acquire_spectrum.v1", {}, **self.ids)
        self.assertEqual(first["status"], "completed")
        output = first["output"]
        self.assertEqual(len(output["wavelengths"]), 8)
        self.assertEqual(len(output["intensities"]), 8)
        self.assertEqual(output["wavelengths"][0], 400.0)
        self.configure(client, integration_time_ms=200)
        second = client.invoke("x-cap.wasatchphotonics.acquire_spectrum.v1", {}, **self.ids)
        self.assertGreater(second["output"]["intensities"][0], output["intensities"][0])

    def test_the_safe_state_disables_the_laser_and_the_estop_latches(self) -> None:
        client = self.serve()
        safe = client.invoke("x-cap.wasatchphotonics.laser_off.v1", {}, **self.ids)
        self.assertEqual(safe["output"], {"laser_enabled": False})
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.wasatchphotonics.acquire_spectrum.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
