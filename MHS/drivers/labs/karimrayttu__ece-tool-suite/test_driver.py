"""Acceptance run of the ECE Tool Suite scope package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call. The fake's values are test data, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Reads(unittest.TestCase):
    def test_the_identity_and_the_light_measurements_read(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        state = driver.read("main", ["identity", "measurements"])
        self.assertIsInstance(state["identity"], str)
        self.assertIn(",", state["identity"])
        self.assertEqual(set(state["measurements"]),
                         {"vpp", "vrms", "vmax", "vmin", "freq", "period"})
        for value in state["measurements"].values():
            self.assertTrue(value is None or isinstance(value, (int, float)))

    def test_the_estop_halts_acquisition_and_latches(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertTrue(driver.read("main", ["identity"])["identity"])


class Actions(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_the_measurement_action_returns_item_value_and_unit(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.karimrayttu.measure.v1", {"item": "vpp"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["item"], "vpp")
        self.assertEqual(receipt["output"]["unit"], "V")
        self.assertIsInstance(receipt["output"]["value"], (int, float))

    def test_two_measurement_items_give_different_outputs(self) -> None:
        client, device_id, session = self.serve()
        first = client.invoke("x-cap.karimrayttu.measure.v1", {"item": "vpp"},
                              device_id=device_id, session_id=session)["output"]
        second = client.invoke("x-cap.karimrayttu.measure.v1", {"item": "freq"},
                               device_id=device_id, session_id=session)["output"]
        self.assertNotEqual(first, second)

    def test_the_capture_reports_a_scalar_summary(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.karimrayttu.capture.v1", {},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertGreaterEqual(receipt["output"]["points"], 1)
        self.assertGreaterEqual(receipt["output"]["duration_s"], 0)

    def test_run_single_and_reset_complete(self) -> None:
        client, device_id, session = self.serve()
        for capability_id, state in (("x-cap.karimrayttu.run.v1", "running"),
                                     ("x-cap.karimrayttu.single.v1", "single"),
                                     ("x-cap.karimrayttu.reset.v1", "reset"),
                                     ("x-cap.karimrayttu.stop_acquisition.v1", "stopped")):
            receipt = client.invoke(capability_id, {}, device_id=device_id, session_id=session)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"]["state"], state)

    def test_the_estop_blocks_a_new_run(self) -> None:
        client, device_id, session = self.serve()
        client.estop("test", device_id=device_id, session_id=session)
        refused = client.invoke("x-cap.karimrayttu.run.v1", {},
                                device_id=device_id, session_id=session)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
