"""Acceptance run of the SharpaWave in-hand rotation package: the gate, plus cases specific to this driver.

The cases run on the fake backend (fake.py).  Isaac Lab, Isaac Sim and a GPU are not available where the gate runs,
so nothing here compares the fake with the upstream environment; the driver's fidelity gaps say what is omitted.
Add cases, never remove the check_driver call.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


def joint_observation(values):
    """The last 64-value frame of the 192-value policy observation."""
    return list(values[-64:])


def policy_values(receipt):
    return receipt["output"]["observation"]["policy"]["values"]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SharpaWaveCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_reset_is_repeatable_for_a_seed(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["seed"], 11)
        values = policy_values(first)
        self.assertEqual(len(values), 192)
        again = self.reset(client, seed=11)
        self.assertEqual(policy_values(again), values)
        different = self.reset(client, seed=12)
        self.assertNotEqual(policy_values(different), values)

    def test_a_step_advances_the_target_and_the_tick(self) -> None:
        client = self.serve()
        start = policy_values(self.reset(client, seed=5))
        start_frame = joint_observation(start)
        receipt = self.step(client, [1.0] * 22)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        frame = joint_observation(policy_values(receipt))
        # sharpa_wave_env.py:177-185 and sharpa_wave_env_cfg.py:52: the target advances by action_scale 1/24 and
        # the fake's first-order joint lag (a placeholder) moves the joint by 0.4 of the target step.
        for index in range(22):
            initial_target = start_frame[22 + index]
            self.assertAlmostEqual(frame[22 + index], initial_target + 1.0 / 24.0, places=9)
            self.assertAlmostEqual(frame[index], (initial_target + 0.4 / 24.0) / math.pi, places=9)
            self.assertAlmostEqual(frame[44 + index % 5], 0.0, places=9)   # tactile channels are not modelled
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_internal_action_saturation_is_applied(self) -> None:
        client = self.serve()
        start = joint_observation(policy_values(self.reset(client, seed=2)))
        receipt = self.step(client, [100.0] * 22)
        self.assertEqual(receipt["status"], "completed")
        frame = joint_observation(policy_values(receipt))
        # The action space is unbounded but the fake applies clip_actions 1.0 (sharpa_wave_env.py:178), so the
        # target advances by 1/24, not 100/24.
        self.assertAlmostEqual(frame[22] - start[22], 1.0 / 24.0, places=9)

    def test_a_wrong_action_length_is_refused_before_the_native_step(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.0] * 21}},
                                **self.ids)
        self.assertIn(refused["status"], ("rejected", "failed"))
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_reward_is_the_configured_sum_of_the_terms(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, [0.5] * 22)
        state = self.state(client)
        info = state["info"]
        expected = (info["rotate_reward"] * 2.5
                    + info["object_linvel_penalty"] * -0.3
                    + info["pos_diff_penalty"] * -0.4
                    + info["torque_penalty"] * -0.1
                    + info["work_penalty"] * -0.5
                    + info["object_pos_diff"] * 0.003)
        self.assertAlmostEqual(receipt["output"]["reward"], expected, places=9)
        self.assertAlmostEqual(info["total_reward"], expected, places=9)
        self.assertEqual((info["height_reset_upper"], info["height_reset_lower"], info["time_out"]),
                         (0.0, 0.0, 0.0))
        self.assertAlmostEqual(info["gravity_z"], -0.05)

    def test_the_fake_episode_uses_the_upstream_counter_threshold(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        before = self.step(client, [0.0] * 22, ticks=398)
        self.assertEqual(before["status"], "completed")
        self.assertEqual((before["output"]["tick"], before["output"]["truncated"]), (398, False))
        receipt = self.step(client, [0.0] * 22)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # The configured maximum is 400; _get_dones compares episode_length_buf >= maximum - 1 (env.py:255).
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (399, False, True))
        ended = self.step(client, [0.0] * 22)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(policy_values(receipt)), 192)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "analytic:sharpa-wave-inhand-rotate-fake")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation_and_the_safety_reset_clears_it(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 22)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 22), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced
        self.assertEqual(client.reset(**self.ids)["status"], "completed")   # safety reset, not cap.world.reset
        self.assertEqual(self.step(client, [0.0] * 22)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
