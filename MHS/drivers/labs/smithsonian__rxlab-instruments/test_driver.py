"""Acceptance run of the Agilent E8257D package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
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
RST = "x-cap.smithsonian.scpi_rst.v1"


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

    def test_writes_reach_the_upstream_methods(self) -> None:
        driver = self.driver()
        driver.write("main", {"frequency": 2500000000.0, "power": -10.0, "output_enabled": True})
        self.assertEqual(driver.native._frequency_writes[-1], (2500000000.0, "Hz"))
        self.assertEqual(driver.native._power_writes[-1], (-10.0, "dBm"))
        self.assertEqual(driver.native._on_calls, 1)
        state = driver.read("main")
        self.assertEqual((state["frequency"], state["power"]), (2500000000.0, -10.0))
        self.assertIs(state["output_enabled"], True)

    def test_the_reads_return_the_fake_identity(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["identity"])
        self.assertIn("E8257D", state["identity"])

    def test_the_estop_turns_the_output_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output_enabled": True})
        driver.estop("test")
        self.assertGreaterEqual(driver.native._off_calls, 1)
        self.assertIs(driver.read("main", ["output_enabled"])["output_enabled"], False)

    def test_the_output_boolean_reaches_power_on_and_power_off(self) -> None:
        driver = self.driver()
        driver.write("main", {"output_enabled": True})
        driver.write("main", {"output_enabled": False})
        self.assertEqual((driver.native._on_calls, driver.native._off_calls), (1, 1))


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_overlay_the_two_setpoints_are_operator_required(self) -> None:
        client = self.serve()
        for patch in ({"frequency": 1000000.0}, {"power": -20.0}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_bounds_the_setpoints(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"frequency": 999999.0}, {"frequency": 1000000001.0},
                      {"power": -30.001}, {"power": 0.001}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"frequency": 1000000.0}, {"frequency": 1000000000.0},
                      {"power": -30.0}, {"power": 0.0}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_output_boolean_needs_no_site_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, output_enabled=True), "completed")
        self.assertEqual(self.configure(client, output_enabled=False), "completed")


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
        client.invoke("cap.device.configure.v1", {"output_enabled": True}, **self.ids)
        calls = driver.native._reset_calls
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(driver.native._reset_calls, calls)
        self.assertIs(client.read("main", fields=["output_enabled"], **self.ids)["state"]["output_enabled"], False)
        refused = client.invoke(RST, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(driver.native._reset_calls, calls)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(driver.native._reset_calls, calls)
        self.assertEqual(driver.reset(), {})
        self.assertEqual(driver.native._reset_calls, calls)

    def test_the_ordinary_command_sends_rst_and_does_not_report_the_output(self) -> None:
        client, driver = self.serve()
        client.invoke("cap.device.configure.v1", {"output_enabled": True}, **self.ids)
        calls = driver.native._reset_calls
        receipt = client.invoke(RST, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"command_sent"})
        self.assertIs(receipt["output"]["command_sent"], True)
        self.assertEqual(driver.native._reset_calls, calls + 1)
        # A later read is the instrument's reply. The fake's post-*RST numbers are placeholders and are not
        # asserted: the clone does not state them (generic.py:65-68).
        state = client.read("main", fields=["output_enabled", "frequency", "power"], **self.ids)["state"]
        self.assertIn("output_enabled", state)
        self.assertIn("frequency", state)
        self.assertIn("power", state)


if __name__ == "__main__":
    unittest.main()
