"""Acceptance run of the REALRobot package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); gym, pybullet and the
upstream package are not installed where the gate runs, so nothing here compares the fake with the PyBullet
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_COMMAND = [0.0] * 9
ZERO_ACTION = {"joint_command": ZERO_COMMAND, "render": [0]}
# env.py:314-321: the largest change of each joint accepted in one step.
MAX_CHANGE = [0.2, 0.2, 0.2, 0.2, 0.2, 0.3, 0.3, 0.1, 0.1]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RealRobotCases(unittest.TestCase):
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
        payload = {"ticks": ticks, "action": dict(action or ZERO_ACTION)}
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        outside_joint = {"joint_command": [3.0] + ZERO_COMMAND[1:], "render": [0]}
        outside_render = {"joint_command": ZERO_COMMAND, "render": [2]}
        for action in (outside_joint, outside_render):
            refused = self.step(client, action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, action)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_per_step_change_is_clamped(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        receipt = self.step(client, {"joint_command": [1.0] * 9, "render": [0]})
        self.assertEqual(receipt["status"], "completed")
        applied = receipt["output"]["observation"]["joint_positions"]["values"]
        for got, expected in zip(applied, MAX_CHANGE):
            self.assertAlmostEqual(got, expected, places=12)
        self.assertEqual(receipt["output"]["reward"], 0.0)
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_the_render_flag_selects_the_camera(self) -> None:
        client = self.serve()
        self.reset(client, seed=0)
        dark = self.step(client, {"joint_command": ZERO_COMMAND, "render": [0]})["output"]
        lit = self.step(client, {"joint_command": ZERO_COMMAND, "render": [1]})["output"]
        self.assertEqual(_total(dark["observation"]["retina"]["values"]), 0)
        self.assertGreater(_total(lit["observation"]["retina"]["values"]), 0)

    def test_a_seed_repeats_the_tabletop_state(self) -> None:
        client = self.serve()

        def objects(seed):
            return self.reset(client, seed=seed)["output"]["observation"]["object_positions"]

        first = objects(11)
        self.assertEqual(objects(11), first)
        self.assertNotEqual(objects(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_observation_has_the_extended_fields(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=0)["output"]["observation"]
        self.assertEqual(set(observation), {
            "joint_positions", "touch_sensors", "retina", "depth", "goal", "mask",
            "object_positions", "goal_mask", "goal_positions",
        })
        self.assertEqual(len(observation["joint_positions"]["values"]), 9)
        self.assertEqual(len(observation["touch_sensors"]["values"]), 4)
        retina = observation["retina"]["values"]
        self.assertEqual((len(retina), len(retina[0]), len(retina[0][0])), (24, 32, 3))
        self.assertEqual((len(observation["depth"]["values"]), len(observation["depth"]["values"][0])), (24, 32))
        self.assertEqual(set(observation["object_positions"]), {"cube", "tomato", "mustard"})

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet:REALRobot2020", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


def _total(values):
    if isinstance(values, (list, tuple)):
        return sum(_total(item) for item in values)
    return values


if __name__ == "__main__":
    unittest.main()
