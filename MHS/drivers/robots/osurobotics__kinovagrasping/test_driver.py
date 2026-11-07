"""Acceptance run of the kinovagripper-v0 package: the gate, plus cases for this driver's fake contract.

The cases run on the fake backend only.  The fake is an analytic stand-in (fake.py), so the cases check the
contract the upstream class declares (its action space, seed handling, reset arguments and lift-reward rule) and
the published fidelity contract; they do not compare the fake with MuJoCo, which is not installed here.
"""

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


class KinovaGraspingCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        for values in ([-0.81, 0.0, 0.0, 0.0], [0.0, 0.81, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_a_step_changes_the_observation(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=5)["output"]["observation"]["values"]
        receipt = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["values"]
        self.assertEqual(len(before), 48)                                  # the declared observation Box
        self.assertEqual(len(after), 48)
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertNotEqual(after, before)                                 # the object lifts with the hand
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, False))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        actions = ([0.0, 0.0, 0.0, 0.0], [0.1, -0.1, 0.0, 0.2], [0.0, 0.0, 0.0, 0.0])

        def trajectory(seed):
            client = self.serve()                                          # a fresh world: the hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in actions]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_carry_the_legacy_arguments(self) -> None:
        client = self.serve()
        options = {"shape_keys": ["CubeS", "CylinderM"], "hand_orientation": "normal"}
        receipt = self.reset(client, seed=2, options=options)
        self.assertEqual(receipt["status"], "completed")
        info = self.state(client)["info"]
        self.assertEqual(info["shape_keys"], ["CubeS", "CylinderM"])
        self.assertEqual(info["hand_orientation"], "normal")

    def test_the_lift_reward_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [0.0, 0.0, 0.8, 0.0])
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 1))
        self.assertEqual(output["reward"], 50.0)                           # kinova_gripper_env.py:661-663
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (150.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
