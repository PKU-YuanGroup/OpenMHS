"""Acceptance run of the OpenCat package: the gate, plus cases for the serial tokens this driver sends."""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Telemetry(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_send_the_firmware_tokens(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["identity"], {"model": "Bittle", "firmware": "N_260806"})
        self.assertEqual(state["orientation"], {"pitch_deg": 0.0, "roll_deg": 0.0})
        self.assertEqual(state["joint_angles_deg"], [0] * 16)
        self.assertEqual(driver.native.sent, [b"?\n", b"v\n", b"j\n"])

    def test_the_estop_sends_the_rest_command(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertIn(b"d\n", driver.native.sent)
        self.assertTrue(driver.native.resting)

    def test_a_stale_rest_reply_does_not_confuse_the_next_read(self) -> None:
        driver = self.driver()
        driver.estop("test")
        state = driver.read("main")
        self.assertEqual(state["identity"]["model"], "Bittle")


class Rest(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session}

    def test_the_rest_action_puts_the_fake_down(self) -> None:
        client, ids = self.serve()
        receipt = client.invoke("x-cap.petoicamp.rest.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"resting": True})


if __name__ == "__main__":
    unittest.main()
