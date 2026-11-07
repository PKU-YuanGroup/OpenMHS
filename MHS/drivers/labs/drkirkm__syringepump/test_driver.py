"""Acceptance run of the Harvard Apparatus OEM syringe-pump package: the gate, plus wire and limit cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WireCommands(unittest.TestCase):
    """The bytes the driver writes on the recording fake (the runtime's limits are not involved)."""

    def driver(self, **options):
        driver = load_driver(HERE, "fake", options=options or None)
        self.addCleanup(driver.close)
        return driver

    def test_address_00_writes_the_unprefixed_lines(self) -> None:
        driver = self.driver()
        driver.write("main", {"flow_rate": 12.5, "diameter": 12.06})
        self.assertEqual(driver.native.written, [b"MLH 12.5\r", b"MMD 12.06\r"])
        receipt = driver.call("x-cap.drkirkm.run.v1", {})
        self.assertEqual(receipt, {"running": True})
        self.assertEqual(driver.native.written[-1], b"RUN\r")
        self.assertTrue(driver.read("main")["pumping"])
        driver.estop("test")
        self.assertEqual(driver.native.written[-1], b"STP\r")
        self.assertFalse(driver.read("main")["pumping"])

    def test_address_01_and_02_use_their_prefixes(self) -> None:
        for address, flow_edit, diameter_edit in (("01", b"01MLH 2.5\r", b"01MMD 4.78\r"),
                                                  ("02", b"02MLH 2.5\r", b"02MMD 4.78\r")):
            driver = self.driver(address=address)
            driver.write("main", {"flow_rate": 2.5, "diameter": 4.78})
            self.assertEqual(driver.native.written, [flow_edit, diameter_edit])
            driver.call("x-cap.drkirkm.run.v1", {})
            self.assertEqual(driver.native.written[-1], address.encode("ascii") + b"RUN\r")
            driver.estop("test")
            self.assertEqual(driver.native.written[-1], address.encode("ascii") + b"STP\r")

    def test_the_safe_state_stops_all_three_addresses(self) -> None:
        driver = self.driver()
        driver.call("x-cap.drkirkm.run.v1", {})
        receipt = driver.call("x-cap.drkirkm.stop.v1", {})
        self.assertEqual(receipt, {"stopped": True})
        self.assertEqual(driver.native.written[-3:], [b"STP\r", b"01STP\r", b"02STP\r"])
        self.assertFalse(driver.read("main")["pumping"])

    def test_the_address_must_be_one_of_the_clone_three(self) -> None:
        driver = self.driver(address="07")
        with self.assertRaises(DriverFailed) as raised:
            driver.write("main", {"flow_rate": 1.0})
        self.assertEqual(raised.exception.code, "MHS.DEVICE.PRECONDITION_UNMET")


class Limits(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_without_an_operator_overlay_every_numeric_write_is_refused(self) -> None:
        client = self.serve()
        for patch in ({"flow_rate": 1.0}, {"diameter": 12.06}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_example_overlay_fills_and_narrows_the_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in ({"flow_rate": 0.0001}, {"flow_rate": 101}, {"diameter": 0.5}, {"diameter": 31}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"flow_rate": 1.0}, {"diameter": 12.06}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


if __name__ == "__main__":
    unittest.main()
