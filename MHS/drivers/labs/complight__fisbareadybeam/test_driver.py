"""Acceptance run of the Fisba ReadyBeam package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def state(self, client, fields=None):
        return client.read("main", fields=fields, **self.ids)["state"]

    def test_the_state_of_the_module(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["device_status"], 1)                      # the fake's placeholder 'Ready'
        self.assertEqual(state["device_type"], "=0001171")               # the fake's placeholder frame
        self.assertNotIn("brightness", state)                            # not written yet

    def test_a_brightness_write_is_reported_and_reaches_the_device(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, brightness=[10.0, 0.0, 25.5]), "completed")
        self.assertEqual(self.state(client)["brightness"], [10.0, 0.0, 25.5])
        self.assertEqual(self.configure(client, brightness=[0.0, 0.0, 0.0]), "completed")
        self.assertEqual(self.state(client)["brightness"], [0.0, 0.0, 0.0])

    def test_the_bounds_of_the_upstream_docstring(self) -> None:
        client = self.serve()
        for patch in ({"brightness": [100.6, 0.0, 0.0]}, {"brightness": [-0.1, 0.0, 0.0]},
                      {"brightness": [0.0, 0.0, 100.51]}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"brightness": [0.0, 0.0, 0.0]}, {"brightness": [100.5, 100.5, 100.5]}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, brightness=[10.0, 20.0, 30.0]), "completed")
        for patch in ({"brightness": [0.0, 0.0, 0.0]}, {"brightness": [100.5, 0.0, 0.0]}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)


class Safety(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_estop_switches_all_channels_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"brightness": [10.0, 20.0, 30.0]})
        self.assertEqual(driver.native._brightness, [10.0, 20.0, 30.0])
        driver.estop("test")
        self.assertEqual(driver.native._brightness, [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
