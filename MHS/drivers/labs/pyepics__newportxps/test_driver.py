"""Acceptance run of the Newport XPS package: the gate, plus cases for this driver.

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
MOVE = "x-cap.pyepics.move_stage.v1"
MOVE_RELATIVE = "x-cap.pyepics.move_stage_relative.v1"
HOME = "x-cap.pyepics.home_group.v1"
ENABLE = "x-cap.pyepics.enable_group.v1"
DISABLE = "x-cap.pyepics.disable_group.v1"
ABORT = "x-cap.pyepics.abort_group.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NewportXPSCases(unittest.TestCase):
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

    def test_the_reads_describe_the_bound_stage(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["stage"], "SampleX.Pos")                 # placeholder stage name
        self.assertEqual(state["group"], "SampleX")                     # placeholder group name
        self.assertEqual(state["position"], 0.0)                        # placeholder start position
        self.assertIn("Ready", state["group_status"]["SampleX"])
        self.assertIn("SampleX.Pos", state["hardware_status"])
        self.assertEqual(state["positioner_errors"]["SampleX.Pos"], "OK")
        self.assertEqual(state["tuning"]["closedloopstatus"], 1.0)      # placeholder tuning value

    def test_the_moves_wait_for_the_site(self) -> None:
        client = self.serve()
        for capability_id, payload in ((MOVE, {"position": 10.0}),
                                       (MOVE_RELATIVE, {"offset": 1.0})):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", capability_id)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, capability_id)
        self.assertEqual(self.state(client)["position"], 0.0)

    def test_the_example_overlay_bounds_the_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke(MOVE, {"position": 12.5}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"]["target"], 12.5)
        self.assertEqual(moved["output"]["position"], 12.5)
        self.assertFalse(moved["output"]["relative"])
        self.assertEqual(self.state(client)["position"], 12.5)
        stepped = client.invoke(MOVE_RELATIVE, {"offset": -2.5}, **self.ids)
        self.assertEqual(stepped["status"], "completed", stepped)
        self.assertEqual(stepped["output"]["offset"], -2.5)
        self.assertEqual(stepped["output"]["position"], 10.0)
        self.assertTrue(stepped["output"]["relative"])
        self.assertEqual(self.state(client)["position"], 10.0)
        for capability_id, payload in ((MOVE, {"position": 1000.1}),
                                       (MOVE, {"position": -1000.1}),
                                       (MOVE_RELATIVE, {"offset": 1000.1}),
                                       (MOVE_RELATIVE, {"offset": -1000.1})):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.state(client)["position"], 10.0)

    def test_the_group_actions(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertTrue(homed["output"]["homed"])
        self.assertEqual(homed["output"]["group"], "SampleX")
        enabled = client.invoke(ENABLE, {}, **self.ids)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertTrue(enabled["output"]["enabled"])
        disabled = client.invoke(DISABLE, {}, **self.ids)
        self.assertEqual(disabled["status"], "completed", disabled)
        self.assertFalse(disabled["output"]["enabled"])
        self.assertIn("Disabled", disabled["output"]["status"])
        aborted = client.invoke(ABORT, {}, **self.ids)
        self.assertEqual(aborted["status"], "completed", aborted)
        self.assertTrue(aborted["output"]["aborted"])

    def test_the_estop_disables_the_group_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke(MOVE, {"position": 5.0}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        client.estop("test", **self.ids)
        self.assertIn("Disabled", self.state(client)["group_status"]["SampleX"])
        refused = client.invoke(MOVE, {"position": 6.0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
