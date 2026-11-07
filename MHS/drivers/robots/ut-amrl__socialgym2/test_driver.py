"""Acceptance run of the SocialGym2 package: the gate, plus cases specific to this simulator.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
AGENTS = tuple(f"player_{index}" for index in range(5))


def joint_action(value: int) -> dict[str, int]:
    """The joint action dict the fake's Dict action space requires: one Discrete(2) per agent."""
    return {agent: value for agent in AGENTS}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SocialGymCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_step_advances_the_environment_and_changes_the_state_hash(self) -> None:
        client = self.serve()
        first = client.invoke("cap.world.step.v1", {"ticks": 2, "action": joint_action(1)}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(first["output"]["tick"], 2)
        self.assertEqual(set(first["output"]["observation"]), set(AGENTS))
        second = client.invoke("cap.world.step.v1", {"ticks": 1, "action": joint_action(0)}, **self.ids)
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(second["output"]["tick"], 3)
        self.assertNotEqual(first["output"]["state_hash"], second["output"]["state_hash"])

    def test_per_agent_maps_stay_in_the_world_state_info(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": joint_action(1)}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = client.read("world", **self.ids)
        self.assertEqual(set(state["state"]["info"]["agents"]), set(AGENTS))
        self.assertEqual(state["state"]["info"]["agents"]["player_0"]["action"], 1)

    def test_reset_and_seed_echo_the_seed(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 7}, **self.ids)
        self.assertEqual(seeded["status"], "completed", seeded)
        self.assertTrue(seeded["output"]["accepted"])
        reset = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["seed"], 7)
        self.assertEqual(set(reset["output"]["observation"]), set(AGENTS))

    def test_an_action_outside_the_agent_discrete_space_is_refused(self) -> None:
        client = self.serve()
        action = joint_action(1)
        action["player_0"] = 2
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": action}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_an_estop_refuses_the_next_step(self) -> None:
        client = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": joint_action(0)}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ESTOP)


class RawParallel:
    """Source-shaped method spaces and raw per-agent five-tuple, never ROS."""
    def __init__(self):
        from types import SimpleNamespace
        Discrete = type("Discrete", (), {})
        Box = type("Box", (), {})
        self.possible_agents = ["a", "b"]
        self.agents = list(self.possible_agents)
        self.action_spaces, self.observation_spaces = {}, {}
        for a in self.agents:
            d = Discrete(); d.n, d.start, d.shape, d.dtype = 2, 0, (), "int64"
            b = Box(); b.low, b.high, b.shape, b.dtype = [-9999.] * 3, [9999.] * 3, (3,), "float32"
            self.action_spaces[a], self.observation_spaces[a] = d, b
        self.calls, self.reset_seeds = [], []
        self.sequence = []
        self.closed = False

    def action_space(self, agent):
        return self.action_spaces[agent]

    def observation_space(self, agent):
        return self.observation_spaces[agent]

    def reset(self, seed=None, return_info=True, options=None):
        self.reset_seeds.append(seed)
        self.agents = list(self.possible_agents)
        return {a: [0.] * 3 for a in self.agents}, {a: {} for a in self.agents}

    def step(self, action_dict):
        self.calls.append(dict(action_dict))
        if self.sequence:
            response = self.sequence.pop(0)
            self.agents = [a for a in response[0] if not (response[2][a] or response[3][a])]
            return response
        return ({a: [1.] * 3 for a in self.agents}, {a: float(i+2) for i,a in enumerate(self.agents)},
                {a: False for a in self.agents}, {a: False for a in self.agents},
                {"robot_data": {"source": "raw"}, **{a: {"native": True} for a in self.agents}})

    def close(self):
        self.closed = True


def response(agents, terms, truncs):
    return ({a: [1.] * 3 for a in agents}, {a: 1. for a in agents}, terms, truncs,
            {a: {"native": True} for a in agents})


class RawParallelCases(unittest.TestCase):
    def serve_raw(self, raw, *, backend="fake"):
        from mhs.adapter import load_driver
        from mhs.driver import build_server
        driver = load_driver(HERE, backend=backend, native=raw)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        did = client.hello()["devices"][0]["device_id"]
        sid = client.open_session(device_ids=[did])["session_id"]
        return driver, client, {"device_id": did, "session_id": sid}

    def test_raw_native_is_projected_by_production_adapter(self):
        raw = RawParallel()
        driver, client, ids = self.serve_raw(raw)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 2, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["reward"], 10.)
        self.assertFalse(receipt["output"]["terminated"])
        self.assertFalse(receipt["output"]["truncated"])
        self.assertEqual(len(raw.calls), 2)
        info = client.read("world", **ids)["state"]["info"]
        self.assertEqual(info["rewards"], {"a": 2., "b": 3.})
        self.assertEqual(info["agents"]["robot_data"], {"source": "raw"})
        self.assertEqual(set(driver.inner.step_input_schema()["properties"]["action"]["properties"]), {"a", "b"})

    def test_retired_agents_and_mixed_terminal_causes(self):
        raw = RawParallel()
        raw.sequence = [response(["a", "b"], {"a": True, "b": False}, {"a": False, "b": False}),
                        response(["b"], {"b": False}, {"b": True})]
        _, client, ids = self.serve_raw(raw)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 2, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(receipt["output"]["terminated"])
        self.assertTrue(receipt["output"]["truncated"])
        self.assertEqual(raw.calls, [{"a": 1, "b": 0}, {"b": 0}])
        again = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, **ids)
        self.assertNotEqual(again["status"], "completed")
        self.assertEqual(len(raw.calls), 2)

    def test_active_agents_reflect_current_terminal_results(self):
        raw = RawParallel()
        raw.sequence = [response(["a", "b"], {"a": True, "b": False}, {"a": False, "b": False})]
        _, client, ids = self.serve_raw(raw)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(client.read("world", **ids)["state"]["info"]["active_agents"], ["b"])

    def test_retired_agents_cannot_add_new_rewards_or_terminal_results(self):
        raw = RawParallel()
        raw.terminations = {"a": True, "b": False}
        raw.sequence = [response(["a", "b"], {"a": True, "b": False}, {"a": False, "b": False})]
        _, client, ids = self.serve_raw(raw)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(raw.calls, [{"b": 0}])

    def test_close_is_irreversible_and_cleanup_is_deferred_once(self):
        import threading
        raw = RawParallel()
        entered, release = threading.Event(), threading.Event()
        original = raw.step
        count = []
        def step(action):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("missing step release")
            return original(action)
        raw.step = step
        raw.close = lambda: count.append("close")
        driver, client, ids = self.serve_raw(raw)
        results = []
        thread = threading.Thread(target=lambda: results.append(client.invoke(
            "cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, deadline_ms=3000, **ids)))
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            driver.close()
            self.assertEqual(count, [])
            with self.assertRaises(Exception):
                driver.inner.parallel.recover()
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        driver.inner.parallel.close()
        self.assertEqual(count, ["close"])
        self.assertTrue(driver.inner.parallel._closed)
        with self.assertRaises(Exception):
            driver.inner.parallel.reset()

    def test_initial_inactive_agents_and_empty_results_are_not_fabricated_success(self):
        raw = RawParallel()
        raw.terminations = {"a": True, "b": False}
        raw.sequence = [response(["b"], {"b": False}, {"b": False})]
        _, client, ids = self.serve_raw(raw)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(raw.calls, [{"b": 0}])
        raw.sequence = [({}, {}, {}, {}, {})]
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_bounds_and_malformed_flags_are_not_success(self):
        raw = RawParallel()
        _, client, ids = self.serve_raw(raw)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 9, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(raw.calls, [])
        raw.sequence = [response(["a", "b"], {"a": "false", "b": False}, {"a": False, "b": False})]
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(receipt["status"], "failed")

    def test_sim_seed_stop_and_reset_do_not_claim_external_confirmation(self):
        raw = RawParallel()
        driver, client, ids = self.serve_raw(raw, backend="sim")
        self.assertNotIn("cap.world.seed.v1", {v["capability_id"] for v in driver.capabilities()})
        rejected = client.invoke("cap.world.reset.v1", {"seed": 99}, **ids)
        self.assertNotEqual(rejected["status"], "completed")
        self.assertEqual(raw.reset_seeds, [])
        reset = client.invoke("x-cap.ut-amrl.reset_unseeded.v1", {}, **ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertNotIn("seed", reset["output"])
        self.assertEqual(raw.reset_seeds, [None])
        stopped = client.estop("external confirmation absent", **ids)
        self.assertIs(stopped.get("output", {}).get("safe_state_achieved"), False, stopped)
        self.assertNotEqual(client.reset(**ids)["status"], "completed")
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"a": 1, "b": 0}}, **ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(raw.calls, [])

    def test_unseeded_reset_is_effectful_and_fenced_during_inflight_step(self):
        import threading
        raw = RawParallel()
        entered, release = threading.Event(), threading.Event()
        original = raw.step
        def blocked(action):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test release absent")
            return original(action)
        raw.step = blocked
        _, client, ids = self.serve_raw(raw)
        receipts = []
        thread = threading.Thread(target=lambda: receipts.append(client.invoke(
            "cap.world.step.v1", {"ticks": 2, "action": {"a": 1, "b": 0}}, deadline_ms=3000, **ids)))
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            stopped = client.estop("blocked raw step", **ids)
            self.assertIs(stopped.get("output", {}).get("safe_state_achieved"), False, stopped)
            before = list(raw.reset_seeds)
            reset = client.invoke("x-cap.ut-amrl.reset_unseeded.v1", {}, **ids)
            self.assertEqual(reset["status"], "rejected", reset)
            self.assertEqual(raw.reset_seeds, before)
            self.assertNotEqual(client.reset(**ids)["status"], "completed")
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(raw.calls), 1)
        self.assertTrue(client.estop("now idle", **ids)["output"]["safe_state_achieved"])
        self.assertEqual(client.reset(**ids)["status"], "completed")
        receipt = client.invoke("x-cap.ut-amrl.reset_unseeded.v1", {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertNotIn("seed", receipt["output"])

    def test_expired_unseeded_reset_never_reaches_native(self):
        import time
        from mhs.bridge.base import BridgeContext
        raw = RawParallel()
        driver, _, _ = self.serve_raw(raw)
        ctx = BridgeContext(extra={"deadline_at": time.monotonic() - 1})
        with self.assertRaises(Exception):
            driver.inner.call("x-cap.ut-amrl.reset_unseeded.v1", {}, ctx)
        self.assertEqual(raw.reset_seeds, [])

    def test_sim_factory_refuses_before_ros_import_or_construction(self):
        import ast
        from mhs.adapter import load_driver
        source = ast.parse((HERE / "sim.py").read_text())
        imports = [n.module for n in ast.walk(source) if isinstance(n, ast.ImportFrom)]
        self.assertEqual(imports, ["mhs.bridge.base"])
        self.assertFalse(any(isinstance(n, ast.Import) for n in ast.walk(source)))
        with self.assertRaises(Exception) as raised:
            load_driver(HERE, backend="sim", options={"launch_config": "operator.launch"})
        self.assertIn("blocked", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
