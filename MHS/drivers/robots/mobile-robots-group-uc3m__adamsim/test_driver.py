"""Acceptance run of the ADAMSim package: the gate, plus repository-specific cases.

Add cases, never remove the check_driver call.  The fake is a pure-Python kinematic stand-in; no
PyBullet, ROS, upstream import or hardware is used here.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DRIVE = "cap.motion.mobile_base.v1"
STOP = "x-cap.mobile-robots-group-uc3m.zero_wheels.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AdamsimCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.served_native = next(iter(server.devices.values())).bridge.native
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def example_overlay(self):
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    def test_reads_return_the_fake_state(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        state = driver.read("main")
        self.assertEqual(state["camera_angle"], 0.0)
        self.assertEqual(len(state["left_arm_joint_positions"]), 6)
        self.assertEqual(len(state["right_arm_joint_positions"]), 6)

    def test_the_drive_inputs_are_refused_without_an_operator_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            DRIVE,
            {"linear_velocity": 0.2, "angular_velocity": 0.0, "duration_s": 1.0},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.served_native.navigation._linear, 0.0)
        self.assertEqual(self.served_native.navigation._angular, 0.0)
        self.assertEqual(self.served_native._tick, 0)

    def test_the_example_overlay_drives_the_fake_base(self) -> None:
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.invoke(
            DRIVE,
            {"linear_velocity": 0.2, "angular_velocity": 0.0, "duration_s": 2.0},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertAlmostEqual(receipt["output"]["distance_m"], 0.4, places=9)
        self.assertAlmostEqual(receipt["output"]["heading_rad"], 0.0, places=9)
        self.assertTrue(receipt["output"]["stopped"])
        self.assertEqual(self.served_native._tick, 200)
        self.assertAlmostEqual(self.served_native._x, 0.4, places=9)
        self.assertEqual(self.served_native.navigation._linear, 0.0)
        self.assertEqual(self.served_native.navigation._angular, 0.0)

    def test_the_stop_action_zeroes_the_wheel_targets(self) -> None:
        driver = load_driver(HERE, "fake", )
        self.addCleanup(driver.close)
        driver.native.navigation.send_velocity(0.4, 0.2)
        output = driver.call(STOP, {})
        self.assertEqual(output, {"stopped": True})
        self.assertEqual(driver.native.navigation._linear, 0.0)
        self.assertEqual(driver.native.navigation._angular, 0.0)

    def test_the_estop_zeroes_the_wheels_and_latches_the_drive(self) -> None:
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertEqual(self.served_native.navigation._linear, 0.0)
        self.assertEqual(self.served_native.navigation._angular, 0.0)
        refused = client.invoke(
            DRIVE,
            {"linear_velocity": 0.2, "angular_velocity": 0.0, "duration_s": 1.0},
            **self.ids,
        )
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # The declared safe-state action remains callable while the latch is engaged.
        allowed = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(allowed["status"], "completed", allowed)

    def test_a_failing_step_still_zeroes_the_wheel_targets(self) -> None:
        # Reviewer case: ADAM.step can raise (with use_ros at the pin it reads self.adam.useRealTimeSimulation,
        # which ADAM never assigns); the drive must fail without leaving the wheels at the commanded velocity.
        client = self.serve(site_limits=self.example_overlay())

        def failing_step():
            raise AttributeError("'ADAM' object has no attribute 'useRealTimeSimulation'")  # placeholder failure

        self.served_native.step = failing_step
        receipt = client.invoke(
            DRIVE,
            {"linear_velocity": 0.2, "angular_velocity": 0.1, "duration_s": 1.0},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(self.served_native.navigation._linear, 0.0)
        self.assertEqual(self.served_native.navigation._angular, 0.0)


if __name__ == "__main__":
    unittest.main()
