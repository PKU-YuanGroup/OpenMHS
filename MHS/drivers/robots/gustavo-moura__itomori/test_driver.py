"""Acceptance run of the itomori package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gymnasium, scipy,
pygame and matplotlib are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.  The equations of the first step were checked by hand against navigation2d.py:325-345.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Navigation2DCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        for values in ([-10.1, 0.0], [10.1, 0.0], [0.0, -10.1], [0.0, 100.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_first_step_matches_the_equations_of_motion(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [10.0, 100.0])
        self.assertEqual(receipt["status"], "completed")
        # by hand from navigation2d.py:325-345 with the start [1, 1, 0, 0], ac=10.0 rad/s and vc=100.0 m/s**2:
        # v = 100*0.1 = 10, a = 10*0.1 = 1 rad, x = y = 1 + 1.5*cos(1) / 1.5*sin(1)
        x, y, velocity, angle, risk, gps = receipt["output"]["observation"]["agent_location"]["values"]
        self.assertAlmostEqual(velocity, 10.0, places=12)
        self.assertAlmostEqual(angle, 1.0, places=12)
        self.assertAlmostEqual(x, 1.0 + 1.5 * math.cos(1.0), places=12)
        self.assertAlmostEqual(y, 1.0 + 1.5 * math.sin(1.0), places=12)
        self.assertEqual((risk, gps), (0.0, 0.52))
        distance = math.hypot(9.0 - x, 9.0 - y)
        self.assertAlmostEqual(receipt["output"]["reward"], 0.9 * distance + 0.1 * 2, places=12)
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, False))
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_reset_starts_at_the_map_origin(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(output["seed"], 7)
        observation = output["observation"]
        self.assertEqual(observation["origin"]["values"], [1.0, 1.0])
        self.assertEqual(observation["destination"]["values"], [9.0, 9.0])
        self.assertEqual(observation["agent_location"]["values"], [1.0, 1.0, 0.0, 0.0, 0.0, 0.5])
        info = self.state(client)["info"]
        self.assertEqual(info["destination_tolerance"], 1.5)
        self.assertEqual(info["failed"], False)
        self.assertEqual(info["obstacles"], [])

    def test_a_seed_repeats_the_start_and_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual(self.reset(client, seed=12)["output"]["observation"], first["observation"])
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_reaching_the_destination_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        # turn to 45 degrees (ac = pi/4 / 0.1) once, then keep vc=100 so the point runs to (9, 9)
        receipt = self.step(client, [math.pi / 4 / 0.1, 100.0])
        self.assertEqual(receipt["status"], "completed")
        for expected_tick in (2, 3, 4):
            receipt = self.step(client, [0.0, 100.0])
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
            if output["terminated"]:
                break
        x, y, velocity, angle, risk, gps = output["observation"]["agent_location"]["values"]
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertAlmostEqual(velocity, 40.0, places=12)
        self.assertAlmostEqual(angle, math.pi / 4, places=12)
        self.assertAlmostEqual(x, 9.485281374238571, places=10)
        self.assertAlmostEqual(y, 9.485281374238571, places=10)
        self.assertAlmostEqual(gps, 0.58, places=12)
        self.assertAlmostEqual(output["reward"], 0.9 * math.hypot(9.0 - x, 9.0 - y) + 0.5, places=12)
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_out_of_bounds_step_fails_the_environment(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        # due east from (1, 1): x is 2.5, 5.0 and 8.5 after the first three steps, then clipping puts it at 10,
        # where is_outofbounds() is true and reward() is math.inf; the bridge reports that as a failed step
        for expected_tick in (1, 2, 3):
            self.assertEqual(self.step(client, [0.0, 100.0])["status"], "completed", expected_tick)
        failed = self.step(client, [0.0, 100.0])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"]["mhs_code"], "MHS.DEVICE.FAULTED")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("itomori:Navigation2DEnv-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertTrue(any("no mass" in gap for gap in fidelity["gaps"]))
        self.assertTrue(any("map_filepath" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
