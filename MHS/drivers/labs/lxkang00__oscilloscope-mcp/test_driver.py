"""Acceptance gate plus repository-specific cases for the oscilloscope-mcp package.

Every case runs the package's local SCPI emulator through the stock loader and server.
Nothing imports the upstream server, an MCP library or a socket.
"""
import importlib
import json
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import build_server, close_server
from mhs.driver.loader import import_driver_module
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
MODULE = import_driver_module(HERE)
OVERLAY = json.loads((HERE / "site-limits.example.json").read_text())


class DriverGate(unittest.TestCase):
    def test_gate(self):
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StockServerCases(unittest.TestCase):
    def open(self, overlay=True):
        driver = load_driver(HERE, backend="fake")
        peer = driver.native
        server = build_server(driver, site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        self.addCleanup(client.close)
        device = next(iter(server.devices))
        session = client.open_session([device], mode=server.devices[device].mode)["session_id"]
        return peer, client, device, session

    def invoke(self, client, device, capability, arguments=None):
        receipt = client.invoke(capability, arguments or {}, device_id=device)
        if receipt["status"] in ("accepted", "running"):
            receipt = client.wait(receipt["operation_id"], timeout=5)
        return receipt

    def test_channel_configuration_uses_the_pinned_scpi_commands(self):
        peer, client, device, _session = self.open()
        receipt = self.invoke(client, device, MODULE.xcap("configure_channel"), {
            "channel": 1, "display": True, "scale": 0.5, "coupling": "D1M", "label": "CH A"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn(":CHANnel1:SWITch ON", peer.calls)
        self.assertIn(":CHANnel1:SCALe 0.5", peer.calls)
        self.assertIn(":CHANnel1:COUPling D1M", peer.calls)
        self.assertIn(':CHANnel1:LABel:TEXT "CH A"', peer.calls)
        receipt = self.invoke(client, device, MODULE.xcap("get_channel"), {"channel": 1})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn("Scale (V/div): 0.5", receipt["output"]["reply"])

    def test_measure_keeps_the_text_reply_and_the_parsed_value(self):
        peer, client, device, _session = self.open()
        receipt = self.invoke(client, device, MODULE.xcap("measure"), {"measurement": "VPP", "source1": "C1"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["measurement"], "VPP")
        self.assertEqual(receipt["output"]["source"], "C1")
        self.assertAlmostEqual(receipt["output"]["value"], 1.234)
        self.assertEqual(receipt["output"]["reply"], "VPP(C1) = 1.234000E+00")
        self.assertIn(":MEASure:VPP? C1?", peer.calls)

    def test_waveform_preamble_is_parsed_without_the_sample_array(self):
        _peer, client, device, _session = self.open()
        receipt = self.invoke(client, device, MODULE.xcap("get_waveform_preamble"), {"source": "C1"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["parsed"])
        self.assertEqual(receipt["output"]["points"], 1000)
        self.assertEqual(receipt["output"]["x_increment_s"], 1e-06)

    def test_operator_required_bounds_refuse_before_any_native_call(self):
        peer, client, device, _session = self.open(overlay=False)
        receipt = self.invoke(client, device, MODULE.xcap("configure_channel"),
                              {"channel": 1, "scale": 0.5})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual([call for call in peer.calls if call.startswith(":CHANnel")], [])
        peer, client, device, _session = self.open(overlay=True)
        receipt = self.invoke(client, device, MODULE.xcap("configure_channel"),
                              {"channel": 1, "scale": 0.5})
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_channel_index_is_enforced_by_the_pinned_schema_bound(self):
        peer, client, device, _session = self.open()
        receipt = self.invoke(client, device, MODULE.xcap("get_channel"), {"channel": 5})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual([call for call in peer.calls if call.startswith(":CHANnel")], [])

    def test_estop_requires_a_fresh_stopped_status(self):
        peer, client, device, session = self.open()
        self.invoke(client, device, MODULE.xcap("acquisition_control"), {"action": "run"})
        stopped = client.estop("acceptance test", device_id=device, session_id=session)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(peer._trigger_status, "STOP")  # placeholder test state, not a device fact
        self.assertIn(":STOP", peer.calls)
        self.assertIn(":TRIGger:STATus?", peer.calls)

        peer, client, device, session = self.open()
        self.invoke(client, device, MODULE.xcap("acquisition_control"), {"action": "run"})
        peer.stuck = True
        stopped = client.estop("acceptance test", device_id=device, session_id=session)
        self.assertNotEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        self.assertFalse(stopped["output"]["safe_state_achieved"], stopped)


class StatusReadCases(unittest.TestCase):
    def test_a_failed_status_query_is_not_served_as_n_a(self):
        # The pinned safe_query returns "N/A" on any error (server.py:165-170); the resource reads use query(), so a
        # transport failure fails the read instead of publishing "N/A" as the trigger or acquisition state.
        driver = load_driver(HERE, backend="fake")
        self.assertEqual(driver.trigger_status(), "STOP")  # placeholder test state, not a device fact
        driver.native.disconnect()
        with self.assertRaises(RuntimeError):
            driver.trigger_status()
        with self.assertRaises(RuntimeError):
            driver.acquisition_state()


class NativeRefusal(unittest.TestCase):
    def test_native_factory_refuses_before_import_or_socket(self):
        native = importlib.import_module(".native", MODULE.__package__)
        with self.assertRaisesRegex(RuntimeError, "native admission blocked"):
            native.connect()


if __name__ == "__main__":
    unittest.main()
