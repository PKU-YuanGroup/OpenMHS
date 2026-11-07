"""Acceptance run of the warehouse_simulation_toolkit package: the gate plus repository cases.

The cases exercise the cmd_vel contract and its receipt, the operator-bound behaviour, the companion-cited stop
(the Gazebo world pause confirmed by the get_physics_properties read-back), its failure paths, the latch, a reset
that leaves the world paused, and that the package offers no unpause. A rosbridge publication is transmission
evidence only, never a motion or stop measurement. Add cases, never remove the ``check_driver`` call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CMD_VEL = "x-cap.wh200720041.cmd_vel.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WarehouseSimulationCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver.native, client

    def direct(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver, driver.native

    @staticmethod
    def services(fake):
        return [message.get("service") for message in fake.sent if message.get("op") == "call_service"]

    def test_cmd_vel_publication_reaches_the_topic_and_reports_what_it_sent(self) -> None:
        driver, fake = self.direct()
        output = driver.call(CMD_VEL, {"linear_velocity": 0.1, "angular_velocity": 0.2})
        self.assertEqual(output, {"published": True, "confirmed": False, "sent_linear_velocity": 0.1,
                                  "sent_angular_velocity": 0.2})
        self.assertEqual(fake.last_cmd_vel["linear"]["x"], 0.1)
        self.assertEqual(fake.last_cmd_vel["angular"]["z"], 0.2)
        self.assertEqual(fake.publish_count, 1)
        advertise = [message for message in fake.sent
                     if message.get("op") == "advertise" and message.get("topic") == "/cmd_vel"]
        publish = [message for message in fake.sent
                   if message.get("op") == "publish" and message.get("topic") == "/cmd_vel"]
        self.assertEqual(len(advertise), 1)
        self.assertEqual(len(publish), 1)
        self.assertEqual(advertise[0]["type"], "geometry_msgs/Twist")

    def test_the_resource_reads_no_topic(self) -> None:
        driver, fake = self.direct()
        fake.paused = True
        self.assertEqual(driver.read("main"), {})

    def test_cmd_vel_is_refused_until_the_operator_supplies_bounds(self) -> None:
        _fake, client = self.serve(overlay=False)
        receipt = client.invoke(CMD_VEL,
                                {"linear_velocity": 0.0, "angular_velocity": 0.0},
                                **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_cmd_vel_example_overlay_narrows_and_is_enforced(self) -> None:
        _fake, client = self.serve()
        payload = {"linear_velocity": 0.05, "angular_velocity": 0.25}
        self.assertEqual(client.invoke(CMD_VEL, payload, **self.ids)["status"], "completed")
        for field, value in (("linear_velocity", 0.51), ("angular_velocity", 1.01)):
            denied = client.invoke(CMD_VEL, dict(payload, **{field: value}), **self.ids)
            self.assertEqual(denied["status"], "rejected", denied)
            self.assertEqual(denied["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        fake, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(fake), [PAUSE, READBACK])
        self.assertTrue(fake.paused)
        refused = client.invoke(CMD_VEL, {"linear_velocity": 0.05, "angular_velocity": 0.25}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                fake, client = self.serve()
                setattr(fake, switch, True)
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertFalse(receipt["output"]["safe_state_achieved"], receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
                refused = client.invoke(CMD_VEL, {"linear_velocity": 0.0, "angular_velocity": 0.0}, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_reset_keeps_the_world_paused_and_a_stored_twist_drives_nothing(self) -> None:
        fake, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(fake.paused)
        receipt = client.invoke(CMD_VEL, {"linear_velocity": 0.05, "angular_velocity": 0.25}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(fake.last_cmd_vel["linear"]["x"], 0.05)  # stored: it acts on the next unpause
        self.assertIsNone(fake.driving_cmd_vel)
        self.assertNotIn("/gazebo/unpause_physics", self.services(fake))

    def test_the_package_offers_no_unpause(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        cls = type(driver)
        self.assertIsNone(driver._model.reenable)
        self.assertEqual(cls.ros_version, 1)
        self.assertEqual(cls.mode, "simulated")
        self.assertEqual(cls.risk, "R2")
        self.assertEqual(cls.device_kind, "world.sim")
        self.assertIsNone(cls.estop_physical_ref)
        self.assertEqual(set(cls.safety_bindings), {"estop", "safe_state"})
        self.assertEqual(set(cls.commands), {CMD_VEL})
        self.assertEqual(set(cls.actions), {CMD_VEL})
        self.assertNotIn("unpause", repr(cls.commands))


if __name__ == "__main__":
    unittest.main()
