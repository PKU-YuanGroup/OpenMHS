"""Acceptance run of this driver package: add cases, never remove the harness call.

Besides the fake's contract, the cases exercise the companion-cited stop (the Gazebo world pause confirmed by the
get_physics_properties read-back), its failure paths, the latch, the reset that leaves the world paused, the absence
of an unpause and the world edits a paused world still applies.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
DELETE = "x-cap.ipa320.delete_model.v1"
SET_STATE = "x-cap.ipa320.set_model_state.v1"
RESUME = "x-cap.ipa320.resume.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"
POSE = {"model_name": "robot", "position_x": 1.5, "position_y": 2.0, "position_z": 0.1,
        "orientation_x": 0.0, "orientation_y": 0.0, "orientation_z": 0.0, "orientation_w": 1.0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FakeTransportContract(unittest.TestCase):
    """Repository-specific checks of the ROS-free recording fake."""

    def setUp(self) -> None:
        self.driver = load_driver(HERE, backend="fake")
        self.fake = self.driver.native

    def tearDown(self) -> None:
        self.driver.close()

    def _call(self, service: str, args: dict | None = None) -> dict:
        self.fake.send({
            "op": "call_service",
            "service": service,
            "type": "std_srvs/Empty",
            "args": args or {},
            "id": "service-request",
        })
        return self.fake.recv()

    def test_world_properties_and_delete(self) -> None:
        reply = self._call("/gazebo/get_world_properties")
        self.assertTrue(reply["result"])
        self.assertIn("apple_juice_box", reply["values"]["model_names"])

        reply = self._call("/gazebo/delete_model", {"model_name": "apple_juice_box"})
        self.assertTrue(reply["result"])
        self.assertTrue(reply["values"]["success"])

        reply = self._call("/gazebo/get_world_properties")
        self.assertNotIn("apple_juice_box", reply["values"]["model_names"])

        # The fake treats a repeated delete as a no-op success.
        reply = self._call("/gazebo/delete_model", {"model_name": "apple_juice_box"})
        self.assertTrue(reply["result"])
        self.assertTrue(reply["values"]["success"])

    def test_model_state_publication_changes_the_read(self) -> None:
        self.fake.send({
            "op": "advertise",
            "topic": "/gazebo/set_model_state",
            "type": "gazebo_msgs/ModelState",
            "id": "advertise",
        })
        self.fake.send({
            "op": "publish",
            "topic": "/gazebo/set_model_state",
            "id": "publish",
            "msg": {
                "model_name": "robot",
                "pose": {
                    "position": {"x": 2.0, "y": 3.0, "z": 0.1},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "twist": {"linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                          "angular": {"x": 0.0, "y": 0.0, "z": 0.0}},
                "reference_frame": "world",
            },
        })
        reply = self._call("/gazebo/get_model_state", {"model_name": "robot"})
        self.assertEqual(reply["values"]["pose"]["position"], {"x": 2.0, "y": 3.0, "z": 0.1})

    def test_service_negative_paths(self) -> None:
        self.fake.fail_world_properties = True
        reply = self._call("/gazebo/get_world_properties")
        self.assertFalse(reply["result"])

        self.fake.fail_world_properties = False
        self.fake.fail_delete_service = True
        reply = self._call("/gazebo/delete_model", {"model_name": "basmati_rice"})
        self.assertFalse(reply["result"])

        self.fake.fail_delete_service = False
        self.fake.reject_delete_application = True
        reply = self._call("/gazebo/delete_model", {"model_name": "basmati_rice"})
        self.assertTrue(reply["result"])
        self.assertFalse(reply["values"]["success"])

        reply = self._call("/gazebo/not_a_service")
        self.assertFalse(reply["result"])


class DriverReads(unittest.TestCase):
    """The driver's service reads require the response's success flag (reviewer case)."""

    def setUp(self) -> None:
        self.driver = load_driver(HERE, backend="fake")

    def tearDown(self) -> None:
        self.driver.close()

    def test_reads_return_names_and_the_robot_pose(self) -> None:
        state = self.driver.read("main")
        self.assertIn("robot", state["model_names"])
        self.assertEqual(set(state["robot_pose"]), {"position", "orientation"})

    def test_missing_robot_model_is_refused_not_read_as_a_zero_pose(self) -> None:
        self.driver.native.poses.pop("robot")
        with self.assertRaises(MHSError) as caught:
            self.driver.read("main", ["robot_pose"])
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")


class CompanionStopCases(unittest.TestCase):
    """The Gazebo world pause (companion gazebo_ros), its read-back and the latch. No unpause is offered."""

    def serve(self):
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_the_e_stop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.service_calls[:2], [PAUSE, READBACK])

    def test_a_read_back_other_than_pause_true_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("unpaused_by_other_client", "fail_readback", "fail_pause"):
            with self.subTest(switch=switch):
                driver, client = self.serve()
                setattr(driver.native, switch, True)
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                refused = client.invoke(DELETE, {"model_name": "basmati_rice"}, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
                self.assertIn("basmati_rice", driver.native.poses)

    def test_edits_are_refused_while_latched_and_the_reset_leaves_the_world_paused(self) -> None:
        driver, client = self.serve()
        self.assertNotIn(RESUME, type(driver).commands)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")) + str(spec.get("topic", "")))
        for action in type(driver).actions.values():
            self.assertFalse(getattr(action, "reenable", False))
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke(SET_STATE, POSE, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertNotIn(UNPAUSE, driver.native.service_calls)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertNotIn("reenable", reset["output"])
        self.assertFalse(reset["output"]["resumed"])
        self.assertTrue(driver.native.paused)
        # After the reset the world is still paused, but its reads answer and an edit still applies.
        self.assertIn("robot", client.read("main", **self.ids)["state"]["model_names"])
        self.assertEqual(client.invoke(SET_STATE, POSE, **self.ids)["status"], "completed")
        self.assertEqual(driver.native.poses["robot"]["position"]["x"], 1.5)
        self.assertTrue(driver.native.paused)
        self.assertNotIn(UNPAUSE, driver.native.service_calls)


if __name__ == "__main__":
    unittest.main()
