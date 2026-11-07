"""Acceptance run of the DC-supply package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
SAFE_COMMAND = "INST:NSEL 2;OUTP OFF;INST:NSEL 3;OUTP OFF"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_voltage_write_selects_the_upstream_channel(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_setpoint_ch2": 5.0})
        driver.write("main", {"voltage_setpoint_ch3": 3.3})
        self.assertEqual(driver.native.written[-2:], ["INST:NSEL 2;VOLT 5", "INST:NSEL 3;VOLT 3.3"])

    def test_a_current_write_selects_the_upstream_channel(self) -> None:
        driver = self.driver()
        driver.write("main", {"current_setpoint_ch2": 0.02})
        driver.write("main", {"current_setpoint_ch3": 0.03})
        self.assertEqual(driver.native.written[-2:], ["INST:NSEL 2;CURR 0.02", "INST:NSEL 3;CURR 0.03"])

    def test_the_output_uses_on_and_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output_enabled_ch2": True})
        driver.write("main", {"output_enabled_ch3": False})
        self.assertEqual(driver.native.written[-2:], ["INST:NSEL 2;OUTP ON", "INST:NSEL 3;OUTP OFF"])

    def test_the_reads_use_the_measurement_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["voltage_setpoint_ch2"], 0.0)
        self.assertEqual(state["current_setpoint_ch3"], 0.0)
        self.assertFalse(state["output_enabled_ch2"])
        self.assertEqual(state["voltage_ch3"], 0.0)
        self.assertEqual(state["current_ch2"], 0.0)
        self.assertEqual(driver.native.written[-2:], ["INST:NSEL 3;MEAS:VOLT?", "INST:NSEL 3;MEAS:CURR?"])

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_setpoint_ch2": 2.5, "current_setpoint_ch2": 0.04})
        state = driver.read("main", ["voltage_setpoint_ch2", "current_setpoint_ch2"])
        self.assertEqual(state, {"voltage_setpoint_ch2": 2.5, "current_setpoint_ch2": 0.04})

    def test_the_estop_switches_both_controlled_channels_off(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], SAFE_COMMAND)

    def test_the_safe_state_action_sends_the_same_command(self) -> None:
        driver = self.driver()
        driver.call("x-cap.madhankumar623.output_off.v1", {})
        self.assertEqual(driver.native.written[-1], SAFE_COMMAND)


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    @staticmethod
    def code(receipt):
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_set_points_need_an_operator_bound(self) -> None:
        client = self.serve()
        for patch in ({"voltage_setpoint_ch2": 1.0}, {"current_setpoint_ch2": 0.01},
                      {"voltage_setpoint_ch3": 1.0}, {"current_setpoint_ch3": 0.01}):
            self.assertEqual(self.code(client.invoke("cap.device.configure.v1", patch, **self.ids)), UNSET, patch)
        self.assertEqual(self.code(client.invoke("cap.device.configure.v1", {"output_enabled_ch2": True},
                                                 **self.ids)), "completed")

    def test_the_example_overlay_only_narrows_the_set_points(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage_setpoint_ch2": 0.0}, {"voltage_setpoint_ch2": 5.0},
                      {"current_setpoint_ch2": 0.0}, {"current_setpoint_ch2": 0.05},
                      {"voltage_setpoint_ch3": 2.5}, {"current_setpoint_ch3": 0.02},
                      {"output_enabled_ch3": True}):
            self.assertEqual(self.code(client.invoke("cap.device.configure.v1", patch, **self.ids)), "completed",
                             patch)
        for patch in ({"voltage_setpoint_ch2": -0.001}, {"voltage_setpoint_ch2": 5.001},
                      {"current_setpoint_ch2": -0.001}, {"current_setpoint_ch2": 0.051},
                      {"voltage_setpoint_ch3": 6.0}, {"current_setpoint_ch3": 0.06}):
            self.assertEqual(self.code(client.invoke("cap.device.configure.v1", patch, **self.ids)), ENVELOPE,
                             patch)


if __name__ == "__main__":
    unittest.main()
