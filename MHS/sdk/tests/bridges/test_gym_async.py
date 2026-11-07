"""Asynchronous Gymnasium environments (asyncio_owned_loop_v1): synthetic peers, never a real remote simulator."""
from __future__ import annotations

import asyncio
import copy
import threading
import time
import unittest
import warnings

from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.bridge.gym_async import AsyncProfile, AsyncProfileError, OwnedLoop
from mhs.bridge.gymnasium import GymnasiumBridge
from tests.bridges.support import Box

STEP, RESET, SEED = "cap.world.step.v1", "cap.world.reset.v1", "cap.world.seed.v1"
ACTION = {"values": [0.5, 0.0, -0.5]}

PROFILE = {
    "mode": "asyncio_owned_loop_v1", "step": "coroutine", "reset": "sync", "reset_kwargs": [],
    "step_timeout_s": 0.5, "reset_timeout_s": 0.5, "close_timeout_s": 0.5,
    "source_refs": ["synthetic-peer.py:1"],
}
STOPPING = {**PROFILE, "remote_stop": "world.pause", "stop_probe": "world.is_paused",
            "stop_timeout_s": 0.3, "settle_timeout_s": 0.3}


def code(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


class World:
    """A steppable remote world: it advances only inside a step, and pause() stops it."""

    def __init__(self, env: "AsyncPeer"):
        self.env = env
        self.paused = True
        self.pauses = 0
        self.probe_answer = True
        self.pause_error: BaseException | None = None

    def pause(self) -> str:
        self.env.threads.append(("pause", threading.current_thread().name))
        if self.pause_error is not None:
            raise self.pause_error
        self.pauses += 1
        self.paused = True
        release = self.env.remote_done
        if release is not None and not release.is_set():
            release.set()   # a paused world completes the remote move it was running
        return "paused"

    def is_paused(self):
        self.env.threads.append(("is_paused", threading.current_thread().name))
        return self.probe_answer if self.paused else False


class AsyncPeer:
    """Two-stage coroutine step (start a remote move, then await it), synchronous reset and close."""

    def __init__(self):
        self.action_space = Box([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])
        self.observation_space = Box([-1e9] * 4, [1e9] * 4)
        self.dt = 0.1
        self.position = [0.0, 0.0, 0.0]
        self.threads: list[tuple[str, str]] = []
        self.world = World(self)
        self.remote_delay = 0.0          # seconds the remote move takes (asyncio sleep: the loop stays free)
        self.block: threading.Event | None = None   # a blocking call inside step (the loop is NOT free)
        self.hold = False                # the remote move waits until the world is paused
        self.remote_done: asyncio.Event | None = None
        self.steps_started = self.steps_finished = 0
        self.resets = self.closes = 0
        self.reset_kwargs: list[dict] = []
        self.close_block: threading.Event | None = None
        self.step_error: BaseException | None = None
        self.return_sync = False

    def reset(self, **kwargs):
        self.threads.append(("reset", threading.current_thread().name))
        self.reset_kwargs.append(dict(kwargs))
        self.resets += 1
        self.position = [0.0, 0.0, 0.0]
        return [0.0, 0.0, 0.0, 0.0]

    def step(self, action):
        if self.return_sync:
            return [0.0] * 4, 0.0, False, {}
        return self._step(action)

    async def _step(self, action):
        self.threads.append(("step", threading.current_thread().name))
        self.steps_started += 1
        if self.step_error is not None:
            raise self.step_error
        self.world.paused = False
        self.remote_done = asyncio.Event()
        move = asyncio.ensure_future(self._remote_move(list(action)))
        if self.block is not None:
            self.block.wait(5.0)          # like a synchronous continue_for_sim_time inside the coroutine
        await move
        self.world.paused = True
        self.steps_finished += 1
        observation = [*self.position, 0.0]
        return observation, -sum(abs(x) for x in self.position), False, {"status": "Running"}

    async def _remote_move(self, action):
        if self.hold:
            await self.remote_done.wait()
        elif self.remote_delay:
            await asyncio.sleep(self.remote_delay)
        self.position = [p + 0.1 * a for p, a in zip(self.position, action)]

    def close(self):
        self.threads.append(("close", threading.current_thread().name))
        if self.close_block is not None:
            self.close_block.wait(5.0)
        self.closes += 1


def make(profile=PROFILE, **options):
    env = AsyncPeer()
    bridge = GymnasiumBridge(env=env, asynchronous=copy.deepcopy(profile), device_id="sim/async", **options)
    return env, bridge


class AsyncProfileTests(unittest.TestCase):
    def test_profile_validation(self):
        AsyncProfile.resolve(PROFILE)
        AsyncProfile.resolve(STOPPING)
        bad = [
            {**PROFILE, "mode": "asyncio"}, {**PROFILE, "step": "async"}, {**PROFILE, "reset_kwargs": ["seed", "seed"]},
            {**PROFILE, "reset_kwargs": ["render"]}, {**PROFILE, "step_timeout_s": 0}, {**PROFILE, "step_timeout_s": True},
            {**PROFILE, "close_timeout_s": float("inf")}, {**PROFILE, "remote_stop": "world.pause()"},
            {**PROFILE, "stop_probe": "world.is_paused"}, {**PROFILE, "stop_timeout_s": 1.0},
            {**PROFILE, "source_refs": "x.py:1"}, {**PROFILE, "extra": 1},
            {key: value for key, value in PROFILE.items() if key != "step_timeout_s"},
            {**PROFILE, "remote_stop": "world.pause"},   # a remote stop needs explicit stop/settle bounds
        ]
        for config in bad:
            with self.subTest(config=config), self.assertRaises(AsyncProfileError):
                AsyncProfile.resolve(config)

    def test_bridge_refuses_incompatible_profiles(self):
        timing = {"mode": "physics_ticks_v1", "control_decimation": 1, "physics_timestep_attr": "dt",
                  "physics_clock_attr": "dt", "native_autoreset": False, "reset_advances_physics": False}
        for extra in ({"timing": timing},
                      {"checkpoint": {"profile": "json_state_v1", "getter": "get_state", "setter": "set_state"}},
                      {"dm_env": {"profile": "dm_env_v1"}}, {"asynchronous": {**PROFILE, "mode": "x"}}):
            with self.subTest(extra=sorted(extra)):
                options = {"asynchronous": PROFILE, **extra}
                with self.assertRaises(Exception) as caught:
                    GymnasiumBridge(env=AsyncPeer(), **options)
                self.assertEqual(code(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


class OwnedLoopExecutionTests(unittest.TestCase):
    def test_coroutine_step_and_sync_reset_run_on_one_owned_thread(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        out = bridge.call(STEP, {"ticks": 2, "action": ACTION})
        self.assertEqual(env.steps_finished, 2)
        self.assertAlmostEqual(out["observation"]["values"][0], 0.1)
        names = {name for _kind, name in env.threads}
        self.assertEqual(len(names), 1, env.threads)
        self.assertNotEqual(names.pop(), threading.current_thread().name)
        self.assertEqual(env.reset_kwargs, [{}])     # the declared signature: no seed, no options

    def test_declared_kinds_are_enforced_without_running_stray_coroutines(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        env.return_sync = True
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        # A coroutine returned where the profile declares a synchronous reset is closed, never awaited.
        env2, bridge2 = make({**PROFILE, "reset": "sync"})
        self.addCleanup(bridge2.close)

        async def async_reset(**_kwargs):
            env2.resets += 1000
            return [0.0] * 4
        env2.reset = async_reset
        with warnings.catch_warnings():
            warnings.simplefilter("error")   # "coroutine was never awaited" would fail here
            with self.assertRaises(Exception) as caught:
                bridge2.call(RESET, {})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        self.assertEqual(env2.resets, 0)

    def test_native_error_is_a_fault_and_the_loop_is_free_again(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        env.step_error = RuntimeError("remote refused the move")
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        self.assertIsNone(bridge._owned_loop.owned())
        env.step_error = None
        bridge.call(STEP, {"ticks": 1, "action": ACTION})

    def test_local_timeout_keeps_remote_work_owned_until_it_settles(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        bridge.call(STEP, {"ticks": 1, "action": ACTION})
        env.remote_delay = 1.0
        started = time.monotonic()
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
        self.assertLess(time.monotonic() - started, 0.9)
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertTrue(caught.exception.data["details"]["may_have_effect"])
        owned = bridge._owned_loop.owned()
        self.assertEqual((owned["kind"], owned["abandoned"]), ("step", True))
        # While owned: no new native work, no safe-state claim, no safety reset.
        with self.assertRaises(Exception) as caught:
            bridge.call(RESET, {})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.BUSY")
        self.assertIsInstance(caught.exception, signals.Busy)
        self.assertEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})
        with self.assertRaises(Exception) as caught:
            bridge.reset()
        self.assertEqual(code(caught.exception), "MHS.SAFETY.RESET_REFUSED")
        # The remote work was not cancelled: it completes and is recorded as a late settlement.
        self.assertTrue(bridge._owned_loop.wait_idle(3.0))
        self.assertEqual(env.steps_finished, 2)
        self.assertEqual(bridge._owned_loop.describe()["late"][0]["outcome"], "returned")
        self.assertNotEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})
        bridge.reset()
        # The world is unverified until an explicit reset.
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        env.remote_delay = 0.0
        bridge.call(RESET, {})
        bridge.call(STEP, {"ticks": 1, "action": ACTION})

    def test_cancellation_is_observed_between_native_calls_only(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        env.remote_delay = 0.15
        cancel = threading.Event()
        context = BridgeContext(cancel_event=cancel)
        threading.Timer(0.05, cancel.set).start()
        with self.assertRaises(signals.Cancelled):
            bridge.call(STEP, {"ticks": 5, "action": ACTION}, context)
        # The in-flight call completed (never cancelled locally); no further call started.
        self.assertEqual((env.steps_started, env.steps_finished), (1, 1))
        self.assertIsNone(bridge._owned_loop.owned())

    def test_no_world_call_is_dispatched_after_an_estop(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        env.remote_delay = 0.1
        outcome = {}

        def step():
            try:
                outcome["out"] = bridge.call(STEP, {"ticks": 5, "action": ACTION})
            except BaseException as exc:  # noqa: BLE001
                outcome["error"] = exc
        caller = threading.Thread(target=step)
        caller.start()
        self.assertTrue(_wait(lambda: env.steps_started == 1))
        self.assertTrue(bridge.estop("between ticks")["confirmed"])
        caller.join(2)
        self.assertIsInstance(outcome.get("error"), signals.Cancelled)
        self.assertEqual((env.steps_started, env.steps_finished), (1, 1))   # the admitted tick settled; no other
        kinds = [kind for kind, _name in env.threads]
        self.assertNotIn("step", kinds[kinds.index("pause"):])

    def test_a_cancelled_operation_is_never_dispatched(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        cancel = threading.Event()
        context = BridgeContext(cancel_event=cancel)
        original = bridge._native_invoke

        def cancel_then_invoke(kind, fn):
            cancel.set()        # cancelled after the call-start check, before submission to the loop
            return original(kind, fn)
        bridge._native_invoke = cancel_then_invoke
        with self.assertRaises(signals.Cancelled):
            bridge.call(STEP, {"ticks": 1, "action": ACTION}, context)
        self.assertEqual((env.resets, env.steps_started), (0, 0))   # not even the implicit first reset ran

    def test_seedless_signature_serves_no_seed(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        ids = [item["capability_id"] for item in bridge.capabilities()]
        self.assertEqual(ids, [STEP, RESET])
        self.assertEqual({item["determinism"] for item in bridge.capabilities()}, {"none"})
        with self.assertRaises(Exception) as caught:
            bridge.call(RESET, {"options": {"x": 1}})
        self.assertEqual(code(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
        with self.assertRaises(Exception) as caught:
            bridge.call(SEED, {"seed": 1})
        self.assertEqual(code(caught.exception), "MHS.CAPABILITY.NOT_BOUND")
        self.assertEqual(env.resets, 0)
        out = bridge.call(RESET, {"seed": 3})   # accepted for the class contract, never passed or recorded
        self.assertEqual((env.reset_kwargs, out["seed"], bridge.world_state()["seed"]), ([{}], 0, None))
        env2, bridge2 = make({**PROFILE, "reset_kwargs": ["seed", "options"]}, seed=7)
        self.addCleanup(bridge2.close)
        bridge2.call(RESET, {"options": {"x": 1}})
        self.assertEqual(env2.reset_kwargs, [{"seed": 7, "options": {"x": 1}}])
        self.assertIn(SEED, [item["capability_id"] for item in bridge2.capabilities()])


class AsyncEstopTests(unittest.TestCase):
    def test_software_latch_without_remote_stop_is_honest(self):
        env, bridge = make()
        self.addCleanup(bridge.close)
        self.assertIsNone(bridge.estop_native)
        self.assertEqual(bridge.estop("idle"), {})
        # The bridge latch refuses a direct caller. The owned-work case below runs after the safety reset.
        with self.assertRaises(Exception) as latched:
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
        self.assertEqual(code(latched.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(env.steps_started, 0)
        bridge.reset()
        env.hold = True
        caller = threading.Thread(target=lambda: self.assertRaises(Exception, bridge.call, STEP,
                                                                   {"ticks": 1, "action": ACTION}))
        caller.start()
        self.assertTrue(_wait(lambda: bridge._owned_loop.owned() is not None))
        with self.assertRaises(Exception) as caught:
            bridge.estop("owned")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertFalse(caught.exception.data["details"]["safe_state_achieved"])
        caller.join(2)
        _release(bridge, env)
        self.assertTrue(bridge._owned_loop.wait_idle(2))
        self.assertEqual(bridge.estop("settled"), {})

    def test_remote_stop_runs_on_the_owned_loop_while_the_step_awaits(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        self.assertEqual(bridge.estop_native, "world.pause")
        env.hold = True       # the remote move only ends when the world is paused
        outcome = {}

        def step():
            try:
                outcome["out"] = bridge.call(STEP, {"ticks": 1, "action": ACTION})
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = exc
        caller = threading.Thread(target=step)
        caller.start()
        self.assertTrue(_wait(lambda: env.steps_started == 1))
        result = bridge.estop("stop the remote move")
        self.assertEqual(result, {"remote_stop": "world.pause", "stop_probe": "world.is_paused", "confirmed": True})
        caller.join(2)
        self.assertIn("out", outcome)           # the step settled because the world paused
        loop_thread = {name for kind, name in env.threads if kind == "step"}
        self.assertEqual({name for kind, name in env.threads if kind in ("pause", "is_paused")}, loop_thread)
        self.assertNotEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})

    def test_stop_behind_a_blocked_loop_is_unknown_then_confirmed_afresh(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        env.block = threading.Event()       # a synchronous native call holds the loop thread
        caller = threading.Thread(target=lambda: _swallow(bridge.call, STEP, {"ticks": 1, "action": ACTION}))
        caller.start()
        self.assertTrue(_wait(lambda: env.steps_started == 1))
        with self.assertRaises(Exception) as caught:
            bridge.estop("blocked")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertIsNotNone(bridge._owned_loop.owned_stop())   # queued, owned, never dropped
        self.assertEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})
        with self.assertRaises(Exception):
            bridge.reset()
        env.block.set()
        caller.join(3)
        self.assertTrue(_wait(lambda: bridge._owned_loop.owned_stop() is None))
        self.assertEqual(env.world.pauses, 1)   # the queued stop ran once the loop was free
        self.assertEqual(bridge.estop("again")["confirmed"], True)
        self.assertEqual(env.world.pauses, 2)   # a fresh stop, fresh evidence
        bridge.reset()

    def test_probe_refusal_and_stop_failure_are_unconfirmed(self):
        env, bridge = make(STOPPING)
        self.addCleanup(bridge.close)
        env.world.probe_answer = "yes"          # only the exact True confirms
        with self.assertRaises(Exception) as caught:
            bridge.estop("probe")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        with self.assertRaises(Exception) as caught:
            bridge.reset()
        self.assertEqual(code(caught.exception), "MHS.SAFETY.RESET_REFUSED")
        env.world.probe_answer = True
        env.world.pause_error = RuntimeError("server refused pause")
        with self.assertRaises(Exception):
            bridge.estop("stop raises")
        self.assertEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})
        env.world.pause_error = None
        bridge.estop("confirmed")
        bridge.reset()
        self.assertNotEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})


class AsyncCloseTests(unittest.TestCase):
    def test_idle_close_stops_then_closes_on_the_loop_and_settles(self):
        env, bridge = make(STOPPING)
        bridge.call(STEP, {"ticks": 1, "action": ACTION})
        loop = bridge._owned_loop
        bridge.close()
        self.assertTrue(bridge._cleanup_done.wait(2))
        self.assertEqual((env.closes, env.world.pauses), (1, 1))
        kinds = [kind for kind, _name in env.threads]
        self.assertLess(kinds.index("pause"), kinds.index("close"))
        self.assertEqual(len({name for _kind, name in env.threads}), 1)
        self.assertFalse(loop.thread_alive)
        self.assertEqual(bridge.async_status()["close"], "settled")
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 1, "action": ACTION})

    def test_close_defers_while_work_is_owned_then_runs_exactly_once(self):
        env, bridge = make()
        env.remote_delay = 0.8
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
        bridge.close()
        self.assertEqual(env.closes, 0)                       # never raced with the owned step
        self.assertTrue(bridge.async_status()["close"].startswith("deferred"))
        self.assertTrue(bridge._cleanup_done.wait(3))
        time.sleep(0.05)
        self.assertEqual(env.closes, 1)
        self.assertEqual(bridge.async_status()["close"], "settled")

    def test_hung_close_is_reported_unsettled(self):
        env, bridge = make()
        bridge.call(RESET, {})
        env.close_block = threading.Event()
        bridge.close()
        self.assertFalse(bridge._cleanup_done.is_set())
        self.assertTrue(bridge.async_status()["close"].startswith("unsettled"))
        self.assertEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})
        env.close_block.set()
        self.assertTrue(_wait(lambda: not bridge._owned_loop.owns_any()))
        self.assertEqual(bridge._owned_loop.shutdown(1), "settled")   # test hygiene: stop the daemon loop


class OwnedLoopUnitTests(unittest.TestCase):
    def test_single_flight_and_stop_lane(self):
        loop = OwnedLoop("test-owned")
        release = threading.Event()
        work = loop.submit("step", lambda: release.wait(2), expect="sync")
        with self.assertRaises(Exception):
            loop.submit("reset", lambda: None, expect="sync")
        stop = loop.submit("remote_stop", lambda: "queued", expect="any", stop=True)
        with self.assertRaises(Exception):
            loop.submit("remote_stop", lambda: None, expect="any", stop=True)
        release.set()
        self.assertTrue(loop.wait(work, 2))
        self.assertEqual(loop.wait(stop, 2), "queued")
        self.assertTrue(_wait(lambda: not loop.owns_any()))
        self.assertEqual(loop.shutdown(1), "settled")


class OwnedShutdownTests(unittest.TestCase):
    def test_shutdown_refuses_while_ordinary_or_stop_work_is_owned(self):
        for stop in (False, True):
            with self.subTest(stop=stop):
                loop = OwnedLoop("test-shutdown-owned")
                release = threading.Event()
                work = loop.submit("remote_stop" if stop else "step", lambda: release.wait(2), expect="sync",
                                   stop=stop)
                self.assertEqual(loop.shutdown(1), "owned")
                self.assertTrue(loop.thread_alive)                 # the loop keeps serving the owned work
                release.set()
                self.assertTrue(loop.wait(work, 2))
                self.assertTrue(_wait(lambda: not loop.owns_any()))
                self.assertEqual(loop.shutdown(1), "settled")
                self.assertFalse(loop.thread_alive)


class OwnershipReleaseOrderingTests(unittest.TestCase):
    """A caller that returns from a call never sees that call as still owned (no sleep, many repetitions)."""

    def test_returned_calls_are_released_before_delivery(self):
        loop = OwnedLoop("test-release-order")
        self.addCleanup(loop.shutdown, 1)

        async def remote():
            await asyncio.sleep(0)
            return "done"
        for index in range(300):
            stop = index % 2 == 0
            self.assertEqual(loop.run("stop" if stop else "step", remote, expect="coroutine", timeout_s=2, stop=stop),
                             "done")
            self.assertFalse(loop.owns_any(), index)

    def test_confirmed_estop_is_immediately_safe(self):
        for _ in range(50):
            env, bridge = make(STOPPING)
            bridge.call(STEP, {"ticks": 1, "action": ACTION})
            self.assertTrue(bridge.estop("race")["confirmed"])
            self.assertNotEqual(bridge.safety_status(), {"safe_state": {"achieved": False}})
            bridge.close()


def _wait(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return bool(predicate())


def _swallow(fn, *args):
    try:
        fn(*args)
    except Exception:  # noqa: BLE001 - the test inspects bridge state instead
        pass


def _release(bridge, env):
    """Let a held remote move finish (as a remote completion would), from the owned loop."""
    loop = bridge._owned_loop._loop
    if env.remote_done is not None and loop is not None:
        loop.call_soon_threadsafe(env.remote_done.set)


if __name__ == "__main__":
    unittest.main()
