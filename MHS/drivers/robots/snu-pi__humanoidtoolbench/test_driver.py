"""Acceptance run of the HumanoidToolBench package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call. The cases run on the fake backend (fake.py): MuJoCo, torch, gear_sonic
and humanoidtoolbench are not installed where the gate runs, so nothing here compares the fake with the upstream
environment. The action and observation shapes are the clone's; the fake's dynamics are placeholders and only their
structure is checked.
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
MAX_EPISODE_STEPS = 3000
JOINT_GROUPS = (
    ("left_leg", 6),
    ("right_leg", 6),
    ("waist", 3),
    ("left_arm", 7),
    ("right_arm", 7),
    ("left_eef", 7),
    ("right_eef", 7),
)
WHOLE_BODY_DOF = sum(size for _, size in JOINT_GROUPS)


def action(**overrides):
    """A complete controller action: every group is present, with the requested overrides."""
    out = {name: [0.0] * size for name, size in JOINT_GROUPS}
    out.update(overrides)
    return out


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HumanoidToolBenchCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": values}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def qpos(self, receipt):
        return receipt["output"]["observation"]["joint_qpos"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action())["status"], "completed")
        for values in (action(left_leg=[1.5, 0.0, 0.0, 0.0, 0.0, 0.0]),
                       action(left_eef=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, math.pi + 0.5]),
                       action(waist=[0.0, -1.1, 0.0])):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_reset_returns_the_43_joint_positions(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["seed"], 7)
        values = output["observation"]["joint_qpos"]["values"]
        self.assertEqual(len(values), WHOLE_BODY_DOF)                   # robots/g1_sonic.py:118
        self.assertEqual(values, [0.0] * WHOLE_BODY_DOF)                # controller init_qpos is zero
        self.assertEqual(self.state(client)["observation"], output["observation"])

    def test_a_step_applies_the_action_and_advances_the_tick(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, action(left_leg=[0.1] * 6, right_eef=[0.2] * 7), ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (2, False, False))
        values = self.qpos(receipt)
        self.assertEqual(values[:6], [0.1] * 6)
        self.assertEqual(values[-7:], [0.2] * 7)
        self.assertEqual(values[6:36], [0.0] * 30)
        self.assertEqual(output["reward"], 0.0)                         # placeholder of the fake
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual(first["seed"], 11)
        other = self.reset(client, seed=12)["output"]
        self.assertEqual(other["seed"], 12)
        self.assertEqual(other["observation"], first["observation"])    # the fake has no layout draw

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((receipt["status"], receipt["output"]), ("completed", {"seed": 21, "accepted": True}))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_registered_limit_truncates_at_3000_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, action(), ticks=MAX_EPISODE_STEPS)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]),
                         (MAX_EPISODE_STEPS, False, True))              # envs/__init__.py:27-37
        ended = self.step(client, action())
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:humanoidtoolbench/G1BallMove-L0-S", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual(fidelity["timestep_ms"], 5.0)                  # 0.005 s physics step
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_observation_stays_inside_its_space(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        receipt = self.step(client, action(left_arm=[0.9] * 7, left_eef=[3.0] * 7))
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(all(-math.pi <= value <= math.pi for value in self.qpos(receipt)))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, action()), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
