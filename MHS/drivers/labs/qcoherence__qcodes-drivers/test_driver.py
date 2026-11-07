"""Acceptance run of the ADwin Gold II driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CONFIGURE = "cap.device.configure.v1"
SET_OUTPUTS = "x-cap.qcoherence.set_output_voltages.v1"
READ_FIFO = "x-cap.qcoherence.read_input_fifo.v1"
ZERO_OUTPUTS = "x-cap.qcoherence.zero_outputs.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ADwinGold2Cases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_reads_follow_the_getters(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(state["adwin_mode"], 0)        # placeholder
        self.assertEqual(state["ramp_size"], 1000)      # placeholder
        self.assertEqual(state["subsampling"], 1)       # placeholder
        self.assertEqual(state["output_mask"], 1)       # placeholder
        self.assertEqual(state["input_mask"], 1)        # placeholder

    def test_writes_change_the_matching_read(self) -> None:
        client, _fake = self.serve()
        applied = client.invoke(CONFIGURE, {"ramp_size": 500}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        state = self.state(client)
        self.assertEqual(state["ramp_size"], 500)

    def test_out_of_envelope_write_is_refused_without_a_native_call(self) -> None:
        client, fake = self.serve()
        refused = client.invoke(CONFIGURE, {"output_mask": 0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(fake.get_output_mask(), 1)     # placeholder, unchanged

    def test_set_output_voltages_sends_the_native_fifo(self) -> None:
        client, fake = self.serve()
        targets = [0.0, 1.0, -1.0, 2.0, -2.0, 0.5, -0.5, 0.0]   # placeholder targets
        receipt = client.invoke(SET_OUTPUTS, {"targets": targets}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["targets"], targets)
        self.assertEqual(receipt["output"]["output_mask"], 255)
        self.assertTrue(receipt["output"]["sent"])
        self.assertEqual(len(fake._sent), 1)
        self.assertEqual(fake.get_output_mask(), 255)

    def test_set_output_voltages_outside_the_voltage_domain_is_refused(self) -> None:
        client, fake = self.serve()
        refused = client.invoke(SET_OUTPUTS, {"targets": [0.0] * 7 + [11.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(fake._sent, [])

    def test_read_input_fifo_converts_the_adc_codes(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(READ_FIFO, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        expected = [fake.binary_to_volt(value) for value in fake.read_inputs()]
        self.assertEqual(receipt["output"]["voltages"], expected)
        self.assertEqual(receipt["output"]["count"], len(expected))

    def test_the_estop_sends_go_to_zero_but_does_not_claim_a_safe_state(self) -> None:
        # Model review: go_to_zero writes an unacknowledged FIFO command whose consumer is outside the clone, so the
        # e-stop sends it and still reports SAFE_STATE_UNREACHED with the latch held.
        client, fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        self.assertIs(stopped["output"]["safe_state_achieved"], False, stopped)
        self.assertEqual(stopped["output"]["safe_state"]["achieved_by"], [], stopped)
        self.assertGreaterEqual(fake._zeroed, 1)
        self.assertEqual(fake.get_output_mask(), 1)     # placeholder, restored after zeroing
        refused = client.invoke(CONFIGURE, {"ramp_size": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_zero_outputs_is_an_ordinary_command_not_a_safe_state_action(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(ZERO_OUTPUTS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["zeroed"])
        self.assertEqual(fake._zeroed, 1)
        self.assertEqual(fake._last_targets, [fake.volt_to_binary(0.0)] * 8)

    def test_subsampling_waits_for_the_operator(self) -> None:
        client, fake = self.serve()
        refused = client.invoke(CONFIGURE, {"subsampling": 2}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", refused)
        self.assertEqual(fake.get_subsampling(), 1)     # placeholder, unchanged

    def test_a_failed_native_set_is_a_failed_receipt(self) -> None:
        client, fake = self.serve()

        def rejected(value):
            raise RuntimeError("placeholder: the ADwin rejected the setting")

        fake.set_ramp_size = rejected
        receipt = client.invoke(CONFIGURE, {"ramp_size": 2}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)


if __name__ == "__main__":
    unittest.main()
