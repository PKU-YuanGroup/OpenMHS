"""Acceptance run of the RIGOL oscilloscope package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The fake's starting values are test data, not device facts.
"""

import unittest
import importlib.util
import threading
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TransportCases(unittest.TestCase):
    def test_stop_write_waits_for_the_current_query_response(self) -> None:
        # Import package adapter definitions only; connect() and all upstream imports stay uncalled.
        spec = importlib.util.spec_from_file_location("rigol_native_adapter_test", HERE / "native.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        entered, release, attempted, written = (threading.Event() for _ in range(4))
        calls = []

        class Peer:
            def query(self, command, timeout_s):
                calls.append(command)
                entered.set()
                if not release.wait(2.0):
                    raise RuntimeError("test did not release the query")
                calls.append("reply")
                return "TD"

            def write(self, command):
                calls.append(command)
                written.set()

        transport = module._SerializedTransport(Peer())
        reader = threading.Thread(target=lambda: transport.query(":TRIGger:STATus?", 1.0))

        def request_stop():
            attempted.set()
            transport.write(":STOP")

        writer = threading.Thread(target=request_stop)
        reader.start()
        try:
            self.assertTrue(entered.wait(1.0))
            writer.start()
            self.assertTrue(attempted.wait(1.0))
            self.assertFalse(written.wait(0.05))
        finally:
            release.set()
            reader.join(2.0)
            if writer.ident is not None:
                writer.join(2.0)
        self.assertEqual(calls, [":TRIGger:STATus?", "reply", ":STOP"])


class State(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_reaches_the_fake_and_is_read_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel1_display": False, "channel1_coupling": "AC"})
        state = driver.read("main", ["channel1_display", "channel1_coupling"])
        self.assertEqual(state, {"channel1_display": False, "channel1_coupling": "AC"})

    def test_the_identity_reads_the_fake_idn(self) -> None:
        driver = self.driver()
        self.assertIn("RIGOL", driver.read("main", ["identity"])["identity"])

    def test_the_estop_stops_the_acquisition(self) -> None:
        driver = self.driver()
        driver.native.run()
        self.assertEqual(driver.read("main", ["trigger_status"])["trigger_status"], "TD")
        driver.estop("test")
        self.assertEqual(driver.read("main", ["trigger_status"])["trigger_status"], "STOP")

    def test_ignored_stop_fails_and_keeps_the_latch(self) -> None:
        driver = self.driver()
        driver.native.run()
        driver.native.stop = lambda: None  # placeholder: command accepted, acquisition remains running
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        stopped = client.estop("ignored stop", **ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        refused = client.invoke("x-cap.zinntikumugai.run.v1", {}, **ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)

    def test_close_releases_the_session_transport(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        driver = self.driver()
        close = Mock()
        driver.native.session = SimpleNamespace(transport=SimpleNamespace(close=close))
        driver.close()
        close.assert_called_once()


class Actions(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_the_measurement_action_returns_a_scalar(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.zinntikumugai.measure.v1", {"item": "vpp"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["value"], 2.5)

    def test_the_trigger_action_applies_the_settings(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.zinntikumugai.configure_trigger.v1",
                                {"source": "EXT", "slope": "falling", "sweep_mode": "normal"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["source"], "EXT")
        self.assertEqual(receipt["output"]["slope"], "falling")
        self.assertEqual(receipt["output"]["sweep_mode"], "normal")

    def test_run_reports_the_trigger_status(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.zinntikumugai.run.v1", {},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["trigger_status"], "TD")

    def test_trigger_action_selects_edge_from_another_trigger_mode(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.configure_trigger(type="pulse")
        result = driver.configure_trigger(source="CH1")
        self.assertEqual(result["type"], "edge")


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

    def test_an_unknown_coupling_is_refused(self) -> None:
        client, device_id, session = self.serve()
        self.assertEqual(self.configure(client, device_id, session, channel1_coupling="BOGUS"), ENVELOPE)


if __name__ == "__main__":
    unittest.main()
