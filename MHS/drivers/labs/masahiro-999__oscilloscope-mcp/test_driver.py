"""Acceptance run of the RIGOL DS1000Z package: the gate, plus cases for this driver.

Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CONFIGURE = "cap.device.configure.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RigolCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke(CONFIGURE, patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_state_and_a_channel_write(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertIn("RIGOL", state["identity"])
        self.assertEqual(state["active_channel_count"], 1)
        self.assertEqual(state["channel_1_scale"], 1.0)
        self.assertEqual(state["timebase_scale"], 1.0e-3)
        self.assertEqual(state["trigger_status"], "RUN")

        self.assertEqual(self.configure(client, channel_1_scale=2.5)["status"], "completed")
        self.assertEqual(self.state(client)["channel_1_scale"], 2.5)

    def test_every_numeric_write_refuses_a_value_outside_its_bound(self) -> None:
        client = self.serve()
        for patch in (
            {"channel_1_scale": 0.0005},
            {"channel_1_offset": 100.5},
            {"timebase_scale": 51.0},
            {"timebase_offset": -100.5},
            {"channel_1_probe": 3.0},
            {"acquire_averages": 3},
        ):
            receipt = self.configure(client, **patch)
            self.assertEqual(receipt["status"], "rejected", patch)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual(state["channel_1_scale"], 1.0)
        self.assertEqual(state["acquire_averages"], 2)

    def test_the_vertical_and_acquisition_writes_apply(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel_1_offset=-1.25)["status"], "completed")
        self.assertEqual(self.configure(client, channel_1_probe=100)["status"], "completed")
        self.assertEqual(self.configure(client, channel_1_coupling="AC")["status"], "completed")
        self.assertEqual(self.configure(client, channel_1_display=False)["status"], "completed")
        self.assertEqual(self.configure(client, timebase_mode="XY")["status"], "completed")
        self.assertEqual(self.configure(client, acquire_type="PEAK")["status"], "completed")
        self.assertEqual(self.configure(client, acquire_averages=64)["status"], "completed")
        self.assertEqual(self.configure(client, trigger_sweep="NORMAL")["status"], "completed")
        self.assertEqual(self.configure(client, trigger_coupling="HFReject")["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["channel_1_offset"], -1.25)
        self.assertEqual(state["channel_1_probe"], 100.0)
        self.assertEqual(state["channel_1_coupling"], "AC")
        self.assertFalse(state["channel_1_display"])
        self.assertEqual(state["timebase_mode"], "XY")
        self.assertEqual(state["acquire_type"], "PEAK")
        self.assertEqual(state["acquire_averages"], 64)
        self.assertEqual(state["trigger_sweep"], "NORMAL")
        self.assertEqual(state["trigger_coupling"], "HFReject")

    def test_the_measure_action_returns_the_requested_values(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.masahiro-999.measure.v1",
                                {"items": ["VPP", "FREQUENCY"], "source": "CHAN1"}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["source"], "CHAN1")
        self.assertEqual(output["items"], ["VPP", "FREQUENCY"])
        self.assertIn("VPP", output["values"])
        self.assertIn("FREQUENCY", output["values"])

    def test_run_control_changes_the_status(self) -> None:
        client = self.serve()
        stopped = client.invoke("x-cap.masahiro-999.run_control.v1", {"action": "STOP"}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"]["action"], "STOP")
        self.assertEqual(self.state(client)["trigger_status"], "STOP")
        running = client.invoke("x-cap.masahiro-999.run_control.v1", {"action": "RUN"}, **self.ids)
        self.assertEqual(running["output"]["action"], "RUN")
        self.assertEqual(self.state(client)["trigger_status"], "RUN")

    def test_the_estop_stops_acquisition_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["trigger_status"], "STOP")
        refused = self.configure(client, timebase_scale=1.0e-3)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = client.invoke("x-cap.masahiro-999.measure.v1", {"items": ["VPP"]}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
