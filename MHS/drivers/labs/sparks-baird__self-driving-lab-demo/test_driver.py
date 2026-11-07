"""Acceptance run of the CLSLab:Light package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MEASURE = "x-cap.sparks-baird.measure_spectrum.v1"
WAVELENGTHS = [410.0, 440.0, 470.0, 510.0, 550.0, 583.0, 620.0, 670.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ClslabLightCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def measure(self, client, **payload):
        return client.invoke(MEASURE, payload, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_color_write_and_its_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["color"], [0, 0, 0])
        applied = self.configure(client, color=[10, 20, 30])
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["color"], [10, 20, 30])
        refused = self.configure(client, color=[256, 0, 0])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["color"], [10, 20, 30])

    def test_the_spectrum_action_and_its_bounds(self) -> None:
        client = self.serve()
        self.configure(client, color=[10, 20, 30])
        receipt = self.measure(client, atime=10, astep=20, gain=128)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["wavelengths"], WAVELENGTHS)
        self.assertEqual(len(output["intensities"]), 8)
        self.assertAlmostEqual(output["integration_ms"], (20 + 1) * (10 + 1) * 2.78 / 1000.0)
        for payload in ({"atime": 256, "astep": 20, "gain": 128},
                        {"atime": 10, "astep": 65535, "gain": 128},
                        {"atime": 10, "astep": 20, "gain": 0.4}):
            refused = self.measure(client, **payload)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_turns_the_led_off_and_latches(self) -> None:
        client = self.serve()
        self.configure(client, color=[40, 50, 60])
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["color"], [0, 0, 0])
        refused = self.configure(client, color=[1, 2, 3])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
