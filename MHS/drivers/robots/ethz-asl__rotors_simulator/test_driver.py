"""Acceptance run of the RotorS Gazebo simulator package: the gate, plus simulator cases.

The cases exercise the two observations, the companion-cited stop (the Gazebo world pause confirmed by the
get_physics_properties read-back), its failure paths, the reset that leaves the world paused, the silence of the
world-update topics while paused, and that the package offers no unpause.  Keep the ``check_driver`` call; add cases,
never remove it.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ODOMETRY = "x-cap.ethz-asl.odometry.v1"
IMU = "x-cap.ethz-asl.imu.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RotorsSimulatorCases(unittest.TestCase):
    def serve(self, **switches):
        driver = self.driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def services(self, native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_odometry_observation_returns_pose_and_twist(self) -> None:
        client, _server = self.serve()
        receipt = client.invoke(ODOMETRY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"pose", "twist"})

    def test_the_imu_observation_returns_an_imu_sample(self) -> None:
        client, _server = self.serve()
        receipt = client.invoke(IMU, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"orientation", "angular_velocity", "linear_acceleration"})

    def test_the_e_stop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver = self.driver()
        result = driver.estop("test")
        self.assertTrue(result["safe_state_achieved"], result)
        self.assertTrue(driver.native.paused)
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])

    def test_the_served_e_stop_completes_and_latches(self) -> None:
        client, _server = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertTrue(receipt["output"]["latched"], receipt)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                driver = self.driver()
                setattr(driver.native, switch, True)
                with self.assertRaises(MHSError) as caught:
                    driver.estop("test")
                self.assertEqual(caught.exception.code, UNREACHED)
                client, _driver = self.serve(**{switch: True})
                served = client.estop("test", **self.ids)
                self.assertEqual(served["status"], "failed", served)
                self.assertEqual(served["error"]["mhs_code"], UNREACHED, served)
                self.assertTrue(served["output"]["latched"], served)

    def test_the_reset_releases_the_latch_only_and_the_world_stays_paused(self) -> None:
        driver = self.driver()
        driver.estop("test")
        driver.reset()
        self.assertTrue(driver.native.paused)
        self.assertNotIn(UNPAUSE, self.services(driver.native))
        with self.assertRaises(MHSError):
            driver.call(ODOMETRY, {})  # still paused: the odometry topic is silent

    def test_the_package_offers_no_unpause(self) -> None:
        driver = self.driver()
        self.assertEqual(set(type(driver).commands), {ODOMETRY, IMU})
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")) + str(spec.get("topic", "")))

    def test_world_update_topics_are_silent_while_paused(self) -> None:
        driver = self.driver()
        driver.native.paused = True
        for capability in (ODOMETRY, IMU):
            with self.subTest(capability=capability):
                with self.assertRaises(MHSError):
                    driver.call(capability, {})

    def test_a_missing_odometry_sample_is_an_observation_timeout(self) -> None:
        driver = self.driver()
        driver.native.drop_odometry = True
        with self.assertRaises(MHSError):
            driver.call(ODOMETRY, {})

    def test_the_resource_reads_no_topic(self) -> None:
        driver = self.driver()
        driver.native.paused = True
        self.assertEqual(driver.read("main"), {})


if __name__ == "__main__":
    unittest.main()
