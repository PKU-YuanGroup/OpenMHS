"""Acceptance run of the Keithley 2450 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
SAFE_ACTION = "x-cap.yongxb.safe_state.v1"
SAFE_COMMAND = "smu.source.output = smu.OFF;smu.source.level = 0"


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

    def test_the_identity_probe_is_the_query_of_the_clone(self) -> None:
        driver = self.driver()
        driver.read("main", ["output"])  # opens the transport and probes *IDN?
        self.assertEqual(driver.native.written[0], "*IDN?")
        self.assertEqual(driver.inner.idn, "KEITHLEY INSTRUMENTS,INC.,MODEL 2450,0000000,1.0")

    def test_a_source_current_write_selects_the_function_and_sets_the_level(self) -> None:
        driver = self.driver()
        driver.write("main", {"source_current": 0.0002})
        self.assertEqual(driver.native.written[-1],
                         "smu.source.func = smu.FUNC_DC_CURRENT;smu.source.level = 0.0002")

    def test_the_compliance_and_output_are_the_attributes_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"compliance_voltage": 10.0, "output": True})
        driver.write("main", {"output": False})
        self.assertEqual(driver.native.written[-3:],
                         ["smu.source.vlimit.level = 10", "smu.source.output = smu.ON",
                          "smu.source.output = smu.OFF"])

    def test_the_reads_select_the_measure_function_and_print(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["voltage", "current"])
        self.assertEqual(driver.native.written[1:],
                         ["smu.measure.func = smu.FUNC_DC_VOLTAGE;print(smu.measure.read())",
                          "smu.measure.func = smu.FUNC_DC_CURRENT;print(smu.measure.read())"])
        self.assertIsInstance(state["voltage"], float)
        self.assertIsInstance(state["current"], float)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"source_current": 0.0005, "compliance_voltage": 5.0})
        state = driver.read("main", ["source_current", "compliance_voltage"])
        self.assertEqual(state, {"source_current": 0.0005, "compliance_voltage": 5.0})

    def test_the_estop_writes_the_safe_command(self) -> None:
        driver = self.driver()
        driver.write("main", {"output": True, "source_current": 0.0005})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], SAFE_COMMAND)


class Runtime(unittest.TestCase):
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

    def configure(self, client, **patch):
        return self.code(client.invoke("cap.device.configure.v1", patch, **self.ids))

    def test_the_source_current_needs_an_operator_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, source_current=0.0001), UNSET)

    def test_the_compliance_voltage_needs_an_operator_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, compliance_voltage=1.0), UNSET)

    def test_the_example_overlay_fills_and_only_narrows_both_envelopes(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"source_current": 0.002}, {"source_current": -0.002},
                      {"compliance_voltage": 51.0}, {"compliance_voltage": -1.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"source_current": 0.0005}, {"source_current": -0.0005},
                      {"compliance_voltage": 0}, {"compliance_voltage": 50}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_output_is_unbounded_and_readable(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, output=True), "completed")
        state = client.read("main", **self.ids)["state"]
        self.assertIs(state["output"], True)
        self.assertEqual(self.configure(client, output=False), "completed")
        self.assertIs(client.read("main", **self.ids)["state"]["output"], False)

    def test_the_safe_state_action_turns_the_output_off_and_zeroes_the_level(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, source_current=0.0005, compliance_voltage=5.0, output=True),
                         "completed")
        receipt = client.invoke(SAFE_ACTION, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = client.read("main", **self.ids)["state"]
        self.assertIs(state["output"], False)
        self.assertEqual(state["source_current"], 0.0)


if __name__ == "__main__":
    unittest.main()
