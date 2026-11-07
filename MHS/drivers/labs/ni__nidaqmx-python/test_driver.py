"""Acceptance run of the NI-DAQmx voltage-task package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
VOLTAGE = 1.25          # the fake's fixed sample (test data, not a device fact)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NidaqmxVoltageTaskCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_state_and_the_single_voltage_measurement(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertTrue(state["task_done"])
        self.assertEqual(state["channel_name"], "Dev1/ai0")
        measured = client.invoke("cap.measure.voltage.v1", {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["voltage"], VOLTAGE)
        self.assertIn("sampled_at", measured["output"])
        rms = client.invoke("cap.measure.voltage.v1", {"dc": False}, **self.ids)
        self.assertEqual(rms["status"], "failed")
        self.assertEqual(rms["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_the_block_acquisition_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.ni.sample_voltages.v1", {"count": 4}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        client = self.serve(str(HERE / "site-limits.example.json"))
        acquired = client.invoke("x-cap.ni.sample_voltages.v1", {"count": 4}, **self.ids)
        self.assertEqual(acquired["status"], "completed")
        self.assertEqual(acquired["output"]["count"], 4)
        self.assertEqual(acquired["output"]["voltages"], [VOLTAGE] * 4)
        for value in (0, 9):
            out_of_range = client.invoke("x-cap.ni.sample_voltages.v1", {"count": value}, **self.ids)
            self.assertEqual(out_of_range["error"]["mhs_code"], ENVELOPE, value)

    def test_the_task_start_and_stop_are_observable(self) -> None:
        client = self.serve()
        self.assertTrue(self.state(client)["task_done"])
        started = client.invoke("x-cap.ni.start_task.v1", {}, **self.ids)
        self.assertEqual(started["status"], "completed")
        self.assertFalse(self.state(client)["task_done"])
        stopped = client.invoke("x-cap.ni.stop_task.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertTrue(self.state(client)["task_done"])

    def test_the_estop_stops_the_task_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertTrue(self.state(client)["task_done"])
        refused = client.invoke("x-cap.ni.start_task.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
