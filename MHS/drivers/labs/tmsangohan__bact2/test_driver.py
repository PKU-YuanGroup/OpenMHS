"""Acceptance run of the bact2 vacuum-sensor driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
VACUUM_READING = "x-cap.tmsangohan.vacuum_reading.v1"
FIELDS = ("pressure", "quality")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VacuumSensorCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_every_field_is_a_fresh_read_of_its_signal(self) -> None:
        client, fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), sorted(FIELDS))
        self.assertEqual(state["pressure"], 1.0e-7)   # placeholder
        self.assertEqual(state["quality"], 1.0)       # placeholder
        for name in FIELDS:
            calls = getattr(fake, name).get_calls
            self.assertTrue(calls, name)
            self.assertEqual(set(calls), {False}, f"{name} must be read with use_monitor=False")

    def test_the_pressure_capability_reads_the_proven_signal(self) -> None:
        client, fake = self.serve()
        before = len(fake.pressure.get_calls)
        receipt = client.invoke(VACUUM_READING, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["pressure"], 1.0e-7)   # placeholder
        self.assertGreater(len(fake.pressure.get_calls), before)
        self.assertEqual(set(fake.pressure.get_calls), {False})

    def test_the_sensor_offers_no_write(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"pressure": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN")

    def test_the_estop_latches_the_extension_and_calls_the_native_stop(self) -> None:
        client, fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertGreater(fake.stop_calls, 0)
        refused = client.invoke(VACUUM_READING, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(self.state(client)["pressure"], 1.0e-7)   # placeholder

    def test_a_failed_pv_read_returns_no_value(self) -> None:
        client, fake = self.serve()

        def disconnected(*, use_monitor=None):
            raise RuntimeError("placeholder: the PV is disconnected")

        fake.pressure.get = disconnected
        receipt = client.invoke(VACUUM_READING, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt.get("output"))

    def test_a_read_timeout_is_an_unknown_outcome_without_a_value(self) -> None:
        # ophyd reports a Channel Access read timeout as a TimeoutError; the Python-object bridge reports every native
        # timeout as MHS.OUTCOME.UNKNOWN and never returns a stale value.
        client, fake = self.serve()

        def silent(*, use_monitor=None):
            raise TimeoutError("placeholder: the PV did not answer")

        fake.pressure.get = silent
        receipt = client.invoke(VACUUM_READING, {}, **self.ids)
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.OUTCOME.UNKNOWN")
        self.assertIsNone(receipt.get("output"))


if __name__ == "__main__":
    unittest.main()
