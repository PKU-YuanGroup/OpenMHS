"""Acceptance run of the syrpp package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
OVERLAY = str(HERE / "site-limits.example.json")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NativePaths(unittest.TestCase):
    """The calls the driver makes on the upstream object, checked on the fake object directly."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_and_writes_reach_the_upstream_methods(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["status"], "pumping program stopped")
        self.assertEqual((state["firmware_version"], state["phase"]), ("NE1000V3.934", 1))
        self.assertEqual(state["diameter"], 1.0)
        self.assertEqual(state["phase_function"], "rate")
        self.assertEqual(state["pumping_rate"], 1.0)
        self.assertEqual(state["direction"], "infuse")
        self.assertFalse(state["alarm"])
        self.assertEqual(state["volume"]["volume"], 0.0)
        driver.write("main", {"diameter": 2.5, "phase": 5, "direction": "withdraw",
                              "phase_function": "stop", "alarm": True, "buzzer": True})
        self.assertEqual(driver.native._diameter, 2.5)
        self.assertEqual(driver.native._phase, 5)
        self.assertEqual(driver.native._direction, "withdraw")
        self.assertEqual(driver.native._function, "stop")
        self.assertTrue(driver.native._alarm)
        self.assertTrue(driver.native._buzzer)
        self.assertTrue(any(call[0] == "set_diameter" for call in driver.native.calls))
        self.assertTrue(any(call[0] == "set_phase" for call in driver.native.calls))

    def test_the_program_actions_and_the_estop_use_stp(self) -> None:
        driver = self.driver()
        started = driver.call("x-cap.yuanxun-yx.start_program.v1", {})
        self.assertEqual(started["status"], "infusing")
        stopped = driver.call("x-cap.yuanxun-yx.stop_program.v1", {})
        self.assertEqual(stopped["status"], "pumping program stopped")
        driver.call("x-cap.yuanxun-yx.start_program.v1", {})
        driver.estop("test")
        self.assertEqual(driver.native._prompt, "S")
        self.assertTrue(any(call[0] == "stop_program" for call in driver.native.calls))

    def test_the_rate_write_sends_rat_and_keeps_the_units(self) -> None:
        driver = self.driver()
        driver.write("main", {"pumping_rate": 4.5})
        self.assertEqual(driver.native._rate, 4.5)
        self.assertTrue(any(call[0] == "set_rate" and call[2] == 4.5 for call in driver.native.calls))


class ServedLimits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        if receipt["status"] in ("rejected", "failed"):
            return receipt["error"]["mhs_code"]
        return receipt["status"]

    def test_the_unsourced_bounds_wait_for_the_site(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, diameter=1.0), UNSET)
        self.assertEqual(self.configure(client, pumping_rate=1.0), UNSET)
        self.assertEqual(self.configure(client, phase=0), ENVELOPE)
        self.assertEqual(self.configure(client, phase=42), ENVELOPE)
        self.assertEqual(self.configure(client, direction="sideways"), ENVELOPE)
        self.assertEqual(self.configure(client, phase_function="pause"), ENVELOPE)

    def test_the_example_overlay_supplies_and_narrows_the_bounds(self) -> None:
        client = self.serve(OVERLAY)
        self.assertEqual(self.configure(client, diameter=1.0), "completed")
        self.assertEqual(self.configure(client, pumping_rate=1.0), "completed")
        self.assertEqual(self.configure(client, phase=5), "completed")
        self.assertEqual(self.configure(client, direction="withdraw"), "completed")
        for patch in ({"diameter": 0.4}, {"diameter": 41.0}, {"pumping_rate": 1001.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)

    def test_the_reads_and_the_safe_state_action(self) -> None:
        client = self.serve(OVERLAY)
        state = client.read("main", **self.ids)["state"]
        self.assertEqual((state["direction"], state["phase"]), ("infuse", 1))
        self.assertFalse(state["alarm"])
        started = client.invoke("x-cap.yuanxun-yx.start_program.v1", {}, **self.ids)
        self.assertEqual(started["output"]["status"], "infusing")
        self.assertEqual(client.read("main", **self.ids)["state"]["status"], "infusing")
        stopped = client.invoke("x-cap.yuanxun-yx.stop_program.v1", {}, **self.ids)
        self.assertEqual(stopped["output"]["status"], "pumping program stopped")


if __name__ == "__main__":
    unittest.main()
