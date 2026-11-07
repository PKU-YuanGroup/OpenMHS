"""Acceptance run of the ManiSkill-ViTac 2025 Track 1 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  Every case runs on the package fake (fake.py); the upstream SAPIEN/IPC
environment is never imported or run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PegInsertionCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, -1.5, 0.0], [0.0, 0.0, 1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_reset_seed_repeats_the_start_and_the_seed_class_sets_it(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first)
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"], first)
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        seeded = self.reset(client)["output"]
        self.assertEqual(seeded["seed"], 21)
        self.assertEqual(seeded["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_the_observation_has_the_marker_flow_shape(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(sorted(observation), ["gt_offset", "marker_flow", "relative_motion"])
        self.assertEqual(len(observation["relative_motion"]["values"]), 4)
        self.assertEqual(len(observation["gt_offset"]["values"]), 3)
        marker_flow = observation["marker_flow"]["values"]
        self.assertEqual(len(marker_flow), 2)
        self.assertEqual(len(marker_flow[0]), 2)
        self.assertEqual(len(marker_flow[0][0]), 128)
        self.assertEqual(len(marker_flow[0][0][0]), 2)

    def test_a_centred_insertion_terminates_at_the_depth_gate(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=5)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 5))
        self.assertEqual(output["reward"], 5.0)                                  # five step penalties plus final_reward
        next_episode = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual(next_episode["status"], "completed")
        self.assertEqual(next_episode["output"]["tick"], 1)                      # autoreset starts a full new episode
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_rotation_past_the_error_threshold_truncates_the_episode(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        theta = observation["gt_offset"]["values"][2]
        direction = 1.0 if theta >= 0.0 else -1.0
        expected_tick = next(n for n in range(1, 5) if abs(theta) + 4.0 * n > 15.0)
        receipt = self.reset(client, seed=5)
        self.assertEqual(receipt["status"], "completed")
        output = None
        for _ in range(8):
            receipt = self.step(client, [0.0, 0.0, direction])
            self.assertEqual(receipt["status"], "completed")
            output = receipt["output"]
            if output["terminated"] or output["truncated"]:
                break
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(output["tick"], expected_tick)                           # the first step past 15 degrees
        next_episode = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual(next_episode["status"], "completed")
        self.assertEqual(next_episode["output"]["tick"], 1)                      # autoreset starts a full new episode
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.hello()["devices"][0]
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["risk_class"], "R0")
        manifest = client.inspect(self.ids["device_id"])
        self.assertEqual(manifest["resources"][0]["kind"], "world.sim")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:PegInsertionRandomizedMarkerEnv-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
