"""Acceptance run of the SMC100 package: the gate, plus cases for this driver.

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


class NativeCommands(unittest.TestCase):
    """What the driver asks the upstream class to do (the fake records the SMC100 mnemonics)."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_use_the_upstream_properties(self) -> None:
        driver = self.driver()
        state = driver.read("main")
        self.assertEqual(state["identity"], "Newport SMC100PP fake")
        self.assertEqual(state["position"], 0.0)
        self.assertFalse(state["is_moving"])
        self.assertEqual(state["speed"], 1.0)
        self.assertEqual(state["acceleration"], 1.0)

    def test_the_move_actions_send_the_clone_commands(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.pymodaq.smc100_move_abs.v1", {"position": 10.0}),
                         {"position": 10.0})
        self.assertEqual(driver.call("x-cap.pymodaq.smc100_move_rel.v1", {"distance": -2.5}),
                         {"distance": -2.5})
        self.assertEqual(driver.read("main", ["position"]), {"position": 7.5})
        self.assertEqual(driver.call("cap.motion.home.v1", {}), {"homed": True})
        self.assertEqual(driver.call("x-cap.pymodaq.smc100_stop.v1", {}), {"stopped": True})
        self.assertEqual(driver.native.written, ["PA10.0", "PR-2.5", "PA0", "ST"])
        self.assertEqual(driver.read("main", ["position"]), {"position": 0.0})

    def test_the_estop_sends_the_native_stop(self) -> None:
        driver = self.driver()
        driver.call("x-cap.pymodaq.smc100_move_abs.v1", {"position": 5.0})
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], "ST")
        self.assertFalse(driver.native.is_moving)


class OperatorEnvelope(unittest.TestCase):
    """The example overlay fills the two operator_required move bounds and may only narrow them."""

    def serve(self):
        server = load(HERE, backend="fake", site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def move(self, client, capability_id, payload):
        receipt = client.invoke(capability_id, payload, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_overlay_supplies_the_move_envelope(self) -> None:
        client = self.serve()
        absolute = "x-cap.pymodaq.smc100_move_abs.v1"
        relative = "x-cap.pymodaq.smc100_move_rel.v1"
        for capability_id, payload in ((absolute, {"position": -101.0}), (absolute, {"position": 101.0}),
                                       (relative, {"distance": -101.0}), (relative, {"distance": 101.0})):
            self.assertEqual(self.move(client, capability_id, payload), ENVELOPE, payload)
        self.assertEqual(self.move(client, absolute, {"position": 100.0}), "completed")
        self.assertEqual(self.move(client, relative, {"distance": -100.0}), "completed")

    def test_without_the_overlay_the_move_bounds_are_unset(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("x-cap.pymodaq.smc100_move_abs.v1", {"position": 1.0},
                                device_id=device_id, session_id=session_id)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")


if __name__ == "__main__":
    unittest.main()
