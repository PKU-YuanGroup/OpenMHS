"""Acceptance run of the caproto ADR TagDriver: the gate, plus cases specific to this package.

Add cases, never remove the check_driver call.  Model review (2026-11-05): the package is an R0 observer; the
author's cases for the setpoint write, the PAUSE e-stop and the cycle start were replaced with read-only cases.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, close_server, load, load_driver
from mhs.bridge.tag_fake import request_key
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
READINGS = "x-cap.nsls-ii-sst.adr_readings.v1"
EXPECTED = {
    "temperature": 0.050,            # placeholder
    "setpoint_readback": 0.050,      # placeholder
    "temperature_rms": 0.0,          # placeholder
    "alternate_temperature": 0.050,  # placeholder
    "heater_output": 0.0,            # placeholder
    "state": "Idle",                 # placeholder
    "cycle_uid": "",                 # placeholder
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ADRCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        self.ids = {"device_id": device, "session_id": session}
        return client

    def test_reads_cover_the_declared_pvs(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.read("main"), EXPECTED)

    def test_the_observation_returns_the_published_values(self) -> None:
        client = self.serve()
        receipt = client.invoke(READINGS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], EXPECTED)

    def test_no_write_or_actuating_command_is_served(self) -> None:
        client = self.serve()
        for capability, payload in (("cap.device.configure.v1", {"setpoint": 0.1}),
                                    ("x-cap.nsls-ii-sst.pause_pid.v1", {}),
                                    ("x-cap.nsls-ii-sst.start_mag_cycle.v1", {})):
            refused = client.invoke(capability, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN", refused)

    def test_estop_is_the_software_latch_and_writes_nothing(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertEqual(driver.native.writes, 0)
        self.assertEqual(driver.native.pvs.get("PAUSE"), None)

    def test_an_unreadable_pv_fails_the_observation(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.refuse.add(request_key({"profile": "epics-ca", "pv": "TEMP"}))
        with self.assertRaises(Exception):
            driver.call(READINGS, {})

    def test_hardware_backend_is_refused_without_a_human_hardware_review(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, "hardware", allow_hardware=True, state_dir=state,
                            options={"prefix": "TEST:"})
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
