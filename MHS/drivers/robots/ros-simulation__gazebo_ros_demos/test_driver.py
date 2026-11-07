"""Acceptance and package-specific cases for the RRBot command fake contract.

The pinned clone declares no acknowledged stop, so the stock gate is expected
to fail G6 and G8 on its safety checks.  The gate is still run in full and its
specific refusal is asserted; the remaining cases exercise the declared ROS-free
recording fake.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
JOINT1 = "x-cap.ros-simulation.rrbot_joint1_position.v1"
JOINT2 = "x-cap.ros-simulation.rrbot_joint2_position.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        # The package has no source-backed stop or safe-state action. Keep
        # running the full stock gate and require its specific safety refusal.
        self.assertEqual(report["failed"], ["G6", "G8"], report)
        codes = {finding["code"] for gate in report["gates"] for finding in gate["findings"]}
        self.assertIn("G6.ESTOP_FAILED", codes)
        self.assertIn("G8.TEST", codes)


class RrbotCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_joint1_command_publishes_one_float64_message(self) -> None:
        driver, client = self.serve()
        receipt = client.invoke(JOINT1, {"position": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        self.assertEqual(driver.native.joint1_commands, [{"data": 0.5}])
        self.assertEqual(driver.native.joint2_commands, [])
        published = [message for message in driver.native.sent
                     if message.get("op") == "publish" and message.get("topic") ==
                     "/rrbot/joint1_position_controller/command"]
        advertised = [message for message in driver.native.sent
                      if message.get("op") == "advertise" and message.get("topic") ==
                      "/rrbot/joint1_position_controller/command"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["msg"], {"data": 0.5})
        self.assertEqual(len(advertised), 1)
        self.assertEqual(advertised[0]["type"], "std_msgs/Float64")

    def test_joint2_command_publishes_one_float64_message(self) -> None:
        driver, client = self.serve()
        receipt = client.invoke(JOINT2, {"position": -0.25}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        self.assertEqual(driver.native.joint1_commands, [])
        self.assertEqual(driver.native.joint2_commands, [{"data": -0.25}])
        published = [message for message in driver.native.sent
                     if message.get("op") == "publish" and message.get("topic") ==
                     "/rrbot/joint2_position_controller/command"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["msg"], {"data": -0.25})

    def test_a_joint_command_is_refused_without_the_operator_envelope(self) -> None:
        driver, client = self.serve(overlay=False)
        receipt = client.invoke(JOINT1, {"position": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)
        self.assertFalse([message for message in driver.native.sent
                          if message.get("op") == "publish"])
        self.assertEqual(driver.native.joint1_commands, [])

    def test_out_of_envelope_joint_command_is_refused_before_the_publication(self) -> None:
        driver, client = self.serve()
        receipt = client.invoke(JOINT2, {"position": 4.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertFalse([message for message in driver.native.sent
                          if message.get("op") == "publish"])
        self.assertEqual(driver.native.joint2_commands, [])

    def test_a_transport_failure_is_not_reported_as_published(self) -> None:
        driver, client = self.serve()
        driver.native.fail_publish = True
        receipt = client.invoke(JOINT1, {"position": 0.5}, **self.ids)
        self.assertIn(receipt["status"], ("failed", "unknown"), receipt)
        self.assertNotEqual(receipt.get("output"), {"published": True, "confirmed": False})

    def test_no_acknowledged_stop_is_declared_and_the_estop_stays_unreached(self) -> None:
        driver, client = self.serve()
        self.assertEqual(dict(type(driver).safety_bindings), {})
        self.assertIsNone(type(driver).estop_physical_ref)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
        refused = client.invoke(JOINT1, {"position": 0.5}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_declaration_is_a_simulated_ros1_arm_without_a_stop(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(type(driver).ros_version, 1)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "robot.arm")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeGazeboRosDemosRrbot"})
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")


if __name__ == "__main__":
    unittest.main()
