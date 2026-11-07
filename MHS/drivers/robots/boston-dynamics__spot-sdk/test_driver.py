"""Acceptance run of the Spot package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); its ``_commands`` list
is what reached the "robot".  Nothing here ran on a Spot.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpotCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.robot = driver.native                              # the fake Robot
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.robot._commands[:]                             # forget the set-up reads
        return self.client

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def write(self, patch):
        return self.client.write("main", patch, **self.ids)

    def sent(self, name=None):
        return [(command, args) for command, args in self.robot._commands if name is None or command == name]

    # -- reads -------------------------------------------------------------------------------------------------
    def test_the_cached_identity_and_hardware_flags_are_read(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["serial_number"], "fake-spot-0001")
        self.assertEqual(state["nickname"], "fake-spot")
        self.assertEqual(state["species"], "spot")
        self.assertEqual(state["usernames"], ["fake-user"])
        self.assertEqual(state["frame_names"], ["body", "odom", "vision"])
        self.assertEqual(state["has_arm"], True)
        self.assertEqual(state["can_power_off_robot"], True)
        self.assertEqual(state["redundant_safety_stop_enabled"], True)
        self.assertEqual(state["motors_on"], False)
        self.assertEqual(state["estopped"], False)

    def test_the_estop_state_read_comes_from_the_robot(self) -> None:
        self.serve()
        self.robot._set_estopped(True)
        self.assertEqual(self.state()["estopped"], True)
        self.robot._set_estopped(False)
        self.assertEqual(self.state()["estopped"], False)

    # -- power write -------------------------------------------------------------------------------------------
    def test_a_power_write_reaches_the_robot_and_changes_state(self) -> None:
        self.serve()
        receipt = self.write({"motors_on": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state()["motors_on"], True)
        self.assertEqual([args for _, args in self.sent("power_on")], [{"timeout_sec": 20,
                                                                        "update_frequency": 1.0, "timeout": None}])
        receipt = self.write({"motors_on": False})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state()["motors_on"], False)
        self.assertEqual([args["cut_immediately"] for _, args in self.sent("power_off")], [False])

    # -- safety ------------------------------------------------------------------------------------------------
    def test_the_estop_cuts_motor_power_and_latches(self) -> None:
        self.serve()
        self.write({"motors_on": True})
        self.client.estop("test", **self.ids)
        cuts = [args for _, args in self.sent("power_off") if args["cut_immediately"] is True]
        self.assertEqual(len(cuts), 1)
        self.assertEqual(self.state()["motors_on"], False)
        refused = self.write({"motors_on": True})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))

    # -- the loader and the reference -------------------------------------------------------------------------
    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
