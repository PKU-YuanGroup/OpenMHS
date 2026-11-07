"""Acceptance run of the TBS2000B package: the gate, plus cases for what is specific to this driver.

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


class Measurements(unittest.TestCase):
    """The upstream methods the driver calls, seen by the fake backend."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_start_on_ch1_and_return_numbers(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["channel"], "CH1")
        self.assertEqual((state["frequency"], state["amplitude"], state["high"]), (1000.0, 1.0, 0.5))
        self.assertIn(("MeasureFreq", "CH1"), driver.native.calls)
        self.assertIn(("MeasureAmpl", "CH1"), driver.native.calls)
        self.assertIn(("MeasureHigh", "CH1"), driver.native.calls)

    def test_a_channel_write_reaches_set_channel_and_selects_the_measurement(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel": "CH3"})
        self.assertEqual(driver.native._channel, "CH3")
        self.assertIn(("SetChannel", "CH3"), driver.native.calls)
        state = driver.read("main", ["channel", "frequency"])
        self.assertEqual(state, {"channel": "CH3", "frequency": 5000.0})
        self.assertIn(("MeasureFreq", "CH3"), driver.native.calls)

    def test_the_estop_closes_the_upstream_session(self) -> None:
        driver = self.driver()
        self.assertFalse(driver.native.closed)
        driver.estop("test")
        self.assertTrue(driver.native.closed)
        self.assertIn(("Close", None), driver.native.calls)
        driver.close()
        self.assertEqual([name for name, _arg in driver.native.calls].count("Close"), 1)


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_only_the_channels_of_set_channel_are_accepted(self) -> None:
        client = self.serve()
        for patch in ({"channel": "CH5"}, {"channel": "ch1"}, {"channel": "DEFAULT"}, {"channel": ""}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"channel": "CH1"}, {"channel": "CH2"}, {"channel": "CH3"}, {"channel": "CH4"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
