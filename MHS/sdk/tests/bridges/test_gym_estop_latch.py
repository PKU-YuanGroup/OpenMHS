"""Gymnasium bridge e-stop latch and stop-attempt generation.

Synthetic peers only. No simulator run and no hardware run. The cases pin two
fail-closed rules:

* a slower confirming e-stop cannot clear a failure a newer attempt or close
  already recorded, and it does not return a confirmed stop;
* a direct caller is refused effectful world calls after an e-stop until the
  safety reset clears the bridge latch, with or without a cancel event.
"""
from __future__ import annotations

import threading
import unittest

from mhs import signals
from mhs.bridge.gymnasium import GymnasiumBridge
from tests.bridges.support import FakeCartPole
from tests.bridges.test_gym_async import ACTION as ASYNC_ACTION
from tests.bridges.test_gym_async import STOPPING, code, make
from tests.bridges.test_sim_host import bridge as hosted_bridge

STEP = "cap.world.step.v1"
RESET = "cap.world.reset.v1"
SEED = "cap.world.seed.v1"
RESTORE = "cap.world.restore.v1"
STATE = "cap.world.state.v1"
SYNC_ACTION = {"index": 1}
NOT_ACHIEVED = {"safe_state": {"achieved": False}}


class BlockingCartPole(FakeCartPole):
    """Blocks inside a native step until released."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self.entered = threading.Event()

    def step(self, action):
        self.entered.set()
        if not self.release.wait(5):
            raise AssertionError("the test did not release the native step")
        return super().step(action)


def _run(fn):
    outcome: dict = {}

    def work():
        try:
            outcome["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - the test inspects it
            outcome["error"] = exc

    worker = threading.Thread(target=work)
    worker.start()
    return worker, outcome


class GenerationTests(unittest.TestCase):
    def test_a_slower_confirming_estop_cannot_clear_a_newer_failure(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        bridge.call(STEP, {"ticks": 1, "action": ASYNC_ACTION})
        real = bridge._commit_stop_attempt
        phase = {"arm": True}
        newer: dict = {}

        def wrapped(generation, unconfirmed):
            # The slow attempt has already probed True and is about to clear the flag.
            if unconfirmed is None and phase["arm"]:
                phase["arm"] = False
                env.world.pause_error = RuntimeError("newer stop refused")
                worker, newer_outcome = _run(lambda: bridge.estop("newer"))
                worker.join(3)
                self.assertFalse(worker.is_alive(), "the newer stop did not finish")
                newer.update(newer_outcome)
            return real(generation, unconfirmed)

        bridge._commit_stop_attempt = wrapped
        with self.assertRaises(Exception) as slow:
            bridge.estop("slow")
        self.assertEqual(code(slow.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertIn("superseded", str(slow.exception))
        self.assertNotIn("value", newer)
        self.assertEqual(code(newer.get("error")), "MHS.OUTCOME.UNKNOWN")
        self.assertIn("RuntimeError", bridge._stop_unconfirmed or "")
        self.assertEqual(bridge.safety_status(), NOT_ACHIEVED)
        with self.assertRaises(Exception) as refused:
            bridge.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.RESET_REFUSED")

    def test_a_close_failure_survives_a_slower_confirmation(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        bridge.call(STEP, {"ticks": 1, "action": ASYNC_ACTION})
        real = bridge._commit_stop_attempt
        phase = {"arm": True}

        def wrapped(generation, unconfirmed):
            if unconfirmed is None and phase["arm"]:
                phase["arm"] = False
                env.world.pause_error = RuntimeError("close stop refused")
                bridge.close()
            return real(generation, unconfirmed)

        bridge._commit_stop_attempt = wrapped
        with self.assertRaises(Exception) as slow:
            bridge.estop("slow")
        self.assertEqual(code(slow.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertIn("superseded", str(slow.exception))
        self.assertIn("remote stop before close raised RuntimeError", bridge._stop_unconfirmed or "")
        self.assertEqual(bridge.safety_status(), NOT_ACHIEVED)

    def test_a_later_confirmed_estop_clears_the_unconfirmed_flag(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        env.world.probe_answer = "no"
        with self.assertRaises(Exception) as failed:
            bridge.estop("probe")
        self.assertEqual(code(failed.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(bridge.safety_status(), NOT_ACHIEVED)
        env.world.probe_answer = True
        confirmed = bridge.estop("again")
        self.assertEqual(confirmed["confirmed"], True)
        self.assertIsNone(bridge._stop_unconfirmed)
        self.assertNotEqual(bridge.safety_status(), NOT_ACHIEVED)
        self.assertEqual(bridge.reset(), {})
        self.assertEqual(bridge.safety_status(), {})
        bridge.call(STEP, {"ticks": 1, "action": ASYNC_ACTION})
        self.assertEqual(env.steps_started, 1)

    def test_a_direct_caller_after_a_confirmed_remote_stop_is_refused_until_reset(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        bridge.call(STEP, {"ticks": 1, "action": ASYNC_ACTION})
        confirmed = bridge.estop("stop")
        self.assertEqual(confirmed["confirmed"], True)
        self.assertEqual(bridge.safety_status(), {})
        with self.assertRaises(Exception) as refused:
            bridge.call(STEP, {"ticks": 1, "action": ASYNC_ACTION})
        self.assertEqual(code(refused.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertTrue(refused.exception.data["details"]["preempted_by_estop"])
        self.assertEqual(env.steps_started, 1)
        bridge.reset()
        bridge.call(STEP, {"ticks": 1, "action": ASYNC_ACTION})
        self.assertEqual(env.steps_started, 2)


class HostedGenerationTests(unittest.TestCase):
    def test_a_slower_hosted_confirmation_cannot_clear_a_newer_readback_failure(self):
        made, _created = hosted_bridge(self)
        made.call(STEP, {"ticks": 1, "action": {"values": [0.5, 0.5]}})
        env = made._env
        real_readback = env.readback
        calls = {"n": 0}

        def readback():
            calls["n"] += 1
            if calls["n"] >= 2:
                return False
            return real_readback()

        env.readback = readback
        real = made._commit_stop_attempt
        phase = {"arm": True}
        newer: dict = {}

        def wrapped(generation, unconfirmed):
            if unconfirmed is None and phase["arm"]:
                phase["arm"] = False
                worker, outcome = _run(lambda: made.estop("newer"))
                worker.join(5)
                self.assertFalse(worker.is_alive(), "the newer hosted stop did not finish")
                newer.update(outcome)
            return real(generation, unconfirmed)

        made._commit_stop_attempt = wrapped
        with self.assertRaises(Exception) as slow:
            made.estop("slow")
        self.assertEqual(code(slow.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertIn("superseded", str(slow.exception))
        self.assertNotIn("value", newer)
        self.assertEqual(code(newer.get("error")), "MHS.OUTCOME.UNKNOWN")
        self.assertIn("returned False", made._stop_unconfirmed or "")
        self.assertEqual(made.safety_status(), NOT_ACHIEVED)


class DirectCallerTests(unittest.TestCase):
    def test_effectful_calls_are_refused_and_reads_stay_available(self):
        env = FakeCartPole()
        bridge = GymnasiumBridge(env=env, device_id="sim/latch")
        self.addCleanup(bridge.close)
        bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})
        seeds = list(env.seeds)
        steps = env.native_steps
        self.assertEqual(bridge.estop("now"), {})
        self.assertEqual(bridge.safety_status(), {})
        for capability, args in (
            (STEP, {"ticks": 1, "action": SYNC_ACTION}),
            (RESET, {}),
            (SEED, {"seed": 3}),
            (RESTORE, {"snapshot": {"world": {}}}),
        ):
            with self.subTest(capability=capability):
                with self.assertRaises(Exception) as refused:
                    bridge.call(capability, args)
                self.assertEqual(code(refused.exception), "MHS.SAFETY.ESTOP_ENGAGED")
                self.assertTrue(refused.exception.data["details"]["preempted_by_estop"])
        with self.assertRaises(Exception) as restored:
            bridge.restore({"world": {}})
        self.assertEqual(code(restored.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.native_steps, steps)
        self.assertEqual(env.seeds, seeds)
        self.assertIsNone(bridge._pending_seed)
        self.assertEqual(bridge.read("world")["tick"], 1)
        self.assertEqual(bridge.world_state()["tick"], 1)
        self.assertEqual(bridge.call(STATE)["state"]["tick"], 1)
        self.assertEqual(bridge.reset(), {})
        self.assertEqual(bridge.call(STEP, {"ticks": 1, "action": {"index": 0}})["tick"], 2)
        self.assertEqual(env.native_steps, steps + 1)

    def test_an_in_flight_sync_step_is_cancelled_and_a_later_call_stays_latched(self):
        env = BlockingCartPole()
        bridge = GymnasiumBridge(env=env, device_id="sim/inflight")
        self.addCleanup(env.release.set)
        self.addCleanup(bridge.close)
        worker, outcome = _run(lambda: bridge.call(STEP, {"ticks": 4, "action": SYNC_ACTION}))
        self.assertTrue(env.entered.wait(2))
        with self.assertRaises(Exception) as stopping:
            bridge.estop("between ticks")
        # The mutation lock is held by the native step, so this attempt cannot confirm.
        # The latch is already set.
        self.assertEqual(code(stopping.exception), "MHS.OUTCOME.UNKNOWN")
        env.release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(outcome.get("error"), signals.Cancelled)
        self.assertNotEqual(code(outcome.get("error")), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.native_steps, 1)
        with self.assertRaises(Exception) as refused:
            bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})
        self.assertEqual(code(refused.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.native_steps, 1)
        self.assertEqual(bridge.reset(), {})
        self.assertEqual(bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})["tick"], 2)

    def test_an_estop_during_safety_reset_keeps_the_latch(self):
        env = FakeCartPole()
        bridge = GymnasiumBridge(env=env, device_id="sim/reset-race")
        self.addCleanup(bridge.close)
        bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})
        inner = bridge._lock
        fired = {"done": False}

        class Hook:
            def acquire(self, blocking=True, timeout=-1):
                if not fired["done"]:
                    fired["done"] = True
                    bridge.estop("during reset")
                return inner.acquire(blocking, timeout)

            def release(self):
                return inner.release()

        bridge._lock = Hook()
        self.assertEqual(bridge.reset(), {})
        bridge._lock = inner
        with self.assertRaises(Exception) as refused:
            bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})
        self.assertEqual(code(refused.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.native_steps, 1)
        self.assertEqual(bridge.reset(), {})
        self.assertEqual(bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})["tick"], 2)


class PendingStopResetTests(unittest.TestCase):
    """A direct safety reset must not release the latch while estop() has not returned."""

    def test_reset_during_owned_stop_submission_stays_refused_after_the_stop_fails(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        original = env.world
        entered, release = threading.Event(), threading.Event()

        class DelayedWorld:
            @property
            def pause(self):
                # Before OwnedLoop submits the stop. Nothing is owned yet.
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test release timed out")
                return original.pause

            def is_paused(self):
                return original.is_paused()

        env.world = DelayedWorld()
        original.pause_error = RuntimeError("native stop refused")
        worker, outcome = _run(lambda: bridge.estop("pending failed stop"))
        self.assertTrue(entered.wait(2), "the stop did not reach path resolution")
        self.assertTrue(bridge._effects_latched())
        with self.assertRaises(Exception) as refused:
            bridge.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(refused.exception.data["details"]["reason"], "stop_path_pending")
        self.assertTrue(bridge._effects_latched())
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive(), "the stop did not settle")
        self.assertEqual(code(outcome.get("error")), "MHS.OUTCOME.UNKNOWN")
        env.world = original
        self.assertEqual(bridge.safety_status(), NOT_ACHIEVED)
        self.assertTrue(bridge._effects_latched())
        with self.assertRaises(Exception) as step:
            bridge.call(STEP, {"ticks": 1, "action": ASYNC_ACTION})
        self.assertEqual(code(step.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.steps_started, 0)

    def test_reset_during_hosted_readback_does_not_unfence_or_confirm_clear(self):
        made, created = hosted_bridge(self)
        action = {"values": [0.5, 0.5]}
        made.call(STEP, {"ticks": 1, "action": action})
        entered, release = threading.Event(), threading.Event()
        real_readback = created.readback

        def delayed_readback():
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test release timed out")
            return real_readback()

        created.readback = delayed_readback
        worker, outcome = _run(lambda: made.estop("between stop and read-back"))
        self.assertTrue(entered.wait(3), "the stop did not reach read-back")
        self.assertTrue(created.state()["fenced"])
        self.assertTrue(made._effects_latched())
        self.assertIsNone(made._stop_unconfirmed)
        with self.assertRaises(Exception) as refused:
            made.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(refused.exception.data["details"]["reason"], "stop_path_pending")
        self.assertTrue(created.state()["fenced"])
        self.assertTrue(made._effects_latched())
        with self.assertRaises(Exception) as step:
            made.call(STEP, {"ticks": 1, "action": action})
        self.assertEqual(code(step.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(made.world_state()["tick"], 1)
        release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive(), "the hosted stop did not settle")
        self.assertEqual(outcome.get("value"), {
            "stop": "conn.pause", "readback": "conn.properties().paused", "confirmed": True,
        })
        self.assertNotIn("error", outcome)
        self.assertTrue(made._effects_latched())
        self.assertEqual(made.safety_status(), {})
        with self.assertRaises(Exception) as later:
            made.call(STEP, {"ticks": 1, "action": action})
        self.assertEqual(code(later.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(made.world_state()["tick"], 1)
        self.assertEqual(made.reset(), {})
        self.assertFalse(created.state()["fenced"])
        self.assertEqual(made.call(STEP, {"ticks": 1, "action": action})["tick"], 2)

    def test_reset_during_sync_safe_state_keeps_the_latch(self):
        env = FakeCartPole()
        bridge = GymnasiumBridge(env=env, device_id="sim/pending-sync")
        self.addCleanup(bridge.close)
        bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})
        steps = env.native_steps
        entered, release = threading.Event(), threading.Event()
        real = bridge.safe_state

        def delayed(ctx=None):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test release timed out")
            return real(ctx)

        bridge.safe_state = delayed
        worker, outcome = _run(lambda: bridge.estop("during safe_state"))
        self.assertTrue(entered.wait(2), "estop did not enter safe_state")
        self.assertTrue(bridge._effects_latched())
        with self.assertRaises(Exception) as refused:
            bridge.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.RESET_REFUSED")
        self.assertEqual(refused.exception.data["details"]["reason"], "stop_path_pending")
        self.assertTrue(bridge._effects_latched())
        with self.assertRaises(Exception) as step:
            bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})
        self.assertEqual(code(step.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.native_steps, steps)
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive(), "estop did not return")
        self.assertEqual(outcome.get("value"), {})
        self.assertTrue(bridge._effects_latched())
        self.assertEqual(bridge.safety_status(), {})
        with self.assertRaises(Exception) as later:
            bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})
        self.assertEqual(code(later.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.native_steps, steps)
        self.assertEqual(bridge.reset(), {})
        self.assertEqual(bridge.call(STEP, {"ticks": 1, "action": SYNC_ACTION})["tick"], 2)


if __name__ == "__main__":
    unittest.main()
