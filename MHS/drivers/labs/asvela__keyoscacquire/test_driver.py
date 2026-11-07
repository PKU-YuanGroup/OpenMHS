"""Acceptance run of the keyoscacquire package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
READ_ERROR = "x-cap.asvela.read_error.v1"


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
        driver.write("main", {"acq_type": "AVERage", "num_averages": 64, "p_mode": "NORMal",
                              "num_points": 512, "wav_format": "ASCii"})
        sent = [line for line in driver.native.written if not line.endswith("?")]
        self.assertIn(":ACQuire:TYPE AVER", sent)
        self.assertIn(":ACQuire:COUNt 64", sent)
        self.assertIn(":WAVeform:POINts:MODE NORMal", sent)
        self.assertIn(":WAVeform:POINts 512", sent)
        self.assertIn(":WAVeform:FORMat ASCii", sent)

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[0], "*IDN?")
        for query in (":ACQuire:TYPE?", ":ACQuire:COUNt?", ":WAVeform:POINts:MODE?",
                      ":WAVeform:POINTs?", ":WAVeform:FORMat?", ":OPERegister:CONDition?"):
            self.assertIn(query, driver.native.written)
        self.assertIn("operation_condition", state)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"acq_type": "NORMal", "num_averages": 32})
        state = driver.read("main", ["acq_type", "num_averages"])
        self.assertEqual(state, {"acq_type": "NORM", "num_averages": 32})

    def test_the_estop_writes_stop_and_clears_the_run_bit(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], ":STOP")
        self.assertEqual(driver.read("main", ["operation_condition"]), {"operation_condition": 0})


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
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_bounds_of_the_upstream_code(self) -> None:
        client = self.serve()
        for patch in ({"num_averages": 1}, {"num_averages": 65537}, {"num_points": -1},
                      {"num_points": 1000001}, {"acq_type": "PEAK"}, {"p_mode": "HIRES"},
                      {"wav_format": "CSV"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"num_averages": 2}, {"num_averages": 65536}, {"num_points": 0},
                      {"acq_type": "HRESolution"}, {"p_mode": "NORMal"}, {"wav_format": "ASCii"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"num_averages": 65}, {"num_points": 10001}, {"p_mode": "MAX"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"num_averages": 64}, {"num_points": 10000}, {"p_mode": "RAW"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_error_queue_action_returns_the_instrument_reply(self) -> None:
        client = self.serve()
        receipt = client.invoke(READ_ERROR, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIsInstance(receipt["output"]["error"], str)


if __name__ == "__main__":
    unittest.main()
