"""Acceptance run of the Rigol DS1054Z package: the gate, plus cases specific to this driver.

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


class ScopeCases(unittest.TestCase):
    """The scalar settings and the acquisition actions of the fake backend."""

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_use_the_upstream_getters(self) -> None:
        state = self.driver().read("main")
        self.assertEqual(state["identity"].split(",")[1], "DS1054Z")
        self.assertEqual(state["acquire_type"], "NORMAL")
        self.assertEqual(state["sample_rate"], 1.0e9)
        self.assertEqual(state["timebase_mode"], "MAIN")
        self.assertEqual(state["trigger_sweep"], "AUTO")
        self.assertEqual(state["ch1_coupling"], "DC")
        self.assertEqual(state["ch1_bw_limit"], "OFF")
        self.assertIs(state["ch1_display"], True)

    def test_a_write_changes_the_state(self) -> None:
        driver = self.driver()
        driver.write("main", {"ch1_display": False, "acquire_type": "PEAK", "ch1_coupling": "AC"})
        state = driver.read("main")
        self.assertIs(state["ch1_display"], False)
        self.assertEqual(state["acquire_type"], "PEAK")
        self.assertEqual(state["ch1_coupling"], "AC")

    def test_the_estop_reaches_the_native_stop(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertEqual(driver.read("main")["trigger_status"], "STOP")

    def test_the_run_action_reports_the_trigger_status(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("x-cap.abduznik.run.v1", {}, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"trigger_status": "AUTO"})


class Limits(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session}

    def configure(self, client, ids, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **ids)
        if receipt["status"] == "rejected":
            return receipt["error"]["mhs_code"]
        return receipt["status"]

    def test_an_allowed_set_refuses_a_value_outside_it(self) -> None:
        client, ids = self.serve()
        self.assertEqual(self.configure(client, ids, acquire_type="SINGLE"), ENVELOPE)
        self.assertEqual(self.configure(client, ids, acquire_type="PEAK"), "completed")

    def test_an_operator_required_bound_waits_for_the_site(self) -> None:
        client, ids = self.serve()
        receipt = client.invoke("cap.device.configure.v1", {"ch1_scale": 0.5}, **ids)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")


if __name__ == "__main__":
    unittest.main()
