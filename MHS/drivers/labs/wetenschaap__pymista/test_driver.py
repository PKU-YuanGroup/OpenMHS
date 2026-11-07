"""Acceptance run of the pymista package: the gate, plus cases for what is specific to this driver.

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

MOVE_ABSOLUTE = "x-cap.wetenschaap.move_absolute.v1"
MOVE_RELATIVE = "x-cap.wetenschaap.move_relative.v1"
HOME_AXES = "x-cap.wetenschaap.home_axes.v1"
STOP = "cap.motion.stop.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ZaberStageCases(unittest.TestCase):
    def serve(self, with_overlay=False):
        site_limits = str(HERE / "site-limits.example.json") if with_overlay else None
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position"], [0.0, 0.0])
        self.assertFalse(state["moving"])
        self.assertEqual(state["homed"], [False, False])

    def test_the_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(MOVE_ABSOLUTE, {"positions": [100.0, -200.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], [0.0, 0.0])

    def test_the_example_overlay_allows_motion_and_bounds_it(self) -> None:
        client = self.serve(with_overlay=True)
        moved = client.invoke(MOVE_ABSOLUTE, {"positions": [1000.0, -500.0]}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["positions"], [1000.0, -500.0])
        self.assertEqual(self.state(client)["position"], [1000.0, -500.0])
        relative = client.invoke(MOVE_RELATIVE, {"displacements": [250.0, 500.0]}, **self.ids)
        self.assertEqual(relative["status"], "completed")
        self.assertEqual(relative["output"]["positions"], [1250.0, 0.0])
        for capability_id, payload in (
            (MOVE_ABSOLUTE, {"positions": [100000.5, 0.0]}),
            (MOVE_RELATIVE, {"displacements": [100000.5, 0.0]}),
        ):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", capability_id)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, capability_id)
        self.assertEqual(self.state(client)["position"], [1250.0, 0.0])

    def test_a_short_vector_keeps_the_trailing_axis(self) -> None:
        client = self.serve(with_overlay=True)
        moved = client.invoke(MOVE_ABSOLUTE, {"positions": [42.0]}, **self.ids)
        self.assertEqual(moved["output"]["positions"], [42.0, 0.0])
        self.assertEqual(self.state(client)["position"], [42.0, 0.0])

    def test_home_and_stop(self) -> None:
        client = self.serve(with_overlay=True)
        client.invoke(MOVE_ABSOLUTE, {"positions": [1000.0, -500.0]}, **self.ids)
        homed = client.invoke(HOME_AXES, {}, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True})
        state = self.state(client)
        self.assertEqual(state["homed"], [True, True])
        self.assertEqual(state["position"], [0.0, 0.0])
        client.invoke(MOVE_ABSOLUTE, {"positions": [500.0, 600.0]}, **self.ids)
        stopped = client.invoke(STOP, {"deceleration": 2.0}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})
        self.assertFalse(self.state(client)["moving"])

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve(with_overlay=True)
        client.invoke(MOVE_ABSOLUTE, {"positions": [1000.0, -500.0]}, **self.ids)
        client.estop("test", **self.ids)
        refused = client.invoke(MOVE_ABSOLUTE, {"positions": [10.0, 20.0]}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertFalse(self.state(client)["moving"])


if __name__ == "__main__":
    unittest.main()
