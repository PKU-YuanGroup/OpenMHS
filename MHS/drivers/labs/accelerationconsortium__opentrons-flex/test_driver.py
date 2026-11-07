"""Acceptance run of the Opentrons Flex package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SITE = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
HOME = "x-cap.accelerationconsortium.home_all.v1"
HALT = "x-cap.accelerationconsortium.halt_motion.v1"
MOVE = "cap.motion.cartesian_pose.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FlexCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        return self.session_client(server)

    def serve_driver(self, site_limits=SITE):
        """A server over a driver this test keeps, so the fake's halt, home and gate state are visible."""
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        return driver, self.session_client(server)

    def session_client(self, server):
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def move(self, client, x=100.0, y=100.0, z=100.0):
        return client.invoke(MOVE, {"position": {"x": x, "y": y, "z": z}}, **self.ids)

    def test_reads_and_lights(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertTrue(state["simulating"])
        self.assertEqual((state["lights_button"], state["lights_rails"]), (False, False))
        self.assertEqual(state["machine_status"],
                         {"estop": "DISENGAGED", "door_open": False, "is_error_state": False})
        self.assertEqual(self.configure(client, lights_button=True)["status"], "completed")
        self.assertEqual(self.configure(client, lights_rails=True)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["lights_button"], state["lights_rails"]), (True, True))
        self.assertEqual(self.configure(client, lights_button=False)["status"], "completed")
        self.assertEqual(self.state(client)["lights_button"], False)
        self.assertEqual(self.state(client)["lights_rails"], True)

    def test_the_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_allows_and_bounds_the_move(self) -> None:
        client = self.serve(SITE)
        moved = self.move(client)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["position"], {"x": 100.0, "y": 100.0, "z": 100.0})
        for x, y, z in ((-0.5, 100.0, 100.0), (100.0, 400.5, 100.0), (100.0, 100.0, 400.5)):
            refused = self.move(client, x, y, z)
            self.assertEqual(refused["status"], "rejected", (x, y, z))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (x, y, z))

    def test_home_completes(self) -> None:
        client = self.serve()
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True})

    def test_the_halt_action_gates_motion_until_a_full_home(self) -> None:
        # flex_motion.py:291-305 and recovery_state.py:47-54: a halt requires a full home; move_to is refused
        # (flex_motion.py:260, 496-499) until home(axes=None) clears the gate (flex_motion.py:247-248).
        driver, client = self.serve_driver()
        self.assertEqual(self.move(client)["status"], "completed")
        stopped = client.invoke(HALT, {}, **self.ids)
        self.assertEqual((stopped["status"], stopped["output"]), ("completed", {"stopped": True}))
        self.assertTrue(driver.native._rehome_required)
        refused = self.move(client, 110.0, 90.0, 120.0)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", PRECONDITION), refused)
        self.assertEqual(driver.native._position.x, 100.0)          # the refused move changed nothing
        self.assertEqual(client.invoke(HOME, {}, **self.ids)["status"], "completed")
        self.assertFalse(driver.native._rehome_required)
        self.assertEqual(self.move(client, 110.0, 90.0, 120.0)["status"], "completed")

    def test_the_stop_action_halts_and_the_estop_latches(self) -> None:
        client = self.serve()
        stopped = client.invoke(HALT, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"]["stopped"], True)
        client.estop("test", **self.ids)
        refused = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_estop_reaches_the_native_halt(self) -> None:
        driver, client = self.serve_driver()
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertGreaterEqual(driver.native._stops, 1)
        self.assertTrue(driver.native._rehome_required)

    def test_the_reenable_is_refused_while_latched_with_nothing_sent(self) -> None:
        driver, client = self.serve_driver()
        client.estop("test", **self.ids)
        refused = client.invoke(HOME, {}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(driver.native._homes, 0)
        self.assertTrue(driver.native._rehome_required)

    def test_the_reset_rearms_nothing_and_names_the_reenable(self) -> None:
        driver, client = self.serve_driver()
        client.estop("test", **self.ids)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["reenable"], HOME)
        self.assertIs(reset["output"]["resumed"], False)
        self.assertEqual(driver.native._homes, 0)                    # SAFE-042: the reset moved nothing
        self.assertTrue(driver.native._rehome_required)
        refused = self.move(client)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", PRECONDITION), refused)
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual((homed["status"], homed["output"]), ("completed", {"homed": True}))
        self.assertEqual(driver.native._homes, 1)
        self.assertEqual(self.move(client)["status"], "completed")

    def test_the_reenable_is_declared_and_never_a_safe_state_action(self) -> None:
        client = self.serve()
        manifest = next(item for item in client.devices() if item["device_id"] == self.ids["device_id"])
        self.assertEqual(manifest["safety"]["estop"]["reenable"], HOME)
        self.assertNotIn(HOME, manifest["safety"]["safe_state"]["achieved_by"])
        self.assertIn(HALT, manifest["safety"]["safe_state"]["achieved_by"])


if __name__ == "__main__":
    unittest.main()
