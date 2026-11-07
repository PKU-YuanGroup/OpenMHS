"""Acceptance run of the ISEG HV supply package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The safety rules (limits, the latch) live in the server, so the
cases drive a served endpoint; ``load_driver`` alone serves no limits.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
LATCHED = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Served(unittest.TestCase):
    """One served endpoint per case, the way an operator runs the package."""

    def serve(self, site_limits=None, **options):
        server = load(HERE, backend="fake", site_limits=site_limits,
                      options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def state(self, client, *fields):
        document = client.read("main", device_id=self.ids["device_id"], fields=list(fields),
                               session_id=self.ids["session_id"])
        return document["state"]

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_reads_are_served(self) -> None:
        client = self.serve()
        state = self.state(client, "voltage", "current", "voltage_target", "ramp_speed", "answer_delay",
                           "autostart", "channel")
        self.assertEqual((state["voltage"], state["current"], state["voltage_target"]), (0.0, 0.0, 0.0))
        self.assertEqual((state["ramp_speed"], state["answer_delay"], state["autostart"], state["channel"]),
                         (100, 1, True, 1))

    def test_a_write_reaches_the_device_and_is_read_back(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, ramp_speed=7, answer_delay=250, autostart=False), "completed")
        state = self.state(client, "ramp_speed", "answer_delay", "autostart")
        self.assertEqual((state["ramp_speed"], state["answer_delay"], state["autostart"]), (7, 250, False))

    def test_the_bounds_of_the_upstream_check_are_enforced(self) -> None:
        client = self.serve()
        for patch in ({"ramp_speed": 0}, {"ramp_speed": 256}, {"answer_delay": 0}, {"answer_delay": 256}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)

    def test_the_operator_bounds_refuse_until_the_overlay_supplies_them(self) -> None:
        client = self.serve()
        for patch in ({"voltage_target": 1.0}, {"channel": 2}):
            self.assertEqual(self.configure(client, **patch), UNSET, patch)

    def test_the_estop_calls_off_and_latches(self) -> None:
        client = self.serve(source_voltage=40.0)
        self.assertEqual(self.state(client, "voltage_target")["voltage_target"], 40.0)
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed")
        self.assertEqual(estop["output"]["estop"], "engaged")
        self.assertEqual(self.state(client, "voltage_target")["voltage_target"], 0.0)
        self.assertEqual(self.configure(client, ramp_speed=5), LATCHED)


class Overlay(unittest.TestCase):
    """The example operator overlay fills the two operator_required bounds and narrows the sourced ones."""

    def serve(self):
        server = load(HERE, backend="fake", site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def test_the_overlay_fills_the_operator_bounds(self) -> None:
        client = self.serve()
        for patch in ({"voltage_target": 0}, {"voltage_target": 1000}, {"channel": 1}, {"channel": 4}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        for patch in ({"voltage_target": -1}, {"voltage_target": 1000.5}, {"channel": 0}, {"channel": 5}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)

    def test_the_overlay_narrows_the_sourced_bounds(self) -> None:
        client = self.serve()
        for patch in ({"ramp_speed": 51}, {"answer_delay": 101}):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in ({"ramp_speed": 50}, {"answer_delay": 100}):
            self.assertEqual(self.configure(client, **patch), "completed", patch)


class BareDriver(unittest.TestCase):
    """The driver without the server: reads and the native calls, no safety rules."""

    def test_an_unknown_parameter_is_refused(self) -> None:
        from mhs.adapter import load_driver

        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        with self.assertRaises(MHSError) as caught:
            driver.write("main", {"no_such_parameter": 1})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.FIELD_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
