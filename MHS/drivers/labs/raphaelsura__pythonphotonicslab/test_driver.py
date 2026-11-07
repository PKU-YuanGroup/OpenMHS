"""Acceptance run of the DG645 package: the gate, plus cases for this driver's wire commands and operator bounds."""

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

    def test_a_write_becomes_the_lines_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"trigger_rate": 1000.0, "burst_count": 3, "polarity": 1})
        self.assertEqual(driver.native.written[0], "*IDN?")
        self.assertEqual(driver.native.written[1:], ["TRAT 1000", "BURC 3", "LPOL 1,1"])
        driver.write("main", {"delay": 1e-6, "amplitude": 1.5, "offset": -0.25})
        self.assertEqual(driver.native.written[-3:], ["DLAY 1,0,1e-06", "LAMP 1,1.5", "LOFF 1,-0.25"])

    def test_the_reads_use_the_clone_queries(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], [
            "LAMP? 1", "LOFF? 1", "LPOL? 1", "DLAY? 1", "HOLD?", "TLVL?", "TRAT?", "BURC?", "BURD?",
            "BURM?", "BURP?", "BURT?", "TIMB?", "TSRC?", "LERR?",
        ])
        self.assertEqual(set(state), {
            "amplitude", "offset", "polarity", "delay", "holdoff", "trigger_level", "trigger_rate",
            "burst_count", "burst_delay", "burst_mode", "burst_period", "burst_config", "timebase",
            "trigger_source", "last_error",
        })
        self.assertEqual(state["last_error"], '0,"No error"')

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"trigger_rate": 2500.5, "burst_period": 0.002, "polarity": 1})
        state = driver.read("main", ["trigger_rate", "burst_period", "polarity"])
        self.assertEqual(state, {"trigger_rate": 2500.5, "burst_period": 0.002, "polarity": 1})

    def test_the_estop_sets_all_four_outputs_to_positive_polarity(self) -> None:
        driver = self.driver()
        driver.write("main", {"polarity": 0})
        driver.estop("test")
        self.assertEqual(driver.native.written[-4:], ["LPOL 1,1", "LPOL 2,1", "LPOL 3,1", "LPOL 4,1"])
        self.assertEqual(driver.read("main", ["polarity"]), {"polarity": 1})


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_overlay_every_numeric_write_is_operator_required(self) -> None:
        client = self.serve()
        for patch in ({"trigger_rate": 1000.0}, {"amplitude": 1.0}, {"polarity": 1}, {"burst_count": 3}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_fills_and_narrows_the_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"trigger_rate": -1.0}, {"trigger_rate": 1000001.0}, {"amplitude": 5.1},
                      {"polarity": 2}, {"burst_count": 0}, {"burst_period": 0.0000001}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"trigger_rate": 1000.0}, {"amplitude": 1.0}, {"polarity": 1},
                      {"burst_count": 3}, {"burst_period": 0.001}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
