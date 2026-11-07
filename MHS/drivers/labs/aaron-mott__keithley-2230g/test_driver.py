"""Acceptance run of the Keithley 2230G package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_selects_the_channel_and_sets_it(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_setpoint_ch1": 1.5, "current_limit_ch1": 0.2,
                              "output_ch1": True})
        self.assertIn("INST:NSEL 1;:VOLT 1.5", driver.native.written)
        self.assertIn("INST:NSEL 1;:CURR 0.2", driver.native.written)
        self.assertIn("INST:NSEL 1;:CHAN:OUTP ON", driver.native.written)

    def test_missing_root_after_selection_is_rejected(self) -> None:
        for tail in ("VOLT 2", "CURR .2", "CHAN:OUTP ON", "VOLT?", "CURR?", "CHAN:OUTP?"):
            with self.subTest(tail=tail):
                driver = self.driver()
                with self.assertRaises(ValueError):
                    driver.native.write("INST:NSEL 2;" + tail)

    def test_rooted_commands_leave_other_channels_unchanged(self) -> None:
        driver = self.driver()
        for channel in (1, 2, 3):
            driver.write("main", {f"voltage_setpoint_ch{channel}": float(channel),
                                  f"current_limit_ch{channel}": channel / 10,
                                  f"output_ch{channel}": True})
        state = driver.read("main")
        for channel in (1, 2, 3):
            self.assertEqual(state[f"voltage_setpoint_ch{channel}"], float(channel))
            self.assertEqual(state[f"current_limit_ch{channel}"], channel / 10)
            self.assertTrue(state[f"output_ch{channel}"])

    def test_the_reads_use_the_channel_and_measurement_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_setpoint_ch2": 2.0, "current_limit_ch2": 0.5,
                              "output_ch2": True})
        state = driver.read("main")
        self.assertEqual(state["voltage_setpoint_ch2"], 2.0)
        self.assertEqual(state["current_limit_ch2"], 0.5)
        self.assertTrue(state["output_ch2"])
        self.assertEqual(state["measured_voltage_ch2"], 2.0)
        self.assertGreater(state["measured_current_ch2"], 0.0)

    def test_the_safe_state_command_disables_every_output(self) -> None:
        driver = self.driver()
        driver.write("main", {"output_ch1": True, "output_ch2": True, "output_ch3": True})
        driver.call("x-cap.aaron-mott.output_off.v1", {})
        self.assertIn("OUTP OFF", driver.native.written)
        state = driver.read("main")
        self.assertEqual((state["output_ch1"], state["output_ch2"], state["output_ch3"]),
                         (False, False, False))

    def test_the_estop_writes_the_all_channel_output_off_command(self) -> None:
        driver = self.driver()
        driver.write("main", {"output_ch1": True})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "OUTP OFF")
        state = driver.read("main")
        self.assertFalse(state["output_ch1"])


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        if receipt["status"] == "rejected":
            return receipt["error"]["mhs_code"]
        return receipt["status"]

    def test_without_an_overlay_every_setpoint_is_operator_required(self) -> None:
        client = self.serve()
        for patch in ({"voltage_setpoint_ch1": 1.0}, {"current_limit_ch1": 0.1}):
            self.assertEqual(self.configure(client, **patch), LIMITS_UNSET, patch)

    def test_the_example_overlay_fills_and_narrows_the_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"voltage_setpoint_ch1": -0.1}, {"voltage_setpoint_ch1": 5.1},
                      {"current_limit_ch1": -0.1}, {"current_limit_ch1": 1.1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"voltage_setpoint_ch1": 0.0}, {"voltage_setpoint_ch1": 5.0},
                      {"current_limit_ch1": 0.0}, {"current_limit_ch1": 1.0},
                      {"output_ch1": True}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
