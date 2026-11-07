"""Acceptance run of the HAMEG HM1507 package: the gate, plus cases for the byte commands of this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The exact command strings the upstream class builds (HAMEG_HM1507.py:93-114)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_timebase_commands_are_the_upstream_bytes(self) -> None:
        driver = self.driver()
        driver.write("main", {"timebase": {"base": "A", "single": False, "time_div": "50ns"}})
        driver.write("main", {"timebase": {"base": "A", "single": True, "time_div": "100s"}})
        driver.write("main", {"timebase": {"base": "B", "single": True, "time_div": "500ms"}})
        self.assertEqual(driver.native.commands,
                         ["TBA=" + chr(0), "TBA=" + chr(60), "TBB=" + chr(53)])

    def test_the_channel_commands_are_the_upstream_bytes(self) -> None:
        driver = self.driver()
        driver.write("main", {"channel": {"channel": 1, "invert": False, "mode_dc": True, "volts_div": "1mV"}})
        driver.write("main", {"channel": {"channel": 2, "invert": True, "mode_dc": False, "volts_div": "20V"}})
        driver.write("main", {"channel": {"channel": 1, "invert": True, "mode_dc": True, "volts_div": "1V"}})
        self.assertEqual(driver.native.commands,
                         ["CH1=" + chr(16), "CH2=" + chr(125), "CH1=" + chr(57)])

    def test_a_write_changes_the_reported_state(self) -> None:
        driver = self.driver()
        patch = {"channel": {"channel": 2, "invert": True, "mode_dc": False, "volts_div": "2V"}}
        driver.write("main", patch)
        self.assertEqual(driver.read("main"), patch)

    def test_autoset_sends_the_upstream_command(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.aakafosfor.autoset.v1", {}), {"applied": True})
        self.assertEqual(driver.native.commands, ["AUTOSET"])

    def test_the_estop_releases_remote_control(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.commands, ["rm0"])
        self.assertFalse(driver.native.connected)


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        return client, {"device_id": device_id,
                        "session_id": client.open_session(device_ids=[device_id])["session_id"]}

    def configure(self, client, ids, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_lists_refuse_a_value_outside_them(self) -> None:
        client, ids = self.serve()
        for patch in (
            {"timebase": {"base": "C", "single": False, "time_div": "1ms"}},
            {"timebase": {"base": "A", "single": False, "time_div": "1ns"}},
            {"channel": {"channel": 3, "invert": False, "mode_dc": True, "volts_div": "1V"}},
            {"channel": {"channel": 1, "invert": False, "mode_dc": True, "volts_div": "3mV"}},
        ):
            self.assertEqual(self.configure(client, ids, **patch), ENVELOPE, patch)
        for patch in (
            {"timebase": {"base": "A", "single": False, "time_div": "50ns"}},
            {"timebase": {"base": "B", "single": True, "time_div": "100s"}},
            {"channel": {"channel": 1, "invert": False, "mode_dc": True, "volts_div": "1mV"}},
            {"channel": {"channel": 2, "invert": True, "mode_dc": False, "volts_div": "20V"}},
        ):
            self.assertEqual(self.configure(client, ids, **patch), "completed", patch)

    def test_the_autoset_action_completes_with_its_output(self) -> None:
        client, ids = self.serve()
        receipt = client.invoke("x-cap.aakafosfor.autoset.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"applied": True})


if __name__ == "__main__":
    unittest.main()
