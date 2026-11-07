"""Acceptance run of the LabJack U12 package: the gate, plus cases for what is specific to this driver.

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

# The fake's canned values (test data, not device facts).
DRIVER_VERSION = 1.21
FIRMWARE_VERSION = 1.0
VOLTAGE = 1.25
COUNTER = 17
LOCAL_ID = 0


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LabjackU12Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertAlmostEqual(state["driver_version"], DRIVER_VERSION)
        self.assertAlmostEqual(state["firmware_version"], FIRMWARE_VERSION)
        self.assertAlmostEqual(state["analog_input_0"], VOLTAGE)
        self.assertEqual(state["counter"], COUNTER)
        self.assertEqual(state["local_id"], LOCAL_ID)
        self.assertFalse(state["streaming"])

    def test_the_local_id_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, local_id=7)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["local_id"], LOCAL_ID)

    def test_the_example_overlay_supplies_the_local_id_and_outputs(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        configured = self.configure(client, local_id=7)
        self.assertEqual(configured["status"], "completed")
        self.assertEqual(self.state(client)["local_id"], 7)
        too_high = self.configure(client, local_id=256)
        self.assertEqual(too_high["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["local_id"], 7)
        applied = client.invoke("x-cap.labpy.set_analog_outputs.v1",
                                {"analog_output_0": 1.0, "analog_output_1": 2.0}, **self.ids)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"], {"analog_output_0": 1.0, "analog_output_1": 2.0})
        too_high = client.invoke("x-cap.labpy.set_analog_outputs.v1",
                                 {"analog_output_0": 6.0, "analog_output_1": 2.0}, **self.ids)
        self.assertEqual(too_high["error"]["mhs_code"], ENVELOPE)

    def test_the_voltage_and_the_block_acquisition(self) -> None:
        client = self.serve()
        measured = client.invoke("cap.measure.voltage.v1", {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["voltage"], VOLTAGE)
        self.assertIn("sampled_at", measured["output"])
        acquired = client.invoke("x-cap.labpy.sample_voltages.v1",
                                 {"count": 4, "scan_rate": 100}, **self.ids)
        self.assertEqual(acquired["status"], "completed")
        self.assertEqual(acquired["output"]["count"], 4)
        self.assertEqual(len(acquired["output"]["voltages"]), 4)
        self.assertAlmostEqual(acquired["output"]["voltages"][0], VOLTAGE)
        too_many = client.invoke("x-cap.labpy.sample_voltages.v1",
                                 {"count": 4097, "scan_rate": 100}, **self.ids)
        self.assertEqual(too_many["error"]["mhs_code"], ENVELOPE)
        too_fast = client.invoke("x-cap.labpy.sample_voltages.v1",
                                 {"count": 4, "scan_rate": 8193}, **self.ids)
        self.assertEqual(too_fast["error"]["mhs_code"], ENVELOPE)

    def test_the_pulse_train(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        started = client.invoke("x-cap.labpy.pulse_out.v1",
                                {"bit_select": 1, "num_pulses": 2, "time_b1": 1, "time_c1": 1, "time_b2": 1,
                                 "time_c2": 1}, **self.ids)
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"], {"bit_select": 1, "num_pulses": 2})
        refused = client.invoke("x-cap.labpy.pulse_out.v1",
                                {"bit_select": 1, "num_pulses": 0, "time_b1": 1, "time_c1": 1, "time_b2": 1,
                                 "time_c2": 1}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_resets_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["streaming"])
        refused = self.configure(client, local_id=7)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = client.invoke("x-cap.labpy.set_analog_outputs.v1",
                                {"analog_output_0": 1.0, "analog_output_1": 2.0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
