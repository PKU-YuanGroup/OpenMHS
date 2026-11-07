"""Acceptance run of the Reglo ICC package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
OVERLAY = str(HERE / "site-limits.example.json")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnitsAndDirections(unittest.TestCase):
    """The action converts uL/s and uL to the upstream mL/minute and mL, and picks the upstream method."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_forward_uses_dispense_vol(self) -> None:
        driver = self.driver()
        output = driver.call("cap.actuation.pump.v1",
                             {"flow_rate": 50, "direction": "forward", "volume": 500})
        self.assertEqual(output, {"dispensed_volume": 500.0})
        self.assertIn(("dispense_vol", 1, 0.5, 3.0, False), driver.native._calls)

    def test_reverse_uses_aspirate_vol(self) -> None:
        driver = self.driver()
        output = driver.call("cap.actuation.pump.v1",
                             {"flow_rate": 30, "direction": "reverse", "volume": 250})
        self.assertEqual(output, {"dispensed_volume": 250.0})
        self.assertIn(("aspirate_vol", 1, 0.25, 1.8, False), driver.native._calls)

    def test_the_estop_reaches_the_native_stop(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertIn(("stop", None), driver.native._calls)

    def test_the_tubing_write_is_readable(self) -> None:
        driver = self.driver()
        driver.write("main", {"tubing_id": 2.0})
        self.assertEqual(driver.read("main", ["tubing_id"]), {"tubing_id": 2.0})


class SiteLimits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def pump(self, client, **payload):
        receipt = client.invoke("cap.actuation.pump.v1", payload, **self.ids)
        if receipt["status"] == "rejected":
            return receipt["error"]["mhs_code"]
        return receipt["status"]

    def test_without_an_overlay_the_pump_refuses(self) -> None:
        client = self.serve()
        self.assertEqual(self.pump(client, flow_rate=50, direction="forward", volume=500), LIMITS_UNSET)
        refused = client.invoke("cap.device.configure.v1", {"tubing_id": 1.52}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_allows_the_pump_and_the_tubing(self) -> None:
        client = self.serve(OVERLAY)
        self.assertEqual(self.pump(client, flow_rate=50, direction="forward", volume=500), "completed")
        self.assertEqual(client.invoke("cap.device.configure.v1", {"tubing_id": 1.52}, **self.ids)["status"],
                         "completed")
        self.assertEqual(self.pump(client, flow_rate=101, direction="forward", volume=500), ENVELOPE)
        self.assertEqual(self.pump(client, flow_rate=50, direction="forward", volume=5001), ENVELOPE)
        refused = client.invoke("cap.device.configure.v1", {"tubing_id": 2.0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_safe_state_action_stops_every_channel(self) -> None:
        client = self.serve(OVERLAY)
        receipt = client.invoke("x-cap.czbiohub-sf.stop_pump.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"stopped": True})


if __name__ == "__main__":
    unittest.main()
