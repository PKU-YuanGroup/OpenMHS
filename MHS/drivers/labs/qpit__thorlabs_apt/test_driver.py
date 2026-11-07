"""Acceptance run of the thorlabs_apt package: the gate, plus cases for what is specific to this driver.

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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ThorlabsAptCases(unittest.TestCase):
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

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_the_reads_show_the_fake_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position"], 0.0)
        self.assertEqual(state["serial_number"], 12345678)          # fake test identity, not a device fact
        self.assertEqual(state["stage_minimum"], -10.0)             # fake test data
        self.assertEqual(state["stage_maximum"], 10.0)              # fake test data
        self.assertEqual(state["stage_units"], 1)                   # fake test data
        self.assertEqual(state["velocity_maximum"], 5.0)            # fake test data
        self.assertEqual(state["acceleration"], 1.0)                # fake test data
        self.assertEqual((state["enabled"], state["in_motion"], state["settled"]), (False, False, True))
        self.assertEqual((state["reverse_limit_switch"], state["forward_limit_switch"]), (1, 1))
        self.assertEqual((state["move_home_direction"], state["move_home_lim_switch"]), (1, 1))

    def test_the_move_and_velocity_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.invoke(client, "x-cap.qpit.move_to.v1", {"position": 1.0})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        refused = self.configure(client, velocity_maximum=2.5)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 0.0)

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def test_the_example_overlay_moves_the_axis(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.invoke(client, "x-cap.qpit.move_to.v1", {"position": 5.0})
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"position": 5.0, "in_motion": True})
        self.assertEqual(self.state(client)["position"], 5.0)
        self.assertEqual(self.invoke(client, "x-cap.qpit.move_by.v1", {"distance": -2.0})["status"],
                         "completed")
        self.assertEqual(self.state(client)["position"], 3.0)
        refused = self.invoke(client, "x-cap.qpit.move_to.v1", {"position": 25.5})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        stopped = self.invoke(client, "x-cap.qpit.stop.v1")
        self.assertEqual(stopped["output"], {"stopped": True})
        self.assertFalse(self.state(client)["in_motion"])

    def test_the_velocity_direction_is_a_closed_set(self) -> None:
        client = self.serve()
        moved = self.invoke(client, "x-cap.qpit.move_velocity.v1", {"direction": 1})
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"direction": 1, "in_motion": True})
        refused = self.invoke(client, "x-cap.qpit.move_velocity.v1", {"direction": 3})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_configuration_writes_reach_the_fake(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, reverse_limit_switch=2)["status"], "completed")
        self.assertEqual(self.state(client)["reverse_limit_switch"], 2)
        self.assertEqual(self.configure(client, forward_limit_switch=5)["status"], "completed")
        self.assertEqual(self.state(client)["forward_limit_switch"], 5)
        self.assertEqual(self.configure(client, move_home_direction=2)["status"], "completed")
        self.assertEqual(self.state(client)["move_home_direction"], 2)
        self.assertEqual(self.configure(client, move_home_lim_switch=4)["status"], "completed")
        self.assertEqual(self.state(client)["move_home_lim_switch"], 4)
        self.assertEqual(self.configure(client, velocity_maximum=2.5)["status"], "completed")
        self.assertEqual(self.state(client)["velocity_maximum"], 2.5)
        self.assertEqual(self.configure(client, acceleration=3.5)["status"], "completed")
        self.assertEqual(self.state(client)["acceleration"], 3.5)
        for patch in ({"reverse_limit_switch": 6}, {"forward_limit_switch": 0},
                      {"move_home_direction": 3}, {"move_home_lim_switch": 2}):
            self.assertEqual(self.configure(client, **patch)["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_channel_and_homing_actions(self) -> None:
        client = self.serve()
        self.assertEqual(self.invoke(client, "x-cap.qpit.enable.v1")["output"], {"enabled": True})
        homed = self.invoke(client, "x-cap.qpit.move_home.v1")
        self.assertEqual(homed["status"], "completed", homed)
        self.assertTrue(homed["output"]["homed"])
        self.assertEqual(self.state(client)["position"], 0.0)
        self.assertEqual(self.invoke(client, "x-cap.qpit.disable.v1")["output"], {"enabled": False})

    def test_the_estop_stops_motion_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.invoke(client, "x-cap.qpit.move_velocity.v1", {"direction": 2})["status"],
                         "completed")
        self.assertTrue(self.state(client)["in_motion"])
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["in_motion"])
        refused = self.invoke(client, "x-cap.qpit.move_velocity.v1", {"direction": 1})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
