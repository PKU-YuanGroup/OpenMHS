"""Acceptance run of the warehouse_robot_simulation package: the gate plus repository cases.

The cases exercise the order publication (the receipt reports the string sent), a malformed order, a
transport failure, the companion-cited stop (the Gazebo world pause confirmed by the
get_physics_properties read-back), its failure paths, the latch, a reset that leaves the world paused,
and that the package offers no unpause.  Add cases, never remove the ``check_driver`` call.
"""

import os
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ORDER = "x-cap.rodriguesrenato.order.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
SAMPLE = "DispatchA ProductR 3 ProductG 5"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        kwargs = {}
        companions = os.environ.get("MHS_DRIVER_GATE_COMPANIONS")
        if companions:
            kwargs["companions_root"] = companions
        report = check_driver(HERE, backend="fake", **kwargs)
        self.assertEqual(report["failed"], [], report)


class WarehouseRobotSimulationCases(unittest.TestCase):
    def session(self):
        """A server built on a driver this test can read, including its fake."""
        driver = load_driver(HERE, "fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        return driver, client, ids

    def direct(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver, driver.native

    @staticmethod
    def publishes(driver, topic):
        return [message for message in driver.native.sent
                if message.get("op") == "publish" and message.get("topic") == topic]

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_order_publication_reaches_the_declared_topic_and_reports_the_sent_string(self) -> None:
        driver, fake = self.direct()
        output = driver.call(ORDER, {"order": SAMPLE})
        self.assertEqual(output, {"submitted": True, "confirmed": False, "sent_order": SAMPLE})
        advertised = [message for message in fake.sent
                      if message.get("op") == "advertise" and message.get("topic") == "/warehouse/order/add"]
        self.assertEqual(len(advertised), 1)
        self.assertEqual(advertised[0]["type"], "std_msgs/String")
        publish = self.publishes(driver, "/warehouse/order/add")
        self.assertEqual(len(publish), 1)
        self.assertEqual(publish[0]["msg"], {"data": SAMPLE})
        self.assertEqual(fake.publish_count, 1)

    def test_two_order_strings_produce_different_receipts(self) -> None:
        driver, fake = self.direct()
        first = "DispatchA ProductR 3"
        second = "DispatchB ProductB 1 ProductG 2"
        self.assertNotEqual(driver.call(ORDER, {"order": first})["sent_order"],
                            driver.call(ORDER, {"order": second})["sent_order"])
        self.assertEqual(fake.published, [first, second])

    def test_the_order_string_is_sent_verbatim(self) -> None:
        driver, fake = self.direct()
        text = "DispatchB ProductB 1 ProductG 2 ProductR 4"
        output = driver.call(ORDER, {"order": text})
        self.assertEqual(output["sent_order"], text)
        self.assertEqual(fake.published, [text])
        self.assertEqual(fake.parsed_orders, [("DispatchB", [("ProductB", 1), ("ProductG", 2),
                                                             ("ProductR", 4)])])

    def test_a_malformed_order_is_still_only_an_unconfirmed_publication(self) -> None:
        driver, fake = self.direct()
        text = "DispatchA ProductR not-a-number"
        output = driver.call(ORDER, {"order": text})
        self.assertEqual(output, {"submitted": True, "confirmed": False, "sent_order": text})
        self.assertEqual(fake.published, [text])
        self.assertEqual(fake.discarded_orders, [text])
        self.assertEqual(fake.parsed_orders, [])

    def test_a_transport_failure_is_not_reported_as_success(self) -> None:
        driver, fake = self.direct()
        fake.fail_next_publish = True
        with self.assertRaises(MHSError) as caught:
            driver.call(ORDER, {"order": "DispatchA ProductR 3"})
        self.assertIn(caught.exception.code,
                      {"MHS.ADAPTER.SHIM_FAILED", "MHS.OUTCOME.UNKNOWN", "MHS.DEVICE.NOT_READY"})

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client, ids = self.session()
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])
        self.assertTrue(driver.native.paused)
        refused = client.invoke(ORDER, {"order": SAMPLE}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                driver, client, ids = self.session()
                setattr(driver.native, switch, True)
                receipt = client.estop("test", **ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
                self.assertFalse(receipt["output"]["safe_state_achieved"])
                refused = client.invoke(ORDER, {"order": SAMPLE}, **ids)
                self.assertEqual(refused["status"], "rejected", refused)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_reset_keeps_the_world_paused_and_offers_no_unpause(self) -> None:
        driver, client, ids = self.session()
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        self.assertEqual(client.reset(**ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke(ORDER, {"order": SAMPLE}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_order"], SAMPLE)
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])

    def test_the_package_offers_no_unpause(self) -> None:
        driver, _fake = self.direct()
        self.assertIsNone(driver._model.reenable)
        cls = type(driver)
        for spec in {**cls.commands, **cls.safety_bindings}.values():
            self.assertNotIn("unpause", str(spec.get("service", "")))
            self.assertNotIn("unpause", str(spec.get("topic", "")))

    def test_the_declaration_binds_the_pause_and_keeps_the_order(self) -> None:
        driver, _fake = self.direct()
        cls = type(driver)
        self.assertEqual(cls.ros_version, 1)
        self.assertEqual(cls.mode, "simulated")
        self.assertEqual(cls.risk, "R2")
        self.assertEqual(cls.device_kind, "world.sim")
        self.assertIsNone(cls.estop_physical_ref)
        self.assertEqual(set(cls.safety_bindings), {"estop", "safe_state"})
        self.assertEqual(cls.safety_bindings["estop"]["service"], PAUSE)
        self.assertEqual(cls.safety_bindings["safe_state"]["service"], READBACK)
        self.assertEqual(cls.safety_bindings["safe_state"]["success"], {"path": "pause", "equals": True})
        self.assertEqual(set(cls.commands), {ORDER})
        self.assertEqual(set(cls.actions), {ORDER})
        self.assertNotIn("unpause", repr(cls.commands))
        self.assertNotIn("/gazebo/unpause_physics", repr(cls.safety_bindings))


if __name__ == "__main__":
    unittest.main()
