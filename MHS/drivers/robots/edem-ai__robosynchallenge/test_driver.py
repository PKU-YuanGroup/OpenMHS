"""Acceptance run of the ClickBell package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): EmbodiChain, dexsim,
torch, the CobotMagic assets and a CUDA/Vulkan GPU are not installed where the gate runs, so nothing here compares the
fake with the upstream environment or claims a simulation run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0] * 14}
ACTION_SIZE = 14
MAX_EPISODE_STEPS = 361


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ClickBellCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or ZERO_ACTION}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def observation(self, receipt):
        return receipt["output"]["observation"]["robot/qpos"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for values in ([1.5] + [0.0] * (ACTION_SIZE - 1), [0.0] * (ACTION_SIZE - 1) + [-1.5]):
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_action_size_is_the_14_active_joints(self) -> None:
        client = self.serve()
        refused = self.step(client, {"values": [0.0] * (ACTION_SIZE - 1)})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_observation_carries_robot_qpos(self) -> None:
        client = self.serve()
        values = self.observation(self.reset(client, seed=1))
        self.assertEqual(len(values), ACTION_SIZE)
        action = {"values": [0.125 * (index - 7) for index in range(ACTION_SIZE)]}
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.observation(receipt), action["values"])
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_seed_repeats_the_start_state(self) -> None:
        def observation(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.observation(self.reset(client, seed=seed))

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_button_metric_is_computed_and_success_is_not_claimed(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client)
        output = receipt["output"]
        info = self.state(client)["info"]
        # click_bell.py:135-150: press_depth = -button_qpos, threshold 0.0048, and the fake has no robot to move it.
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))
        self.assertEqual(info["press_depth"], 0.0)
        self.assertEqual(info["movement_threshold"], 0.0048)
        self.assertEqual(info["is_success"], False)

    def test_the_deployed_step_limit_truncates_at_361(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = None
        for _ in range(MAX_EPISODE_STEPS):
            receipt = self.step(client)
            self.assertEqual(receipt["status"], "completed", receipt)
            output = receipt["output"]
        # configs/click_bell/random/gym_config.json:4 sets max_episode_steps 361 for the deployed random protocol.
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (MAX_EPISODE_STEPS, False, True))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("embodichain:robosynchallenge/ClickBell", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        before = self.state(client)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 1}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced
        released = client.reset(**self.ids)
        self.assertEqual(released["status"], "completed", released)
        self.assertEqual(self.state(client), before)                            # latch reset resumes nothing
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
