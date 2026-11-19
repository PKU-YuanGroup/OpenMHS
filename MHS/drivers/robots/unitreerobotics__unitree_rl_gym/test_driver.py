"""Acceptance run of the Unitree RL Gym Go2 package: the gate, plus cases for this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``)
through the stock server; the upstream Isaac Gym simulator is not installed where the gate runs, so
nothing here compares the fake with upstream and no hardware is attached.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for
from mhs.driver.loader import import_driver_module

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO = [0.0] * 12
ONE = [0.1] * 12
OVERLAY = str(HERE / "site-limits.example.json")


class TensorBuffer:
    """A test double that preserves Tensor construction and list-conversion behavior without a simulator."""
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values

    def new_tensor(self, rows):
        return TensorBuffer(rows)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2Cases(unittest.TestCase):
    def serve(self, site_limits=OVERLAY, **options):
        driver = load_driver(HERE, backend="fake", options=options)
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.fake = driver.native
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values=None, ticks=1):
        payload = {"ticks": ticks}
        if values is not None:
            payload["action"] = {"values": values}
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    # -- the served interface ------------------------------------------------------------------------------
    def test_reset_returns_the_go2_start_document(self) -> None:
        client = self.serve()
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        observation = receipt["output"]["observation"]
        self.assertEqual((observation["num_envs"], observation["num_actions"],
                          observation["num_observations"]), (1, 12, 48))
        self.assertEqual(len(observation["obs"]), 1)
        self.assertEqual(len(observation["obs"][0]), 48)
        self.assertEqual(observation["obs"][0][36:48], ZERO)
        self.assertEqual(receipt["output"]["seed"], 0)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["scenario"]), (0, 1, "go2"))

    def test_a_step_carries_the_action_into_the_observation_and_changes_the_state(self) -> None:
        client = self.serve()
        self.reset(client)
        del self.fake._commands[:]
        receipt = self.step(client, [ONE])
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["reward"], 0.0)
        self.assertIs(output["terminated"], False)
        self.assertIs(output["truncated"], False)
        self.assertEqual(output["observation"]["obs"][0][36:48], ONE)
        self.assertEqual([name for name, _ in self.fake._commands], ["step"])
        self.assertEqual(self.state(client)["tick"], 1)

    def test_ticks_apply_one_step_each(self) -> None:
        client = self.serve()
        self.reset(client)
        del self.fake._commands[:]
        receipt = self.step(client, [ONE], ticks=3)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual([name for name, _ in self.fake._commands], ["step", "step", "step"])
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_per_agent_action_and_a_flat_action_are_both_accepted(self) -> None:
        client = self.serve(num_envs=2)
        self.reset(client)
        nested = [[0.1] * 12, [0.2] * 12]
        receipt = self.step(client, nested)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["observation"]["num_envs"], 2)
        self.assertNotIn("reward", output)                 # one scalar cannot carry two agents
        self.assertNotIn("terminated", output)
        self.assertEqual(len(output["observation"]["rewards"]), 2)
        self.assertEqual(output["observation"]["obs"][0][36:48], [0.1] * 12)
        self.assertEqual(output["observation"]["obs"][1][36:48], [0.2] * 12)
        flat = self.step(client, [0.3] * 12)
        self.assertEqual(flat["status"], "completed", flat)
        self.assertEqual(flat["output"]["observation"]["obs"][0][36:48], [0.3] * 12)
        self.assertEqual(flat["output"]["observation"]["obs"][1][36:48], [0.3] * 12)

    def test_a_bad_action_is_refused_before_the_native_step(self) -> None:
        client = self.serve()
        self.reset(client)
        del self.fake._commands[:]
        driver_failures = (
            {"values": [0.0] * 11},
            {"values": [[0.0] * 12, [0.0] * 12]},
        )
        for action in driver_failures:
            receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": action}, **self.ids)
            self.assertEqual(receipt["status"], "failed", action)
            self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID, action)
        extra = client.invoke("cap.world.step.v1",
                              {"ticks": 1, "action": {"values": [0.0] * 12, "extra": 1}}, **self.ids)
        self.assertEqual(extra["status"], "rejected")                  # the served action object is closed
        self.assertEqual(extra["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.fake._commands, [])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_policy_bounds_are_required_and_cover_flat_and_nested_actions(self) -> None:
        client = self.serve(site_limits=None)
        receipt = self.step(client, ONE)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", receipt)
        self.assertEqual(self.fake._commands, [])
        missing = self.step(client)
        self.assertEqual(missing["error"]["mhs_code"], INPUT_INVALID, missing)
        self.assertEqual(self.fake._commands, [])
        client = self.serve(num_envs=2)
        for values in ([1.1] + ZERO[1:], [-1.1] + ZERO[1:],
                       [ZERO, ZERO[:-1] + [1.1]], [ZERO, ZERO[:-1] + [-1.1]]):
            refused = self.step(client, values)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", refused)
        self.assertEqual(self.fake._commands, [])

    def test_step_constructs_a_native_tensor_from_the_observation_buffer(self) -> None:
        client = self.serve()
        self.fake.obs_buf = TensorBuffer(self.fake.obs_buf)
        original_step = self.fake.step
        received = []

        def require_tensor(actions):
            self.assertIsInstance(actions, TensorBuffer)
            received.append(actions.tolist())
            self.fake.obs_buf = self.fake.obs_buf.tolist()
            return original_step(actions)

        self.fake.step = require_tensor
        receipt = self.step(client, ONE)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(received, [[ONE]])

    def test_viewer_is_refused_before_loading_the_upstream(self) -> None:
        with self.assertRaisesRegex(ValueError, "headless=True"):
            import_driver_module(HERE).make_env(headless=False)

    def test_null_native_terminal_flag_is_refused(self) -> None:
        client = self.serve()
        original_step = self.fake.step

        def missing_flag(actions):
            obs, privileged, rewards, flags, extras = original_step(actions)
            return obs, privileged, rewards, [None], extras

        self.fake.step = missing_flag
        receipt = self.step(client, ONE)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)

    def test_ticks_outside_the_class_bound_are_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        del self.fake._commands[:]
        for ticks in (0, 10001):
            receipt = self.step(client, [ZERO], ticks=ticks)
            self.assertEqual(receipt["status"], "rejected", ticks)
            self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.fake._commands, [])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_reset_accepts_and_ignores_options(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, options={"unused": True})["status"], "completed")
        self.assertEqual(self.state(client)["episode"], 1)

    # -- native terminal semantics -------------------------------------------------------------------------
    def test_a_native_contact_termination_is_reported_as_terminated(self) -> None:
        client = self.serve()
        self.reset(client)
        self.fake._force_termination(0)
        receipt = self.step(client, [ZERO])
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["terminated"], True)
        self.assertIs(receipt["output"]["truncated"], False)
        self.assertEqual(receipt["output"]["observation"]["episode_lengths"], [0])

    def test_a_native_timeout_is_reported_as_truncated(self) -> None:
        client = self.serve()
        self.reset(client)
        self.fake.max_episode_length = 1
        receipt = self.step(client, [ZERO])
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["terminated"], False)
        self.assertIs(receipt["output"]["truncated"], True)
        self.assertEqual(receipt["output"]["observation"]["episode_lengths"], [0])

    # -- safety and shape ----------------------------------------------------------------------------------
    def test_the_estop_latches_the_world_and_keeps_the_state_readable(self) -> None:
        client = self.serve()
        self.reset(client)
        self.assertEqual(self.step(client, [ZERO])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [ZERO]), self.reset(client)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_driver_declares_no_reset_hook_and_no_seed_capability(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.assertIsNone(driver.reset_hook)
        model = type(driver).driver_model()
        capabilities = [binding.capability_id for binding in model.bindings]
        self.assertNotIn("cap.world.seed.v1", capabilities)
        self.assertEqual(model.mode, "simulated")
        self.assertEqual(type(driver).native, "legged_gym.envs.base.legged_robot:LeggedRobot")

    def test_the_simulated_driver_has_no_hardware_backend(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "no_hardware_backend")


if __name__ == "__main__":
    unittest.main()
