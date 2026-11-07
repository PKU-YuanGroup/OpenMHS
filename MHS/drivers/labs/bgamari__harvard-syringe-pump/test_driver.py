"""Acceptance run of the Harvard Apparatus syringe pump package: the gate, plus cases for this driver.

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


class WireCommands(unittest.TestCase):
    """The command map, checked on the lines the fake transport receives (the runtime's limits are not involved)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_write_becomes_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        driver.write("main", {"diameter": 1.5, "flow_rate": 2.5, "target_volume": 3.0, "mode": "VOL"})
        self.assertEqual(driver.native.written, ["DIA 1.5", "RAT 2.5 MM", "TGT 3", "MOD VOL"])

    def test_the_reads_use_the_commands_of_the_clone(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(driver.native.written, ["DIA", "RAT", "TGT", "MOD", "DEL", "VER"])
        self.assertEqual((state["diameter"], state["flow_rate"]), (1.0, 1.0))
        self.assertEqual((state["target_volume"], state["mode"]), (0.0, "PMP"))
        self.assertEqual(state["version"], "fake-1.0")

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"diameter": 2.5, "flow_rate": 4.5, "target_volume": 6.0, "mode": "VOL"})
        state = driver.read("main", ["diameter", "flow_rate", "target_volume", "mode"])
        self.assertEqual(state, {"diameter": 2.5, "flow_rate": 4.5, "target_volume": 6.0, "mode": "VOL"})

    def test_the_actions_report_the_prompt_of_the_reply(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.bgamari.start_pump.v1", {}), {"status": "running"})
        self.assertEqual(driver.call("x-cap.bgamari.stop_pump.v1", {}), {"status": "stopped"})
        self.assertEqual(driver.call("x-cap.bgamari.set_direction.v1", {"direction": "REF"}),
                         {"status": "reverse"})
        self.assertEqual(driver.native.written, ["RUN", "STP", "DIR REF"])

    def test_the_estop_sends_stp(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.native.written, ["STP"])


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

    def test_without_an_overlay_the_numeric_bounds_are_unset(self) -> None:
        client = self.serve()
        for patch in ({"diameter": 1.0}, {"flow_rate": 2.0}, {"target_volume": 3.0}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_fills_and_narrows_the_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"diameter": 1.0}, {"flow_rate": 2.0}, {"target_volume": 3.0},
                      {"mode": "PMP"}, {"mode": "VOL"}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        for patch in ({"diameter": 100.0}, {"flow_rate": 20.0}, {"target_volume": 20.0}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        self.assertIn(self.configure(client, mode="BAD"),
                      (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"))

    def test_the_direction_action_rejects_a_token_outside_the_clone(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.bgamari.set_direction.v1", {"direction": "BAD"}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertIn(receipt["error"]["mhs_code"], (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"))


if __name__ == "__main__":
    unittest.main()
