"""Acceptance run of the RIGOL DP832A package: the gate, plus cases for what is specific to this driver.

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
        return driver

    def test_a_setpoint_write_selects_the_channel_and_sets_the_value(self) -> None:
        driver = self.driver()
        driver.write("main", {"voltage_1": 5.0, "current_2": 0.4})
        self.assertEqual(driver.native.written[0], "*IDN?")             # the identity probe on connect
        self.assertEqual(driver.native.written[1:],
                         [":INST:NSEL 1;:VOLT 5", ":INST:NSEL 2;:CURR 0.4"])

    def test_protection_writes_use_the_selected_channel(self) -> None:
        driver = self.driver()
        driver.write("main", {"ovp_3": 5.5, "ocp_3": 3.3})
        self.assertEqual(driver.native.written[1:],
                         [":INST:NSEL 3;:VOLT:PROT 5.5", ":INST:NSEL 3;:CURR:PROT 3.3"])

    def test_an_output_write_sends_on_and_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"out_1": True})
        driver.write("main", {"out_1": False})
        self.assertEqual(driver.native.written[1:], [":OUTP CH1,ON", ":OUTP CH1,OFF"])

    def test_the_reads_use_the_measurement_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:],
                         [":MEAS:VOLT? CH1", ":MEAS:VOLT? CH2", ":MEAS:VOLT? CH3",
                          ":MEAS:CURR? CH1", ":MEAS:CURR? CH2", ":MEAS:CURR? CH3",
                          ":MEAS:POWE? CH1", ":MEAS:POWE? CH2", ":MEAS:POWE? CH3"])
        self.assertEqual(state["measured_voltage_1"], 0.0)             # placeholder fake value
        self.assertEqual(state["measured_current_3"], 0.1)             # placeholder fake value

    def test_the_estop_disables_every_output(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-3:],
                         [":OUTP CH1,OFF", ":OUTP CH2,OFF", ":OUTP CH3,OFF"])

    def test_the_safe_state_action_is_the_same_three_off_commands(self) -> None:
        driver = self.driver()
        driver.call("x-cap.majidbenk.output_off.v1", {})
        self.assertEqual(driver.native.written[1:],
                         [":OUTP CH1,OFF;:OUTP CH2,OFF;:OUTP CH3,OFF"])


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_bounds_of_the_clone(self) -> None:
        client = self.serve()
        refused = ({"voltage_1": 30.1}, {"voltage_2": 30.1}, {"voltage_3": 5.1},
                   {"current_1": 3.1}, {"current_2": 3.1}, {"current_3": 3.1},
                   {"ovp_1": 33.1}, {"ovp_2": 33.1},
                   {"ovp_3": 5.6}, {"ocp_1": 3.4})
        for patch in refused:
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        accepted = ({"voltage_1": 30.0}, {"voltage_3": 5.0}, {"current_1": 3.0},
                    {"ovp_1": 33.0}, {"ovp_3": 5.5},
                    {"ocp_1": 3.3})
        for patch in accepted:
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
