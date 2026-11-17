"""Acceptance run of the JDS6600 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PHASE = "x-cap.lpender3672.set_phase.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class JDS6600Cases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        self.native = driver.native
        server = build_server(driver)
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

    def test_both_channels_read_as_the_device_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["identification"], "JDS6600-15 SN:00000000")
        for channel in (1, 2):
            self.assertEqual(state[f"ch{channel}_waveform"], "SINE")
            self.assertEqual(state[f"ch{channel}_frequency_hz"], 1000.0)
            self.assertEqual(state[f"ch{channel}_amplitude_vpp"], 1.0)
            self.assertEqual(state[f"ch{channel}_duty_pct"], 50.0)
            self.assertEqual(state[f"ch{channel}_enabled"], False)

    def test_a_write_reaches_the_device_and_reads_back(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, ch1_frequency_hz=1234.567)["status"], "completed")
        self.assertAlmostEqual(self.state(client)["ch1_frequency_hz"], 1234.57, places=2)  # centi-Hz wire code
        self.assertEqual(self.state(client)["ch2_frequency_hz"], 1000.0)
        self.assertEqual(self.configure(client, ch1_enabled=True)["status"], "completed")
        self.assertTrue(self.state(client)["ch1_enabled"])
        self.assertFalse(self.state(client)["ch2_enabled"])

    def test_out_of_envelope_values_never_reach_the_native(self) -> None:
        client = self.serve()
        for patch in ({"ch1_frequency_hz": 15e6 + 1},
                      {"ch2_amplitude_vpp": -0.5},
                      {"ch1_offset_v": 10.0},
                      {"ch2_duty_pct": 100.1},
                      {"ch1_waveform": "SAW"}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertIn(refused["error"]["mhs_code"],
                          (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID", "MHS.RESOURCE.FIELD_INVALID"), patch)
        state = self.state(client)
        self.assertEqual(state["ch1_frequency_hz"], 1000.0)
        self.assertEqual(state["ch1_waveform"], "SINE")

    def test_the_phase_action_rounds_to_tenths_of_a_degree(self) -> None:
        client = self.serve()
        done = client.invoke(PHASE, {"degrees": 90.04}, **self.ids)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["output"], {"phase_deg": 90.0})
        refused = client.invoke(PHASE, {"degrees": 361}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_disables_both_outputs_and_latches(self) -> None:
        client = self.serve()
        self.configure(client, ch1_enabled=True, ch2_enabled=True)
        self.assertTrue(self.state(client)["ch1_enabled"])
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertFalse(state["ch1_enabled"])
        self.assertFalse(state["ch2_enabled"])
        refused = self.configure(client, ch2_enabled=True)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_frequency_that_rounds_to_zero_fails_before_the_native_write(self) -> None:
        client = self.serve()
        for frequency in (0.0, 0.001):
            with patch.object(self.native, "configure_channel", wraps=self.native.configure_channel) as write:
                receipt = self.configure(client, ch1_frequency_hz=frequency)
            self.assertEqual(receipt["status"], "failed", receipt)
            write.assert_not_called()
        self.assertEqual(self.state(client)["ch1_frequency_hz"], 1000.0)

    def test_builtin_waveform_selection_clears_a_preexisting_arbitrary_slot(self) -> None:
        client = self.serve()
        self.native._channels[1].arb_slot = 3  # placeholder: an operator-selected slot
        self.assertEqual(self.state(client)["ch1_arbitrary_slot"], 3)
        with patch.object(self.native, "configure_channel", wraps=self.native.configure_channel) as write:
            receipt = self.configure(client, ch1_waveform="SQUARE")
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIsNone(write.call_args.args[0].arb_slot)
        self.assertIsNone(self.native.read_channel(1).arb_slot)
        self.assertEqual(self.native.read_channel(1).waveform, "SQUARE")

    def test_the_stop_attempts_channel_two_when_channel_one_raises(self) -> None:
        client = self.serve()
        self.configure(client, ch1_enabled=True, ch2_enabled=True)
        original = self.native.enable_output

        def fail_first(channel, on):
            if channel == 1:
                raise RuntimeError("placeholder: channel-one exchange failed")
            return original(channel, on)

        with patch.object(self.native, "enable_output", side_effect=fail_first):
            receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertFalse(self.native.output_enabled(2))

    def test_an_ignored_stop_fails_and_keeps_the_latch(self) -> None:
        client = self.serve()
        self.configure(client, ch1_enabled=True, ch2_enabled=True)
        with patch.object(self.native, "enable_output", return_value=None):
            receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = self.configure(client, ch1_enabled=True)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_missing_stop_readback_does_not_confirm_disabled_outputs(self) -> None:
        client = self.serve()
        with patch.object(self.native, "output_enabled", return_value=None):
            receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")


if __name__ == "__main__":
    unittest.main()
