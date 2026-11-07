"""Acceptance run of the drl_uav ROS package: the gate, plus cases specific to this game contract.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STATUS = "x-cap.px4-gazebo-simulation.game-status.v1"
ACTION = "x-cap.px4-gazebo-simulation.game-action.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DrlUavCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def served(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver

    def test_the_status_observation_returns_the_four_message_fields(self) -> None:
        client, _driver = self.served()
        receipt = client.invoke(STATUS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"vel1", "vel2", "pos1", "pos2"})
        for value in receipt["output"].values():
            self.assertIsInstance(value, (int, float))

    def test_the_resource_reads_expose_the_same_four_fields(self) -> None:
        client, _driver = self.served()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(set(state), {"vel1", "vel2", "pos1", "pos2"})

    def test_the_publication_reaches_the_fake_and_moves_the_toy_state(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(ACTION, {"action": 1.0}),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.sent_actions, [1.0])
        self.assertAlmostEqual(driver.native.pos1, 3.6)
        self.assertEqual(driver.call(ACTION, {"action": 0.0}),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.sent_actions, [1.0, 0.0])
        self.assertAlmostEqual(driver.native.pos1, 3.5)

    def test_the_documented_restart_action_is_transmitted_without_a_stop_claim(self) -> None:
        client, _driver = self.served()
        before = client.read("main", **self.ids)["state"]["pos1"]
        receipt = client.invoke(ACTION, {"action": -1.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        # The toy game_test.py ignores -1 and only restarts above 100.0, so the
        # fake state is unchanged; a publication is not a restart confirmation.
        after = client.read("main", **self.ids)["state"]["pos1"]
        self.assertEqual(after, before)

    def test_an_out_of_envelope_action_is_refused_before_the_fake(self) -> None:
        client, driver = self.served()
        receipt = client.invoke(ACTION, {"action": 2.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(driver.native.sent_actions, [])

    def test_a_silent_status_topic_fails_the_observation(self) -> None:
        driver = self.driver()
        driver.native.silent_status = True
        with self.assertRaises(MHSError) as caught:
            driver.call(STATUS, {})
        self.assertIn(caught.exception.code, {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_malformed_status_message_fails_the_observation(self) -> None:
        driver = self.driver()
        driver.native.malformed_status = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(STATUS, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_the_stock_estop_latches_without_an_upstream_stop(self) -> None:
        client, driver = self.served()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED)
        self.assertEqual(stopped["output"]["estop"], "software_only")
        self.assertTrue(stopped["output"]["latched"])
        refused = client.invoke(ACTION, {"action": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(driver.native.sent_actions, [])


if __name__ == "__main__":
    unittest.main()
