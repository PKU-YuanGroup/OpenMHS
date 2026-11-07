"""Acceptance run of the TwinCAT NC axis telemetry driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CAPABILITY = "cap.sensing.read.v1"
CHANNELS = (
    "act_acc",
    "act_pos",
    "act_pos_modulo",
    "act_torque",
    "act_velo",
    "axis_state",
    "cmd_no",
    "control_d_word",
    "couple_state",
    "ctrl_output",
    "drive_output",
)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NcAxisTelemetryCases(unittest.TestCase):
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

    def test_every_telemetry_channel_is_a_fresh_signal_read(self) -> None:
        client, fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), sorted(CHANNELS))
        for name in CHANNELS:
            signal = getattr(fake, name)
            self.assertEqual(state[name], signal._value, name)  # placeholder values in fake.py
            self.assertGreaterEqual(signal._gets, 1, name)

    def test_the_capability_returns_every_channel(self) -> None:
        client, _fake = self.serve()
        receipt = client.invoke(CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        values = receipt["output"]["values"]
        self.assertEqual(sorted(values), sorted(CHANNELS))
        self.assertEqual(values["act_pos"], 12.5)  # placeholder

    def test_the_capability_reads_only_the_selected_channels(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        result = driver.read_channels(["act_pos"])
        self.assertEqual(result, {"values": {"act_pos": 12.5}})  # placeholder
        self.assertEqual(fake.act_pos._gets, 1)
        for name in CHANNELS:
            if name != "act_pos":
                self.assertEqual(getattr(fake, name)._gets, 0, name)

    def test_a_name_outside_the_channels_contributes_no_value(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        self.assertEqual(driver.read_channels(["not_a_channel"]), {"values": {}})
        for name in CHANNELS:
            self.assertEqual(getattr(fake, name)._gets, 0, name)

    def test_the_class_example_completes_without_inventing_a_channel(self) -> None:
        # cap.sensing.read.v1 carries the example fields ["temperature"]. This axis has no temperature channel, so
        # the generic selector contributes no value; the call completes with an empty values object.
        client, _fake = self.serve()
        receipt = client.invoke(CAPABILITY, {"fields": ["temperature"]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"], {})

    def test_the_driver_offers_no_write(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"act_pos": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN")

    def test_a_failed_ads_read_returns_no_value(self) -> None:
        client, fake = self.serve()

        def disconnected():
            raise RuntimeError("placeholder: the ADS symbol could not be read")

        fake.act_pos.get = disconnected
        receipt = client.invoke(CAPABILITY, {"fields": ["act_pos"]}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt.get("output"))

    def test_a_native_timeout_returns_no_value(self) -> None:
        # A direct Driver method is not a bridge command: an exception other than DriverFailed/Cancelled/Busy/
        # OutcomeUnknown is reported as MHS.ADAPTER.SHIM_FAILED, and the receipt carries no output.
        client, fake = self.serve()

        def silent():
            raise TimeoutError("placeholder: the ADS symbol did not answer")

        fake.act_velo.get = silent
        receipt = client.invoke(CAPABILITY, {"fields": ["act_velo"]}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")
        self.assertIsNone(receipt.get("output"))

    def test_the_estop_keeps_reads_available(self) -> None:
        # This R0 integration has no native stop and no physical effect. The e-stop still completes as the
        # endpoint's software latch, and reads remain available because they actuate nothing.
        client, _fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(self.state(client)["act_pos"], 12.5)  # placeholder


if __name__ == "__main__":
    unittest.main()
