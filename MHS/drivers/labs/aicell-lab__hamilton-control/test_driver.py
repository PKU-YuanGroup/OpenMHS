"""Acceptance run of the incubator package: the gate, plus cases for this repository.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DEVICE = "hamilton-control-incubator"
OVERLAY = {
    "devices": {
        f"mhs://localhost/{DEVICE}": {
            "cap.thermal.setpoint.v1": {
                "target_temperature": {"min": 20, "max": 40, "unit": "Cel", "source": "operator",
                                       "reason": "test overlay: a narrow range around the test setpoint"}
            },
            "x-cap.aicell-lab.start_shaking.v1": {
                "frequency": {"min": 0.1, "max": 5, "unit": "Hz", "source": "operator",
                              "reason": "test overlay: a narrow range around the test frequency"}
            },
        }
    }
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class IncubatorCases(unittest.TestCase):
    def setUp(self) -> None:
        self.server = load(HERE, backend="fake")
        self.addCleanup(close_server, self.server)
        self.client = client_for(self.server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}

    def invoke(self, capability, payload):
        return self.client.invoke(capability, payload, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def test_temperature_is_read_and_measured(self) -> None:
        self.assertIsInstance(self.state()["temperature"], (int, float))
        receipt = self.invoke("cap.measure.temperature.v1", {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIsInstance(receipt["output"]["temperature"], (int, float))
        self.assertIn("sampled_at", receipt["output"])

    def test_temperature_setpoint_needs_the_operator_envelope(self) -> None:
        receipt = self.invoke("cap.thermal.setpoint.v1", {"target_temperature": 37})
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", receipt)

    def test_temperature_setpoint_with_an_operator_overlay(self) -> None:
        server = load(HERE, backend="fake", site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 37},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["setpoint"], 37)
        self.assertEqual(client.read("main", device_id=device_id, session_id=session)["state"]["temperature"], 37.0)

    def test_start_and_stop_shaking(self) -> None:
        server = load(HERE, backend="fake", site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("x-cap.aicell-lab.start_shaking.v1", {"frequency": 1.0},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        receipt = client.invoke("x-cap.aicell-lab.stop_shaking.v1", {},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["stopped"])

    def test_fetch_and_take_return_a_plate(self) -> None:
        before = self.state()["num_free_sites"]
        receipt = self.invoke("x-cap.aicell-lab.fetch_plate.v1", {"plate_name": "plate_1"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state()["num_free_sites"], before + 1)
        receipt = self.invoke("x-cap.aicell-lab.take_in_plate.v1", {"site": "random"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state()["num_free_sites"], before)

    def test_estop_is_unreached_and_keeps_the_latch(self) -> None:
        # Model review: no source-backed stop exists, so the e-stop is never reported as reached.
        self.invoke("x-cap.aicell-lab.fetch_plate.v1", {"plate_name": "plate_1"})
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        receipt = self.invoke("x-cap.aicell-lab.fetch_plate.v1", {"plate_name": "plate_2"})
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", receipt)


if __name__ == "__main__":
    unittest.main()
