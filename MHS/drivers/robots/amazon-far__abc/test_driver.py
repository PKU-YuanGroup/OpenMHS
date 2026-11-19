"""Acceptance run of the ABC YAM package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the package's fake backend (fake.py): the upstream
MuJoCo package and the simulator assets are not installed where the gate runs, so nothing here compares the fake with
the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION = [0.0] * 14


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class YAMCases(unittest.TestCase):
    def serve(self, **options):
        server = load(HERE, backend="fake", options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or ACTION}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_derived_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, values=[0.5] * 14)["status"], "completed")
        for values in ([1.5] + [0.0] * 13, [-1.5] + [0.0] * 13):
            refused = self.step(client, values=values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)        # the refused steps ran no native step

    def test_a_step_returns_the_documented_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, values=[0.25] * 14, ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, False, False))
        self.assertEqual(sorted(observation), ["camera_timestamps", "images", "masks", "prompt", "state"])
        self.assertEqual(observation["state"]["values"], [0.25] * 14)
        self.assertEqual(sorted(observation["images"]), ["left", "right", "top"])
        for name in ("left", "right", "top"):
            image = observation["images"][name]["values"]
            self.assertEqual((len(image), len(image[0]), len(image[0][0])), (3, 4, 4))
            self.assertEqual(observation["masks"][name]["index"], 1)
            self.assertAlmostEqual(observation["camera_timestamps"][name]["values"], 0.068)
        self.assertIsInstance(observation["prompt"]["value"], str)

    def test_reset_preserves_the_arm_pose(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        self.assertEqual(self.step(client, values=[0.5] * 14)["status"], "completed")
        after = self.reset(client, seed=4)["output"]
        # abc_sim/env.py:498-510: the next reset carries the current arm pose instead of init_q
        self.assertEqual(after["observation"]["state"]["values"], [0.5] * 14)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_forget_arm_state_drops_the_carried_pose(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        env = driver.native
        env.reset(seed=5)
        env.step([0.5] * 14)
        env.forget_arm_state()
        observation, _info = env.reset(seed=6)
        self.assertEqual(observation["state"], [0.0] * 14)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["status"], "completed", seeded)
        self.assertTrue(seeded["output"]["accepted"])
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_max_episode_steps_truncates(self) -> None:
        client = self.serve(max_episode_steps=2)
        self.reset(client, seed=7)
        self.assertEqual(self.step(client)["status"], "completed")
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"], receipt["output"]["tick"]),
                         (False, True, 2))
        ended = self.step(client)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")

    def test_reset_retains_serializable_randomization_info(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=23)["status"], "completed")
        info = self.state(client)["info"]
        self.assertEqual(info["randomization"], {
            "seed": 23, "object_states": {}, "scale_states": {},
            "metadata": {"fixture": "placeholder"},
        })

    def test_fake_images_follow_the_configured_dimensions(self) -> None:
        client = self.serve(camera_height=2, camera_width=3)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        for image in receipt["output"]["observation"]["images"].values():
            values = image["values"]
            self.assertEqual((len(values), len(values[0]), len(values[0][0])), (3, 2, 3))

    def test_fake_step_chunk_accepts_the_upstream_two_dimensional_shape(self) -> None:
        driver = load_driver(HERE, backend="fake", options={"chunk_dim": 2})
        self.addCleanup(driver.close)
        env = driver.native
        env.reset(seed=24)
        final, history, _reward, terminated, truncated, _info = env.step_chunk(
            [[0.1] * 14, [0.2] * 14])
        self.assertEqual(final["state"], [0.2] * 14)
        self.assertEqual(history["state"], [[0.1] * 14, [0.2] * 14])
        self.assertFalse(terminated or truncated)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:abc_sim fake kinematic stand-in", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (34.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("partial", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=8)["status"], "completed")
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=9)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)        # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
