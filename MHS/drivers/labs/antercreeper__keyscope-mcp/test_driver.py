"""Acceptance run of the keyscope-mcp package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The fake's starting values are test data, not device facts.
"""

import importlib.util
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


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
        driver.write("main", {"channel1_display": False, "channel1_coupling": "AC",
                              "channel1_invert": True, "acquire_type": "PEAK"})
        state = driver.read("main", ["channel1_display", "channel1_coupling", "channel1_invert",
                                     "acquire_type"])
        self.assertEqual(state, {"channel1_display": False, "channel1_coupling": "AC",
                                 "channel1_invert": True, "acquire_type": "PEAK"})

    def test_the_identity_reads_the_fake_idn(self) -> None:
        driver = self.driver()
        self.assertIn("EDUX1052G", driver.read("main", ["identity"])["identity"])

    def test_the_estop_stops_the_fake(self) -> None:
        driver = self.driver()
        driver.native.run()
        self.assertTrue(driver.native._running)
        driver.estop("test")
        self.assertFalse(driver.native._running)


class Actions(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, session

    def test_the_measurement_action_returns_a_scalar(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.antercreeper.measure.v1", {"channel": 1, "measurement": "vpp"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["value"], 2.5)

    def test_the_run_single_and_stop_actions_report_completion(self) -> None:
        client, device_id, session = self.serve()
        for capability_id in ("x-cap.antercreeper.run.v1", "x-cap.antercreeper.single.v1",
                              "x-cap.antercreeper.stop_acquisition.v1"):
            receipt = client.invoke(capability_id, {}, device_id=device_id, session_id=session)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertTrue(receipt["output"]["operation_complete"])


class NativeFailures(unittest.TestCase):
    def serve(self, native):
        server = load(HERE, backend="fake", native=native)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session_id}

    def native(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver.native

    def test_false_opc_fails_each_completion_action(self):
        for name in ("run", "single", "reset_to_defaults", "stop_acquisition"):
            with self.subTest(action=name):
                native = self.native()
                native.opc = lambda: False
                client, ids = self.serve(native)
                receipt = client.invoke(f"x-cap.antercreeper.{name}.v1", {}, **ids)
                self.assertEqual(receipt["status"], "failed", receipt)

    def test_false_opc_keeps_the_estop_failed_and_latched(self):
        native = self.native()
        native.run()
        native.opc = lambda: False
        client, ids = self.serve(native)
        receipt = client.estop("unacknowledged stop", **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = client.invoke("x-cap.antercreeper.run.v1", {}, **ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_device_error_is_not_an_acknowledged_stop(self):
        native = self.native()
        native.get_error = lambda: (-200, "placeholder command rejection")
        client, ids = self.serve(native)
        receipt = client.estop("rejected stop", **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_reset_does_not_restart_acquisition(self):
        native = self.native()
        native.run()
        client, ids = self.serve(native)
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        self.assertEqual(client.reset(**ids)["status"], "completed")
        self.assertFalse(native._running)


class NativeLifecycle(unittest.TestCase):
    def lifecycle(self):
        # Load only our native.py. Its upstream import is inside connect(), which is never called here.
        spec = importlib.util.spec_from_file_location("keyscope_close_case", HERE / "native.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.StopPreservingClose()

    def test_the_hardware_lifecycle_closes_without_any_run_command(self):
        class VisaSession:
            closed = 0

            def write(self, command):
                raise AssertionError(f"close must not send a command: {command}")

            def close(self):
                self.closed += 1

        session = VisaSession()
        lifecycle = self.lifecycle()
        lifecycle._inst = session
        lifecycle.close()
        lifecycle.close()
        self.assertEqual(session.closed, 1)
        self.assertIsNone(lifecycle._inst)

    def test_close_failure_is_not_suppressed(self):
        class VisaSession:
            def close(self):
                raise RuntimeError("placeholder VISA close failure")

        lifecycle = self.lifecycle()
        lifecycle._inst = VisaSession()
        with self.assertRaisesRegex(RuntimeError, "VISA close failure"):
            lifecycle.close()


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

    def test_a_measurement_channel_outside_the_dsl_range_is_refused(self) -> None:
        client, device_id, session = self.serve()
        receipt = client.invoke("x-cap.antercreeper.measure.v1", {"channel": 3, "measurement": "vpp"},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)


if __name__ == "__main__":
    unittest.main()
