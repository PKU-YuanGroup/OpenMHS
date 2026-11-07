"""Acceptance run of the ur_gripper_gz package: the gate plus the simulated stop.

The fake is a ROS-free F0 canned transport.  These cases exercise the
joint_states read, a silent subscription, the companion world pause confirmed
by the E2 read-back, its failure paths, a reset that leaves the world paused,
the absence of an unpause and the operator bridges.  No Gazebo process, ROS
graph or hardware is contacted.
"""

import json
import os
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.bridge.base import BridgeContext
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
# run_check reads MHS_DRIVER_GATE_COMPANIONS only when inner=True (the G9 child). A direct
# check_driver call ignores that variable unless companions_root is passed, so this test
# forwards the supplied root and does not overwrite it. The fallback is the project corpus
# at work/companions (the directory that holds MHS/sdk), not a path beside the checkout.
_SUPPLIED = os.environ.get("MHS_DRIVER_GATE_COMPANIONS")
if _SUPPLIED:
    COMPANIONS = Path(_SUPPLIED)
else:
    from mhs.driver.package import find_root
    _root = find_root(HERE)
    COMPANIONS = (Path(_root) / "work" / "companions") if _root is not None else HERE.parents[3] / "work" / "companions"

JOINT = "x-cap.cambel.joint-states.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
CONTROL = "/world/empty/control"
STATS = "/world/empty/stats"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        self.assertTrue((COMPANIONS / "LOCK.json").is_file(), COMPANIONS)
        report = check_driver(HERE, backend="fake", companions_root=COMPANIONS)
        self.assertEqual(report["failed"], [], report)


class UrGripperGzCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def served(self, **switches):
        driver = self.driver()
        for name, value in switches.items():
            setattr(driver.native, name, value)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_the_joint_state_read_returns_the_placeholder_sample(self) -> None:
        output = self.driver().call(JOINT, {})
        self.assertEqual(set(output), {"name", "position", "velocity"})
        self.assertEqual(len(output["name"]), len(output["position"]))
        self.assertEqual(len(output["name"]), len(output["velocity"]))
        self.assertTrue(output["name"])

    def test_the_device_resource_reads_no_topic(self) -> None:
        self.assertEqual(self.driver().read("main"), {})

    def test_a_silent_joint_states_subscription_is_a_timeout(self) -> None:
        driver = self.driver()
        driver.native.withhold_joint_states = True
        with self.assertRaises(MHSError) as caught:
            driver.call(JOINT, {}, BridgeContext(deadline_ms=50))
        self.assertIn("MHS.", str(caught.exception))

    def test_the_e_stop_pauses_the_world_and_confirms_it_from_fresh_statistics(self) -> None:
        driver, client = self.served()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(driver.native.controls, [{"pause": True}])
        self.assertTrue(driver.native.paused)
        wire = [(message.get("op"), message.get("service") or message.get("topic")) for message in driver.native.sent
                if message.get("op") in ("call_service", "subscribe", "unsubscribe")]
        self.assertEqual(wire, [("call_service", CONTROL), ("subscribe", STATS), ("unsubscribe", STATS)])
        # An x-cap id is not treated as a read by the latch, so the observation is refused until reset.
        reading = client.invoke(JOINT, {}, **self.ids)
        self.assertEqual(reading["status"], "rejected", reading)
        self.assertEqual(reading["error"]["mhs_code"], ESTOP)

    def test_an_unanswered_or_failed_pause_a_running_world_or_no_statistics_leave_the_e_stop_unconfirmed(self):
        for switch in ("fail_control", "reject_control", "ignore_pause", "silent_stats"):
            with self.subTest(switch=switch):
                _driver, client = self.served(**{switch: True})
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_the_reset_keeps_the_world_paused_and_offers_no_unpause(self) -> None:
        driver, client = self.served()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertIsNone(driver._model.reenable)
        self.assertEqual([control.get("pause") for control in driver.native.controls], [True])
        self.assertFalse(any(control.get("pause") is False for control in driver.native.controls))
        reading = client.invoke(JOINT, {}, **self.ids)
        self.assertEqual(reading["status"], "completed", reading)
        self.assertIn("name", reading["output"])
        self.assertTrue(driver.native.paused)

    def test_no_trajectory_topic_and_no_reenable_are_declared(self) -> None:
        driver = self.driver()
        topics = [spec.get("topic") for spec in type(driver).commands.values()]
        self.assertEqual(topics, ["/joint_states"])
        self.assertFalse(any(str(topic).endswith("joint_trajectory") for topic in topics))
        self.assertIsNone(driver._model.reenable)
        self.assertEqual(set(type(driver).safety_bindings), {"estop", "safe_state"})
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeUrGripperGz"})

    def test_the_declaration_names_the_operator_run_bridges(self) -> None:
        cls = type(self.driver())
        self.assertEqual([item["args"].split("@")[0] for item in cls.operator_bridges], [CONTROL, STATS])
        self.assertEqual(cls.estop_latency_ms, 1500)
        self.assertEqual(cls.mode, "simulated")
        self.assertEqual(cls.risk, "R2")
        reference_path = HERE / "reference.json"
        if reference_path.is_file():
            reference = json.loads(reference_path.read_text())
            self.assertEqual(len(reference["safety"]["operator_bridges"]), 2)
            self.assertIn("## Operator must run", (HERE / "REFERENCE.md").read_text())


if __name__ == "__main__":
    unittest.main()
