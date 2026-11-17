"""Acceptance run of the DHO824 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
SINGLE = "x-cap.aimoda.single.v1"
READ_ERROR = "x-cap.aimoda.read_error.v1"


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
        driver.write("main", {"acquisition_status": "RUN", "channel1_coupling": "AC",
                              "channel1_scale": 0.1, "channel1_probe": 10, "channel1_display": False,
                              "channel1_invert": True, "channel1_bandwidth_limit": "20M",
                              "timebase_scale": 0.0002, "dvm_enabled": True, "dvm_mode": "DC"})
        sent = [line for line in driver.native.written if not line.endswith("?")]
        self.assertIn(":RUN", sent)
        self.assertIn(":CHAN1:COUP AC", sent)
        self.assertIn(":CHAN1:SCAL 0.1", sent)
        self.assertIn(":CHAN1:PROB 10", sent)
        self.assertIn(":CHAN1:DISP OFF", sent)
        self.assertIn(":CHAN1:INV ON", sent)
        self.assertIn(":CHAN1:BWL 20M", sent)
        self.assertIn(":TIM:MAIN:SCAL 0.0002", sent)
        self.assertIn(":DVM:ENABle ON", sent)
        self.assertIn(":DVM:MODE DC", sent)

    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written[0], "*IDN?")
        for query in (":TRIG:STAT?", ":DVM:ENABle?", ":DVM:CURRent?", ":DVM:MODE?",
                      ":CHAN1:DISP?", ":CHAN1:COUP?", ":CHAN1:SCAL?", ":CHAN1:OFFS?",
                      ":CHAN1:PROB?", ":CHAN1:INV?", ":CHAN1:BWL?", ":TIM:MAIN:SCAL?",
                      ":TIM:MAIN:OFFS?"):
            self.assertIn(query, driver.native.written)
        self.assertEqual(state["identity"], "RIGOL TECHNOLOGIES,DHO824,DHO8A000000000,00.01.04")
        self.assertEqual(state["acquisition_status"], "STOP")

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel1_coupling": "AC", "channel1_scale": 0.2,
                              "acquisition_status": "RUN", "dvm_enabled": True})
        state = driver.read("main", ["channel1_coupling", "channel1_scale", "acquisition_status",
                                     "dvm_enabled"])
        self.assertEqual(state, {"channel1_coupling": "AC", "channel1_scale": 0.2,
                                 "acquisition_status": "RUN", "dvm_enabled": True})

    def test_the_estop_writes_stop_and_stops_the_acquisition(self) -> None:
        driver = self.driver()
        driver.write("main", {"acquisition_status": "RUN"})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], ":STOP")
        self.assertEqual(driver.read("main", ["acquisition_status"]), {"acquisition_status": "STOP"})

    def test_the_single_action_sends_sing(self) -> None:
        driver = self.driver()
        output = driver.call(SINGLE, {})
        self.assertEqual(output, {"command": ":SING"})
        self.assertIn(":SING", driver.native.written)
        self.assertEqual(driver.read("main", ["acquisition_status"]), {"acquisition_status": "WAIT"})

    def test_the_error_queue_action_returns_the_instrument_reply(self) -> None:
        driver = self.driver()
        output = driver.call(READ_ERROR, {})
        self.assertEqual(output["error"], '0,"No error"')

    def test_instrument_error_after_write_produces_failed_receipt(self) -> None:
        native = self.driver().native
        server = load(HERE, backend="fake", native=native)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        native.errors.append('-222,"Data out of range"')  # placeholder instrument failure
        receipt = client.invoke("cap.device.configure.v1", {"channel1_coupling": "AC"},
                                device_id=device_id, session_id=session_id)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED", receipt)
        self.assertIn(":CHAN1:COUP AC", native.written)
        self.assertEqual(native.errors, [])


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

    def test_vertical_scale_requires_deployment_bounds(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel1_scale=0.0005), "MHS.SAFETY.LIMITS_UNSET")

    def test_the_sourced_bounds_are_enforced(self) -> None:
        client = self.serve()
        for patch in ({"timebase_scale": 4e-9}, {"timebase_scale": 501.0},
                      {"channel1_coupling": "LFReject"}, {"channel1_bandwidth_limit": "20MHz"},
                      {"channel1_probe": 15.0}, {"dvm_mode": "AC+DC_RMS"},
                      {"acquisition_status": "SINGLE"}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"timebase_scale": 5e-9}, {"timebase_scale": 500.0},
                      {"channel1_coupling": "GND"}, {"channel1_bandwidth_limit": "OFF"},
                      {"channel1_probe": 1.0}, {"dvm_mode": "DCRM"},
                      {"acquisition_status": "RUN"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_example_overlay_bounds_scale_and_restricts_probe_ratio(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"channel1_scale": 0.0004}, {"channel1_scale": 10.1}, {"channel1_probe": 10.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"channel1_probe": 1.0}, {"channel1_scale": 0.0005}, {"channel1_scale": 10.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_single_extension_is_callable_through_the_server(self) -> None:
        client = self.serve()
        receipt = client.invoke(SINGLE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"command": ":SING"})
        receipt = client.invoke(READ_ERROR, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["error"], '0,"No error"')


if __name__ == "__main__":
    unittest.main()
