"""Acceptance run of the Tektronix DPO70000 package: the gate, plus cases for the command map.

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

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"acquisition_mode": "AVE", "acquisition_num_samples": 10000,
                              "acquisition_enhanced_state": True, "acquisition_magnivu": True})
        self.assertEqual(driver.native.written, ["ACQ:MOD AVE", "ACQ:NUMSAM 10000",
                                                 "ACQ:ENHANCEDE:STATE 1", "ACQ:MAG ON"])

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[:3], ["ACQ:MOD?", "ACQ:MOD:ACT?", "ACQ:NUMAC?"])
        self.assertEqual(state["acquisition_mode"], "SAM")
        self.assertEqual(state["acquisition_num_samples"], 16000)
        self.assertEqual(state["acquisition_state"], "STOP")
        self.assertEqual(state["acquisition_magnivu"], False)
        self.assertEqual(state["trigger_state"], "READY")

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"acquisition_mode": "ENV", "acquisition_state": "RUN",
                              "acquisition_enhanced_state": True})
        state = driver.read("main", ["acquisition_mode", "acquisition_state", "acquisition_enhanced_state"])
        self.assertEqual(state, {"acquisition_mode": "ENV", "acquisition_state": "RUN",
                                 "acquisition_enhanced_state": True})

    def test_the_estop_sends_stop_and_the_state_is_stopped(self) -> None:
        driver = self.driver()
        driver.write("main", {"acquisition_state": "RUN"})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], ":STOP")
        self.assertEqual(driver.read("main", ["acquisition_state"]), {"acquisition_state": "STOP"})


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_allowed_sets_and_the_sample_range(self) -> None:
        client = self.serve()
        for patch in ({"acquisition_mode": "BOGUS"}, {"acquisition_sampling_mode": "BOGUS"},
                      {"acquisition_state": "BOGUS"}, {"acquisition_stop_after": "BOGUS"},
                      {"acquisition_enhanced_enob": "ON"}, {"acquisition_interp_8bit": "BOGUS"},
                      {"acquisition_num_samples": 4999}, {"acquisition_num_samples": 2147400001}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"acquisition_mode": "ENV"}, {"acquisition_sampling_mode": "IT"},
                      {"acquisition_state": "STOP"}, {"acquisition_stop_after": "SEQ"},
                      {"acquisition_enhanced_enob": "AUTO"}, {"acquisition_interp_8bit": "ON"},
                      {"acquisition_num_samples": 5000}, {"acquisition_num_samples": 2147400000}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
