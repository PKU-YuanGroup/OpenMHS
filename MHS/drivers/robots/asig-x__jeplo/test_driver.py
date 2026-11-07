"""Acceptance run of the JEPLO Unitree Go2 package: the gate, plus cases for this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the package fake backend (fake.py): the upstream
Isaac Sim / Isaac Lab stack was not available where the gate runs, so nothing here compares the fake with the real
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class JeploGo2Cases(unittest.TestCase):
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

    def test_the_fake_is_a_world_simulator(self) -> None:
        client = self.serve()
        hello = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        self.assertEqual((hello["mode"], hello["risk_class"]), ("simulated", "R0"))
        self.assertEqual([item["kind"] for item in device["resources"]], ["world.sim"])

    def test_a_step_reaches_the_fake_and_moves_the_joint_state(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["policy"]["values"]
        receipt = self.step(client, [1.0] * 12)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        moved = output["observation"]["policy"]["values"]
        # go2_loco_env_cfg.py:179-180 and go2_loco_env.py:469-473: target = home + 0.25 * action
        self.assertAlmostEqual(moved[0], start[0] + 0.25, places=7)
        self.assertEqual(moved[12:], [0.0] * (len(moved) - 12))       # placeholder tail of the policy group
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_configured_joint_target_clip_is_applied(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        output = self.step(client, [1e6] * 12)["output"]
        self.assertEqual(output["observation"]["policy"]["values"][:12], [100.0] * 12)

    def test_the_action_box_has_the_upstream_width_and_no_finite_bound(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        self.assertEqual(self.step(client, [1e6] * 12)["status"], "completed")
        for values in ([], [0.0] * 11, [0.0] * 13):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", len(values))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(values))
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_ticks_are_bounded_by_the_world_class(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        for ticks in (0, 10001):
            refused = self.step(client, [0.0] * 12, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)                 # the refused steps changed nothing

    def test_the_observation_has_the_upstream_widths(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=2)["output"]["observation"]
        policy = observation["policy"]["values"]
        depth = observation["depth"]["values"]
        self.assertEqual(len(policy), 10 * 45 + 300 + 50 + 45)
        self.assertEqual((len(depth), len(depth[0]), len(depth[0][0])), (2, 25, 60))

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        other = self.reset(client, seed=12)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertNotEqual(first["observation"], other["observation"])
        self.assertEqual((first["seed"], other["seed"]), (11, 12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_passed_through(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 2)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        fidelity = client.inspect(self.ids["device_id"])["fidelity"]
        self.assertEqual(fidelity["engine"], "isaaclab:Unitree-Go2-Locomotion")
        self.assertEqual((fidelity["fidelity_level"], fidelity["timestep_ms"]), ("F0", 20.0))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 12)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 12), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
