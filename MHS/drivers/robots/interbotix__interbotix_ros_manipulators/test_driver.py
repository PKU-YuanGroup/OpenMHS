"""Acceptance run of the Interbotix wx250s package: the gate, plus wire cases.

The gate is expected to stop at G3 because the pinned clone has no native stop;
the remaining cases exercise the two declared wire endpoints directly.  The
``check_driver`` call is kept unchanged.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
GROUP = "x-cap.interbotix.joint_group.v1"
STATES = "x-cap.interbotix.joint_states.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate_records_the_stop_blocker(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], ["G3"], report)
        findings = [finding["code"] for gate in report["gates"] if gate["id"] == "G3"
                    for finding in gate["findings"]]
        self.assertIn("G3.STRICT", findings, report)


class WireCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_joint_states_observation_returns_names_and_positions(self) -> None:
        driver = self.driver()
        output = driver.call(STATES, {})
        self.assertEqual(len(output["names"]), 7)
        self.assertEqual(len(output["positions"]), 7)
        self.assertTrue(all(isinstance(value, (int, float)) for value in output["positions"]))

    def test_group_command_reports_transmission_only(self) -> None:
        driver = self.driver()
        command = [0.0, -0.2, 0.3, 0.0, 0.0, 0.0]  # placeholder test command
        output = driver.call(GROUP, {"joint_positions": command})
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertEqual(driver.native.last_group_command, {"name": "arm", "cmd": command})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/wx250s/commands/joint_group")
        self.assertEqual(advertised[-1]["type"], "interbotix_xs_msgs/JointGroupCommand")
        published = [message for message in driver.native.sent if message.get("op") == "publish"]
        self.assertEqual(published[-1]["msg"], {"name": "arm", "cmd": command})

    def test_group_command_requires_the_operator_envelope(self) -> None:
        client, device_id, session = self.serve()
        command = [0.0, -0.2, 0.3, 0.0, 0.0, 0.0]  # placeholder test command
        refused = client.invoke(GROUP, {"joint_positions": command},
                                device_id=device_id, session_id=session)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_allows_a_bounded_command(self) -> None:
        overlay = json.loads((HERE / "site-limits.example.json").read_text())
        client, device_id, session = self.serve(site_limits=overlay)
        command = [0.0, -0.2, 0.3, 0.0, 0.0, 0.0]  # placeholder test command
        receipt = client.invoke(GROUP, {"joint_positions": command},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})

    def test_silent_joint_states_topic_times_out(self) -> None:
        driver = self.driver()
        driver.native.silent_joint_states = True
        with self.assertRaises(Exception) as caught:
            driver.call(STATES, {})
        self.assertIn(getattr(caught.exception, "code", None),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_malformed_joint_states_is_an_output_failure(self) -> None:
        driver = self.driver()
        driver.native.malformed_joint_states = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(STATES, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
