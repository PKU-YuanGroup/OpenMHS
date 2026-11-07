"""Acceptance run of the KDS Gemini 88 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The lines the driver writes on the fake's serial port (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_setup_puts_the_pump_in_the_independent_condition(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.native.ser.written[0], b"condition Independent\r\n")

    def test_a_write_becomes_the_command_of_the_tutorial(self) -> None:
        driver = self.driver()
        driver.write("main", {"syringe_volume": 5, "diameter": 4.85, "target_time": 30,
                              "target_volume": 5, "flow_rate": 10})
        self.assertEqual(driver.native.ser.written[1:], [
            b"svolume ab 5 ul\r\n",
            b"diameter ab 4.85\r\n",
            b"ttime ab 30 sec\r\n",
            b"tvolume ab 5 ul\r\n",
            b"irate ab 10 ml/min\r\n",
        ])

    def test_status_run_and_the_estop(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("main")["status"], "FAKE: idle")     # placeholder reply
        receipt = driver.call("x-cap.phamdangnguyen.run.v1", {"channel": "ab"})
        self.assertEqual(receipt, {"channel": "ab", "running": True})
        self.assertTrue(driver.read("main")["running"])
        driver.estop("test")
        self.assertEqual(driver.native.ser.written[-1], b"stop ab\r\n")
        self.assertFalse(driver.read("main")["running"])

    def test_the_syringe_action_uses_the_documented_three_tokens(self) -> None:
        driver = self.driver()
        receipt = driver.call("x-cap.phamdangnguyen.syringe.v1",
                              {"channel": "ab", "code": "sst", "index": 1})
        self.assertEqual(receipt, {"channel": "ab", "code": "sst", "index": 1})
        self.assertEqual(driver.native.ser.written[-1], b"syr ab sst 1\r\n")


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_operator_overlay_every_numeric_write_is_refused(self) -> None:
        client = self.serve()
        for patch in ({"syringe_volume": 5}, {"diameter": 4.85}, {"target_time": 30},
                      {"target_volume": 5}, {"flow_rate": 10}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_fills_and_narrows_the_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"syringe_volume": 0.5}, {"syringe_volume": 50001}, {"diameter": 51},
                      {"target_time": 0.5}, {"target_time": 3601}, {"target_volume": 50001},
                      {"flow_rate": 101}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"syringe_volume": 5}, {"diameter": 4.85}, {"target_time": 30},
                      {"target_volume": 5}, {"flow_rate": 10}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_syringe_index_is_operator_required_and_the_status_is_readable(self) -> None:
        client = self.serve()
        payload = {"channel": "ab", "code": "sst", "index": 1}
        receipt = client.invoke("x-cap.phamdangnguyen.syringe.v1", payload, **self.ids)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET, receipt)
        state = client.read("main", **self.ids)
        self.assertIn("status", state["state"])


if __name__ == "__main__":
    unittest.main()
