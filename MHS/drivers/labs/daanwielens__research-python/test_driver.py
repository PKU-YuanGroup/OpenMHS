"""Acceptance run of the Lake Shore 332 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

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


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.written.clear()
        return driver

    def test_the_reads_are_the_queries_of_the_upstream_program(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written, ["KRDG?", "CRDG?", "SETP? 1", "RANGE?", "HTR?", "PID? 1",
                                                 "MOUT? 1"])
        self.assertEqual(state["temperature"], 250.0)
        self.assertEqual(state["temperature_celsius"], -23.15)
        self.assertEqual(state["setpoint"], 250.0)
        self.assertEqual(state["heater_range"], 1)
        self.assertEqual(state["heater_output"], 5.0)
        self.assertEqual(state["pid"], "10,20,0")
        self.assertEqual(state["manual_output"], 0.0)

    def test_a_write_becomes_the_command_of_the_upstream_program(self) -> None:
        driver = self.driver()
        driver.write("main", {"setpoint": 100.0, "heater_range": 2, "manual_output": 12.5})
        self.assertEqual(driver.native.written, ["SETP 1,100", "RANGE 2", "MOUT 1,12.5"])
        state = driver.read("main", ["setpoint", "heater_range", "manual_output"])
        self.assertEqual(state, {"setpoint": 100.0, "heater_range": 2, "manual_output": 12.5})

    def test_the_pid_action_sends_one_pid_command(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.daanwielens.set_pid.v1", {"p": 10, "i": 20.5, "d": 0})
        self.assertEqual(output, {})
        self.assertEqual(driver.native.written, ["PID 1,10,20.5,0"])
        self.assertEqual(driver.read("main", ["pid"]), {"pid": "10,20.5,0"})

    def test_the_estop_sets_the_heater_range_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"heater_range": 3})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "RANGE 0")
        self.assertEqual(driver.read("main", ["heater_range", "heater_output"]),
                         {"heater_range": 0, "heater_output": 0.0})

    def test_the_safe_state_action_writes_range_zero(self) -> None:
        driver = self.driver()
        driver.call("x-cap.daanwielens.heater_off.v1", {})
        self.assertEqual(driver.native.written, ["RANGE 0"])
        self.assertEqual(driver.read("main", ["heater_range"]), {"heater_range": 0})


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_bounds_of_the_upstream_gui(self) -> None:
        client = self.serve()
        for patch in ({"setpoint": 4.4}, {"setpoint": 280.1}, {"manual_output": -0.1},
                      {"manual_output": 100.1}, {"heater_range": 4}, {"heater_range": -1}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"setpoint": 4.5}, {"setpoint": 280.0}, {"manual_output": 0.0},
                      {"manual_output": 100.0}, {"heater_range": 0}, {"heater_range": 3}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_pid_bounds(self) -> None:
        client = self.serve()
        for payload in ({"p": 0.09, "i": 1.0, "d": 0.0}, {"p": 1000.1, "i": 1.0, "d": 0.0},
                        {"p": 1.0, "i": 0.09, "d": 0.0}, {"p": 1.0, "i": 1000.1, "d": 0.0},
                        {"p": 1.0, "i": 1.0, "d": -0.1}, {"p": 1.0, "i": 1.0, "d": 200.1}):
            receipt = client.invoke("x-cap.daanwielens.set_pid.v1", payload, **self.ids)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, payload)
        receipt = client.invoke("x-cap.daanwielens.set_pid.v1",
                                {"p": 0.1, "i": 1000.0, "d": 200.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"setpoint": 10.0}, {"manual_output": 50.1}, {"heater_range": 2}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"setpoint": 20.0}, {"manual_output": 50.0}, {"heater_range": 1}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
