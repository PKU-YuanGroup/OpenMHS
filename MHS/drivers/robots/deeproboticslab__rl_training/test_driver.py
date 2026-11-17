"""Acceptance run of the Deep Robotics DR02 AMP package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream Isaac Lab
stack was not available where the gate runs, so nothing here compares the fake with an Isaac Lab run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
OVERLAY = str(HERE / "site-limits.example.json")
GROUP_SIZES = {"policy": 73, "critic": 121, "amp_obs_history": 305, "obs_future": 69, "vel": 3}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DeepRoboticsDR02AmpCases(unittest.TestCase):
    def serve(self, overlay=True):
        server = load(HERE, backend="fake", site_limits=OVERLAY if overlay else None)
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

    def test_the_fake_is_a_world_simulator(self) -> None:
        client = self.serve()
        hello = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        self.assertEqual((hello["mode"], hello["risk_class"]), ("simulated", "R0"))
        self.assertEqual([item["kind"] for item in device["resources"]], ["world.sim"])

    def test_the_observation_groups_match_the_config(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(sorted(observation), sorted(GROUP_SIZES))
        for group, size in GROUP_SIZES.items():
            self.assertEqual(len(observation[group]["values"]), size, group)

    def test_the_action_is_a_21_element_joint_target(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        values = [0.1] * 21
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed")
        # policy = [ang_vel(3), proj_grav(3), cmd(3), cmd_flag(1), dof_pos(21), dof_vel(21), actions(21)]
        self.assertEqual(receipt["output"]["observation"]["policy"]["values"][52:], values)
        for wrong in ([0.0] * 20, [0.0] * 22):
            refused = self.step(client, wrong)
            self.assertEqual(refused["status"], "rejected", len(wrong))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(wrong))
        self.assertEqual(self.state(client)["tick"], 1)              # the refused steps changed nothing

    def test_action_values_require_an_operator_envelope(self) -> None:
        client = self.serve(overlay=False)
        self.reset(client, seed=1)
        refused = self.step(client, [0.0] * 21)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.state(client)["tick"], 0)
        client = self.serve()
        self.reset(client, seed=1)
        for value in (-101.0, 101.0):
            refused = self.step(client, [value] * 21)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fake_placeholder_clips_raw_input(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [50.0] * 21)
        self.assertEqual(receipt["status"], "completed")
        # Fake-only processing; the external action manager's scaling/offset/clip order is not established.
        self.assertEqual(receipt["output"]["observation"]["policy"]["values"][52:], [10.0] * 21)

    def test_ticks_are_bounded_by_the_world_class(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        for ticks in (0, 10001):
            refused = self.step(client, [0.0] * 21, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)              # the refused steps changed nothing

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        other = self.reset(client, seed=12)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertNotEqual(first["observation"], other["observation"])
        self.assertEqual((first["seed"], other["seed"]), (11, 12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 2)

    def test_the_episode_truncates_at_1000_control_ticks(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        output = self.step(client, [0.0] * 21, ticks=1000)["output"]
        # 20 s episode / (decimation 4 x sim.dt 0.005 s) = 1000 control ticks (amp_env_cfg.py:675-680)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1000, False, True))
        ended = self.step(client, [0.0] * 21)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        fidelity = client.inspect(self.ids["device_id"])["fidelity"]
        self.assertEqual(fidelity["engine"], "analytic")
        self.assertEqual((fidelity["fidelity_level"], fidelity["timestep_ms"]), ("F0", 20.0))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 21)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 21), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
