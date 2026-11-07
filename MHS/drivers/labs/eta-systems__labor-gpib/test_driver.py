"""Acceptance run of the NGMO2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNKNOWN = "MHS.DEVICE.PRECONDITION_UNMET"
RST = "x-cap.eta-systems.scpi_rst.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NativeCalls(unittest.TestCase):
    """The decorated methods on the fake backend object (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_every_write_reaches_the_fake_and_is_read_back(self) -> None:
        driver = self.driver()
        driver.write("main", {
            "voltage_setpoint": 12.0,
            "current_limit": 1.5,
            "measurement_interval": 0.01,
            "averaging_samples": 4,
            "output_enabled": True,
            "sense_function": "curr",
            "current_range": "medium",
            "output_format": "double",
            "display_enabled": False,
        })
        state = driver.read("main")
        self.assertEqual(state["voltage_setpoint"], 12.0)
        self.assertEqual(state["current_limit"], 1.5)
        self.assertAlmostEqual(state["measurement_interval"], 0.01)
        self.assertEqual(state["averaging_samples"], 4)
        self.assertTrue(state["output_enabled"])
        self.assertEqual(state["sense_function"], "curr")
        self.assertEqual(state["current_range"], "medium")
        self.assertEqual(state["output_format"], "double")
        self.assertFalse(state["display_enabled"])

    def test_the_estop_turns_the_channel_a_output_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output_enabled": True})
        driver.estop("test")
        self.assertFalse(driver.read("main", ["output_enabled"])["output_enabled"])
        self.assertEqual(driver.native.channel_a.is_on(), "OFF")


class RuntimeLimits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session_id}

    @staticmethod
    def configure(client, ids, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_upstream_ranges_refuse_out_of_envelope_writes(self) -> None:
        client, ids = self.serve()
        for patch in ({"voltage_setpoint": -0.001}, {"voltage_setpoint": 15.001},
                      {"current_limit": -0.001}, {"current_limit": 5.001},
                      {"measurement_interval": 0.000001}, {"measurement_interval": 1.001},
                      {"averaging_samples": 0}, {"averaging_samples": 11}):
            self.assertEqual(self.configure(client, ids, **patch), ENVELOPE, patch)
        for patch in ({"voltage_setpoint": 0.0}, {"voltage_setpoint": 15.0},
                      {"current_limit": 0.0}, {"current_limit": 5.0},
                      {"measurement_interval": 0.00001}, {"measurement_interval": 1.0},
                      {"averaging_samples": 1}, {"averaging_samples": 10}):
            self.assertEqual(self.configure(client, ids, **patch), "completed", patch)

    def test_the_allowed_set_refuses_an_unknown_name(self) -> None:
        client, ids = self.serve()
        for patch in ({"sense_function": "voltage"}, {"current_range": "5a"},
                      {"output_format": "binary"}):
            self.assertEqual(self.configure(client, ids, **patch), ENVELOPE, patch)


class Capabilities(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        return client, device_id, {"device_id": device_id, "session_id": session_id}

    def test_both_measure_actions_return_the_fake_value(self) -> None:
        client, device_id, ids = self.serve()
        client.invoke("cap.device.configure.v1",
                      {"voltage_setpoint": 5.0, "current_limit": 0.25, "output_enabled": True}, **ids)
        voltage = client.invoke("cap.measure.voltage.v1", {}, **ids)
        current = client.invoke("cap.measure.current.v1", {}, **ids)
        self.assertEqual(voltage["status"], "completed", voltage)
        self.assertEqual(current["status"], "completed", current)
        self.assertAlmostEqual(voltage["output"]["voltage"], 5.0)
        self.assertAlmostEqual(current["output"]["current"], 0.25)
        self.assertIsInstance(voltage["output"]["sampled_at"], str)
        self.assertIsInstance(current["output"]["sampled_at"], str)

    def test_the_safe_state_action_turns_the_output_off(self) -> None:
        client, device_id, ids = self.serve()
        client.invoke("cap.device.configure.v1", {"output_enabled": True}, **ids)
        receipt = client.invoke("x-cap.eta-systems.output_off.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"output_enabled": False})
        state = client.read(device_id=device_id, resource_id="main", session_id=ids["session_id"])
        self.assertFalse(state["state"]["output_enabled"])


class ScpiRst(unittest.TestCase):
    """SAFE-042: the safety reset must not write *RST. The ordinary command may, and only when asked."""

    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver

    def test_the_declaration_is_an_ordinary_command(self) -> None:
        _client, driver = self.serve()
        model = type(driver).driver_model()
        self.assertIsNone(model.reset_attr)
        self.assertIsNone(model.reenable)
        binding = next(item for item in model.bindings if item.capability_id == RST)
        self.assertFalse(binding.safe_state)
        self.assertFalse(binding.reenable)

    def test_the_safety_reset_and_the_estop_do_not_send_rst(self) -> None:
        client, driver = self.serve()
        written = client.invoke("cap.device.configure.v1",
                                {"voltage_setpoint": 3.0, "current_limit": 1.0, "averaging_samples": 4},
                                **self.ids)
        self.assertEqual(written["status"], "completed", written)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertNotIn("*RST", driver.native.commands)
        refused = client.invoke(RST, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertNotIn("*RST", driver.native.commands)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertNotIn("*RST", driver.native.commands)
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["voltage_setpoint"], 3.0)
        self.assertEqual(state["current_limit"], 1.0)
        self.assertEqual(state["averaging_samples"], 4)
        self.assertEqual(driver.reset(), {})
        self.assertNotIn("*RST", driver.native.commands)

    def test_the_ordinary_command_sends_rst_and_forgets_the_cached_set_points(self) -> None:
        client, driver = self.serve()
        client.invoke("cap.device.configure.v1",
                      {"voltage_setpoint": 3.0, "current_limit": 1.0, "averaging_samples": 4,
                       "output_enabled": True},
                      **self.ids)
        before = list(driver.native.commands)
        receipt = client.invoke(RST, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"command_sent": True})
        # A state read before the command queries the instrument. The command itself adds *RST then *CLS.
        self.assertNotIn("*RST", before)
        self.assertEqual(driver.native.commands[-2:], ["*RST", "*CLS"])
        self.assertEqual(driver.native.commands.count("*RST"), 1)
        for field in ("voltage_setpoint", "current_limit", "averaging_samples"):
            with self.assertRaises(MHSError) as caught:
                client.read("main", fields=[field], **self.ids)
            self.assertEqual(caught.exception.code, UNKNOWN, field)
        # The output query is a real instrument reply. The fake's post-*RST value is a placeholder
        # and is not asserted.
        output = client.read("main", fields=["output_enabled"], **self.ids)["state"]["output_enabled"]
        self.assertIsInstance(output, bool)
        again = client.invoke("cap.device.configure.v1", {"voltage_setpoint": 2.5}, **self.ids)
        self.assertEqual(again["status"], "completed", again)
        self.assertEqual(client.read("main", fields=["voltage_setpoint"], **self.ids)["state"]["voltage_setpoint"],
                         2.5)
        with self.assertRaises(MHSError) as still:
            client.read("main", fields=["current_limit"], **self.ids)
        self.assertEqual(still.exception.code, UNKNOWN)

    def test_a_failed_write_after_rst_refuses_the_cached_set_points(self) -> None:
        client, driver = self.serve()
        written = client.invoke("cap.device.configure.v1",
                                {"voltage_setpoint": 3.0, "current_limit": 1.0, "averaging_samples": 4},
                                **self.ids)
        self.assertEqual(written["status"], "completed", written)
        native_send = driver.native.send_command

        def fail_cls(command):
            if command == "*CLS":
                raise OSError("injected transport failure on the write after *RST")
            return native_send(command)

        driver.native.send_command = fail_cls
        receipt = client.invoke(RST, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")
        self.assertIn("*RST", driver.native.commands)
        for field in ("voltage_setpoint", "current_limit", "averaging_samples"):
            with self.assertRaises(MHSError) as caught:
                client.read("main", fields=[field], **self.ids)
            self.assertEqual(caught.exception.code, UNKNOWN, field)


if __name__ == "__main__":
    unittest.main()
