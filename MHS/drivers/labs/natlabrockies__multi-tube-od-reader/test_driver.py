"""Acceptance run of the Multi-Tube-OD-Reader package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MultiTubeOdReaderCases(unittest.TestCase):
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

    def test_the_sixteen_ports_and_the_identity(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["name"], "fake-mtodr")                  # placeholder test data
        self.assertEqual(state["serial_number"], "470000001")          # placeholder test data
        self.assertEqual(state["port_positions"], list(range(1, 17)))
        self.assertEqual(state["port_usage"], [0] * 16)

    def test_the_firmware_name_is_written(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.device.configure.v1", {"name": "incubator-a"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["name"], "incubator-a")

    def test_a_port_voltage_is_measured(self) -> None:
        client = self.serve()
        first = client.invoke("cap.measure.voltage.v1", {"channel": "1"}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(first["output"]["voltage"], 0.5)              # placeholder test data
        self.assertIn("sampled_at", first["output"])
        last = client.invoke("cap.measure.voltage.v1", {"channel": "16"}, **self.ids)
        self.assertEqual(last["status"], "completed", last)
        self.assertEqual(last["output"]["voltage"], 4.25)             # placeholder test data

    def test_an_out_of_range_port_is_refused(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.measure.voltage.v1", {"channel": "17"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_the_indicator_blinks(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.natlabrockies.blink.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"blinked": True})

    def test_the_estop_latches_the_actions(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.natlabrockies.blink.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused_write = client.invoke("cap.device.configure.v1", {"name": "after-estop"}, **self.ids)
        self.assertEqual(refused_write["status"], "rejected", refused_write)
        self.assertEqual(refused_write["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
