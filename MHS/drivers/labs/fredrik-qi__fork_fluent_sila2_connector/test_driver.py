"""Acceptance run of the Tecan Fluent package: the gate, plus cases specific to this connector.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ASPIRATE = {"volume": 10, "labware": "plate_1", "liquid_class": "Water", "well_offset": 0}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FluentCases(unittest.TestCase):
    def serve(self, site_limits=None, **options):
        server = load(HERE, backend="fake", site_limits=site_limits, options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def invoke(self, client, capability_id, payload):
        return client.invoke(capability_id, payload, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["state"], "EditMode")
        self.assertEqual(state["progress"], -1)
        self.assertEqual(state["last_error"], "")
        self.assertEqual(state["runnable_methods"], ["DemoMethod"])
        self.assertEqual(state["variable_names"], ["DemoVariable"])

    def test_numeric_inputs_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.invoke(client, "x-cap.fredrik-qi.aspirate.v1", ASPIRATE)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["progress"], -1)

    def test_the_example_overlay_bounds_the_volume(self) -> None:
        client = self.serve(OVERLAY)
        completed = self.invoke(client, "x-cap.fredrik-qi.aspirate.v1", ASPIRATE)
        self.assertEqual(completed["status"], "completed", completed)
        self.assertIn("state", completed["output"])
        refused = self.invoke(client, "x-cap.fredrik-qi.aspirate.v1", dict(ASPIRATE, volume=1001))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_method_lifecycle_and_a_variable(self) -> None:
        client = self.serve()
        self.assertEqual(self.invoke(client, "x-cap.fredrik-qi.start_fluent.v1", {})["status"], "completed")
        prepared = self.invoke(client, "x-cap.fredrik-qi.prepare_method.v1", {"method": "DemoMethod"})
        self.assertEqual(prepared["status"], "completed")
        set_value = self.invoke(client, "x-cap.fredrik-qi.set_variable_value.v1",
                                {"variable_name": "Volume", "value": "42"})
        self.assertEqual(set_value["status"], "completed")
        self.assertEqual(set_value["output"], {"value": "42"})
        self.assertEqual(self.invoke(client, "x-cap.fredrik-qi.run_method.v1", {})["status"], "completed")
        self.assertEqual(self.state(client)["state"], "RunModeRunning")
        self.assertEqual(self.invoke(client, "x-cap.fredrik-qi.pause_run.v1", {})["status"], "completed")
        self.assertEqual(self.state(client)["state"], "RunModePaused")
        self.assertEqual(self.invoke(client, "x-cap.fredrik-qi.resume_run.v1", {})["status"], "completed")
        stopped = self.invoke(client, "x-cap.fredrik-qi.stop_method.v1", {})
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"state": "RunModeRunFinished"})
        self.assertIn("Volume", self.state(client)["variable_names"])

    def test_the_estop_stops_the_method_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.fredrik-qi.run_method.v1", {})
        self.assertEqual(self.state(client)["state"], "RunModeRunning")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        self.assertEqual(self.state(client)["state"], "RunModeRunFinished")
        refused = self.invoke(client, "x-cap.fredrik-qi.run_method.v1", {})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_stop_that_leaves_the_run_running_is_not_a_safe_state(self) -> None:
        client = self.serve(stop_ignored=True)
        self.invoke(client, "x-cap.fredrik-qi.run_method.v1", {})
        failed = self.invoke(client, "x-cap.fredrik-qi.stop_method.v1", {})
        self.assertEqual(failed["status"], "failed", failed)
        self.assertEqual(failed["error"]["mhs_code"], UNREACHED)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertEqual(self.state(client)["state"], "RunModeRunning")
        refused = self.invoke(client, "x-cap.fredrik-qi.run_method.v1", {})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_no_stop_before_a_start_command_created_the_runtime(self) -> None:
        client = self.serve(attached=False)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        refused = self.invoke(client, "x-cap.fredrik-qi.start_fluent.v1", {})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_api_commands_need_a_live_execution_channel(self) -> None:
        client = self.serve(OVERLAY, channel_checked=True)
        self.assertEqual(self.invoke(client, "x-cap.fredrik-qi.stop_method.v1", {})["status"], "completed")
        refused = self.invoke(client, "x-cap.fredrik-qi.aspirate.v1", ASPIRATE)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(self.invoke(client, "x-cap.fredrik-qi.run_method.v1", {})["status"], "completed")
        self.assertEqual(self.invoke(client, "x-cap.fredrik-qi.aspirate.v1", ASPIRATE)["status"], "completed")

    def test_the_labware_actions(self) -> None:
        client = self.serve(OVERLAY)
        dropped = self.invoke(client, "x-cap.fredrik-qi.drop_tips.v1", {"labware": "waste"})
        self.assertEqual(dropped["status"], "completed")
        located = self.invoke(client, "x-cap.fredrik-qi.set_location.v1",
                              {"labware": "plate_1", "rotation": 90, "target_location": "site_1",
                               "target_site": 1})
        self.assertEqual(located["status"], "completed")
        transferred = self.invoke(client, "x-cap.fredrik-qi.transfer_labware.v1",
                                  {"labware_to_location": "plate_1", "target_location": "site_2",
                                   "target_position": 1, "only_use_selected_site": True})
        self.assertEqual(transferred["status"], "completed")
        back = self.invoke(client, "x-cap.fredrik-qi.transfer_labware_back_to_base.v1",
                           {"labware_name": "plate_1"})
        self.assertEqual(back["status"], "completed")


if __name__ == "__main__":
    unittest.main()
