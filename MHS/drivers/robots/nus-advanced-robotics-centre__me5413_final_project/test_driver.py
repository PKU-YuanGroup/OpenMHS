"""Acceptance run of the ME5413 Gazebo world package: the gate plus repository cases.

Besides the world-control surface, the cases exercise the companion-cited stop (the Gazebo world pause confirmed by
the get_physics_properties read-back), its failure paths, the latch, the reset that leaves the world paused, the
absence of an unpause, and what a paused world still does.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
RESUME = "x-cap.nus-advanced-robotics-centre.resume.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Me5413WorldCases(unittest.TestCase):
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

    def test_clear_objects_publishes_zero(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.nus-advanced-robotics-centre.clear_objects.v1", {})
        self.assertTrue(output["published"])
        self.assertFalse(output["confirmed"])
        self.assertEqual(driver.native.last_respawn_command, 0)

    def test_regenerate_objects_publishes_one(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.nus-advanced-robotics-centre.regenerate_objects.v1", {})
        self.assertTrue(output["published"])
        self.assertFalse(output["confirmed"])
        self.assertEqual(driver.native.last_respawn_command, 1)

    def test_open_exit_publishes_true(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.nus-advanced-robotics-centre.open_exit.v1", {})
        self.assertTrue(output["published"])
        self.assertFalse(output["confirmed"])
        self.assertIn("/cmd_unblock", driver.native.published_topics)

    def test_remove_moving_obstacle_deletes_planar_box(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.nus-advanced-robotics-centre.remove_moving_obstacle.v1", {})
        self.assertTrue(output["success"])
        self.assertEqual(driver.native.deleted_models, ["planar_box"])
        self.assertFalse(driver.native.moving_obstacle_present)

    def test_a_repeat_delete_of_the_absent_obstacle_fails(self) -> None:
        driver = self.driver()
        driver.call("x-cap.nus-advanced-robotics-centre.remove_moving_obstacle.v1", {})
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.nus-advanced-robotics-centre.remove_moving_obstacle.v1", {})

    def test_box_odom_observation_returns_a_pose(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.nus-advanced-robotics-centre.box_odom.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]["pose"]), {"position", "orientation"})
        self.assertEqual(set(receipt["output"]["pose"]["position"]), {"x", "y", "z"})

    def test_box_markers_observation_returns_an_array(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.nus-advanced-robotics-centre.box_markers.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["markers"], [])

    def test_delete_model_application_refusal_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_delete_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.nus-advanced-robotics-centre.delete_model.v1", {"model_name": "planar_box"})

    def test_failed_delete_service_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_delete_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.nus-advanced-robotics-centre.delete_model.v1", {"model_name": "planar_box"})

    def served(self):
        driver = self.driver()
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return driver, client, {"device_id": device_id, "session_id": session}

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        # The stop is the companion gazebo_ros world pause; deleting planar_box is never part of it.
        driver, client, ids = self.served()
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.service_calls[:2], [PAUSE, READBACK])
        self.assertEqual(driver.native.deleted_models, [])
        self.assertTrue(driver.native.moving_obstacle_present)
        refused = client.invoke("x-cap.nus-advanced-robotics-centre.clear_objects.v1", {}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = client.invoke("x-cap.nus-advanced-robotics-centre.remove_moving_obstacle.v1", {}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_read_back_other_than_pause_true_leaves_the_estop_unconfirmed_and_latched(self) -> None:
        for switch in ("unpaused_by_other_client", "fail_readback", "fail_pause"):
            with self.subTest(switch=switch):
                driver, client, ids = self.served()
                setattr(driver.native, switch, True)
                receipt = client.estop("test", **ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
                self.assertTrue(receipt["output"]["latched"], receipt)
                refused = client.invoke("x-cap.nus-advanced-robotics-centre.open_exit.v1", {}, **ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_package_offers_no_unpause_and_the_reset_leaves_the_world_paused(self) -> None:
        driver, client, ids = self.served()
        self.assertNotIn(RESUME, type(driver).commands)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")) + str(spec.get("topic", "")))
        for action in type(driver).actions.values():
            self.assertFalse(getattr(action, "reenable", False))
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        reset = client.reset(**ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertNotIn("reenable", reset["output"])
        self.assertFalse(reset["output"]["resumed"])
        self.assertTrue(driver.native.paused)
        self.assertNotIn(UNPAUSE, driver.native.service_calls)

    def test_a_paused_world_still_applies_a_delete_and_silences_box_odom(self) -> None:
        driver = self.driver()
        driver.native.paused = True
        output = driver.call("x-cap.nus-advanced-robotics-centre.remove_moving_obstacle.v1", {})
        self.assertTrue(output["success"])
        self.assertFalse(driver.native.moving_obstacle_present)
        self.assertTrue(driver.native.paused)
        driver.native.moving_obstacle_present = True
        with self.assertRaises(Exception) as caught:
            driver.call("x-cap.nus-advanced-robotics-centre.box_odom.v1", {})
        self.assertIn("MHS.", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
