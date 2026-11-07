"""Acceptance run of the syringe-pump package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

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


class NativeCalls(unittest.TestCase):
    """The calls the driver makes on the upstream object, checked on the fake object directly."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_writes_reach_the_upstream_methods(self) -> None:
        driver = self.driver()
        driver.write("main", {"diameter": 1.0})
        self.assertEqual(driver.native.diameter, 1.0)
        self.assertIn("set_diameter", driver.native.calls)
        driver.write("main", {"direction": "WDR"})
        self.assertEqual(driver.native.direction, "WDR")
        self.assertIn("set_direction_withdraw", driver.native.calls)
        driver.write("main", {"direction": "INF"})
        self.assertEqual(driver.native.direction, "INF")
        self.assertIn("set_direction_infuse", driver.native.calls)

    def test_the_rate_is_one_rat_command_with_its_unit(self) -> None:
        driver = self.driver()
        driver.write("main", {"pumping_rate": {"value": 2.5, "rate_unit": "UH"}})
        self.assertEqual((driver.native.rate, driver.native.rate_unit), (2.5, "UH"))
        self.assertIn("set_pumping_rate", driver.native.calls)

    def test_the_actions_and_the_estop_reach_the_native_stop(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.giansimone.run_pump.v1", {})
        self.assertEqual(output["reply"], "OK")
        self.assertTrue(driver.native.running)
        driver.call("x-cap.giansimone.reverse_direction.v1", {})
        self.assertEqual(driver.native.direction, "REV")
        self.assertIn("set_direction_reverse", driver.native.calls)
        driver.estop("test")
        self.assertFalse(driver.native.running)
        self.assertIn("stop_pump", driver.native.calls)

    def test_the_native_diameter_check_is_strict_at_the_endpoints(self) -> None:
        driver = self.driver()
        for value in (0.1, 50.0):
            with self.assertRaises(ValueError):
                driver.native.set_diameter(driver.native.adr1, value)


class ServedLimits(unittest.TestCase):
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
        return receipt["error"]["mhs_code"] if receipt["status"] in ("rejected", "failed") else receipt["status"]

    def test_the_diameter_bounds_and_the_operator_required_rate(self) -> None:
        client = self.serve()
        for patch in ({"diameter": 0.05}, {"diameter": 50.1}, {"direction": "REV"},
                      {"pumping_rate": {"value": 1.0, "rate_unit": "XX"}}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        self.assertEqual(self.configure(client, diameter=1.0), "completed")
        self.assertEqual(self.configure(client, direction="WDR"), "completed")
        self.assertEqual(self.configure(client, pumping_rate={"value": 1.0, "rate_unit": "UM"}), UNSET)

    def test_the_example_overlay_only_narrows_and_fills_the_rate(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"diameter": 0.4}, {"diameter": 41.0},
                      {"pumping_rate": {"value": 1001.0, "rate_unit": "UM"}},
                      {"pumping_rate": {"value": 1.0, "rate_unit": "MM"}}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        self.assertEqual(self.configure(client, diameter=1.0), "completed")
        self.assertEqual(self.configure(client, pumping_rate={"value": 1.0, "rate_unit": "UM"}), "completed")


if __name__ == "__main__":
    unittest.main()
