"""Acceptance run of the Alia package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AliaCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_initial_state_is_the_fake_placeholder(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["ref_waveform"], "Square")
        self.assertEqual(state["ref_freq"], 250.0)
        self.assertEqual(state["ref_offset"], 1.5)
        self.assertEqual(state["ref_amplitude"], 0.8)
        self.assertAlmostEqual(state["ref_amplitude_rms"], 0.8, places=6)
        self.assertEqual((state["ref_clipping_high"], state["ref_clipping_low"]), (False, False))
        self.assertEqual((state["adc_autocal_valid"], state["adc_autocal_gaincorr"],
                          state["adc_autocal_offsetcorr"]), (True, 0, 0))
        self.assertEqual((state["sampling_rate"], state["block_size"]), (25000.0, 100))
        self.assertFalse(state["running"])

    def test_the_frequency_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, ref_freq=100)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["ref_freq"], 250.0)          # the fake placeholder, untouched

    def test_the_example_overlay_supplies_the_frequency_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, ref_freq=100)["status"], "completed")
        self.assertEqual(self.state(client)["ref_freq"], 100.0)          # the fake quantizes to Fs/N_LUT
        for value in (24, 1251):
            refused = self.configure(client, ref_freq=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["ref_freq"], 100.0)

    def test_the_voltage_bounds_and_the_clipping_flags(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, ref_offset=1.0, ref_amplitude=1.0)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["ref_offset"], state["ref_amplitude"]), (1.0, 1.0))
        self.assertEqual((state["ref_clipping_high"], state["ref_clipping_low"]), (False, False))
        self.assertEqual(self.configure(client, ref_offset=0.5)["status"], "completed")
        self.assertTrue(self.state(client)["ref_clipping_low"])
        self.assertEqual(self.configure(client, ref_offset=3.0)["status"], "completed")
        self.assertTrue(self.state(client)["ref_clipping_high"])
        for patch in ({"ref_offset": -0.1}, {"ref_offset": 3.4}, {"ref_amplitude": -0.1},
                      {"ref_amplitude": 3.4}, {"ref_amplitude_rms": 3.4}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_waveform_write_and_the_acquisition_actions(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, ref_waveform="Sine")["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["ref_waveform"], "Sine")
        self.assertTrue(math.isclose(state["ref_amplitude"], 0.8 * math.sqrt(2.0), rel_tol=1e-9))
        refused = self.configure(client, ref_waveform="Unknown")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        started = client.invoke("x-cap.dennis-van-gils.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"running": True})
        self.assertTrue(self.state(client)["running"])
        stopped = client.invoke("x-cap.dennis-van-gils.stop_acquisition.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"running": False})
        self.assertFalse(self.state(client)["running"])

    def test_the_estop_stops_the_acquisition_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.dennis-van-gils.start_acquisition.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        refused = client.invoke("x-cap.dennis-van-gils.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
