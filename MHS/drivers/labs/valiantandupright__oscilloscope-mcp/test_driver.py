"""Acceptance run of the oscilloscope package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The fake's starting values and waveform are test data, not device
facts.  No hardware backend was run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
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

    def test_a_write_reaches_the_fake_and_is_read_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel1_display": False, "channel1_coupling": "AC", "trigger_source": "CHANNEL2"})
        state = driver.read("main", ["channel1_display", "channel1_coupling", "trigger_source"])
        self.assertEqual(state, {"channel1_display": False, "channel1_coupling": "AC",
                                 "trigger_source": "CHANNEL2"})

    def test_the_identity_reads_the_fake_idn(self) -> None:
        driver = self.driver()
        self.assertIn("KEYSIGHT", driver.read("main", ["identity"])["identity"])

    def test_the_estop_latches_and_refuses_a_write(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        client.estop("test", device_id=device_id, session_id=session)
        refused = client.invoke("cap.device.configure.v1", {"channel1_display": True},
                                device_id=device_id, session_id=session)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


class Actions(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        self.native = driver.native
        server = build_server(driver, site_limits=site_limits or str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_the_measurement_action_returns_a_scalar(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.valiantandupright.measure.v1", {"channel": 1, "item": "vpp"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertAlmostEqual(receipt["output"]["value"], 2.0)

    def test_the_capture_action_returns_the_waveform_arrays(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.valiantandupright.capture.v1", {"channel": 1},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(len(output["time_s"]), 8)
        self.assertEqual(len(output["voltage_v"]), 8)
        self.assertAlmostEqual(output["stats"]["vpp"], 2.0)

    def test_the_channel_configuration_action_writes_and_reads_back(self) -> None:
        client, device_id, session = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.valiantandupright.configure_channel.v1",
                                {"channel": 2, "scale_v_per_div": 1.0, "coupling": "AC"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["channel"], 2)
        self.assertEqual(receipt["output"]["scale_v_per_div"], 1.0)
        self.assertEqual(receipt["output"]["coupling"], "AC")

    def test_instrument_errors_fail_the_capture_receipt(self) -> None:
        client, device_id, session = self.serve()
        result = self.native.capture(1)
        result["warnings"] = ['-222,"Data out of range"']  # placeholder instrument rejection
        self.native.capture = lambda channel: result
        receipt = client.invoke("x-cap.valiantandupright.capture.v1", {"channel": 1},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED", receipt)

    def test_missing_capture_fields_are_not_fabricated(self) -> None:
        client, device_id, session = self.serve()
        self.native.capture = lambda channel: {"warnings": [], "stats": {}}
        receipt = client.invoke("x-cap.valiantandupright.capture.v1", {"channel": 1},
                                device_id=device_id, session_id=session)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)

    def test_missing_measurement_is_not_replaced_with_a_null_value(self) -> None:
        client, device_id, session = self.serve()
        self.native.measure = lambda channel, names: {}
        receipt = client.invoke("x-cap.valiantandupright.measure.v1", {"channel": 1, "item": "vpp"},
                                device_id=device_id, session_id=session)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)

    def test_rejected_stop_keeps_the_latch(self) -> None:
        client, device_id, session = self.serve()
        self.native.errors = lambda: ['-113,"Undefined header"']  # placeholder rejection of STOP
        ids = {"device_id": device_id, "session_id": session}
        stopped = client.estop("rejected STOP", **ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        refused = client.invoke("x-cap.valiantandupright.run.v1", {}, **ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_instrument_rejection_fails_a_configuration_receipt(self) -> None:
        client, device_id, session = self.serve()
        self.native.errors = lambda: ['-222,"Data out of range"']  # placeholder failed setting
        receipt = client.invoke("cap.device.configure.v1", {"channel1_display": True},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def configure(self, client, device_id, session, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, device_id=device_id, session_id=session)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_an_operator_required_setting_is_refused_without_an_overlay(self) -> None:
        client, device_id, session = self.serve()
        self.assertEqual(self.configure(client, device_id, session, channel1_scale_v_per_div=0.5), UNSET)

    def test_the_example_overlay_supplies_the_operator_bound(self) -> None:
        client, device_id, session = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, device_id, session, channel1_scale_v_per_div=0.5), "completed")
        self.assertEqual(self.configure(client, device_id, session, channel1_scale_v_per_div=10.0), ENVELOPE)

    def test_an_unknown_coupling_and_an_unset_trigger_level_are_refused(self) -> None:
        client, device_id, session = self.serve()
        self.assertEqual(self.configure(client, device_id, session, channel1_coupling="BOGUS"), ENVELOPE)
        self.assertEqual(self.configure(client, device_id, session, trigger_level_v=1.0), UNSET)

    def test_channel_selection_requires_the_operator_envelope(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.valiantandupright.capture.v1", {"channel": 1},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET, receipt)


if __name__ == "__main__":
    unittest.main()
