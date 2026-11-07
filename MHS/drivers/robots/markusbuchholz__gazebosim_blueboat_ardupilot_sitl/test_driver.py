"""Acceptance cases for the BlueBoat Gazebo/ArduPilot SITL package.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
THRUST = "x-cap.markusbuchholz.set_motor_thrust.v1"
STOP = "x-cap.markusbuchholz.stop.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BlueboatCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_read_state_comes_from_the_node_data_snapshots(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["base_mode"], 0)
        self.assertEqual(state["heading_deg"], 90.0)
        self.assertEqual(len(state["servo_outputs"]), 8)
        self.assertEqual(state["servo_outputs"], [1500] * 8)

    def test_motor_thrust_reaches_the_upstream_motor_numbers(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(THRUST, {"port_pct": 25.0, "stbd_pct": 30.0})
        self.assertEqual(output, {"port_pct": 25.0, "stbd_pct": 30.0})
        self.assertEqual(driver.native.sent,
                         [("motor", 3, 25), ("motor", 4, 30)])

    def test_the_thrust_envelope_is_enforced(self) -> None:
        client = self.serve()
        for port, stbd in ((101.0, 10.0), (-1.0, 10.0), (10.0, 101.0), (10.0, -1.0)):
            refused = client.invoke(THRUST, {"port_pct": port, "stbd_pct": stbd}, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["heading_deg"], 90.0)

    def test_arm_and_disarm_change_the_heartbeat_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["base_mode"], 0)
        self.assertEqual(client.invoke("x-cap.markusbuchholz.arm.v1", {}, **self.ids)["status"],
                         "completed")
        self.assertEqual(self.state(client)["base_mode"], 128)
        self.assertEqual(client.invoke("x-cap.markusbuchholz.disarm.v1", {}, **self.ids)["status"],
                         "completed")
        self.assertEqual(self.state(client)["base_mode"], 0)

    def test_the_stop_action_sends_zero_thrust_and_disarm(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call(STOP, {}), {"requested": True})
        self.assertEqual(driver.native.sent,
                         [("motor", 3, 0), ("motor", 4, 0), ("disarm",)])

    def test_the_unacknowledged_estop_is_not_certified_and_latches(self) -> None:
        # The node only transmits the zero-thrust and disarm MAVLink commands and reads no
        # acknowledgement: the e-stop sends them, reports SAFE_STATE_UNREACHED and keeps the latch.
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        native = server.devices[device_id].bridge.native
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertEqual(native.sent[:3], [("motor", 3, 0), ("motor", 4, 0), ("disarm",)])
        mark = len(native.sent)
        refused = client.invoke(THRUST, {"port_pct": 10.0, "stbd_pct": 10.0}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertNotIn(("motor", 3, 10), native.sent[mark:])

    def test_the_zero_thrust_and_disarm_action_is_not_a_safe_state_action(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        device_id = client_for(server).hello()["devices"][0]["device_id"]
        self.assertEqual(server.devices[device_id].safety.safe_state["achieved_by"], [])

    def test_a_missing_servo_field_is_refused(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        with driver.native.data_lock:
            del driver.native.data["SERVO_OUTPUT_RAW"]["servo8_raw"]
        with self.assertRaises(Exception) as caught:
            driver.read("main")
        self.assertIn("servo8_raw", str(caught.exception))

    def test_a_failed_disarm_is_not_hidden(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_disarm = True
        with self.assertRaises(RuntimeError) as caught:
            driver.call(STOP, {})
        self.assertIn("disarm failure", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
