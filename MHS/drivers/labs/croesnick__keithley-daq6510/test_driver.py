"""Acceptance run of the DAQ6510 package: the gate, plus cases for this driver's one wire command.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
IDENTITY = "Keithley Instruments Inc., Model DAQ 6510"  # placeholder: test data from tests/fixtures/devices.yml:10


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_identity_state_read_is_the_clone_query(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["idn"])
        self.assertEqual(state, {"idn": IDENTITY})
        # The first *IDN? is the identity check on connect; the second is the state read.
        self.assertEqual(driver.native.written, ["*IDN?", "*IDN?"])

    def test_the_identity_extension_reads_the_same_query(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.croesnick.identity.v1", {})
        self.assertEqual(output, {"idn": IDENTITY})
        self.assertEqual(driver.native.written, ["*IDN?", "*IDN?"])


class ServerSurface(unittest.TestCase):
    """The extension reaches the fake through a strict server and validates its output."""

    def test_the_extension_is_a_read_capability(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("x-cap.croesnick.identity.v1", {},
                                device_id=device_id, session_id=session_id)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"idn": IDENTITY})


if __name__ == "__main__":
    unittest.main()
