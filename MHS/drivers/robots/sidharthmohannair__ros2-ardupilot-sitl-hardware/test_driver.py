"""Acceptance run of the ArduPilot/MAVROS ROS package: the gate plus repository cases.

The fake is a ROS-free F0 recording transport.  These cases exercise the
declared MAVROS topics and services, the operator-required takeoff and
position envelope, ordinary LAND requests and their negative replies; native safety remains blocked.  No ROS
graph, MAVROS node, flight controller or hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STATE = "x-cap.sidharthmohannair.state.v1"
POSE = "x-cap.sidharthmohannair.pose.v1"
GUIDED = "x-cap.sidharthmohannair.guided.v1"
ARM = "x-cap.sidharthmohannair.arm.v1"
TAKEOFF = "x-cap.sidharthmohannair.takeoff.v1"
SETPOINT = "x-cap.sidharthmohannair.setpoint_position.v1"
RTL = "x-cap.sidharthmohannair.rtl.v1"
LAND = "x-cap.sidharthmohannair.land.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        # The selected native stop/lifecycle is unproven. Keep running the
        # full stock gate and require its specific safety refusal.
        self.assertEqual(report["failed"], ["G3"], report)
        codes = {f["code"] for g in report["gates"] for f in g["findings"]}
        self.assertIn("G3.NO_ESTOP", codes)
        self.assertIn("G3.NO_SAFE_STATE", codes)


class MissionCases(unittest.TestCase):
    def serve(self, *, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
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

    def test_state_and_pose_observations_return_the_fake_samples(self) -> None:
        client = self.serve()
        state = client.invoke(STATE, {}, **self.ids)
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(state["output"], {"connected": True, "armed": False, "mode": "GUIDED"})
        pose = client.invoke(POSE, {}, **self.ids)
        self.assertEqual(pose["status"], "completed", pose)
        self.assertEqual(pose["output"]["position"], {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_guided_and_arm_reach_the_declared_services(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(GUIDED, {}), {"mode_sent": True})
        self.assertTrue(driver.native.armed is False)
        self.assertEqual(driver.call(ARM, {}), {"success": True})
        self.assertTrue(driver.native.armed)
        services = [message for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services[0]["service"], "/mavros/set_mode")
        self.assertEqual(services[0]["args"], {"custom_mode": "GUIDED"})
        self.assertEqual(services[1]["service"], "/mavros/cmd/arming")
        self.assertEqual(services[1]["args"], {"value": True})

    def test_takeoff_is_refused_without_the_operator_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(TAKEOFF, {"altitude": 10.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_setpoint_is_refused_without_the_operator_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke(SETPOINT, {"x": 1.0, "y": 2.0, "z": 3.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_takeoff_and_setpoint_complete_inside_the_example_overlay(self) -> None:
        client = self.serve(site_limits=HERE / "site-limits.example.json")
        takeoff = client.invoke(TAKEOFF, {"altitude": 10.0}, **self.ids)
        self.assertEqual(takeoff["status"], "completed", takeoff)
        self.assertEqual(takeoff["output"], {"success": True})
        self.assertEqual(client.read("main", **self.ids)["state"]["position"]["z"], 10.0)
        setpoint = client.invoke(SETPOINT, {"x": 1.0, "y": 2.0, "z": 3.0}, **self.ids)
        self.assertEqual(setpoint["status"], "completed", setpoint)
        self.assertEqual(setpoint["output"], {"published": True, "confirmed": False})
        self.assertEqual(client.read("main", **self.ids)["state"]["position"],
                         {"x": 1.0, "y": 2.0, "z": 3.0})

    def test_setpoint_publication_is_transmission_only(self) -> None:
        driver = self.driver()
        output = driver.call(SETPOINT, {"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertEqual(output, {"published": True, "confirmed": False})
        publishes = [message for message in driver.native.sent
                     if message.get("op") == "publish"]
        self.assertEqual(len(publishes), 1)
        self.assertEqual(publishes[0]["topic"], "/mavros/setpoint_position/local")
        self.assertEqual(publishes[0]["msg"]["pose"]["position"], {"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertEqual(driver.native.position, {"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertEqual(publishes[0]["msg"]["header"], {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}})

    def test_rtl_and_land_request_the_documented_modes(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(RTL, {}), {"mode_sent": True})
        self.assertEqual(driver.native.mode, "RTL")
        self.assertEqual(driver.call(LAND, {}), {"mode_sent": True})
        self.assertEqual(driver.native.mode, "LAND")

    def test_unproven_estop_latches_but_never_sends_land(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIs(receipt["output"]["safe_state_achieved"], False, receipt)
        for cap in (GUIDED, LAND):
            refused = client.invoke(cap, {}, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.read("main", **self.ids)["state"]["mode"], "GUIDED")

    def test_failed_arm_service_does_not_report_success(self) -> None:
        driver = self.driver()
        driver.native.fail_arm_transport = True
        with self.assertRaises(DriverFailed):
            driver.call(ARM, {})

    def test_rejected_arm_application_does_not_report_success(self) -> None:
        driver = self.driver()
        driver.native.fail_arm_application = True
        with self.assertRaises(DriverFailed):
            driver.call(ARM, {})

    def test_missing_mode_field_does_not_report_success(self) -> None:
        driver = self.driver()
        driver.native.mode_missing_sent = True
        with self.assertRaises(DriverFailed):
            driver.call(GUIDED, {})

    def test_land_transport_failure_is_not_a_successful_mode_request(self) -> None:
        driver = self.driver()
        driver.native.fail_land_transport = True
        with self.assertRaises(DriverFailed):
            driver.call(LAND, {})

    def test_land_application_failure_is_not_a_successful_mode_request(self) -> None:
        driver = self.driver()
        driver.native.fail_land_application = True
        with self.assertRaises(DriverFailed):
            driver.call(LAND, {})

    def test_land_acknowledgement_without_state_change_has_no_safety_permission(self):
        driver = self.driver()
        driver.native.ack_land_without_transition = True
        driver.native.armed = True
        driver.native.position["z"] = 10.0
        self.assertEqual(driver.call(LAND, {}), {"mode_sent": True})
        self.assertEqual(driver.native.mode, "GUIDED")
        self.assertTrue(driver.native.armed)
        self.assertFalse(type(driver).actions[LAND].safe_state)
        self.assertEqual(type(driver).safety_bindings, {})
        self.assertIsNone(type(driver).estop_physical_ref)


if __name__ == "__main__":
    unittest.main()
