"""Acceptance run of the LabJack U3 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
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


class LabjackU3Cases(unittest.TestCase):
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

    def test_the_initial_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["analog_input_0"], 1.25)
        self.assertEqual(state["internal_temperature"], 295.15)
        self.assertEqual((state["fio_analog"], state["eio_analog"]), (15, 0))
        self.assertEqual(state["dio_states"], [0] * 20)

    def test_the_voltage_measurement(self) -> None:
        client = self.serve()
        measured = client.invoke("cap.measure.voltage.v1", {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertEqual(measured["output"]["voltage"], 1.25)
        self.assertIn("sampled_at", measured["output"])
        refused = client.invoke("cap.measure.voltage.v1", {"dc": False}, **self.ids)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_the_analog_masks_are_written_and_read_back(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, fio_analog=255)["status"], "completed")
        self.assertEqual(self.configure(client, eio_analog=7)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["fio_analog"], state["eio_analog"]), (255, 7))
        for patch in ({"fio_analog": 256}, {"eio_analog": -1}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual((self.state(client)["fio_analog"], self.state(client)["eio_analog"]), (255, 7))

    def test_a_digital_line_is_driven_and_read(self) -> None:
        client = self.serve()
        driven = client.invoke("x-cap.labjack.set_digital_output.v1", {"pin": 3, "value": 1}, **self.ids)
        self.assertEqual(driven["status"], "completed")
        self.assertEqual(driven["output"], {"applied": True, "pin": 3, "value": 1})
        self.assertEqual(self.state(client)["dio_states"][3], 1)
        for payload in ({"pin": 20, "value": 1}, {"pin": 0, "value": 2}, {"pin": 0, "value": 0.5}):
            refused = client.invoke("x-cap.labjack.set_digital_output.v1", payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.state(client)["dio_states"][3], 1)

    def test_the_reset_action_returns_the_power_up_state(self) -> None:
        client = self.serve()
        self.configure(client, fio_analog=255)
        client.invoke("x-cap.labjack.set_digital_output.v1", {"pin": 4, "value": 1}, **self.ids)
        reset = client.invoke("x-cap.labjack.reset.v1", {}, **self.ids)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"], {"fio_analog": 15, "eio_analog": 0})
        state = self.state(client)
        self.assertEqual(state["fio_analog"], 15)
        self.assertEqual(state["dio_states"][4], 0)

    def test_the_estop_resets_the_device_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.labjack.set_digital_output.v1", {"pin": 5, "value": 1}, **self.ids)
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["dio_states"][5], 0)
        refused = client.invoke("x-cap.labjack.set_digital_output.v1", {"pin": 5, "value": 1}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
