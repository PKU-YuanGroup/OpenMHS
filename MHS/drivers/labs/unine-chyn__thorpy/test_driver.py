"""Acceptance run of the Thorpy package: the gate, plus cases specific to this driver.

Keep the check_driver call; add cases, never remove it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STOP_FRAME = b"\x65\x04\x01\x01\x50\x01"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StageSurface(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        return driver

    def test_initial_state_reads_the_generic_stage(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertIsInstance(state["position"], float)
        self.assertIsInstance(state["max_velocity"], float)
        self.assertIsInstance(state["acceleration"], float)
        self.assertIs(state["homed"], False)

    def test_a_write_reaches_the_generic_stage_and_reads_back(self) -> None:
        driver = self.driver()
        driver.write("main", {"position": 2.5, "max_velocity": 0.75, "acceleration": 3.0})
        state = driver.read("main", ["position", "max_velocity", "acceleration"])
        self.assertEqual(state, {"position": 2.5, "max_velocity": 0.75, "acceleration": 3.0})

    def test_home_returns_when_the_status_bit_is_set(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.unine-chyn.stage_home.v1", {}), {"homed": True})
        self.assertEqual(driver.read("main", ["homed"]), {"homed": True})

    def test_the_estop_sends_the_stop_frame_and_the_action_reports_stopped(self) -> None:
        driver = self.driver()
        driver.estop("unit test")
        self.assertEqual(driver.native.sent[-1], STOP_FRAME)
        self.assertEqual(driver.call("x-cap.unine-chyn.stage_stop.v1", {}), {"stopped": True})


class OperatorLimits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_writes_are_refused_without_an_operator_bound(self) -> None:
        client = self.serve()
        for patch in ({"position": 1.0}, {"max_velocity": 1.0}, {"acceleration": 1.0}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_fills_the_bounds_and_narrows_them(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, position=11.0), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.configure(client, position=1.0), "completed")
        self.assertEqual(self.configure(client, max_velocity=0.5), "completed")
        self.assertEqual(self.configure(client, acceleration=5.0), "completed")


if __name__ == "__main__":
    unittest.main()
