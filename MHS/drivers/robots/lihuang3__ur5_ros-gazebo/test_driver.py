"""Acceptance run of the UR5 vacuum-gripper ROS package: the gate plus package cases.

The cases exercise the vacuum services and observations, the companion-cited stop (the Gazebo world pause confirmed
by the get_physics_properties read-back) that keeps each vacuum channel's state, its failure paths, the latch, a reset
that leaves the world paused while the vacuum services still answer, and that the package offers no unpause.  Add
cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GripperCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_all_nine_on_and_off_services_reach_the_fake(self) -> None:
        driver = self.driver()
        on_ids = [f"x-cap.lihuang3.vacuum_gripper_{index}_on.v1" for index in range(9)]
        off_ids = [f"x-cap.lihuang3.vacuum_gripper_{index}_off.v1" for index in range(9)]
        self.assertEqual(set(on_ids) | set(off_ids),
                         {item for item in driver.commands if item.startswith("x-cap.lihuang3.vacuum_gripper_")})
        for index in range(9):
            self.assertEqual(driver.call(on_ids[index], {}), {"acknowledged": True})
            self.assertTrue(driver.native.vacuum[index])
            self.assertEqual(driver.call(off_ids[index], {}), {"acknowledged": True})
            self.assertFalse(driver.native.vacuum[index])
        called = [message.get("service") for message in driver.native.sent
                  if message.get("op") == "call_service"]
        self.assertEqual(called, [
            "/ur5/vacuum_gripper/on",
            "/ur5/vacuum_gripper/off",
            "/ur5/vacuum_gripper1/on",
            "/ur5/vacuum_gripper1/off",
            "/ur5/vacuum_gripper2/on",
            "/ur5/vacuum_gripper2/off",
            "/ur5/vacuum_gripper3/on",
            "/ur5/vacuum_gripper3/off",
            "/ur5/vacuum_gripper4/on",
            "/ur5/vacuum_gripper4/off",
            "/ur5/vacuum_gripper5/on",
            "/ur5/vacuum_gripper5/off",
            "/ur5/vacuum_gripper6/on",
            "/ur5/vacuum_gripper6/off",
            "/ur5/vacuum_gripper7/on",
            "/ur5/vacuum_gripper7/off",
            "/ur5/vacuum_gripper8/on",
            "/ur5/vacuum_gripper8/off",
        ])

    def test_grasping_observation_tracks_the_first_channel(self) -> None:
        # fake-only: the fake reports the first channel's on state; the upstream plugin (not in the
        # clone) reports a grasp only for an object within its range.
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.lihuang3.grasping.v1", {}), {"grasping": False})
        self.assertEqual(driver.call("x-cap.lihuang3.vacuum_gripper_0_on.v1", {}), {"acknowledged": True})
        self.assertEqual(driver.call("x-cap.lihuang3.grasping.v1", {}), {"grasping": True})
        self.assertEqual(driver.call("x-cap.lihuang3.vacuum_gripper_0_off.v1", {}), {"acknowledged": True})
        self.assertEqual(driver.call("x-cap.lihuang3.grasping.v1", {}), {"grasping": False})

    def test_tracker_and_block_pose_observations_validate(self) -> None:
        driver = self.driver()
        tracker = driver.call("x-cap.lihuang3.tracker.v1", {})
        self.assertEqual(set(tracker), {"x", "y", "z", "error_x", "error_y", "error_z",
                                        "flag1", "flag2", "flag3"})
        blocks = driver.call("x-cap.lihuang3.block_poses.v1", {})
        self.assertEqual(set(blocks), {"x", "y", "z"})
        self.assertEqual(len(blocks["x"]), len(blocks["y"]))
        self.assertEqual(len(blocks["y"]), len(blocks["z"]))

    def test_a_failed_service_does_not_report_an_acknowledgement(self) -> None:
        driver = self.driver()
        driver.native.fail_service = "/ur5/vacuum_gripper/on"
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.lihuang3.vacuum_gripper_0_on.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertFalse(driver.native.vacuum[0])

    def test_a_rejected_application_response_is_a_failure(self) -> None:
        # fake-only negative path: an std_srvs/Empty response has no fields, so this exercises only the
        # binding's success predicate.
        driver = self.driver()
        driver.native.fail_application = "/ur5/vacuum_gripper/on"
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.lihuang3.vacuum_gripper_0_on.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")
        self.assertFalse(driver.native.vacuum[0])

    def served(self, **switches):
        driver = self.driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return driver, client, {"device_id": device_id, "session_id": session}

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_e_stop_pauses_the_world_keeps_the_vacuum_and_latches(self) -> None:
        driver, client, ids = self.served()
        for index in range(9):
            self.assertEqual(client.invoke(f"x-cap.lihuang3.vacuum_gripper_{index}_on.v1", {}, **ids)["status"],
                             "completed")
        mark = len(self.services(driver.native))
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native)[mark:], [PAUSE, READBACK])  # no vacuum service is called
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.vacuum, [True] * 9)
        for action in ("on", "off"):
            refused = client.invoke(f"x-cap.lihuang3.vacuum_gripper_0_{action}.v1", {}, **ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                _driver, client, ids = self.served(**{switch: True})
                receipt = client.estop("test", **ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
                refused = client.invoke("x-cap.lihuang3.vacuum_gripper_0_on.v1", {}, **ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_reset_keeps_the_world_paused_and_the_vacuum_still_answers(self) -> None:
        driver, client, ids = self.served()
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        self.assertEqual(client.reset(**ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke("x-cap.lihuang3.vacuum_gripper_0_on.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)  # stored; acts when the operator unpauses
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        with self.assertRaises(MHSError):
            driver.call("x-cap.lihuang3.grasping.v1", {})  # a paused world publishes no grasping

    def test_the_package_offers_no_unpause_and_no_safe_state_action(self) -> None:
        driver = self.driver()
        self.assertEqual(len(driver._model.achieved_by), 0)
        self.assertIsNone(driver._model.reenable)
        self.assertEqual(set(type(driver).safety_bindings), {"estop", "safe_state"})
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")))


if __name__ == "__main__":
    unittest.main()
