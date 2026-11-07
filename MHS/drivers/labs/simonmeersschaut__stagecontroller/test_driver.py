"""Acceptance run of the StageController package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
START = "x-cap.simonmeersschaut.start_rotation.v1"
STOP = "x-cap.simonmeersschaut.stop_rotation.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Commands(unittest.TestCase):
    """The commands the driver sends, checked on the strings the upstream `send` method receives."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_actions_send_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(START, {}), {"started": True})
        self.assertEqual(driver.call(STOP, {}), {"stopped": True})
        self.assertEqual(driver.native.sent, ["XL+", "XS"])

    def test_the_estop_sends_the_upstream_stop(self) -> None:
        driver = self.driver()
        driver.call(START, {})
        driver.estop("test")
        self.assertEqual(driver.native.sent[-1], "XS")
        self.assertEqual(driver.estop_native, "send")

    def test_the_fake_answers_only_the_commands_the_driver_sends(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.native.send("XS"), b"")  # placeholder: the fake reply is empty
        self.assertEqual(driver.native.sent, ["XS"])


class Served(unittest.TestCase):
    """The runtime side: the e-stop latches and a later start is refused before the fake is called."""

    def test_the_latch_refuses_the_start_after_an_estop(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session_id}
        self.assertEqual(client.invoke(START, {}, **ids)["status"], "completed")
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        receipt = client.invoke(START, {}, **ids)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")


if __name__ == "__main__":
    unittest.main()
