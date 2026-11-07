"""Acceptance run of the LeCroy WaveRunner 104MXi-A package: the gate, plus cases for what is specific to this driver.

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
    """The command map, checked on the lines the fake transport receives (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_identity_probe_comes_first(self) -> None:
        driver = self.driver()
        driver.read("main", ["trigger_mode"])                 # the first request opens the transport
        self.assertEqual(driver.native.written[0], "*IDN?")

    def test_a_write_becomes_the_command_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"trigger_mode": "norm"})
        self.assertEqual(driver.native.written[-1], "TRMD norm")
        driver.write("main", {"acquisition_type": "hres"})
        self.assertEqual(driver.native.written[-1], ":acquire:type hres")
        driver.write("main", {"sample_mode": "etim"})
        self.assertEqual(driver.native.written[-1], ":acquire:mode etim")
        driver.write("main", {"acquisition_averages": 32})
        self.assertEqual(driver.native.written[-1], ":acquire:count 32")
        driver.write("main", {"timebase_mode": "wind"})
        self.assertEqual(driver.native.written[-1], ":timebase:mode wind")
        driver.write("main", {"timebase_reference": "righ"})
        self.assertEqual(driver.native.written[-1], ":timebase:reference righ")

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[1:], [
            "TRMD?", ":acquire:type?", ":acquire:mode?", ":acquire:count?", ":timebase:mode?",
            ":timebase:reference?", ":measure:frequency? C1", ":measure:period? C1", ":measure:vpp? C1"])
        self.assertEqual((state["trigger_mode"], state["acquisition_type"], state["sample_mode"]),
                         ("auto", "norm", "rtim"))
        self.assertEqual(state["acquisition_averages"], 16)
        self.assertEqual((state["timebase_mode"], state["timebase_reference"]), ("main", "cent"))
        self.assertEqual((state["measurement_frequency"], state["measurement_period"],
                          state["measurement_vpp"]), (1.0e6, 1.0e-6, 2.0))

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"trigger_mode": "single", "acquisition_averages": 64})
        state = driver.read("main", ["trigger_mode", "acquisition_averages"])
        self.assertEqual((state["trigger_mode"], state["acquisition_averages"]), ("single", 64))

    def test_the_estop_stops_the_acquisition(self) -> None:
        driver = self.driver()
        driver.write("main", {"acquisition_averages": 32})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], ":stop")
        self.assertEqual(driver.read("main", ["acquisition_averages"]), {"acquisition_averages": 32})


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
        for patch in ({"acquisition_averages": 0}, {"acquisition_averages": 65537},
                      {"trigger_mode": "illegal"}, {"acquisition_type": "normal"}, {"sample_mode": "real_time"},
                      {"timebase_mode": "window"}, {"timebase_reference": "center"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"acquisition_averages": 1}, {"acquisition_averages": 65536}, {"trigger_mode": "stop"},
                      {"acquisition_type": "aver"}, {"sample_mode": "etim"}, {"timebase_mode": "roll"},
                      {"timebase_reference": "righ"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"trigger_mode": "single"}, {"acquisition_averages": 2048},
                      {"timebase_reference": "righ"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"trigger_mode": "norm"}, {"acquisition_averages": 512}, {"timebase_reference": "left"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
