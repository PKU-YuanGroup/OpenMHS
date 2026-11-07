"""Acceptance run of the Thorlabs Kinesis brushless-motor package: the gate, plus cases for this driver.

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
MOVE_ABS = "x-cap.pymodaq.thorlabs_move_abs.v1"
MOVE_REL = "x-cap.pymodaq.thorlabs_move_rel.v1"
HOME = "x-cap.pymodaq.thorlabs_home.v1"
STOP = "x-cap.pymodaq.thorlabs_stop.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ThorlabsBrushlessChannelCases(unittest.TestCase):
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
        self.assertEqual(state["position"], 0.0)                     # the fake's placeholder start position
        self.assertEqual(state["target_position"], 0.0)              # placeholder
        self.assertEqual(state["units"], "mm")                       # placeholder
        self.assertEqual(state["homed"], False)                      # placeholder
        self.assertEqual(state["channel"], 1)                        # the binding default

    def test_the_moves_wait_for_the_site(self) -> None:
        client = self.serve()
        for capability_id, payload in ((MOVE_ABS, {"position": 25.0}),
                                       (MOVE_REL, {"offset": -5.0})):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", capability_id)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, capability_id)
        self.assertEqual(self.state(client)["position"], 0.0)
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertEqual(homed["output"], {"started": True})

    def test_the_example_overlay_bounds_the_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke(MOVE_ABS, {"position": 100.5}, **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"target": 100.5, "position": 100.5})
        self.assertEqual(self.state(client)["position"], 100.5)
        stepped = client.invoke(MOVE_REL, {"offset": -25.5}, **self.ids)
        self.assertEqual(stepped["status"], "completed", stepped)
        self.assertEqual(stepped["output"], {"offset": -25.5, "target": 75.0, "position": 75.0})
        self.assertEqual(self.state(client)["position"], 75.0)
        for capability_id, payload in ((MOVE_ABS, {"position": 1000.01}),
                                       (MOVE_ABS, {"position": -1000.01}),
                                       (MOVE_REL, {"offset": 1000.01}),
                                       (MOVE_REL, {"offset": -1000.01})):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.state(client)["position"], 75.0)

    def test_the_home_move_and_the_native_stop(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke(MOVE_ABS, {"position": 42.0}, **self.ids)
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed", homed)
        self.assertEqual(homed["output"], {"started": True})
        state = self.state(client)
        self.assertEqual((state["position"], state["homed"]), (0.0, True))
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_latches_the_moves(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke(MOVE_ABS, {"position": 25.0}, **self.ids)
        client.estop("test", **self.ids)
        refused = client.invoke(MOVE_ABS, {"position": 30.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["position"], 25.0)


if __name__ == "__main__":
    unittest.main()
