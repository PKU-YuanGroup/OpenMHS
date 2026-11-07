"""Acceptance run of the Duke Humanoid package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py) and inspect the fake
BipedController directly; nothing here touched the robot or the upstream clone.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
STEP = "x-cap.generalroboticslab.step.v1"
STOP = "x-cap.generalroboticslab.stop.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DukeHumanoidCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.biped = driver.native                              # the fake BipedController
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session_id = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session_id}
        return self.client

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def write(self, patch):
        return self.client.write("main", patch, **self.ids)

    def step(self):
        return self.client.invoke(STEP, {}, **self.ids)

    # -- reads ----------------------------------------------------------------------------------------------
    def test_the_state_reads_the_fake_sensor_and_motor_sample(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["joint_positions"], [0.0] * 10)
        self.assertEqual(state["joint_velocities"], [0.0] * 10)
        self.assertEqual(state["joint_currents"], [0.0] * 10)
        self.assertEqual(state["dof_position_target"], [0.0] * 10)
        self.assertEqual(state["foot_force_raw"], [900, 1100, 1000, 800])
        self.assertEqual(state["foot_contact"], [True, False])
        self.assertEqual(state["gravity_vector"], [0.0, 0.0, -1.0])
        self.assertEqual(state["base_quaternion"], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(state["sample_rate"], 500.0)
        self.assertEqual((state["command_forward"], state["command_lateral"], state["command_yaw"]),
                         (0.0, 0.0, 0.0))

    # -- commands -------------------------------------------------------------------------------------------
    def test_every_command_waits_for_an_operator_bound(self) -> None:
        self.serve()
        for name in ("command_forward", "command_lateral", "command_yaw"):
            refused = self.write({name: 0.1})
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET), name)
        self.assertEqual(self.biped.commands, [0.0, 0.0, 0.0])   # no command reached the fake

        self.serve(OVERLAY)                                      # the example overlay fills the three bounds
        receipt = self.write({"command_forward": 0.2, "command_yaw": -0.1})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["applied"], {"command_forward": 0.2, "command_yaw": -0.1})
        self.assertEqual(self.biped.commands, [0.2, 0.0, -0.1])
        self.assertEqual(self.state()["command_forward"], 0.2)

        over = self.write({"command_forward": 0.31})              # the overlay allows -0.3..0.3
        self.assertEqual((over["status"], over["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(over["error"]["details"]["bound"], 0.3)
        self.assertEqual(self.biped.commands, [0.2, 0.0, -0.1])  # the refused write reached nothing

    # -- control step ----------------------------------------------------------------------------------------
    def test_a_step_runs_the_upstream_step_and_changes_the_target(self) -> None:
        self.serve()
        before = self.state()["dof_position_target"]
        receipt = self.step()
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(receipt["output"]["action"]), 10)
        self.assertEqual(self.biped._steps, 1)
        after = self.state()["dof_position_target"]
        self.assertNotEqual(after, before)
        self.assertEqual(after, receipt["output"]["dof_position_target"])
        self.assertEqual(receipt["output"]["dof_position_target"], self.biped.dof_pos_target)

    # -- stop, safe state and e-stop -------------------------------------------------------------------------
    def test_the_safe_state_action_stops_the_control_loops(self) -> None:
        self.serve(OVERLAY)
        self.write({"command_forward": 0.2})
        receipt = self.client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"stopped": True})
        self.assertEqual(self.biped.motor.max_torque, [0.0] * 10)
        self.assertTrue(self.biped.motor.should_terminate)
        self.assertEqual(self.biped.commands, [0.0, 0.0, 0.0])

    def test_the_estop_reaches_the_native_stop_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.write({"command_yaw": 0.1})
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.biped.motor.max_torque, [0.0] * 10)
        self.assertTrue(self.biped.motor.should_terminate)
        self.assertEqual(self.biped.commands, [0.0, 0.0, 0.0])
        refused_step = self.step()
        self.assertEqual((refused_step["status"], refused_step["error"]["mhs_code"]), ("rejected", ESTOP))
        refused_write = self.write({"command_forward": 0.1})
        self.assertEqual((refused_write["status"], refused_write["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(self.biped._steps, 0)

    # -- the loader ------------------------------------------------------------------------------------------
    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
