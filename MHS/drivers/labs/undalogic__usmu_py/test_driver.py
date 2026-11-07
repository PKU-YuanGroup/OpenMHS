"""Acceptance run of the uSMU package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
CONFIGURE = "x-cap.undalogic.usmu.configure.v1"
IV_POINT = "x-cap.undalogic.usmu.iv_point.v1"
OUTPUT = "x-cap.undalogic.usmu.output.v1"


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

    def test_the_two_reads_reach_the_fake(self) -> None:
        driver = self.driver()
        state = driver.read("main", ["identification", "adc_0_1"])
        self.assertEqual(state["identification"], "uSMU fake")       # placeholder value of the stand-in
        self.assertIsInstance(state["adc_0_1"], int)

    def test_configure_and_iv_point_reach_the_native(self) -> None:
        driver = self.driver()
        configured = driver.call(CONFIGURE, {"oversample_rate": 7, "current_range": 3})
        self.assertEqual(configured, {"oversample_rate": 7, "current_range": 3})
        native = driver.native
        self.assertEqual((native._oversample, native._current_range), (7, 3))
        driver.call(OUTPUT, {"enabled": True})
        point = driver.call(IV_POINT, {"voltage": 2.0, "current_limit": 20.0})
        self.assertEqual(point["voltage"], 2.0)
        self.assertAlmostEqual(point["current"], 0.002)              # placeholder load of the stand-in
        self.assertEqual((native._voltage, native._current_limit_ma), (2.0, 20.0))

    def test_the_estop_reaches_disable_output(self) -> None:
        driver = self.driver()
        driver.call(OUTPUT, {"enabled": True})
        self.assertTrue(driver.native._output)
        driver.estop("test")
        self.assertFalse(driver.native._output)
        self.assertEqual(driver.native._writes[-1], "disable_output")


class ServerCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def invoke(self, client, capability_id, payload):
        return client.invoke(capability_id, payload, **self.ids)

    def test_without_an_overlay_the_operator_bounds_are_unset(self) -> None:
        client = self.serve()
        for capability_id, payload in (
            (CONFIGURE, {"oversample_rate": 10, "current_range": 2}),
            (IV_POINT, {"voltage": 1.0, "current_limit": 20.0}),
        ):
            refused = self.invoke(client, capability_id, payload)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, refused)

    def test_the_example_overlay_bounds_every_numeric_input(self) -> None:
        client = self.serve(OVERLAY)
        accepted = self.invoke(client, CONFIGURE, {"oversample_rate": 10, "current_range": 2})
        self.assertEqual(accepted["status"], "completed", accepted)
        refused_inputs = (
            (CONFIGURE, {"oversample_rate": 0, "current_range": 2}),
            (CONFIGURE, {"oversample_rate": 101, "current_range": 2}),
            (CONFIGURE, {"oversample_rate": 10, "current_range": 5}),
            (IV_POINT, {"voltage": 11.0, "current_limit": 20.0}),
            (IV_POINT, {"voltage": -11.0, "current_limit": 20.0}),
            (IV_POINT, {"voltage": 1.0, "current_limit": -1}),
            (IV_POINT, {"voltage": 1.0, "current_limit": 101}),
        )
        for capability_id, payload in refused_inputs:
            refused = self.invoke(client, capability_id, payload)
            self.assertEqual(refused["status"], "rejected", (payload, refused))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (payload, refused))

    def test_the_iv_point_and_the_output_action(self) -> None:
        client = self.serve(OVERLAY)
        enabled = self.invoke(client, OUTPUT, {"enabled": True})
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(enabled["output"], {"enabled": True})
        point = self.invoke(client, IV_POINT, {"voltage": 2.0, "current_limit": 20.0})
        self.assertEqual(point["status"], "completed", point)
        self.assertEqual(point["output"]["voltage"], 2.0)
        self.assertAlmostEqual(point["output"]["current"], 0.002)    # placeholder load of the stand-in
        disabled = self.invoke(client, OUTPUT, {"enabled": False})
        self.assertEqual(disabled["output"], {"enabled": False})

    def test_the_estop_latches_and_refuses_the_output_action(self) -> None:
        client = self.serve(OVERLAY)
        self.invoke(client, OUTPUT, {"enabled": True})
        client.estop("test", **self.ids)
        refused = self.invoke(client, OUTPUT, {"enabled": True})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)


if __name__ == "__main__":
    unittest.main()
