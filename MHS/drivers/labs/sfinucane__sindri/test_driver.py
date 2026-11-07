"""Acceptance run of the BERTScope package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The fake's starting values are test data, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class _Endpoint(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)


class Reads(_Endpoint):
    def test_the_detector_and_mainframe_state_reads_the_fake(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertIn("BERTScope", state["identity"])
        self.assertEqual(state["internal_temperature"], 31.5)
        self.assertFalse(state["running"])
        self.assertEqual(state["run_duration"], 0.0)
        self.assertEqual(state["detector_bit_count"], 1_000_000)
        self.assertEqual(state["detector_error_count"], 1_000)
        self.assertEqual(state["detector_bit_error_rate"], 0.001)
        self.assertEqual(state["detector_elapsed_time"], 10.0)
        self.assertEqual(state["detector_resyncs"], 3)
        self.assertEqual(state["detector_error_free_bits_count"], 999_000)
        self.assertEqual(state["detector_error_free_time"], 9.5)


class Write(_Endpoint):
    def test_an_in_range_run_duration_reaches_the_fake(self) -> None:
        client = self.serve()
        receipt = self.configure(client, run_duration=120.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["run_duration"], 120.0)

    def test_the_run_duration_bound_is_the_upstream_feat_limit(self) -> None:
        client = self.serve()
        for value in (-1.0, 36_000_001.0):
            receipt = self.configure(client, run_duration=value)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["run_duration"], 0.0)

    def test_the_upper_bound_is_inclusive(self) -> None:
        client = self.serve()
        receipt = self.configure(client, run_duration=36_000_000.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["run_duration"], 36_000_000.0)


class Actions(_Endpoint):
    def test_run_and_stop_report_the_mainframe_state(self) -> None:
        client = self.serve()
        started = self.invoke(client, "x-cap.sfinucane.run.v1")
        self.assertEqual(started["status"], "completed", started)
        self.assertEqual(started["output"], {"running": True})
        self.assertTrue(self.state(client)["running"])
        stopped = self.invoke(client, "x-cap.sfinucane.stop.v1")
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"running": False})
        self.assertFalse(self.state(client)["running"])

    def test_the_factory_reset_clears_the_mainframe_settings(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.sfinucane.run.v1")
        self.configure(client, run_duration=60.0)
        reset = self.invoke(client, "x-cap.sfinucane.factory_reset.v1")
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"], {"running": False})
        state = self.state(client)
        self.assertFalse(state["running"])
        self.assertEqual(state["run_duration"], 0.0)

    def test_the_detector_result_reset_clears_the_counters(self) -> None:
        client = self.serve()
        reset = self.invoke(client, "x-cap.sfinucane.reset_detector_results.v1")
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"], {"bit_count": 0, "error_count": 0})
        state = self.state(client)
        self.assertEqual((state["detector_bit_count"], state["detector_error_count"]), (0, 0))


class Safety(_Endpoint):
    def test_the_estop_stops_the_mainframe_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.sfinucane.run.v1")
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        refused = self.invoke(client, "x-cap.sfinucane.run.v1")
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
