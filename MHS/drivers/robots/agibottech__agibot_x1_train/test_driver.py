"""Acceptance run of the X1DHStandEnv package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``); the upstream
environment needs Isaac Gym, torch and a GPU, so nothing here compares the fake with upstream or runs a device.
"""

import unittest
import threading
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ACTION_SIZE = 12
OBSERVATION_SIZE = 3102
PRIVILEGED_SIZE = 219


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class X1DHStandCases(unittest.TestCase):
    def serve(self, with_limits=True):
        driver = load_driver(HERE, backend="fake")
        limits = str(HERE / "site-limits.example.json") if with_limits else None
        server = build_server(driver, site_limits=limits)
        self.addCleanup(close_server, server)
        self.fake = driver.native
        self.fake._calls.clear()
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, values=None, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"values": list(values if values is not None else [0.0] * ACTION_SIZE)}},
            **self.ids,
        )

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def native_steps(self):
        return [args for name, args in self.fake._calls if name == "step"]

    def test_reset_returns_the_upstream_sized_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(len(output["observation"]["obs"]), OBSERVATION_SIZE)
        self.assertEqual(len(output["observation"]["privileged_obs"]), PRIVILEGED_SIZE)
        self.assertEqual(output["seed"], 0)
        self.assertGreaterEqual(output["revision"], 1)
        state = self.state(client)
        self.assertEqual((state["tick"], state["terminated"], state["truncated"]), (0, False, False))

    def test_step_advances_one_native_step_per_tick(self) -> None:
        client = self.serve()
        self.reset(client)
        values = [0.5, -0.5, 0.25, -0.25, 0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.4, -0.4]
        receipt = self.step(client, values=values, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertIsInstance(output["reward"], float)
        self.assertIs(output["terminated"], False)
        self.assertIs(output["truncated"], False)
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(len(self.native_steps()), 3)
        self.assertEqual(self.native_steps()[-1], values)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (3, 1))
        self.assertEqual(state["reward"], output["reward"])

    def test_action_outside_the_clip_is_refused_before_the_native_step(self) -> None:
        client = self.serve()
        self.reset(client)
        for index, value in ((0, 101.0), (ACTION_SIZE - 1, -101.0)):
            values = [0.0] * ACTION_SIZE
            values[index] = value
            refused = self.step(client, values=values)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
            self.assertEqual(refused["error"]["details"]["path"], f"action.values[{index}]")
        self.assertEqual(self.native_steps(), [])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_action_requires_an_operator_envelope(self) -> None:
        client = self.serve(with_limits=False)
        refused = self.step(client)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", refused)
        self.assertEqual(self.native_steps(), [])

    def test_terminal_step_keeps_its_reward_after_auto_reset(self) -> None:
        client = self.serve()
        self.fake._step_count = 2399  # placeholder: immediately before the fake's terminal step
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["terminated"])
        self.assertGreater(receipt["output"]["reward"], 0.0)

    def test_estop_prevents_remaining_ticks_of_an_inflight_batch(self) -> None:
        client = self.serve()
        entered, release = threading.Event(), threading.Event()
        original_step = self.fake.step

        def held_step(actions):
            result = original_step(actions)
            entered.set()
            if not release.wait(2.0):
                raise RuntimeError("test did not release the held fake step")
            return result

        self.fake.step = held_step
        results = []
        thread = threading.Thread(target=lambda: results.append(self.step(client, ticks=3)))
        thread.start()
        try:
            self.assertTrue(entered.wait(1.0))
            client.estop("cancel tick batch", **self.ids)
        finally:
            release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.native_steps()), 1)
        self.assertEqual(self.state(client)["tick"], 1)
        self.assertNotEqual(results[0]["status"], "completed", results)

    def test_nonfinite_done_is_not_converted_to_true(self) -> None:
        client = self.serve()
        original_step = self.fake.step

        def invalid_step(actions):
            obs, privileged, reward, _done, extras = original_step(actions)
            return obs, privileged, reward, float("nan"), extras

        self.fake.step = invalid_step
        receipt = self.step(client)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)

    def test_ticks_outside_the_class_bound_are_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.native_steps(), [])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_wrong_action_shape_is_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        short = self.step(client, values=[0.0] * (ACTION_SIZE - 1))
        self.assertEqual((short["status"], short["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        missing = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {}}, **self.ids)
        self.assertEqual((missing["status"], missing["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.native_steps(), [])

    def test_a_non_empty_reset_options_object_is_refused(self) -> None:
        client = self.serve()
        refused = self.reset(client, options={"unexpected": True})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.fake._calls, [])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client)
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertEqual(len(state["observation"]["obs"]), OBSERVATION_SIZE)


if __name__ == "__main__":
    unittest.main()
