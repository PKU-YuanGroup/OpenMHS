"""Acceptance run of the mrw-code morphology-stage package: the gate plus repository cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MorphologyStageCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_fake_starts_from_a_ready_bench_state(self) -> None:
        client = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state, {"step": 0.0, "port_open": True, "calibration_flag": True})

    def test_calibration_opens_the_port_and_sets_the_upstream_writes(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call("x-cap.mrw-code.calibrate.v1", {}), {"calibration_flag": True})
        self.assertTrue(driver.native.portConnectStatus)
        self.assertTrue(driver.native.systemCalibrate)
        self.assertEqual(driver.native.arduino.written[:2], [b"$X\n", b"G10 P0 L20 X0 Y0 Z0\n"])

    def test_a_relative_move_uses_the_upstream_method_and_serial_bytes(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.call("x-cap.mrw-code.calibrate.v1", {})
        receipt = driver.call("x-cap.mrw-code.move_relative.v1",
                              {"axis": "x", "direction": "negative", "step": 12.5})
        self.assertEqual(receipt, {"commanded": True, "axis": "x", "direction": "negative", "step": 12.5})
        self.assertEqual(driver.native.last_move, ("X", -12.5))
        # Fake-only formatting: the upstream QDoubleSpinBox.textFromValue may round the divided value.
        self.assertEqual(driver.native.last_command, "$J=G21G91X-0.125F50\n")

    def test_home_requires_the_upstream_calibration_flag(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.systemCalibrate = False
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.mrw-code.home.v1", {})
        self.assertEqual(caught.exception.code, PRECONDITION)
        driver.native.systemCalibrate = True
        self.assertEqual(driver.call("x-cap.mrw-code.home.v1", {}), {"commanded": True})

    def test_the_connect_action_does_not_toggle_a_connected_port(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.mrw-code.connect.v1", {}, **self.ids)["output"],
                         {"port_open": True})
        self.assertEqual(client.invoke("x-cap.mrw-code.connect.v1", {}, **self.ids)["output"],
                         {"port_open": True})
        self.assertTrue(client.read("main", **self.ids)["state"]["port_open"])

    def test_the_step_envelope_is_enforced_before_the_native_call(self) -> None:
        client = self.serve()
        for value in (-0.1, 100.1):
            refused = client.invoke("x-cap.mrw-code.move_relative.v1",
                                    {"axis": "z", "direction": "positive", "step": value}, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
            refused = client.invoke("cap.device.configure.v1", {"step": value}, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(client.read("main", **self.ids)["state"]["step"], 0.0)

    def test_in_range_step_write_is_visible(self) -> None:
        client = self.serve()
        written = client.invoke("cap.device.configure.v1", {"step": 37.5}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(client.read("main", **self.ids)["state"]["step"], 37.5)

    def test_the_exit_action_closes_the_command_channel(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call("x-cap.mrw-code.close_command_channel.v1", {}),
                         {"command_channel_closed": True})
        self.assertFalse(driver.native.arduino.isOpen())
        # quitSystem leaves the upstream UI flag set although the port is closed.
        self.assertTrue(driver.native.portConnectStatus)
        # Reconnecting goes through the upstream toggle, which clears the calibration flag first.
        self.assertEqual(driver.call("x-cap.mrw-code.connect.v1", {}), {"port_open": True})
        self.assertFalse(driver.native.systemCalibrate)
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.mrw-code.home.v1", {})
        self.assertEqual(caught.exception.code, PRECONDITION)
        self.assertEqual(driver.call("x-cap.mrw-code.calibrate.v1", {}), {"calibration_flag": True})
        self.assertTrue(driver.native.arduino.isOpen())

    def test_the_estop_runs_the_exit_path_but_does_not_claim_a_safe_state(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        written_before = list(driver.native.arduino.written)
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, UNREACHED)
        self.assertFalse(driver.native.arduino.isOpen())
        self.assertTrue(driver.native.window_closed)
        # The Exit path writes no stop command to the controller.
        self.assertEqual(driver.native.arduino.written, written_before)

    def test_the_estop_latches_and_reports_the_safe_state_unreached(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        refused = client.invoke("x-cap.mrw-code.move_relative.v1",
                                {"axis": "x", "direction": "positive", "step": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")


if __name__ == "__main__":
    unittest.main()
