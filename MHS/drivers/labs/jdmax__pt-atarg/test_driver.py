"""Acceptance run of the Lake Shore 218 package: the gate, plus cases for this driver.

The fake returns placeholder readings; the cases check the shape and the read path, not any measurement of a unit.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.base import BridgeFailed
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
READ_CHANNELS = "x-cap.jdmax.read_channels.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Ls218Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_state_reads_the_channel_array(self) -> None:
        client = self.serve()
        temperatures = self.state(client)["temperatures"]
        self.assertEqual(len(temperatures), 8)
        self.assertTrue(all(isinstance(value, (int, float)) for value in temperatures))

    def test_the_read_action_returns_the_same_channel_array(self) -> None:
        client = self.serve()
        state = self.state(client)
        receipt = client.invoke(READ_CHANNELS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["temperatures"], state["temperatures"])

    def test_the_e_stop_drains_the_query_and_latches(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertTrue(output["latched"])
        self.assertTrue(output["safe_state_achieved"])
        self.assertEqual(output["estop"], "engaged")      # the runtime reports the native stop as engaged
        # The monitor is read-only: reads remain available after the latch.
        self.assertEqual(len(self.state(client)["temperatures"]), 8)

    def test_a_failed_native_read_fails_the_e_stop_closed(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)

        def failed_read():
            raise OSError("no reply from the serial-to-Ethernet adapter")

        driver.native.read_all = failed_read
        with self.assertRaises(BridgeFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_an_empty_native_reply_is_not_a_successful_channel_read(self) -> None:
        driver = load_driver(HERE, "fake")
        driver.native.read_all = lambda: []  # upstream regex finds no numbers in an empty/malformed reply
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(READ_CHANNELS, {}, device_id=device_id, session_id=session_id)
        self.assertNotEqual(receipt["status"], "completed", receipt)


if __name__ == "__main__":
    unittest.main()
