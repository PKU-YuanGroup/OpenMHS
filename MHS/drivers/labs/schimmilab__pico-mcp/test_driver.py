"""Acceptance run of the PicoScope package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The fake's starting values are test data, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
AWG = "x-cap.schimmilab.set_signal_generator.v1"
STOP = "x-cap.schimmilab.stop_signal_generator.v1"
CAPTURE = "x-cap.schimmilab.capture_block.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class State(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_state_reads_the_fake(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["connected", "variant", "serial", "resolution_bits", "max_adc",
                                     "channel_a_enabled", "channel_a_coupling", "channel_a_range_v",
                                     "channel_c_enabled"])
        self.assertTrue(state["connected"])
        self.assertEqual(state["variant"], "5442B")
        self.assertEqual(state["resolution_bits"], 12)
        self.assertEqual(state["channel_a_enabled"], True)
        self.assertEqual(state["channel_a_coupling"], "DC")
        self.assertEqual(state["channel_c_enabled"], False)

    def test_a_write_reaches_the_fake_and_is_read_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel_a_enabled": False, "channel_a_coupling": "AC",
                             "channel_b_range_v": 0.5})
        state = driver.read("main", ["channel_a_enabled", "channel_a_coupling", "channel_b_range_v"])
        self.assertEqual(state, {"channel_a_enabled": False, "channel_a_coupling": "AC",
                                 "channel_b_range_v": 0.5})


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_stated_channel_range_is_enforced(self) -> None:
        client = self.serve()
        for value in (0.005, 20.5):
            self.assertEqual(self.configure(client, channel_a_range_v=value), ENVELOPE, value)
        self.assertEqual(self.configure(client, channel_a_coupling="BOGUS"), ENVELOPE)

    def test_the_awg_and_the_capture_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(AWG, {"frequency_hz": 1000, "amplitude_v": 1, "wave": "sine"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], UNSET)
        refused = client.invoke(CAPTURE, {"samples": 1000, "timebase": 8, "trigger_channel": "none",
                                         "trigger_mv": 0, "trigger_direction": "rising"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_fills_the_operator_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        awg = client.invoke(AWG, {"frequency_hz": 1000, "amplitude_v": 1, "wave": "sine"}, **self.ids)
        self.assertEqual(awg["status"], "completed", awg)
        self.assertEqual(awg["output"]["frequency_hz"], 1000.0)
        capture = client.invoke(CAPTURE, {"samples": 1000, "timebase": 8, "trigger_channel": "none",
                                          "trigger_mv": 0, "trigger_direction": "rising"}, **self.ids)
        self.assertEqual(capture["status"], "completed", capture)
        self.assertEqual(capture["output"]["samples"], 1000)
        self.assertEqual(len(capture["output"]["measurements"]), 2)      # channels A and B start enabled
        self.assertEqual(capture["output"]["measurements"][0]["channel"], "A")
        refused = client.invoke(CAPTURE, {"samples": 50, "timebase": 8, "trigger_channel": "none",
                                          "trigger_mv": 0, "trigger_direction": "rising"}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)


class Safety(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_estop_turns_the_awg_off_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        started = client.invoke(AWG, {"frequency_hz": 1000, "amplitude_v": 1, "wave": "sine"}, **self.ids)
        self.assertEqual(started["status"], "completed", started)
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        refused = client.invoke(AWG, {"frequency_hz": 1000, "amplitude_v": 1, "wave": "sine"}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)          # a safe-state action stays available


if __name__ == "__main__":
    unittest.main()
