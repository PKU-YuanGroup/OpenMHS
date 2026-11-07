"""Acceptance run of the Siglent SDG 2042X package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


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

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": "ON", "waveform": "SQUARE", "frequency": 100.0,
                              "amplitude": 2.5, "offset": 1.25, "duty_cycle": 50.0})
        self.assertEqual(driver.native.written[0], "*IDN?")                       # the identity check on connect
        self.assertEqual(driver.native.written[1:], [
            "C2:OUTP ON",
            "C2:BaSic_WaVe WVTP,SQUARE",
            "C2:BaSic_WaVe FRQ,100",
            "C2:BaSic_WaVe AMP,2.5",
            "C2:BaSic_WaVe OFST,1.25",
            "C2:BaSic_WaVe DUTY,50",
        ])

    def test_the_reads_use_the_queries_of_the_guide(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], ["C2:OUTP?", "C2:BaSic_WaVe?", "C2:BaSic_WaVe?",
                                                    "C2:BaSic_WaVe?", "C2:BaSic_WaVe?", "C2:BaSic_WaVe?"])
        self.assertEqual(state, {"output": "OFF", "waveform": "SQUARE", "frequency": 1000.0,
                                  "amplitude": 1.0, "offset": 0.0, "duty_cycle": 50.0})

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": "ON", "waveform": "RAMP", "frequency": 2500.5,
                              "amplitude": 0.25, "offset": -1.5, "duty_cycle": 25.0})
        state = driver.read("main")
        self.assertEqual(state, {"output": "ON", "waveform": "RAMP", "frequency": 2500.5,
                                  "amplitude": 0.25, "offset": -1.5, "duty_cycle": 25.0})

    def test_the_estop_turns_the_output_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": "ON"})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "C2:OUTP OFF")
        self.assertEqual(driver.read("main", ["output"]), {"output": "OFF"})


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

    def test_the_bounds_of_the_clone(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, output="INVALID"), ENVELOPE)
        for patch in ({"output": "ON"}, {"output": "OFF"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        for patch in ({"frequency": 1.0}, {"amplitude": 1.0}, {"offset": 0.0}, {"duty_cycle": 50},
                      {"waveform": "SQUARE"}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_sets_the_duty_cycle_and_the_waveforms(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"duty_cycle": 60}, {"duty_cycle": -1}, {"waveform": "SINE"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"duty_cycle": 40}, {"waveform": "SQUARE"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
