"""Acceptance run of the DAQmx package: the gate, plus cases for what is specific to this driver.

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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DaqmxCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, value):
        return client.invoke("cap.device.configure.v1", {"analog_output": value}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_voltage_write_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, 3.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["analog_output"], 0.0)      # the fake's placeholder, untouched

    def test_the_example_overlay_supplies_the_output_window(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, -3.5)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["analog_output"], -3.5)
        self.assertGreaterEqual(state["last_write_index"], 1)           # the fake's placeholder counter advanced
        for value in (-10.01, 10.01):
            refused = self.configure(client, value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["analog_output"], -3.5)

    def test_the_reads_describe_the_fake_card(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["device"], "Dev1")                       # the fake's placeholder
        self.assertEqual(state["analog_output_max_rate"], 1000000.0)    # the fake's placeholder
        self.assertEqual(state["analog_input_max_rate"], 500000.0)      # the fake's placeholder
        self.assertTrue(state["analog_triggering_supported"])
        self.assertEqual(state["trigger_source_count"], 2)              # the fake's placeholder list

    def test_the_estop_stops_the_task_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, 4.0)["status"], "completed")
        client.estop("test", **self.ids)
        refused = self.configure(client, 4.0)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["analog_output"], 4.0)      # the refused write changed nothing


if __name__ == "__main__":
    unittest.main()
