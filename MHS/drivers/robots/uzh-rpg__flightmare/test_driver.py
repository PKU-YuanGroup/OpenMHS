"""Acceptance and repository-specific cases for the Flightmare vector-environment package.

The first case is the stock gate.  The other cases exercise the production
``VecEnvGymAdapter`` with a raw native-shaped peer through the stock server,
check the fake's preserved batch contract, and cover the refused-multi-agent
and envelope paths.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverDefinitionError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent


class Box:
    """A small per-agent Box for the test peer; low/high are plain lists."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class RawPeer:
    """A raw vector environment shaped like ``FlightEnvVec``, not like Gymnasium.

    ``reset`` returns a batch, ``step`` returns a four-element tuple of batch
    values and a per-environment info list, and ``seed`` is the native name.
    """

    def __init__(self, count=1, terminal=True):
        self._count = count
        self._terminal = terminal
        self._closed = False
        self._observation = [[1.0, 2.0, 3.0, 4.0] for _ in range(count)]
        self.seed_values = []
        self.reset_calls = 0
        self.step_rows = []
        self.action_space = Box([-1.0] * 4, [1.0] * 4)
        self.observation_space = Box([float("-inf")] * 4, [float("inf")] * 4)

    @property
    def num_envs(self):
        return self._count

    def seed(self, seed=0):
        self.seed_values.append(int(seed))

    def reset(self):
        if self._closed:
            raise RuntimeError("closed")
        self.reset_calls += 1
        return [list(row) for row in self._observation]

    def step(self, action):
        if self._closed:
            raise RuntimeError("closed")
        rows = [list(row) for row in action]
        self.step_rows.append(rows)
        observation = [[row[0] + 0.25, 2.0, 3.0, 4.0] for row in rows]
        reward = [0.5 for _ in rows]
        done = [bool(self._terminal) for _ in rows]
        info = [{"episode": {"r": 0.5, "l": 1}} for _ in rows]
        return observation, reward, done, info

    def close(self):
        self._closed = True


def adapter_class():
    """The production adapter class, obtained from the package without a direct import."""

    driver = load_driver(HERE, "fake")
    try:
        return type(driver.native)
    finally:
        driver.close()


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AdapterCases(unittest.TestCase):
    def serve_peer(self, peer):
        server = load(HERE, backend="fake", native=adapter_class()(peer))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_a_raw_native_peer_reaches_the_stock_world_endpoints(self) -> None:
        peer = RawPeer(terminal=False)
        client = self.serve_peer(peer)
        reset = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(peer.seed_values, [7])
        self.assertEqual(peer.reset_calls, 1)
        self.assertEqual(reset["output"]["observation"], {"values": [1.0, 2.0, 3.0, 4.0]})
        step = client.invoke("cap.world.step.v1",
                             {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0, -0.5]}},
                             **self.ids)
        self.assertEqual(step["status"], "completed", step)
        self.assertEqual(step["output"]["observation"], {"values": [0.75, 2.0, 3.0, 4.0]})
        self.assertEqual(step["output"]["reward"], 0.5)
        self.assertFalse(step["output"]["terminated"])
        self.assertEqual(peer.step_rows, [[[0.5, 0.0, 0.0, -0.5]]])

    def test_the_adapter_extracts_one_environment_not_a_sum_or_an_all(self) -> None:
        peer = RawPeer(terminal=True)
        client = self.serve_peer(peer)
        reset = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        step = client.invoke("cap.world.step.v1",
                             {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0, 0.0]}},
                             **self.ids)
        self.assertEqual(step["status"], "completed", step)
        self.assertTrue(step["output"]["terminated"])
        self.assertEqual(step["output"]["reward"], 0.5)
        again = client.invoke("cap.world.step.v1",
                              {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0, 0.0]}},
                              **self.ids)
        self.assertEqual(again["status"], "failed", again)
        self.assertEqual(again["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(len(peer.step_rows), 1)

    def test_action_outside_the_native_box_is_refused_before_the_peer(self) -> None:
        peer = RawPeer(terminal=False)
        client = self.serve_peer(peer)
        receipt = client.invoke("cap.world.step.v1",
                                {"ticks": 1, "action": {"values": [2.0, 0.0, 0.0, 0.0]}},
                                **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(peer.step_rows, [])

    def test_the_adapter_refuses_a_multi_environment_batch(self) -> None:
        with self.assertRaises(ValueError):
            adapter_class()(RawPeer(count=2))


class FakeCases(unittest.TestCase):
    def test_the_fake_preserves_the_native_vector_contract(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        raw = driver.native._raw
        observation = raw.reset()
        self.assertEqual(len(observation), 1)
        self.assertEqual(len(observation[0]), 12)
        result = raw.step([[0.0] * 4])
        self.assertEqual(len(result), 4)
        observations, rewards, done, info = result
        self.assertEqual(len(observations), 1)
        self.assertEqual(len(rewards), 1)
        self.assertEqual(len(done), 1)
        self.assertIsInstance(info, list)
        self.assertEqual(len(info), 1)

    def test_the_fake_seed_is_applied_only_on_reset(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        raw = driver.native._raw
        self.assertEqual(driver.call("cap.world.seed.v1", {"seed": 11}), {"seed": 11, "accepted": True})
        self.assertIsNone(raw._seed)
        self.assertEqual(driver.call("cap.world.reset.v1", {"seed": 11})["seed"], 11)
        self.assertEqual(raw._seed, 11)


class ConstructionOwnershipCases(unittest.TestCase):
    def factory_case(self, count, *, close_fails=False, count_fails=False):
        seed = load_driver(HERE, "fake")
        peer_type = type(seed.native._raw)
        seed.close()
        original_init, original_close = peer_type.__init__, peer_type.close
        peers, close_calls = [], []
        cleanup_error = RuntimeError("controlled raw close failure")

        def construct(peer, *args, **kwargs):
            original_init(peer, *args, **kwargs)
            peer._num_envs = count
            peers.append(peer)

        def close(peer):
            close_calls.append(peer)
            if close_fails:
                raise cleanup_error
            original_close(peer)

        def read_count(peer):
            raise ValueError("controlled native count read failure")

        patches = [patch.object(peer_type, "__init__", construct), patch.object(peer_type, "close", close)]
        if count_fails:
            patches.append(patch.object(peer_type, "num_envs", property(read_count)))
        from contextlib import ExitStack
        error = None
        try:
            with ExitStack() as stack:
                for item in patches:
                    stack.enter_context(item)
                try:
                    driver = load_driver(HERE, "fake")
                except DriverDefinitionError as exc:
                    error = exc
                else:
                    driver.close()
            self.assertEqual(len(peers), 1)
            self.assertEqual(close_calls, peers, "raw owner must be closed exactly once")
            self.assertEqual(peers[0]._closed, not close_fails)
            if count == 1 and not count_fails:
                self.assertIsNone(error)
            else:
                self.assertIsInstance(error, DriverDefinitionError)
                expected = "controlled native count read failure" if count_fails else "num_envs == 1"
                self.assertIn(expected, str(error))
                if close_fails:
                    self.assertIn("raw cleanup also failed (RuntimeError: controlled raw close failure)",
                                  str(error))
                else:
                    self.assertNotIn("raw cleanup also failed", str(error))
        finally:
            for peer in peers:
                original_close(peer)  # Dispose only controlled test peers after recording evidence.

    def test_rejected_native_batch_is_closed_by_stock_loader_unwind(self):
        self.factory_case(2)

    def test_native_count_read_failure_still_closes_raw_owner(self):
        self.factory_case(1, count_fails=True)

    def test_cleanup_failure_remains_in_original_validation_error_chain(self):
        self.factory_case(2, close_fails=True)

    def test_accepted_single_environment_has_one_normal_close(self):
        self.factory_case(1)

    def test_factory_failure_keeps_both_original_exception_objects(self):
        driver = load_driver(HERE, "fake")
        peer_type = type(driver.native._raw)
        original_init, original_close = peer_type.__init__, peer_type.close
        constructed = []
        cleanup_error = RuntimeError("controlled cleanup object")

        def construct(peer, *args, **kwargs):
            original_init(peer, *args, **kwargs)
            peer._num_envs = 2
            constructed.append(peer)

        try:
            with patch.object(peer_type, "__init__", construct), \
                    patch.object(peer_type, "close", side_effect=cleanup_error):
                with self.assertRaises(RuntimeError) as caught:
                    driver.open_native()
            error = caught.exception
            self.assertIsInstance(error.construction_error, ValueError)
            self.assertIs(error.__cause__, error.construction_error)
            self.assertIs(error.cleanup_error, cleanup_error)
            self.assertEqual(len(constructed), 1)
        finally:
            for peer in constructed:
                original_close(peer)
            driver.close()


if __name__ == "__main__":
    unittest.main()
