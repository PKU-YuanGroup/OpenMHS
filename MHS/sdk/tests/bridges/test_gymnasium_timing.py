"""Synthetic physics clocks: contract evidence, never MuJoCo compatibility."""
from __future__ import annotations
import copy
import threading
import types
import unittest

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.bridge.simulation_timing import CONTEXT_KEY, PhysicsTiming, SimulationTimingReport, TimingError
from tests.bridges.support import FakeCartPole

CONFIG = {"mode": "physics_ticks_v1", "control_decimation": 5,
          "physics_timestep_attr": "model.opt.timestep", "physics_clock_attr": "data.time",
          "native_autoreset": False, "reset_advances_physics": False,
          "source_refs": ["synthetic-peer.py:1"]}
CHECKPOINT = {"profile": "json_state_v1", "getter": "get_state", "setter": "set_state",
              "max_bytes": 4096}
STEP = "cap.world.step.v1"
RESET = "cap.world.reset.v1"
ACTION = {"index": 1}


class ClockEnv(FakeCartPole):
    def __init__(self, *, terminate_after=50):
        super().__init__(terminate_after=terminate_after)
        self.model = types.SimpleNamespace(opt=types.SimpleNamespace(timestep=0.002))
        self.data = types.SimpleNamespace(time=0.0)
        self.dt = 0.01  # control period; must never become the opted-in physics dt
        self.calls = self.resets = self.restores = 0
        self.advance = 5
        self.failure = None
        self.after_physics = None

    def reset(self, **kwargs):
        self.resets += 1
        self.data.time = 0.0
        return super().reset(**kwargs)

    def step(self, action):
        self.calls += 1
        for _ in range(self.advance):
            self.data.time += self.model.opt.timestep
        if self.after_physics:
            self.after_physics(self)
        if self.failure == "raise":
            raise RuntimeError("native failure after advancing")
        result = super().step(action)
        if self.failure == "shape":
            return (result[0],)
        if self.failure == "reward":
            return result[0], float("nan"), result[2], result[3], result[4]
        return result

    def get_state(self):
        # This synthetic peer has no RNG or wrapper state. Counters and seed
        # history are diagnostic lifetime records, not inputs to its dynamics.
        # Fault callbacks are test machinery and cannot be serialized honestly.
        if self.failure is not None or self.after_physics is not None:
            raise ValueError("fault-injected clock peers do not support checkpoints")
        return {**super().get_state(), "clock": self.data.time,
                "configuration": {"terminate_after": self.terminate_after,
                                  "advance": self.advance,
                                  "physics_timestep": self.model.opt.timestep}}

    def set_state(self, state):
        if state["configuration"] != self.get_state()["configuration"]:
            raise ValueError("clock checkpoint belongs to a different native configuration")
        self.restores += 1
        super().set_state(state)
        self.data.time = state["clock"]


def request(bridge, ticks, *, context=None):
    context = context or BridgeContext()
    sink = SimulationTimingReport(bridge.timing_descriptor(), ticks)
    context.extra[CONTEXT_KEY] = sink
    return context, sink


class GymnasiumTimingTests(unittest.TestCase):
    def make(self, **options):
        env = ClockEnv(terminate_after=options.pop("terminate_after", 50))
        bridge = GymnasiumBridge(env=env, timing=CONFIG, **options)
        self.addCleanup(bridge.close)
        return env, bridge

    def test_physics_ticks_map_to_control_calls(self):
        env, bridge = self.make()
        ctx, sink = request(bridge, 15)
        out = bridge.call(STEP, {"ticks": 15, "action": ACTION}, ctx)
        self.assertEqual((env.calls, out["tick"], sink.snapshot()["completed_ticks"]), (3, 15, 15))
        self.assertEqual(sink.snapshot()["simulated_duration_ms"], 30.0)
        self.assertEqual(set(out), {"observation", "reward", "terminated", "truncated", "tick", "state_hash"})

    def test_invalid_ticks_refuse_before_initial_reset(self):
        for value in (None, True, 1, 6, 5.5, 10005, -5):
            with self.subTest(value=value):
                env, bridge = self.make()
                args = {"action": ACTION}
                if value is not None:
                    args["ticks"] = value
                with self.assertRaises(Exception):
                    bridge.call(STEP, args)
                self.assertEqual((env.resets, env.calls, env.data.time), (0, 0, 0.0))

    def test_termination_and_autoreset_use_command_total(self):
        for autoreset, completed, episode_tick, resets in ((False, 10, 10, 1), (True, 15, 5, 2)):
            env, bridge = self.make(autoreset=autoreset, terminate_after=2)
            ctx, sink = request(bridge, 15)
            out = bridge.call(STEP, {"ticks": 15, "action": ACTION}, ctx)
            self.assertEqual((out["tick"], env.resets), (episode_tick, resets))
            self.assertEqual(sink.snapshot()["completed_ticks"], completed)
            self.assertEqual(sink.snapshot()["simulated_duration_ms"], completed * 2)

    def test_failures_after_physics_preserve_count_and_require_reset(self):
        for mode, count in (("raise", 3), ("shape", 5), ("reward", 5)):
            with self.subTest(mode=mode):
                env, bridge = self.make()
                env.failure, env.advance = mode, count
                ctx, sink = request(bridge, 5)
                with self.assertRaises(Exception):
                    bridge.call(STEP, {"ticks": 5, "action": ACTION}, ctx)
                self.assertEqual(sink.snapshot()["completed_ticks"], count)
                self.assertEqual(sink.snapshot()["simulated_duration_ms"], count * 2)
                with self.assertRaises(Exception):
                    bridge.call(STEP, {"ticks": 5, "action": ACTION})
                self.assertEqual(env.calls, 1)
                env.failure, env.advance = None, 5
                bridge.call(RESET, {})
                self.assertEqual(bridge.call(STEP, {"ticks": 5, "action": ACTION})["tick"], 5)

    def test_clock_fault_is_uncertain_and_reset_verifies_recovery(self):
        for change in (lambda e: setattr(e.data, "time", float("nan")),
                       lambda e: setattr(e.data, "time", -1.0),
                       lambda e: setattr(e.data, "time", 0.001),
                       lambda e: setattr(e.model.opt, "timestep", 0.004)):
            env, bridge = self.make()
            env.after_physics = change
            ctx, sink = request(bridge, 5)
            with self.assertRaises(Exception):
                bridge.call(STEP, {"ticks": 5, "action": ACTION}, ctx)
            note = sink.snapshot()
            self.assertIsNone(note["completed_ticks"])
            self.assertIsNone(note["simulated_duration_ms"])
            self.assertFalse(note["in_flight"])
            with self.assertRaises(Exception):
                bridge.call(STEP, {"ticks": 5, "action": ACTION})
            self.assertEqual(env.calls, 1)
            env.after_physics = None
            env.model.opt.timestep = 0.002
            bridge.call(RESET, {})
            self.assertEqual(bridge.call(STEP, {"ticks": 5, "action": ACTION})["tick"], 5)

    def test_clock_changes_before_native_refuse_zero_mutations(self):
        for attr, value in (("clock", 0.01), ("timestep", 0.004)):
            env, bridge = self.make()
            if attr == "clock":
                env.data.time = value
            else:
                env.model.opt.timestep = value
            with self.assertRaises(Exception):
                bridge.call(STEP, {"ticks": 5, "action": ACTION})
            self.assertEqual((env.calls, env.resets), (0, 0))

    def test_cancel_after_native_call_counts_actual_block(self):
        env, bridge = self.make()
        event = threading.Event()
        env.after_physics = lambda e: event.set()
        ctx, sink = request(bridge, 15, context=BridgeContext(cancel_event=event))
        with self.assertRaises(signals.Cancelled):
            bridge.call(STEP, {"ticks": 15, "action": ACTION}, ctx)
        self.assertEqual((env.calls, sink.snapshot()["completed_ticks"]), (1, 5))

    def test_snapshot_fingerprint_refuses_legacy_before_setter(self):
        env, bridge = self.make(checkpoint={"profile": "json_state_v1", "getter": "get_state", "setter": "set_state"})
        bridge.call(STEP, {"ticks": 5, "action": ACTION})
        snapshot = bridge.snapshot()
        legacy = copy.deepcopy(snapshot)
        del legacy["world"]["native_checkpoint"]["simulation_timing"]
        with self.assertRaises(Exception):
            bridge.restore(legacy)
        self.assertEqual(env.restores, 0)
        bridge.call(STEP, {"ticks": 5, "action": ACTION})
        bridge.restore(snapshot)
        self.assertEqual((bridge.read("world")["tick"], env.data.time), (5, 0.01))

    def test_native_budget_counts_control_calls_not_physics_ticks(self):
        env, bridge = self.make(max_steps=2)
        bridge.call(STEP, {"ticks": 10, "action": ACTION})
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 5, "action": ACTION})
        self.assertEqual(env.calls, 2)

    def test_config_and_native_clock_are_validated(self):
        for changes in ({"control_decimation": True}, {"control_decimation": 0},
                        {"native_autoreset": True}, {"reset_advances_physics": True},
                        {"physics_clock_attr": "__dict__"}, {"mode": "native_transition"}):
            env = ClockEnv()
            with self.assertRaises(Exception):
                GymnasiumBridge(env=env, timing={**CONFIG, **changes})
            self.assertEqual((env.calls, env.resets), (0, 0))

    def test_explicit_d1_and_legacy_default_are_separate(self):
        env = ClockEnv()
        env.advance = 1
        bridge = GymnasiumBridge(env=env, timing={**CONFIG, "control_decimation": 1})
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.call(STEP, {"ticks": 3, "action": ACTION})["tick"], 3)
        legacy_env = ClockEnv()
        legacy = GymnasiumBridge(env=legacy_env)
        self.addCleanup(legacy.close)
        self.assertEqual(legacy.call(STEP, {"action": ACTION})["tick"], 1)
        self.assertEqual((legacy_env.calls, legacy_env.data.time), (1, 0.01))

    def test_normal_return_with_wrong_period_cannot_claim_exact_duration(self):
        for count in (0, 4, 6):
            env, bridge = self.make()
            env.advance = count
            ctx, sink = request(bridge, 5)
            with self.assertRaises(Exception):
                bridge.call(STEP, {"ticks": 5, "action": ACTION}, ctx)
            self.assertIsNone(sink.snapshot()["completed_ticks"])
            self.assertIsNone(sink.snapshot()["simulated_duration_ms"])
            self.assertEqual(sink.snapshot()["known_completed_ticks"], 0)

    def test_native_reset_inside_step_is_a_fault_not_zero_physics(self):
        env, bridge = self.make()
        env.after_physics = lambda e: setattr(e.data, "time", 0.0)
        ctx, sink = request(bridge, 5)
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 5, "action": ACTION}, ctx)
        self.assertIsNone(sink.snapshot()["completed_ticks"])
        self.assertIsNone(sink.snapshot()["simulated_duration_ms"])

    def test_restore_does_not_bypass_required_fault_reset(self):
        env, bridge = self.make(checkpoint={"profile": "json_state_v1", "getter": "get_state", "setter": "set_state"})
        bridge.call(STEP, {"ticks": 5, "action": ACTION})
        snapshot = bridge.snapshot()
        env.failure = "raise"
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 5, "action": ACTION})
        with self.assertRaises(Exception):
            bridge.restore(snapshot)
        self.assertEqual(env.restores, 0)

    def test_one_report_cannot_be_reused_and_trigger_autoreset(self):
        env, bridge = self.make(terminate_after=1, autoreset=True)
        ctx, sink = request(bridge, 5)
        bridge.call(STEP, {"ticks": 5, "action": ACTION}, ctx)
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 5, "action": ACTION}, ctx)
        self.assertEqual((env.calls, env.resets), (1, 1))

    def test_timestep_change_during_reset_prevents_recovery(self):
        env, bridge = self.make()
        original = env.reset
        def changed(**kwargs):
            result = original(**kwargs)
            env.model.opt.timestep = 0.004
            return result
        env.reset = changed
        with self.assertRaises(Exception):
            bridge.call(RESET, {})
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 5, "action": ACTION})
        self.assertEqual(env.calls, 0)

    def test_server_dispatch_missing_timing_binding_is_refused_before_mutation(self):
        env, bridge = self.make()
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 5, "action": ACTION}, BridgeContext(operation_id="operation"))
        self.assertEqual((env.calls, env.resets), (0, 0))

    def test_invalid_info_or_accumulated_reward_cannot_be_overwritten(self):
        for mode, calls in (("info", 1), ("reward_sum", 2)):
            class InvalidResult(ClockEnv):
                def step(self, action):
                    result = super().step(action)
                    if mode == "info":
                        return (*result[:4], {"opaque": object()})
                    return (result[0], 1e308, *result[2:])
            env = InvalidResult()
            bridge = GymnasiumBridge(env=env, timing=CONFIG)
            self.addCleanup(bridge.close)
            ctx, sink = request(bridge, 15)
            with self.assertRaises(Exception):
                bridge.call(STEP, {"ticks": 15, "action": ACTION}, ctx)
            self.assertEqual(env.calls, calls)
            self.assertEqual(sink.snapshot()["completed_ticks"], calls * 5)
            self.assertEqual(sink.snapshot()["stop_reason"], "invalid_result")
            self.assertIsNotNone(bridge._timing_fault)

    def test_accumulated_clock_is_preserved_by_bridge_snapshot_restore(self):
        env, bridge = self.make(terminate_after=100000, checkpoint={
            "profile": "json_state_v1", "getter": "get_state", "setter": "set_state"})
        bridge.call(STEP, {"ticks": 10000, "action": ACTION})
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot["world"]["native_checkpoint"]["physics_clock"], env.data.time)
        self.assertNotEqual(env.data.time, 20.0)  # ordinary IEEE-754 accumulated drift
        bridge.call(STEP, {"ticks": 5, "action": ACTION})
        bridge.restore(snapshot)
        self.assertEqual(bridge.read("world")["tick"], 10000)
        self.assertEqual(env.data.time, snapshot["world"]["native_checkpoint"]["physics_clock"])
        self.assertEqual(bridge.call(STEP, {"ticks": 5, "action": ACTION})["tick"], 10005)
        restores = env.restores
        for bad in (True, float("nan"), float("inf"), -1.0, None):
            changed = copy.deepcopy(snapshot)
            changed["world"]["native_checkpoint"]["physics_clock"] = bad
            with self.assertRaises(Exception):
                bridge.restore(changed)
            self.assertEqual(env.restores, restores)

    def test_roundoff_bound_does_not_accept_off_grid_or_large_jumps(self):
        for mutation in (lambda e: setattr(e.data, "time", e.data.time + 0.001),
                         lambda e: setattr(e.data, "time", 1e9)):
            env = ClockEnv()
            env.advance = 10000
            env.after_physics = mutation
            bridge = GymnasiumBridge(env=env, timing={**CONFIG, "control_decimation": 10000})
            self.addCleanup(bridge.close)
            ctx, sink = request(bridge, 10000)
            with self.assertRaises(Exception):
                bridge.call(STEP, {"ticks": 10000, "action": ACTION}, ctx)
            self.assertIsNone(sink.snapshot()["completed_ticks"])
            self.assertIsNone(sink.snapshot()["simulated_duration_ms"])

    def test_period_resolution_ceiling_refuses_ambiguous_clock_arithmetic(self):
        env = ClockEnv()
        timing = PhysicsTiming.resolve({**CONFIG, "control_decimation": 10000}, lambda name: getattr(env, name))
        with self.assertRaises(TimingError):
            timing.check_step_resolution(1e9)
        with self.assertRaises(TimingError):
            timing.ticks_between(1e9, 1e9 + 20.0)
        self.assertEqual((env.calls, env.resets), (0, 0))


if __name__ == "__main__":
    unittest.main()
