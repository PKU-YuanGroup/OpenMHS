"""Acceptance run of the MolmoSpaces package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend only.  The fake is an analytic stand-in for the GymEnv wrapper, not a MuJoCo
run, so nothing here compares it with the upstream simulator.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ARM = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
GRIPPER = [0.01, 0.02]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MolmoSpacesCases(unittest.TestCase):
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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_one_batch_element_and_the_seed(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=11)["output"]
        self.assertEqual(output["seed"], 11)
        observations = output["observation"]["values"]
        self.assertEqual(len(observations), 1)                      # GymEnv is single-environment only
        self.assertEqual(sorted(observations[0]), ["qpos"])
        self.assertEqual(len(observations[0]["qpos"]["arm"]), 7)    # Franka arm joints
        self.assertEqual(len(observations[0]["qpos"]["gripper"]), 2)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["seed"]), (0, 1, 11))

    def test_step_advances_the_tick_and_applies_the_move_group(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, {"arm": ARM, "gripper": GRIPPER})
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        qpos = output["observation"]["values"][0]["qpos"]
        self.assertEqual(qpos["arm"], ARM)
        self.assertEqual(qpos["gripper"], GRIPPER)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]
        self.assertEqual(accepted, {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            # an empty action keeps the sampled qpos, so the seed stays visible in the step hashes
            return [self.step(client, {})["output"]["state_hash"] for _ in range(3)]

        first = trajectory(5)
        self.assertEqual(trajectory(5), first)
        self.assertNotEqual(trajectory(6), first)

    def test_an_unknown_reset_option_is_refused(self) -> None:
        client = self.serve()
        refused = self.reset(client, options={"variant": "ceiling"})
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.FAULTED")
        self.assertEqual(self.reset(client, options={"house_index": 1})["status"], "completed")
        self.assertEqual(self.reset(client, options={"force_advance_scene": True})["status"], "completed")

    def test_the_task_horizon_truncates(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        output = self.step(client, {"arm": ARM, "gripper": GRIPPER}, ticks=500)["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 500))
        self.assertEqual(output["reward"], 0.0)                     # the fake models no lift
        ended = self.step(client, {"arm": ARM, "gripper": GRIPPER})
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_out_of_shape_move_group_is_refused(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, {"arm": [0.0, 0.0]})
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED")
        self.assertEqual(self.state(client)["tick"], 0)             # the failed step advanced nothing

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")           # the fake is an analytic wrapper
        self.assertIn("molmo_spaces", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"arm": ARM, "gripper": GRIPPER})["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, {"arm": ARM, "gripper": GRIPPER}), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced

    def test_ticks_are_bounded_by_the_family_schema(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        refused = self.step(client, {"arm": ARM, "gripper": GRIPPER}, ticks=0)
        self.assertIn(refused["error"]["mhs_code"], (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"))
        self.assertEqual(self.state(client)["tick"], 0)


if __name__ == "__main__":
    unittest.main()
