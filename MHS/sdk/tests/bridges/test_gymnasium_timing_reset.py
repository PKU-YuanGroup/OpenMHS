"""Resets that integrate physics (settling) under physics_ticks_v1, and the explicit checkpoint opt-out.

Synthetic clocks only: contract evidence, never SAPIEN, MuJoCo or hardware compatibility.
"""
from __future__ import annotations

import copy
import json
import types
import unittest

from mhs.bridge.base import BridgeContext
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.bridge.simulation_timing import CONTEXT_KEY, PhysicsTiming, SimulationTimingReport, TimingError
from tests.bridges.support import FakeCartPole
from tests.bridges.test_gymnasium_timing import CHECKPOINT, CONFIG, ClockEnv

STEP, RESET = "cap.world.step.v1", "cap.world.reset.v1"
ACTION = {"index": 1}
SETTLING = {**CONFIG, "reset_advances_physics": True, "reset_clock": "continue", "max_reset_ticks": 40}
RESTART = {**SETTLING, "reset_clock": "restart"}
#: The physics_ticks_v1 descriptor of CONFIG as produced before this extension (byte-identity pin).
V1_DESCRIPTOR = json.loads(
    '{"control_decimation": 5, "control_period_ms": 10.0, "mode": "physics_ticks_v1", "notes": ["Physics timestep '
    '2 ms; control period 10 ms (5 physics ticks). ticks is required and must be a positive multiple of 5; action '
    'is held for each opaque control call. Runtime clock deltas account completed physics ticks. Reset must return '
    'the clock to zero without integration; native autoreset and external clock advancement are unsupported. No '
    'wall-clock pacing. Source references are declarations, not validation evidence."], "physics_clock_attr": '
    '"data.time", "physics_timestep_attr": "model.opt.timestep", "physics_timestep_ms": 2.0, "source_refs": '
    '["synthetic-peer.py:1"], "tick_unit": "physics", "version": 1}')


class SettlingEnv(ClockEnv):
    """Reset settles the scene for ``settle`` physics ticks; the clock restarts or keeps running."""

    def __init__(self, *, settle=25, clock="continue", **kwargs):
        super().__init__(**kwargs)
        self.settle, self.clock = settle, clock
        self.reset_extra = 0.0

    def reset(self, **kwargs):
        self.resets += 1
        if self.clock == "restart":
            self.data.time = 0.0
        for _ in range(self.settle):
            self.data.time += self.model.opt.timestep
        self.data.time += self.reset_extra
        return FakeCartPole.reset(self, **kwargs)


def bridge_for(config, **env_options):
    env = SettlingEnv(**env_options)
    bridge = GymnasiumBridge(env=env, timing=copy.deepcopy(config))
    return env, bridge


def reset_report(bridge):
    context = BridgeContext()
    report = SimulationTimingReport(bridge.timing_descriptor(), None)
    context.extra[CONTEXT_KEY] = report
    return context, report


class IntegratingResetConfigTests(unittest.TestCase):
    def getter(self):
        env = types.SimpleNamespace(model=types.SimpleNamespace(opt=types.SimpleNamespace(timestep=0.002)),
                                    data=types.SimpleNamespace(time=0.0))
        return lambda name: getattr(env, name)

    def test_v1_declarations_are_byte_identical(self):
        self.assertEqual(PhysicsTiming.resolve(CONFIG, self.getter()).descriptor(), V1_DESCRIPTOR)

    def test_integrating_reset_requires_explicit_clock_semantics_and_bound(self):
        PhysicsTiming.resolve(SETTLING, self.getter())
        PhysicsTiming.resolve(RESTART, self.getter())
        bad = [
            {**CONFIG, "reset_clock": "continue"}, {**CONFIG, "max_reset_ticks": 10},
            {**SETTLING, "reset_clock": "rewind"}, {**SETTLING, "max_reset_ticks": 0},
            {**SETTLING, "max_reset_ticks": True}, {**SETTLING, "max_reset_ticks": 1_000_001},
            {key: value for key, value in SETTLING.items() if key != "max_reset_ticks"},
            {**SETTLING, "reset_advances_physics": "yes"}, {**SETTLING, "native_autoreset": True},
        ]
        for config in bad:
            with self.subTest(config=config), self.assertRaises(TimingError):
                PhysicsTiming.resolve(config, self.getter())
        descriptor = PhysicsTiming.resolve(SETTLING, self.getter()).descriptor()
        self.assertEqual((descriptor["reset_advances_physics"], descriptor["reset_clock"], descriptor["max_reset_ticks"]),
                         (True, "continue", 40))
        self.assertIn("up to 40 physics ticks (80 ms) of settling", descriptor["notes"][0])
        self.assertNotIn("Reset must return the clock to zero", descriptor["notes"][0])


class IntegratingResetBridgeTests(unittest.TestCase):
    def test_continue_clock_reset_ticks_are_measured_and_not_episode_ticks(self):
        env, bridge = bridge_for(SETTLING)
        self.addCleanup(bridge.close)
        context, report = reset_report(bridge)
        bridge.call(RESET, {}, context)
        snapshot = report.snapshot()
        self.assertEqual((snapshot["reset_integrated_ticks"], snapshot["reset_calls_verified"]), (25, 1))
        self.assertEqual(snapshot["reset_integrated_duration_ms"], 50.0)
        self.assertEqual((snapshot["completed_ticks"], snapshot["requested_ticks"]), (0, None))
        self.assertEqual(bridge.world_state()["tick"], 0)
        # Control ticks resume at the settled clock.
        step_context = BridgeContext()
        step_context.extra[CONTEXT_KEY] = SimulationTimingReport(bridge.timing_descriptor(), 10)
        out = bridge.call(STEP, {"ticks": 10, "action": ACTION}, step_context)
        self.assertEqual(out["tick"], 10)
        self.assertAlmostEqual(env.data.time, 0.07)
        # A second reset integrates from the running clock (continue semantics).
        context, report = reset_report(bridge)
        bridge.call(RESET, {}, context)
        self.assertEqual(report.snapshot()["reset_integrated_ticks"], 25)

    def test_restart_clock_counts_from_zero(self):
        env, bridge = bridge_for(RESTART, clock="restart", settle=30)
        self.addCleanup(bridge.close)
        env.data.time = 0.5   # whatever the clock was, a restart rewinds it first
        bridge._timing_last_clock = 0.5
        context, report = reset_report(bridge)
        bridge.call(RESET, {}, context)
        self.assertEqual(report.snapshot()["reset_integrated_ticks"], 30)

    def test_implicit_first_reset_and_autoreset_report_reset_ticks_in_the_step_receipt(self):
        env, bridge = bridge_for(SETTLING, terminate_after=2)
        self.addCleanup(bridge.close)
        bridge.autoreset = True
        context = BridgeContext()
        report = SimulationTimingReport(bridge.timing_descriptor(), 15)
        context.extra[CONTEXT_KEY] = report
        out = bridge.call(STEP, {"ticks": 15, "action": ACTION}, context)
        snapshot = report.snapshot()
        self.assertEqual((snapshot["completed_ticks"], snapshot["reset_calls_verified"]), (15, 2))
        self.assertEqual(snapshot["reset_integrated_ticks"], 50)      # two settling resets of 25
        self.assertEqual(out["tick"], 5)

    def test_reset_beyond_its_declared_bound_or_off_grid_is_a_timing_fault(self):
        for settle, extra in ((41, 0.0), (10, 0.0007)):
            with self.subTest(settle=settle, extra=extra):
                env, bridge = bridge_for(SETTLING, settle=settle)
                self.addCleanup(bridge.close)
                env.reset_extra = extra
                context, report = reset_report(bridge)
                with self.assertRaises(Exception) as caught:
                    bridge.call(RESET, {}, context)
                self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.FAULTED")
                snapshot = report.snapshot()
                self.assertIsNone(snapshot["reset_integrated_ticks"])
                self.assertEqual(snapshot["accounting"], "unknown")
                with self.assertRaises(Exception) as caught:
                    bridge.call(STEP, {"ticks": 5, "action": ACTION})
                self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.PRECONDITION_UNMET")
                env.settle, env.reset_extra = 10, 0.0
                bridge.call(RESET, {}, reset_report(bridge)[0])   # a verified explicit reset clears the fault
                bridge.call(STEP, {"ticks": 5, "action": ACTION})

    def test_non_integrating_v1_still_refuses_a_settling_reset(self):
        env, bridge = bridge_for(CONFIG, settle=3, clock="restart")
        self.addCleanup(bridge.close)
        with self.assertRaises(Exception) as caught:
            bridge.call(RESET, {})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.FAULTED")

    def test_checkpoint_round_trip_stays_control_aligned(self):
        env = SettlingEnv(settle=7)
        bridge = GymnasiumBridge(env=env, timing=copy.deepcopy(SETTLING), checkpoint=copy.deepcopy(CHECKPOINT))
        self.addCleanup(bridge.close)
        bridge.call(RESET, {}, reset_report(bridge)[0])
        bridge.call(STEP, {"ticks": 5, "action": ACTION})
        snapshot = bridge.snapshot()
        bridge.call(STEP, {"ticks": 10, "action": ACTION})
        restored = bridge.restore(snapshot)
        self.assertEqual(restored["world"]["tick"], 5)
        self.assertAlmostEqual(env.data.time, 0.024)   # 7 settling + 5 control ticks of 2 ms

    def test_explicit_checkpoint_opt_out(self):
        bridge = GymnasiumBridge(env=FakeCartPole(), checkpoint={"profile": "none", "reason": "native state omits RNG"})
        self.addCleanup(bridge.close)
        self.assertFalse(bridge.snapshot_supported)
        self.assertEqual(bridge.checkpoint_opt_out_reason(), "native state omits RNG")
        with self.assertRaises(Exception) as caught:
            bridge.snapshot()
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.CAPABILITY.NOT_BOUND")
        for bad in ({"profile": "none"}, {"profile": "none", "reason": " "}, {"profile": "none", "reason": "x", "getter": "a"},
                    {"profile": "none", "reason": "x" * 301}):
            with self.subTest(bad=bad), self.assertRaises(Exception) as caught:
                GymnasiumBridge(env=FakeCartPole(), checkpoint=bad)
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.ADAPTER.MANIFEST_INVALID")


if __name__ == "__main__":
    unittest.main()
