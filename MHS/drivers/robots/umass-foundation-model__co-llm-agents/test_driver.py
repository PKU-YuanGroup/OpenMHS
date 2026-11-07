"""Acceptance run of the TDW-MAT package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py): the gate cannot
install TDW, the ThreeDWorld build or the transport-challenge assets, so nothing here compares the fake with the
upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


def single_action(kind=0, object_id=0, arm=0, message=""):
    """One action of the single-agent space; the bridge takes it under the agent id "0"."""
    return {"type": kind, "object": object_id, "arm": arm, "message": message}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TDWCases(unittest.TestCase):
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

    def step(self, client, kind=0, object_id=0, arm=0, message="", ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": single_action(kind, object_id, arm, message)}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, kind=0)["status"], "completed")
        for refused in (self.step(client, kind=7), self.step(client, object_id=30),
                        self.step(client, arm=2)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_observation_shape_follows_the_single_agent_space(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]
        agent = observation["0"]
        self.assertEqual(len(agent["rgb"]["values"]), 3)         # rgb (3, w, h), tdw_gym.py:120
        self.assertEqual(len(agent["rgb"]["values"][0]), 2)      # the fake's 2x2 frame, see the fidelity gaps
        self.assertEqual(len(agent["agent"]["values"]), 6)       # the pose Box(-30, 30, (6,)), tdw_gym.py:123
        self.assertEqual(len(agent["visible_objects"]["items"]), 50)   # tdw_gym.py:126
        self.assertEqual(len(agent["held_objects"]["items"]), 2)       # tdw_gym.py:124
        self.assertEqual(agent["FOV"]["values"], [90.0])               # tdw_gym.py:251
        self.assertEqual(agent["current_frames"]["index"], 0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                              # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, kind=action)["output"]["state_hash"] for action in (0, 1, 2, 0, 1)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_a_move_changes_the_pose(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=5)["output"]["observation"]["0"]["agent"]["values"]
        after = self.step(client, kind=0)["output"]["observation"]["0"]["agent"]["values"]
        self.assertAlmostEqual(after[0] - before[0], 0.0, places=9)       # yaw 0: x stays, z grows
        self.assertAlmostEqual(after[2] - before[2], 0.5, places=9)       # tdw_gym.py:628

    def test_grasp_and_put_in_end_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        grasped = self.step(client, kind=3, object_id=0, arm=0)
        self.assertEqual(grasped["status"], "completed")
        held = grasped["output"]["observation"]["0"]["held_objects"]["items"][0]
        self.assertEqual(held["id"]["index"], 0)
        delivered = self.step(client, kind=4, object_id=0, arm=0)
        self.assertEqual(delivered["status"], "completed")
        self.assertEqual((delivered["output"]["terminated"], delivered["output"]["truncated"]), (True, False))
        ended = self.step(client, kind=0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")

    def test_the_action_contract_is_the_declared_single_agent_space(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        step = next(item for item in device["capabilities"] if item["capability_id"] == "cap.world.step.v1")
        action = step["input_schema"]["properties"]["action"]
        self.assertEqual(sorted(action["properties"]), ["arm", "message", "object", "type"])
        self.assertEqual(action["properties"]["type"]["maximum"], 6)     # Discrete(7), tdw_gym.py:105
        self.assertEqual(action["properties"]["object"]["maximum"], 29)  # Discrete(30), tdw_gym.py:106
        self.assertEqual(action["properties"]["arm"]["maximum"], 1)      # Discrete(2), tdw_gym.py:107
        self.assertEqual(sorted(step["limits"]), ["action.arm", "action.object", "action.type"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, kind=0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, kind=0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
