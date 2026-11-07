"""Acceptance run of the GymFC package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): Gazebo, the C++ plugins and a digital twin are not available where the
gate runs, so nothing here compares the fake with the upstream simulator.  The fake reproduces the registered
environment's interface, spaces, action clipping, six-element state and 4.608 s episode; its motor mixing and rate
response are stand-ins.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
MAX_SIM_STEPS = 4608                 # 4.608 s / 0.001 s (registration and attitude.world:16)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GymFCCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        for values in ([-1.1, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.1], [0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertIn(refused["error"]["mhs_code"], (ENVELOPE, INPUT_INVALID), values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_returns_the_six_element_state_and_a_finite_reward(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [1.0, 0.0, 1.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 6)
        self.assertTrue(all(isinstance(value, float) for value in values), values)
        self.assertTrue(output["reward"] == output["reward"] and abs(output["reward"]) != float("inf"))
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertEqual(len(state["observation"]["values"]), 6)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            # the first pulse time is 0.512 s (step.py:43,60), so the sampled target enters the observation at
            # step 513 of the 1 ms episode; 600 ticks cover it
            output = self.step(client, [0.5, 0.5, 0.5, 0.5], ticks=600)["output"]
            return output["state_hash"], output["observation"]["values"]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_registered_episode_ends_after_4608_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.5, 0.5, 0.5, 0.5], ticks=MAX_SIM_STEPS)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # max_sim_time 4.608 s (registration) / max_step_size 0.001 s (attitude.world:16)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (MAX_SIM_STEPS, True, False))
        ended = self.step(client, [0.5, 0.5, 0.5, 0.5])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_reset_options_do_not_change_the_legacy_interface(self) -> None:
        client = self.serve()
        # BaseEnv.reset takes no seed/options; the bridge falls back to seed() + reset() (gymnasium bridge).
        self.assertEqual(self.reset(client, seed=5, options={"ignored": True})["status"], "completed")
        self.assertEqual(self.state(client)["seed"], 5)
        self.assertEqual(len(self.reset(client, seed=5)["output"]["observation"]["values"]), 6)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gazebo", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (1.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
