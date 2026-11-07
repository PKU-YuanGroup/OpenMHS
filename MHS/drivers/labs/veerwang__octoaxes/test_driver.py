"""Acceptance run of the Octoaxes package: the gate, plus cases for this driver's own wire frames.

Add cases, never remove the check_driver call.
"""

import struct
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireFrames(unittest.TestCase):
    """What the driver hands to the transport: the 8-byte payloads of the upstream GUI."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_comes_from_the_position_broadcast(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual((state["x_position_um"], state["y_position_um"], state["z_steps"]), (0.0, 0.0, 0))
        self.assertFalse(state["moving"])

    def test_move_xy_sends_the_two_moveto_commands(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.veerwang.move_xy.v1", {"x_um": 1000.0, "y_um": 2000.0})
        self.assertEqual(output, {"x_um": 1000.0, "y_um": 2000.0, "commanded": True})
        commands = driver.native.commands
        self.assertEqual([command[1] for command in commands], [6, 7])
        mm_per_step = 2.54 / (200 * 256)
        self.assertEqual(struct.unpack(">i", commands[0][2:6])[0], int(1.0 / mm_per_step))
        self.assertEqual(struct.unpack(">i", commands[1][2:6])[0], int(2.0 / mm_per_step))

    def test_illumination_sends_the_port_intensity_and_on_byte(self) -> None:
        driver = self.driver()
        output = driver.call("cap.imaging.illumination.v1", {"channel": "D2", "intensity": 20.0})
        self.assertEqual(output, {"applied": True, "channel": "D2", "intensity": 20.0})
        command = driver.native.commands[-1]
        self.assertEqual(command[1], 37)
        self.assertEqual(command[2], 1)
        self.assertEqual((command[3] << 8) | command[4], int(round(0.20 * 65535)))
        self.assertEqual(command[5], 1)

    def test_the_estop_de_energises_the_axes_and_turns_the_ports_off(self) -> None:
        driver = self.driver()
        driver.call("cap.imaging.illumination.v1", {"channel": "D1", "intensity": 10.0})
        driver.estop("test")
        self.assertFalse(any(driver.native._enabled.values()))
        self.assertFalse(any(port["on"] for port in driver.native._ports.values()))

    def test_the_safe_state_action_reaches_the_native_stop(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.veerwang.safe_state.v1", {})
        self.assertEqual(output, {"safe": True})


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session_id}

    def invoke(self, client, ids, capability_id, payload):
        receipt = client.invoke(capability_id, payload, **ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_upstream_travel_bounds_are_refused(self) -> None:
        client, ids = self.serve()
        for payload in ({"x_um": -11.0, "y_um": 0.0}, {"x_um": 115001.0, "y_um": 0.0},
                        {"x_um": 0.0, "y_um": -11.0}, {"x_um": 0.0, "y_um": 76001.0}):
            self.assertEqual(self.invoke(client, ids, "x-cap.veerwang.move_xy.v1", payload), ENVELOPE, payload)
        for payload in ({"x_um": -10.0, "y_um": -10.0}, {"x_um": 115000.0, "y_um": 76000.0}):
            self.assertEqual(self.invoke(client, ids, "x-cap.veerwang.move_xy.v1", payload), "completed", payload)

    def test_the_illumination_percentage_is_bounded(self) -> None:
        client, ids = self.serve()
        for value in (-1.0, 101.0):
            payload = {"channel": "D1", "intensity": value}
            self.assertEqual(self.invoke(client, ids, "cap.imaging.illumination.v1", payload), ENVELOPE, payload)
        for value in (0.0, 100.0):
            payload = {"channel": "D1", "intensity": value}
            self.assertEqual(self.invoke(client, ids, "cap.imaging.illumination.v1", payload), "completed", payload)


if __name__ == "__main__":
    unittest.main()
