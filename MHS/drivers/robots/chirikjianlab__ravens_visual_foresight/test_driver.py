"""Acceptance run of the Ravens Visual Foresight package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): pybullet, gym and the
upstream assets are not installed where the gate runs, so nothing here compares the fake with the upstream simulator.
"""

import importlib.util
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

_spec = importlib.util.spec_from_file_location("ravens_visual_foresight_fake", HERE / "fake.py")
_fake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fake)
FakeEnvironmentMCTS = _fake.FakeEnvironmentMCTS


def layout(seed):
    """The fake's seeded block and target layout; the probe uses the same seed through the server."""
    probe = FakeEnvironmentMCTS()
    probe.seed(seed)
    probe.reset()
    return [list(position) for position in probe.block_positions], [list(target) for target in probe.targets]


def pose(position):
    return [list(position), [0.0, 0.0, 0.0, 1.0]]


def place_action(pick_position, place_position):
    return {"pose0": pose(pick_position), "pose1": pose(place_position)}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RavensCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=None):
        fields = {} if seed is None else {"seed": seed}
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_native_shapes_are_preserved(self) -> None:
        probe = FakeEnvironmentMCTS()
        probe.seed(3)
        reset_result = probe.reset()
        self.assertEqual(len(reset_result), 6)
        self.assertIsInstance(reset_result[0], dict)
        self.assertEqual(len(reset_result[0]["color"]), 3)
        self.assertEqual(len(reset_result[0]["color"][0]), 8)
        action = place_action(probe.block_positions[0], probe.targets[0])
        step_result = probe.step(action)
        self.assertEqual(len(step_result), 4)
        self.assertEqual(len(step_result[0]), 2)
        self.assertIsNotNone(step_result[0][1])
        self.assertGreater(step_result[1], 0.0)
        self.assertFalse(step_result[2])

    def test_reset_and_step_publish_the_observation(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=5)
        self.assertEqual(reset["status"], "completed", reset)
        observation = reset["output"]["observation"]
        self.assertEqual(len(observation["color"]["items"]), 3)
        self.assertEqual(len(observation["depth"]["items"]), 3)
        self.assertEqual(len(observation["color"]["items"][0]["values"]), 8)
        blocks, targets = layout(5)
        receipt = self.step(client, place_action(blocks[0], targets[0]))
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertAlmostEqual(output["reward"], 1.0 / 3.0)
        self.assertEqual(len(output["observation"]["values"]), 2)
        self.assertEqual(len(output["observation"]["values"][0]["color"]), 3)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_all_three_blocks_terminate_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        blocks, targets = layout(5)
        total = 0.0
        output = None
        for index, (block, target) in enumerate(zip(blocks, targets)):
            receipt = self.step(client, place_action(block, target))
            self.assertEqual(receipt["status"], "completed", receipt)
            output = receipt["output"]
            total += output["reward"]
            self.assertEqual(output["terminated"], index == 2)
        self.assertAlmostEqual(total, 1.0)
        self.assertEqual(output["tick"], 3)
        refused = self.step(client, place_action(blocks[0], targets[0]))
        self.assertEqual(refused["status"], "failed")

    def test_a_seed_repeats_the_layout(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=9)["output"]["observation"]
        second = self.reset(client, seed=9)["output"]["observation"]
        self.assertEqual(first, second)
        other = self.reset(client, seed=10)["output"]["observation"]
        self.assertNotEqual(first, other)

    def test_pose_shape_and_source_bounds_are_checked_before_dispatch(self) -> None:
        import copy

        client = self.serve()
        self.reset(client, seed=5)
        before = self.state(client)
        blocks, targets = layout(5)
        valid = place_action(blocks[0], targets[0])
        cases = []
        for name in ("pose0", "pose1"):
            for index, value in ((0, 0.24), (0, 0.76), (1, -0.51), (1, 0.51),
                                 (2, -0.01), (2, 0.29)):
                payload = copy.deepcopy(valid)
                payload[name][0][index] = value
                cases.append((payload, "MHS.SAFETY.ENVELOPE_VIOLATION"))
            for value in (-1.01, 1.01):
                payload = copy.deepcopy(valid)
                payload[name][1][0] = value
                cases.append((payload, "MHS.SAFETY.ENVELOPE_VIOLATION"))
            for part, invalid in ((0, [0.5, 0.0]), (1, [0.0, 0.0, 1.0]), (0, ["bad", 0.0, 0.1])):
                payload = copy.deepcopy(valid)
                payload[name][part] = invalid
                cases.append((payload, "MHS.CAPABILITY.INPUT_INVALID"))
        for payload, code in cases:
            refused = self.step(client, payload)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", code), payload)
            self.assertEqual(self.state(client), before)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 13}, **self.ids)
        self.assertEqual((accepted["status"], accepted["output"]["accepted"]), ("completed", True))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 13)
        second = self.reset(client, seed=13)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        self.assertEqual(device["mode"], "simulated")
        fidelity = device["fidelity"]
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        before = self.state(client)
        client.estop("test", **self.ids)
        blocks, targets = layout(2)
        for refused in (self.step(client, place_action(blocks[0], targets[0])), self.reset(client, seed=2)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client), before)


if __name__ == "__main__":
    unittest.main()
