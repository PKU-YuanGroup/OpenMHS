"""Acceptance run of the Tektronix DPO70000 package: the gate, plus cases for this driver's actions.

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


class TekDPO70000Cases(unittest.TestCase):
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

    def invoke(self, client, capability_id):
        return client.invoke(capability_id, {}, **self.ids)

    def test_the_initial_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["acquire_mode"], "sample")
        self.assertEqual(state["acquire_mode_actual"], "sample")
        self.assertEqual(state["acquire_enhanced_enob"], "AUTO")
        self.assertEqual(state["acquire_interp_8bit"], "AUTO")
        self.assertFalse(state["acquire_enhanced_state"])
        self.assertFalse(state["acquire_magnivu"])
        self.assertEqual(state["acquire_num_acquisitions"], 0)
        self.assertEqual(state["acquire_num_avgs"], 16)
        self.assertEqual(state["acquire_num_envelop"], 100)
        self.assertEqual(state["acquire_num_frames"], 0)
        self.assertEqual(state["acquire_state"], "stop")
        self.assertEqual(state["trigger_state"], "ready")

    def test_the_run_and_stop_actions_change_the_state(self) -> None:
        client = self.serve()
        started = self.invoke(client, "x-cap.instrumentkit.acquisition_run.v1")
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"], {"acquire_state": "run"})
        self.assertEqual(self.state(client)["acquire_state"], "run")
        stopped = self.invoke(client, "x-cap.instrumentkit.acquisition_stop.v1")
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"acquire_state": "stop"})
        self.assertEqual(self.state(client)["acquire_state"], "stop")

    def test_the_trigger_actions_are_observable(self) -> None:
        client = self.serve()
        forced = self.invoke(client, "x-cap.instrumentkit.force_trigger.v1")
        self.assertEqual(forced["status"], "completed")
        self.assertEqual(forced["output"], {"trigger_state": "armed"})
        self.assertEqual(self.state(client)["trigger_state"], "armed")
        reset = self.invoke(client, "x-cap.instrumentkit.reset.v1")
        self.assertEqual(reset["output"], {"reset": True})
        self.assertEqual(self.state(client)["trigger_state"], "ready")
        software = self.invoke(client, "x-cap.instrumentkit.software_trigger.v1")
        self.assertEqual(software["status"], "completed")
        self.assertEqual(software["output"], {"trigger_state": "armed"})

    def test_the_estop_stops_acquisition_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.instrumentkit.acquisition_run.v1")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["acquire_state"], "stop")
        refused = self.invoke(client, "x-cap.instrumentkit.acquisition_run.v1")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
