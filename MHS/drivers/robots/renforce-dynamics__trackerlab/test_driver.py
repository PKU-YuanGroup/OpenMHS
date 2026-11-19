"""Acceptance run of the TrackerLab G1 23-DoF package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py).  Isaac Lab, Isaac Sim, torch and the GPU stack are not installed where
the gate runs, so nothing here compares the fake with the upstream environment; the fidelity ``gaps`` say so.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = {"values": [0.0] * 23}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TrackerLabCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY if overlay else None)
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

    def test_raw_actions_require_an_operator_envelope(self) -> None:
        client = self.serve(overlay=False)
        before = self.state(client)
        receipt = self.step(client, [1.0] * 23)
        self.assertEqual((receipt["status"], receipt.get("error", {}).get("mhs_code")),
                         ("rejected", "MHS.SAFETY.LIMITS_UNSET"))
        self.assertEqual(self.state(client), before)

    def test_the_example_envelope_refuses_both_sides_of_every_action(self) -> None:
        client = self.serve()
        before = self.state(client)
        for index in range(23):
            for value in (-20.0001, 20.0001):
                values = [0.0] * 23
                values[index] = value
                with self.subTest(index=index, value=value):
                    receipt = self.step(client, values)
                    self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]),
                                     ("rejected", ENVELOPE))
        self.assertEqual(self.state(client), before)
        self.assertEqual(self.step(client, [1.0] * 23)["status"], "completed")

    def test_the_fake_applies_the_configured_joint_velocity_observation_scale(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [1.0] * 23)
        self.assertEqual(receipt["status"], "completed", receipt)
        policy = receipt["output"]["observation"]["policy"]["values"]
        # Fake-only target tracking: relative target 0.5 over 0.02 s gives 25,
        # then the task's 0.05 observation scale (g1_23d_tracking_env_cfg.py:178) gives 1.25.
        self.assertEqual(policy[58:81], [1.25] * 23)

    def test_the_fake_target_approximation_scales_and_clips(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [1.0] * 23)
        self.assertEqual(receipt["status"], "completed", receipt)
        policy = receipt["output"]["observation"]["policy"]["values"]
        self.assertEqual(len(policy), 104)
        # JointPositionActionCfg: scale=0.5 (manager_based_tracker_env_cfg/configs.py:157), so the relative joint
        # position block (positions 35..57) is 0.5 * 1.0 and the last-action block (81..103) is the raw action.
        self.assertEqual(policy[35:58], [0.5] * 23)
        self.assertEqual(policy[81:104], [1.0] * 23)
        # Fake-only zero-offset approximation of scale/clip; native default offsets are not modelled.
        clipped = self.step(client, [20.0] * 23)["output"]["observation"]["policy"]["values"]
        self.assertEqual(clipped[35:58], [6.0] * 23)
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(receipt["output"]["reward"], 0.0)              # the fake reports no reward

    def test_the_action_vector_has_23_joint_values(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        for values in ([0.0] * 22, [0.0] * 24, []):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", len(values))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(values))
        self.assertEqual(self.state(client)["tick"], 0)                 # the refused steps changed nothing

    def test_a_missing_action_is_rejected_before_dispatch(self) -> None:
        client = self.serve()
        before = self.state(client)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]),
                         ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client), before)

    def test_ticks_are_bounded_by_the_world_class(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        for ticks in (0, 10001):
            refused = self.step(client, [0.0] * 23, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        def observation(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            return receipt["output"]["observation"]

        first = observation(7)
        self.assertEqual(observation(7), first)
        self.assertNotEqual(observation(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_the_fake_episode_truncates_at_1000_control_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0] * 23, ticks=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # The fake chooses this budget from the configured duration and control step; it does not
        # reproduce Isaac Lab's in-step timeout/reset implementation outside the clone.
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1000, False, True))
        ended = self.step(client, [0.0] * 23)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 23)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 23), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable and not advanced
        held = self.state(client)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.state(client), held)                     # safety reset advances no simulation

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:trackerlab-g1-23d-walk-stand-in (Isaac Lab target)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)


if __name__ == "__main__":
    unittest.main()
