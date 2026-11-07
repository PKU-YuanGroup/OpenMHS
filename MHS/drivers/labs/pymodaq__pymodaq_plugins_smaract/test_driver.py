"""Acceptance run of the SmarAct MCS2 package: the gate, plus cases for this driver.

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
ABSOLUTE = "x-cap.pymodaq.smaract_absolute_move.v1"
RELATIVE = "x-cap.pymodaq.smaract_relative_move.v1"
REFERENCE = "x-cap.pymodaq.smaract_find_reference.v1"
STOP = "x-cap.pymodaq.smaract_stop.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SmarActMCS2Cases(unittest.TestCase):
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

    def test_the_reads_describe_the_bound_channel(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position"], 0)                       # the fake's placeholder start position
        self.assertEqual(state["units"], "meter")                    # placeholder
        self.assertEqual(state["base_resolution"], -12)              # placeholder
        self.assertEqual(state["positioner_type"], "SLC-24180")      # placeholder
        self.assertEqual(state["number_of_channels"], 3)             # placeholder
        self.assertEqual(state["channel"], 0)
        self.assertIn("MCS2", state["device_name"])

    def test_the_moves_wait_for_the_site(self) -> None:
        client = self.serve()
        for capability_id, payload in ((ABSOLUTE, {"position": 1000}),
                                       (RELATIVE, {"offset": 1000})):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", capability_id)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, capability_id)
        self.assertEqual(self.state(client)["position"], 0)
        started = client.invoke(REFERENCE, {}, **self.ids)
        self.assertEqual(started["status"], "completed")

    def test_the_example_overlay_bounds_the_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke(ABSOLUTE, {"position": 1000}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"position": 1000, "target": 1000})
        self.assertEqual(self.state(client)["position"], 1000)
        stepped = client.invoke(RELATIVE, {"offset": -400}, **self.ids)
        self.assertEqual(stepped["status"], "completed", stepped)
        self.assertEqual(stepped["output"], {"position": 600, "offset": -400})
        self.assertEqual(self.state(client)["position"], 600)
        for capability_id, payload in ((ABSOLUTE, {"position": 1000001}),
                                       (ABSOLUTE, {"position": -1000001}),
                                       (RELATIVE, {"offset": 1000001}),
                                       (RELATIVE, {"offset": -1000001})):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.state(client)["position"], 600)

    def test_the_reference_search_and_the_stop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke(ABSOLUTE, {"position": 2500}, **self.ids)
        referenced = client.invoke(REFERENCE, {}, **self.ids)
        self.assertEqual(referenced["status"], "completed", referenced)
        self.assertEqual(referenced["output"], {"started": True})
        self.assertEqual(self.state(client)["position"], 0)
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_latches_the_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = client.invoke(ABSOLUTE, {"position": 100}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
