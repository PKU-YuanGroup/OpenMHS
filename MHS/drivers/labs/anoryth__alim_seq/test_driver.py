"""Acceptance run of the HMP4040 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SET_OUTPUT = "x-cap.anoryth.set_output.v1"
ALL_OUTPUTS_OFF = "x-cap.anoryth.all_outputs_off.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HMP4040Cases(unittest.TestCase):
    def serve(self, site_limits=HERE / "site-limits.example.json"):
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

    def set_output(self, client, channel, enabled):
        return client.invoke(SET_OUTPUT, {"channel": channel, "enabled": enabled}, **self.ids)

    def test_the_four_channels_start_at_zero_and_identify_the_native(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertTrue(state["identity"])
        for channel in (1, 2, 3, 4):
            self.assertEqual(state[f"voltage_ch{channel}"], 0.0)
            self.assertEqual(state[f"current_ch{channel}"], 0.0)

    def test_setpoints_require_an_operator_envelope(self):
        client = self.serve(site_limits=None)
        receipt = self.configure(client, voltage_setpoint_ch1=1.0)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_example_operator_setpoints_are_bounded(self) -> None:
        client = self.serve()
        for patch in ({"voltage_setpoint_ch1": 32.01}, {"voltage_setpoint_ch1": -0.01},
                      {"current_setpoint_ch4": 10.01}, {"current_setpoint_ch4": -0.01}):
            receipt = self.configure(client, **patch)
            self.assertEqual(receipt["status"], "rejected", patch)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, patch)
        for patch in ({"voltage_setpoint_ch1": 32.0}, {"voltage_setpoint_ch1": 0.0},
                      {"current_setpoint_ch4": 10.0}, {"current_setpoint_ch4": 0.0}):
            self.assertEqual(self.configure(client, **patch)["status"], "completed", patch)

    def test_the_channel_action_is_bounded_to_the_four_channels(self) -> None:
        client = self.serve()
        refused = self.set_output(client, 5, True)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_set_output_action_switches_one_channel_and_reports_the_measurement(self) -> None:
        client = self.serve()
        self.configure(client, voltage_setpoint_ch2=5.0, current_setpoint_ch2=0.5)
        receipt = self.set_output(client, 2, True)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"channel": 2, "enabled": True, "voltage": 5.0})
        state = self.state(client)
        self.assertEqual((state["voltage_ch2"], state["current_ch2"]), (5.0, 0.5))
        receipt = self.set_output(client, 2, False)
        self.assertEqual(receipt["output"], {"channel": 2, "enabled": False, "voltage": 0.0})
        state = self.state(client)
        self.assertEqual((state["voltage_ch2"], state["current_ch2"]), (0.0, 0.0))

    def test_fake_setpoints_follow_the_upstream_four_decimal_commands(self):
        client = self.serve()
        self.configure(client, voltage_setpoint_ch1=1.234567, current_setpoint_ch1=0.345678)
        self.assertEqual(self.set_output(client, 1, True)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["voltage_ch1"], state["current_ch1"]), (1.2346, 0.3457))

    def test_the_off_request_switches_the_fake_channels_off(self) -> None:
        client = self.serve()
        self.configure(client, voltage_setpoint_ch1=3.3, voltage_setpoint_ch3=1.2)
        self.assertEqual(self.set_output(client, 1, True)["status"], "completed")
        self.assertEqual(self.set_output(client, 3, True)["status"], "completed")
        receipt = client.invoke(ALL_OUTPUTS_OFF, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["off_requested"], True)
        self.assertEqual(receipt["output"]["voltages"], [0.0, 0.0, 0.0, 0.0])
        state = self.state(client)
        self.assertEqual((state["voltage_ch1"], state["voltage_ch3"]), (0.0, 0.0))

    def test_the_estop_attempt_does_not_certify_the_stop(self) -> None:
        client = self.serve()
        self.configure(client, voltage_setpoint_ch1=4.0)
        self.assertEqual(self.set_output(client, 1, True)["status"], "completed")
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(estop["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(self.state(client)["voltage_ch1"], 0.0)
        refused = self.set_output(client, 1, True)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
