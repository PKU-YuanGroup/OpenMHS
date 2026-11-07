"""Acceptance run of the Tecan Genesis package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
SPACING = "x-cap.erikbgithub.set_tip_spacing.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Behaviour(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_home_queues_and_dispatches_pis(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.erikbgithub.init_system.v1", {}), {"initialized": True})
        self.assertEqual(driver.native.cmdStack, [("PIS", "M1")])
        self.assertEqual(driver.native.runningStack, ["M1"])
        self.assertEqual(driver.read("main", ["dispatched_commands"]), {"dispatched_commands": 1})

    def test_tip_spacing_dispatches_psy(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(SPACING, {"spacing": 38.0}), {"spacing": 38.0})
        self.assertEqual(driver.native.cmdStack, [("PSY380", "A1")])
        self.assertEqual(driver.native.runningStack, ["A1"])

    def test_estop_discards_the_queued_commands(self) -> None:
        driver = self.driver()
        driver.call("x-cap.erikbgithub.init_system.v1", {})
        driver.estop("test")
        self.assertEqual(driver.native.cmdStack, [])
        self.assertEqual(driver.native.runningStack, [])
        self.assertEqual(driver.read("main", ["command_stack", "dispatched_commands"]),
                         {"command_stack": 0, "dispatched_commands": 0})


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def spacing(self, client, value):
        receipt = client.invoke(SPACING, {"spacing": value}, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_psy_bounds_of_the_clone(self) -> None:
        client = self.serve()
        for value in (8.9, 38.1):
            self.assertEqual(self.spacing(client, value), ENVELOPE, value)
        for value in (9.0, 38.0):
            self.assertEqual(self.spacing(client, value), "completed", value)


if __name__ == "__main__":
    unittest.main()
