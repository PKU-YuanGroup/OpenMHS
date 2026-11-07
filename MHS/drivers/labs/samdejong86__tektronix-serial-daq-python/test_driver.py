"""Acceptance run of this driver package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


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

    def test_a_settings_write_uses_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {
            "ch1_scale": 0.5,
            "coupling_ch1": "AC",
            "impedance_ch1": "MEG",
            "trigger_level": 1.0,
            "trigger_source": "CH1",
            "trigger_slope": "RISE",
            "horizontal_scale": 1e-6,
            "trigger_position": 20.0,
            "record_length": "5.E2",
            "ch2_scale": 0.2,
            "coupling_ch2": "DC",
            "impedance_ch2": "FIF",
        })
        self.assertEqual(driver.native.written[0], "*IDN?")  # the identity check on connect (tekdaq.py:85-90)
        self.assertEqual(driver.native.written[1:], [
            "CH1:SCA 0.5",
            "CH1:COUPL AC",
            "CH1:IMPED MEG",
            "TRIGGER:A:LEVEL 1",
            "TRIG:A:EDGE:SOU CH1",
            "TRIG:A:EDGE:SLO RISE",
            "HOR:SCA 1e-06",
            "HOR:TRIG:POS 20",
            "HOR:RECORDLENGTH 5.E2",
            "CH2:SCA 0.2",
            "CH2:COUPL DC",
            "CH2:IMPED FIF",
        ])

    def test_a_scale_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"ch1_scale": 0.25})
        state = driver.read("main")
        self.assertEqual(state["ch1_scale"], 0.25)
        self.assertEqual(driver.native.written[-2:], ["CH1:SCALE?", "CH2:SCALE?"])

    def test_the_estop_writes_the_stop_and_unlock_commands(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-2:], ["ACQ:STOPA SEQ", "LOC NONE"])


if __name__ == "__main__":
    unittest.main()
