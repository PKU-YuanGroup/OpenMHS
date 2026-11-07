"""Gymnasium bridge family (MHS-000 section 9.3), aligned with the ``cap.world.*`` classes.

Lazily imports ``gymnasium`` (falling back to the legacy ``gym`` package) and
serves an environment through:

* ``cap.world.step.v1``  -- input ``{ticks, action}``; steps ``ticks`` times
  (stopping at a terminal state unless ``autoreset=True``) and returns
  ``{observation, reward, terminated, truncated, tick, state_hash}``;
* ``cap.world.reset.v1`` -- ``{seed?, options?}`` -> ``{observation, seed}``;
* ``cap.world.seed.v1``  -- ``{seed}`` -> ``{seed, accepted}`` (used by the next reset).

Actions and observations are JSON objects derived from the spaces (SIM-03):
``Discrete(n)`` is ``{"index": i}``, ``Box`` is ``{"values": [..]}`` with the
space's ``low``/``high`` as per-element limits, ``Dict`` maps to named fields
(a ``Discrete`` field is an integer, a ``Box`` field a number array, a
nested ``Dict`` an object bounded member by member, a ``Tuple`` field an
array of its items), ``MultiDiscrete``/``MultiBinary`` are
``{"values": [ints]}`` and ``Tuple`` is ``{"items": [..]}``.  The elements of
a ``Tuple`` (top level or inside a ``Dict``) get structure but no limits: a
simulation-only residual.  :meth:`GymnasiumBridge.capabilities` publishes the
derived input schema and limits; :meth:`call` enforces them itself too
(structure, then limits -> ``MHS.SAFETY.ENVELOPE_VIOLATION``, then the rest of
the schema) before any ``env.step``.

The derived limits say where the space came from.  A space of an environment
the bridge built itself (``gym.make(env_id)``, the ``env_spec`` factory) is
``upstream_code``; a pre-built ``env=`` (a driver package's fake backend, a
test double) is not: its limits carry no ``source``, only a ``ref`` that
names ``env_origin``.  ``action_space_ref`` (``path:LINE`` of the upstream
code that defines the space) makes them ``upstream_code`` with that ref.

An ``asynchronous`` profile (``asyncio_owned_loop_v1``, :mod:`mhs.bridge.gym_async`)
awaits ``async def step``/``reset`` on one owned event loop within declared
bounds; a call that outlives its bound stays owned (never cancelled locally),
the e-stop reaches an explicitly declared remote stop or reports an honest
outcome, and close is settled.  Engaging the e-stop latches the bridge: a later
effectful call is refused until ``reset`` (the safety reset) clears that latch,
with or without the endpoint's cancel event.  That reset is refused while the
e-stop that set the latch has not yet answered.  Only the latest stop attempt may
clear an unconfirmed stop, so a slower confirmation cannot report the safe
state after a newer attempt or close recorded a failure.  A ``process`` profile (``isolated_process_v1``,
:mod:`mhs.bridge.sim_host`) drives an environment built in a child process the
endpoint owns: exits inside the environment end only that process, every call
is bounded, and the e-stop is the declared simulator stop confirmed by its
declared read-back, or an unreached safe state.  A ``dm_env`` profile (``dm_env_v1``,
:mod:`mhs.bridge.dm_env_adapter`) maps dm_env ``TimeStep`` results; a TimeStep
that reaches the tuple path without it is refused, never misread.

Protocol snapshots require an explicit ``checkpoint`` JSON-state profile.
The profile resolves declared methods on the supplied environment and exposes
its bounded native checkpoint in the served world state. Method presence or
profile configuration alone never establishes exact determinism.
``cap.world.render.v1`` stays unbound until an artifact store exists.

The module is import-safe without gymnasium; pass a pre-built ``env=`` (tests
use fakes) or ``env_id=`` for ``gym.make``.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from functools import partial, wraps
import threading
import importlib
import json
import math
import sys
import time
from typing import Any, Mapping, Sequence

from mhs import canonical, signals
from mhs import limits as _limits
from mhs.bridge.base import Bridge, BridgeBusy, BridgeContext, MappingError, jsonable, make_mhs_error, unsupported
from mhs.bridge.base import main as _bridge_main
from mhs.bridge.dm_env_adapter import is_timestep_like

__all__ = ["GymnasiumBridge", "main"]

_FLOAT_MAX = sys.float_info.max
# Dict spaces nest at most this deep in the derived schema and limits; a
# deeper Dict member is refused by the schema (``{"not": {}}``).
_MAX_SPACE_DEPTH = 8
# Effectful world calls. A direct caller is refused these after the e-stop
# latch engages. Reads (``read``, state, snapshot) stay available.
_EFFECT_CALLS = frozenset({
    "cap.world.step.v1",
    "cap.world.reset.v1",
    "cap.world.seed.v1",
    "cap.world.restore.v1",
})


def _dict_items(space: Any) -> list[tuple[str, str, Any]]:
    """Map native string keys to distinct limit-path names without changing native calls.

    Existing identifier keys are retained. Other keys receive short numbered
    aliases in sorted native-key order; identifiers already present in the
    native Dict reserve their spelling. Descriptions disclose the mapping.
    """
    spaces = space.spaces
    if any(not isinstance(key, str) for key in spaces):
        raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", "Gym Dict action keys must be strings",
                             {"retryable": False})
    def ordinary(key: str) -> bool:
        return bool(key) and key.isascii() and (key[0].isalpha() or key[0] == "_") and all(
            char.isalnum() or char == "_" for char in key)
    aliases = {key: key for key in spaces if ordinary(key)}
    reserved = set(aliases.values())
    number = 0
    for key in sorted(key for key in spaces if key not in aliases):
        while f"mhs_key_{number}" in reserved:
            number += 1
        alias = f"mhs_key_{number}"
        aliases[key] = alias
        reserved.add(alias)
        number += 1
    return [(aliases[key], key, sub) for key, sub in spaces.items()]


def _space_kind_by_name(name: str, space: Any) -> str | None:
    if name == "Discrete" and hasattr(space, "n"):
        return "discrete"
    if name == "Box" and hasattr(space, "low") and hasattr(space, "high"):
        return "box"
    if name == "Dict" and isinstance(getattr(space, "spaces", None), Mapping):
        return "dict"
    if name == "MultiDiscrete" and hasattr(space, "nvec"):
        return "multidiscrete"
    if name == "MultiBinary" and hasattr(space, "n"):
        return "multibinary"
    if name == "Tuple" and isinstance(getattr(space, "spaces", None), (list, tuple)):
        return "tuple"
    return None


def _space_kind(space: Any) -> str | None:
    """The space family, by class name (subclasses included); a space with ``low``/``high`` is a Box."""

    if space is None:
        return None
    for cls in type(space).__mro__:
        kind = _space_kind_by_name(cls.__name__, space)
        if kind is not None:
            return kind
    # duck typing: never let a bounded space through without its bounds
    if hasattr(space, "low") and hasattr(space, "high"):
        return "box"
    if hasattr(space, "nvec"):
        return "multidiscrete"
    return None


def _flat(values: Any) -> list[float]:
    raw = values.tolist() if hasattr(values, "tolist") else values
    out: list[float] = []

    def walk(item: Any) -> None:
        if isinstance(item, (list, tuple)):
            for element in item:
                walk(element)
        else:
            out.append(float(item))

    walk(raw)
    return out


def _shape(space: Any) -> tuple[int, ...]:
    shape = getattr(space, "shape", None)
    return tuple(int(item) for item in shape) if shape is not None else ()


def _finite_bound(value: float, default: float) -> float:
    return value if math.isfinite(value) else default


def _box_bounds(space: Any) -> tuple[list[float], list[float]]:
    lows = [_finite_bound(value, -_FLOAT_MAX) for value in _flat(space.low)]
    highs = [_finite_bound(value, _FLOAT_MAX) for value in _flat(space.high)]
    return lows, highs


def _discrete_range(space: Any) -> tuple[int, int]:
    start = int(getattr(space, "start", 0) or 0)
    return start, start + int(space.n) - 1


def _multidiscrete_range(space: Any) -> tuple[list[int], list[int]]:
    """Per-element ``(lows, highs)`` of a ``MultiDiscrete`` (``start`` .. ``start + nvec - 1``)."""

    sizes = [int(value) for value in _flat(space.nvec)]
    start = getattr(space, "start", None)
    starts = [int(value) for value in _flat(start)] if start is not None else [0] * len(sizes)
    if len(starts) != len(sizes):
        starts = [0] * len(sizes)
    return starts, [low + size - 1 for low, size in zip(starts, sizes)]


def _box_count(space: Any) -> int:
    shape = _shape(space)
    if shape:
        count = 1
        for item in shape:
            count *= item
        return count
    return len(_flat(space.low))


def _owns_native(method):
    """Retain the environment across a complete synchronous native entry point."""
    @wraps(method)
    def owned(self, *args, **kwargs):
        with self._native_admission():
            return method(self, *args, **kwargs)
    return owned


class GymnasiumBridge(Bridge):
    """Bridge a Gymnasium environment onto the ``cap.world.*`` classes."""

    bridge_kind = "gymnasium"
    bridge_id = "mhs.bridge.gymnasium"

    def __init__(
        self,
        *,
        env: Any = None,
        env_id: str | None = None,
        env_spec: Mapping[str, Any] | None = None,
        seed: int | None = None,
        render_mode: str | None = None,
        device_id: str | None = None,
        max_steps: int = 1_000_000,
        modules: Mapping[str, Any] | None = None,
        autoreset: bool = False,
        max_ticks: int = 10_000,
        env_origin: str | None = None,
        action_space_ref: str | None = None,
        timing: Mapping[str, Any] | None = None,
        checkpoint: Mapping[str, Any] | None = None,
        asynchronous: Mapping[str, Any] | None = None,
        dm_env: Mapping[str, Any] | None = None,
        process: Mapping[str, Any] | None = None,
        host: Any = None,
    ):
        super().__init__(device_id=device_id)
        self._lifecycle = threading.Lock()
        #: The e-stop epoch at which the running call() was admitted (per serving thread).
        self._admitted = threading.local()
        self._native_owners = 0
        self._cleanup_started = False
        self._cleanup_done = threading.Event()
        self.bridge_id = f"mhs.bridge.gymnasium:{env_id or (env_spec or {}).get('module', '?')}"
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", "seed must be a non-negative integer",
                                 {"retryable": False})
        if action_space_ref is not None and (not isinstance(action_space_ref, str) or not action_space_ref.strip()
                                             or len(action_space_ref) > 500):
            raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                 "action_space_ref must be a reference such as path/in/clone.py:88",
                                 {"retryable": False})
        self._env = env
        # a pre-built env is not known to be upstream code: env_origin says what it is
        self._prebuilt = env is not None
        self._env_origin = env_origin
        self._action_space_ref = action_space_ref
        self._env_id = env_id
        self._env_spec = dict(env_spec or {})
        self._configured_seed = seed
        self._seed: int | None = seed
        self._pending_seed: int | None = None
        self._render_mode = render_mode
        self._max_steps = int(max_steps)
        self._max_ticks = int(max_ticks)
        self.autoreset = bool(autoreset)
        self._tick = 0
        self._episode = 0
        self._total_steps = 0
        self._terminated = False
        self._truncated = False
        self._last_reward: float | None = None
        self._last_observation: Any = None
        self._restored_observation: dict[str, Any] | None = None
        self._checkpoint = None
        self._checkpoint_fault: str | None = None
        self._restore_admission_epoch: int | None = None
        self._restore_stop_check = None
        #: The reviewed reason of an explicit per-backend checkpoint opt-out ({"profile": "none"}).
        self._checkpoint_opt_out: str | None = None
        if checkpoint is not None:
            from .gym_checkpoint import JsonCheckpoint, checkpoint_opt_out
            try:
                if isinstance(checkpoint, Mapping) and checkpoint.get("profile") == "none":
                    self._checkpoint_opt_out = checkpoint_opt_out(checkpoint)
                else:
                    self._checkpoint = JsonCheckpoint.resolve(checkpoint)
            except ValueError as exc:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", str(exc), {"retryable": False}) from exc
        self._last_info: dict[str, Any] = {}
        self._modules = modules
        #: Native reset keywords: None keeps the legacy Gymnasium/gym behaviour (seed, options and the
        #: legacy ``env.seed()`` fallback); a tuple is an explicit, reviewed signature with no fallback.
        self._reset_kwargs: tuple[str, ...] | None = None
        self._async = None
        self._owned_loop = None
        self._async_fault: str | None = None
        self._stop_unconfirmed: str | None = None
        #: Monotonic id of the latest stop attempt (e-stop or close). A commit
        #: whose id is older does not clear or replace ``_stop_unconfirmed``.
        self._stop_generation = 0
        self._stop_state = threading.Lock()
        #: Bridge-level e-stop latch. Independent of the endpoint's cancel event
        #: and of ``safety_status`` (a confirmed stop still reports no unconfirmed
        #: failure; effectful calls stay refused until safety reset).
        self._estop_latched = False
        #: E-stop calls that have set the latch and have not returned. Reset
        #: refuses while this is non-zero. The count moves only under
        #: ``_stop_state`` and is never held across native I/O.
        self._stop_paths_pending = 0
        self._close_outcome: str | None = None
        self._dm_env = None
        #: An isolated simulator host (isolated_process_v1): the profile, and the host itself (never recorded by the
        #: gate: ``env`` is the host as the gate sees it; this reference is only read for state and the safety path).
        self._process = None
        self._host = None
        self._host_fault: str | None = None
        if process is not None:
            from .sim_host import ProcessHost, ProcessProfile, ProcessProfileError
            if (timing is not None or self._checkpoint is not None or asynchronous is not None
                    or dm_env is not None):
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "isolated_process_v1 does not combine with physics timing, JSON checkpoints, "
                                     "the asynchronous profile or the dm_env profile", {"retryable": False})
            if not isinstance(host, ProcessHost) or env is None:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "isolated_process_v1 needs its ProcessHost (a GymnasiumDriver process backend)",
                                     {"retryable": False})
            try:
                self._process = ProcessProfile.resolve(process)
            except ProcessProfileError as exc:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", f"invalid isolated-process profile: {exc}",
                                     {"retryable": False}) from exc
            if self._process != host.profile:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "the host was built from another isolated-process profile", {"retryable": False})
            self._host = host
            self._reset_kwargs = self._process.reset_kwargs
        if asynchronous is not None:
            from .gym_async import AsyncProfile, AsyncProfileError, OwnedLoop
            if timing is not None or self._checkpoint is not None or dm_env is not None:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "asyncio_owned_loop_v1 does not combine with physics timing, JSON "
                                     "checkpoints or the dm_env profile", {"retryable": False})
            try:
                self._async = AsyncProfile.resolve(asynchronous)
            except AsyncProfileError as exc:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", f"invalid asynchronous profile: {exc}",
                                     {"retryable": False}) from exc
            self._reset_kwargs = self._async.reset_kwargs
            self._owned_loop = OwnedLoop(name=f"mhs-gym-owned-{(device_id or 'env').rsplit('/', 1)[-1]}"[:60])
            self._owned_loop.add_listener(self._on_owned_settled)
        if dm_env is not None:
            from .dm_env_adapter import DmEnvAdapter, DmEnvError, DmEnvProfile
            if timing is not None or self._checkpoint is not None:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "dm_env_v1 does not combine with physics timing or JSON checkpoints",
                                     {"retryable": False})
            if env is None:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "dm_env_v1 needs a pre-built dm_env environment (a backend factory)",
                                     {"retryable": False})
            try:
                self._dm_env = DmEnvProfile.resolve(dm_env)
                self._env = DmEnvAdapter(env, self._dm_env)
            except DmEnvError as exc:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", f"invalid dm_env environment: {exc}",
                                     {"retryable": False}) from exc
            self._reset_kwargs = ()
        self._gym: Any = None
        self._step_limits: _limits.EffectiveLimits | None = None
        self._physics_timing = None
        self._timing_fault: str | None = None
        self._timing_last_clock: float | None = None
        if timing is not None:
            from .simulation_timing import PhysicsTiming
            try:
                self._physics_timing = PhysicsTiming.resolve(timing, self._env_attr)
                self._timing_last_clock = self._physics_timing.sample(self._env_attr)
                if min(self._max_ticks, 10000) < self._physics_timing.decimation:
                    raise ValueError("max_ticks is smaller than one control period")
            except Exception as exc:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", f"invalid physics timing: {exc}",
                                     {"retryable": False}) from exc

        if self._checkpoint is not None:
            self._checkpoint_access()  # callable paths are required; no native getter is invoked here

    @contextmanager
    def _native_admission(self):
        # This short lifecycle lock never covers native code or the mutation
        # lock. Closing fences new admissions immediately, including callers
        # waiting for another owned native call to finish.
        with self._lifecycle:
            self.ensure_open()
            self._native_owners += 1
        try:
            yield
        finally:
            with self._lifecycle:
                self._native_owners -= 1
                cleanup = self._claim_cleanup()
            if cleanup:
                threading.Thread(target=self._cleanup_native, name="mhs-gym-close", daemon=True).start()

    def _claim_cleanup(self) -> bool:
        # Called only with _lifecycle held. An unsupported completion object
        # may still own hidden work after its synchronous call returns. This
        # profile cannot establish its termination, so cannot close its env.
        if (not self._closed or self._native_owners or self._checkpoint_fault
                or self._cleanup_started):
            return False
        if self._owned_loop is not None and self._owned_loop.owns_any():
            # Owned remote work has not settled: closing the environment now could
            # race it. Cleanup is retried when it settles (_on_owned_settled).
            self._close_outcome = "deferred: native work still owned"
            return False
        self._cleanup_started = True
        return True

    def _on_owned_settled(self) -> None:
        # Runs on the owned loop thread: never block it. A deferred close resumes elsewhere.
        if self._closed and not self._cleanup_started:
            threading.Thread(target=self._retry_cleanup, name="mhs-gym-close-retry", daemon=True).start()

    def _retry_cleanup(self) -> None:
        with self._lifecycle:
            cleanup = self._claim_cleanup()
        if cleanup:
            self._cleanup_native()

    def _cleanup_native(self) -> None:
        if self._owned_loop is not None:
            self._cleanup_owned()
            return
        if self._host is not None:
            # Bounded and exactly once: stop, a world call in flight, env.close in the host, the host's exit.
            # The generation keeps an in-flight e-stop from clearing a failure this close records.
            generation = self._open_stop_attempt()
            try:
                self._close_outcome = self._host.close()
            except Exception as exc:  # noqa: BLE001 - close never claims native success
                self._close_outcome = f"unsettled: the host close raised {type(exc).__name__}"
            finally:
                if self._close_outcome != "settled":
                    self._commit_stop_attempt(generation, (self._close_outcome or "host close unsettled")[:300])
                self._env = None
                super().close()
                self._cleanup_done.set()
            return
        try:
            env = self._env
            if env is not None:
                close = getattr(env, "close", None)
                if callable(close):
                    close()
        except Exception:  # noqa: BLE001 - close never claims native success
            pass
        finally:
            self._env = None
            super().close()
            self._cleanup_done.set()

    # -- asynchronous environments (asyncio_owned_loop_v1) ----------------------
    def _cleanup_owned(self) -> None:
        """Exactly-once settled close on the owned loop; deferred while native work is owned."""
        while True:
            outcome = self._close_owned(self._env)
            if not outcome.startswith("deferred"):
                break
            with self._lifecycle:
                # Retried by _on_owned_settled; re-check here in case it settled in between.
                self._cleanup_started = False
                self._close_outcome = outcome
                retry = self._claim_cleanup()
            if not retry:
                return
        self._close_outcome = outcome
        if outcome == "settled":
            self._env = None
            Bridge.close(self)
            self._cleanup_done.set()
        # Otherwise the owned loop still holds native close/stop work: cleanup is not claimed complete.

    def _close_owned(self, env: Any) -> str:
        """Remote stop (when declared), then env.close(), then loop shutdown -- all bounded; never raises."""
        from .gym_async import OwnedBusy, OwnedTimeout, resolve_path
        loop, profile = self._owned_loop, self._async
        # Supersede any in-flight e-stop: its confirmation must not clear a failure this close records.
        generation = self._open_stop_attempt()
        notes: list[str] = []
        if env is not None:
            if profile.remote_stop is not None:
                try:
                    stop = resolve_path(env, profile.remote_stop)
                    loop.run("remote_stop", stop, expect="any", timeout_s=profile.stop_timeout_s, stop=True)
                except (OwnedTimeout, OwnedBusy):
                    self._commit_stop_attempt(generation, "the remote stop before close is still owned")
                    return "deferred: the remote stop before close is still owned"
                except Exception as exc:  # noqa: BLE001 - recorded; the environment is closed anyway
                    self._commit_stop_attempt(
                        generation, f"remote stop before close raised {type(exc).__name__}")
                    notes.append(f"remote stop before close raised {type(exc).__name__}")
            close = getattr(env, "close", None)
            if callable(close):
                try:
                    loop.run("close", close, expect="any", timeout_s=profile.close_timeout_s)
                except OwnedBusy:
                    return "deferred: native work is still owned"
                except OwnedTimeout:
                    return (f"unsettled: env.close did not return within {profile.close_timeout_s:g} s; "
                            "the owned loop keeps running it")
                except Exception as exc:  # noqa: BLE001 - close never claims native success
                    notes.append(f"env.close raised {type(exc).__name__}")
        state = loop.shutdown(profile.close_timeout_s)
        if state == "owned":
            return "deferred: native work is still owned"
        if state == "timed_out":
            notes.append(f"the owned loop did not stop within {profile.close_timeout_s:g} s")
        return "settled" if not notes else "unsettled: " + "; ".join(notes)

    def _effects_latched(self) -> bool:
        with self._stop_state:
            return self._estop_latched

    def _stop_path_is_pending(self) -> bool:
        with self._stop_state:
            return self._stop_paths_pending > 0

    def _refuse_pending_stop(self) -> None:
        """Refuse a safety reset while an e-stop that latched the bridge has not answered.

        The mark is set in the same ``_stop_state`` section as the latch, before any native
        stop, and cleared only after that ``estop`` call returns. Reset must not unfence a
        host or clear the latch in that gap: the attempt can still fail, or confirm, after
        a direct caller has resumed the world.
        """
        if not self._stop_path_is_pending():
            return
        raise make_mhs_error(
            "MHS.SAFETY.RESET_REFUSED",
            "the stop path of the last e-stop is still running (the native e-stop "
            "has not answered); wait for it to answer before reset",
            {"retryable": False, "details": {"reason": "stop_path_pending", "latched": True}},
        )

    def _open_stop_attempt(self) -> int:
        """Take the next stop-attempt id. An older attempt can no longer publish."""
        with self._stop_state:
            self._stop_generation += 1
            return self._stop_generation

    def _commit_stop_attempt(self, generation: int, unconfirmed: str | None) -> bool:
        """Publish this attempt's stop outcome only while it is still the latest.

        ``unconfirmed`` None clears the failure flag (this attempt confirmed).
        A slower attempt must not clear, or replace, a newer attempt's record.
        Returns False when a newer attempt has already started.
        """
        with self._stop_state:
            if generation != self._stop_generation:
                return False
            self._stop_unconfirmed = unconfirmed
            return True

    def _world_fence_exception(self, message: str) -> BaseException | None:
        """An exception when this admission must not dispatch a world call, else None.

        The endpoint's cancel event, and an e-stop that landed after admission,
        both raise :class:`signals.Cancelled` (the owned-loop guard's contract).
        A call admitted while the bridge latch is already engaged raises
        ``MHS.SAFETY.ESTOP_ENGAGED``. Neither path dispatches native work.
        """
        context = getattr(self._admitted, "context", None)
        epoch = getattr(self._admitted, "epoch", None)
        if (context is not None and context.cancelled()) or (epoch is not None and self.estop_epoch != epoch):
            return signals.Cancelled(message)
        if self._effects_latched():
            return make_mhs_error(
                "MHS.SAFETY.ESTOP_ENGAGED",
                "the call was not executed: the e-stop latch is engaged",
                {"retryable": False, "details": {"preempted_by_estop": True}},
            )
        return None

    def _raise_world_fence(self, message: str) -> None:
        fence = self._world_fence_exception(message)
        if fence is not None:
            raise fence

    def _native_invoke(self, kind: str, fn: Any) -> Any:
        """Call one native entry point: directly, or on the owned loop within its declared bound.

        Owned-loop outcomes become bridge errors marked ``mhs_bridge_outcome`` so
        callers never re-label them as native failures.
        """
        if self._host is not None:
            return self._host_invoke(kind, fn)
        loop = self._owned_loop
        if loop is None:
            return fn()
        from .gym_async import OwnedBusy, OwnedTimeout, ProfileViolation
        profile = self._async
        expect = profile.step if kind == "step" else profile.reset if kind == "reset" else "any"
        timeout = (profile.step_timeout_s if kind == "step" else profile.reset_timeout_s if kind == "reset"
                   else profile.close_timeout_s)
        epoch = getattr(self._admitted, "epoch", None)
        context = getattr(self._admitted, "context", None)

        def guard() -> None:
            # Under the owned loop's lock: no world call is dispatched after an e-stop engaged or after the
            # operation was cancelled. The epoch covers a direct caller with no cancel event; the latch
            # covers a call that itself started after the e-stop.
            if (epoch is not None and self.estop_epoch != epoch) or (context is not None and context.cancelled()):
                refused = signals.Cancelled(f"an e-stop or cancellation preceded dispatch of the native {kind}")
                refused.mhs_bridge_outcome = True
                raise refused
            if self._effects_latched():
                refused = make_mhs_error(
                    "MHS.SAFETY.ESTOP_ENGAGED",
                    f"the native {kind} was not executed: the e-stop latch is engaged",
                    {"retryable": False, "details": {"preempted_by_estop": True}},
                )
                refused.mhs_bridge_outcome = True
                raise refused

        try:
            return loop.run(kind, fn, expect=expect, timeout_s=timeout,
                            guard=guard if kind in ("step", "reset") else None)
        except OwnedBusy as exc:
            error = BridgeBusy(f"earlier native {exc.owned.get('kind')} is still owned; nothing was dispatched",
                               {"details": {"owned": exc.owned}})
        except OwnedTimeout as exc:
            self._async_fault = (f"native {kind} outcome unknown: it did not settle within {timeout:g} s and "
                                 "stays owned until it settles; an explicit world reset is then required")
            error = make_mhs_error("MHS.OUTCOME.UNKNOWN", f"{exc}; it was not cancelled locally",
                                   {"retryable": False, "details": {"may_have_effect": True, "owned": True}})
        except ProfileViolation as exc:
            self._async_fault = f"asynchronous profile violated: {exc}"
            error = make_mhs_error("MHS.DEVICE.FAULTED", str(exc), {"retryable": False})
        error.mhs_bridge_outcome = True
        raise error

    def _estop_owned(self) -> dict[str, Any]:
        """E-stop of an asynchronous environment: declared remote stop, probe, settlement -- or an honest outcome."""
        from .gym_async import OwnedBusy, OwnedTimeout, resolve_path
        loop, profile = self._owned_loop, self._async
        generation = self._open_stop_attempt()

        def unknown(reason: str, details: Mapping[str, Any] | None = None) -> Exception:
            return make_mhs_error("MHS.OUTCOME.UNKNOWN", "safe state is unverified: " + reason,
                                  {"retryable": False, "details": {"safe_state_achieved": False, **dict(details or {})}})

        def fail(reason: str, details: Mapping[str, Any] | None = None, exc: BaseException | None = None) -> None:
            # A newer attempt owns the flag: keep its record and still fail this one.
            self._commit_stop_attempt(generation, reason)
            error = unknown(reason, details)
            if exc is None:
                raise error
            raise error from exc

        if profile.remote_stop is None:
            owned = loop.owned() or loop.owned_stop()
            if owned is not None:
                raise unknown(f"no remote stop is declared and native {owned['kind']} is still owned", {"owned": owned})
            return {}
        if self._closed and self._cleanup_started:
            if self._close_outcome == "settled":
                return {}
            raise unknown(f"the environment is closing ({self._close_outcome or 'cleanup running'})")
        env = self._env
        if env is None:
            return {}   # never constructed: no native work ever ran
        try:
            stop = resolve_path(env, profile.remote_stop)
            probe = resolve_path(env, profile.stop_probe) if profile.stop_probe else None
        except Exception as exc:  # noqa: BLE001 - an unresolved stop is no stop
            fail(f"declared remote stop unavailable ({type(exc).__name__})", exc=exc)
        earlier = loop.current_stop()
        if earlier is not None:
            # One stop at a time: wait (bounded) for an earlier stop or probe, then stop afresh.
            try:
                loop.wait(earlier, profile.stop_timeout_s)
            except OwnedTimeout:
                fail("an earlier remote stop or probe is still owned", {"owned_stop": loop.owned_stop()})
            except Exception:  # noqa: BLE001 - it settled; a fresh stop follows
                pass
        try:
            loop.run("remote_stop", stop, expect="any", timeout_s=profile.stop_timeout_s, stop=True)
        except (OwnedTimeout, OwnedBusy) as exc:
            fail(f"the remote stop did not run within {profile.stop_timeout_s:g} s "
                 "(it stays queued on the owned loop)", {"owned": loop.owned()}, exc)
        except Exception as exc:  # noqa: BLE001
            fail(f"the remote stop raised {type(exc).__name__}", exc=exc)
        if probe is not None:
            try:
                confirmed = loop.run("stop_probe", probe, expect="any", timeout_s=profile.stop_timeout_s, stop=True)
            except Exception as exc:  # noqa: BLE001
                fail(f"the stop probe did not answer ({type(exc).__name__})", exc=exc)
            if confirmed is not True:
                fail(f"the stop probe returned {type(confirmed).__name__} {confirmed!r}"[:200])
        if not loop.wait_idle(profile.settle_timeout_s):
            owned = loop.owned()
            fail(f"owned native {owned['kind'] if owned else 'work'} did not settle within "
                 f"{profile.settle_timeout_s:g} s after the remote stop", {"owned": owned})
        if not self._commit_stop_attempt(generation, None):
            # A newer e-stop or close already recorded its own outcome. Do not claim this one confirmed.
            raise unknown("a newer stop attempt superseded this confirmation")
        return {"remote_stop": profile.remote_stop, "stop_probe": profile.stop_probe,
                "confirmed": probe is not None}

    def async_status(self) -> dict[str, Any] | None:
        """Diagnostics of the owned loop; readable after close (no native admission)."""
        if self._async is None:
            return None
        return {**self._async.descriptor(), **self._owned_loop.describe(), "fault": self._async_fault,
                "stop_unconfirmed": self._stop_unconfirmed, "close": self._close_outcome}

    # -- isolated simulator host (isolated_process_v1) --------------------------------------------------------------
    def _host_invoke(self, kind: str, fn: Any) -> Any:
        """One world call in the simulator host, within its bound; host outcomes become bridge errors.

        ``fn`` is ``env.step``/``env.reset`` of the host (as the gate records it) with its arguments; it receives
        the dispatch guard, which the host runs under its send lock immediately before the request is written.
        """
        from .sim_host import ChildCallError, HostAfterEffect, HostBusy, HostFenced, HostTimeout, HostUnavailable
        epoch = getattr(self._admitted, "epoch", None)
        context = getattr(self._admitted, "context", None)

        def guard() -> None:
            # No world call is sent after an e-stop engaged or after the operation was cancelled.
            # The epoch covers a direct caller with no cancel event; the latch covers a call that
            # itself started after the e-stop.
            if (epoch is not None and self.estop_epoch != epoch) or (context is not None and context.cancelled()):
                refused = signals.Cancelled(f"an e-stop or cancellation preceded dispatch of the native {kind}")
                refused.mhs_bridge_outcome = True
                raise refused
            if self._effects_latched():
                refused = make_mhs_error(
                    "MHS.SAFETY.ESTOP_ENGAGED",
                    f"the native {kind} was not executed: the e-stop latch is engaged",
                    {"retryable": False, "details": {"preempted_by_estop": True}},
                )
                refused.mhs_bridge_outcome = True
                raise refused

        try:
            return fn(guard=guard)
        except HostFenced as exc:
            error = signals.Cancelled(f"{exc}; nothing reached the environment")
        except HostBusy as exc:
            error = BridgeBusy(f"earlier simulator host {exc.owned.get('op')} is still owned; nothing was sent",
                               {"details": {"owned": exc.owned}})
        except HostTimeout as exc:
            if not exc.sent:
                error = BridgeBusy(f"{exc}; nothing was sent", {"details": {"owned": self._host.world_owned()}})
            else:
                self._host_fault = (f"native {kind} outcome unknown: the simulator host did not answer within its "
                                    "bound and it stays owned until it answers; an explicit world reset is then "
                                    "required")
                error = make_mhs_error("MHS.OUTCOME.UNKNOWN", f"{exc}; it was not cancelled",
                                       {"retryable": False, "details": {"may_have_effect": True, "owned": True}})
        except HostAfterEffect as exc:
            self._host_fault = (f"native {kind} ran in the simulator host but its result was lost; an explicit "
                                "world reset is required")
            error = make_mhs_error("MHS.OUTCOME.UNKNOWN", f"{exc}"[:300],
                                   {"retryable": False, "details": {"may_have_effect": True}})
        except HostUnavailable as exc:
            if exc.sent:
                self._host_fault = f"the simulator host ended during native {kind}; its outcome is unknown"
                error = make_mhs_error("MHS.OUTCOME.UNKNOWN", f"{exc}; the {kind} may have taken effect"[:300],
                                       {"retryable": False, "details": {"may_have_effect": True}})
            else:
                error = make_mhs_error("MHS.DEVICE.NOT_READY", f"{exc}"[:300], {"retryable": False})
        except ChildCallError as exc:
            if not exc.exit_requested:
                raise   # the environment raised: the caller reports env.<kind> failed (MHS.DEVICE.FAULTED)
            error = make_mhs_error("MHS.DEVICE.FAULTED",
                                   f"the environment requested interpreter exit during {kind} ({exc}); the simulator "
                                   "host contained it and now accepts only close"[:300], {"retryable": False})
        error.mhs_bridge_outcome = True
        raise error

    def _estop_hosted(self) -> dict[str, Any]:
        """E-stop of a simulator host: fence and stop, settle, stop again, read back -- or an unreached safe state."""
        host, profile, env = self._host, self._process, self._env
        generation = self._open_stop_attempt()

        def unknown(reason: str, details: Mapping[str, Any] | None = None) -> Exception:
            # A newer attempt owns the flag: keep its record and still fail this one.
            self._commit_stop_attempt(generation, reason[:300])
            return make_mhs_error("MHS.OUTCOME.UNKNOWN", "safe state is unverified: " + reason[:300],
                                  {"retryable": False,
                                   "details": {"safe_state_achieved": False, **dict(details or {})}})

        if not host.started:
            return {}   # never started: no environment and no simulator of this host exist
        if (self._closed and self._cleanup_started) or env is None:
            if self._close_outcome == "settled":
                return {}
            raise unknown(f"the simulator host is closing or closed ({self._close_outcome or 'close running'})")
        try:
            first = env.stop()   # fences the host first: no world call is sent from here on
        except Exception as exc:  # noqa: BLE001 - a stop that did not complete is no stop
            raise unknown(f"the simulator stop {profile.stop} did not complete ({type(exc).__name__}: {exc})") from exc
        active = first.get("world_active") if isinstance(first, Mapping) else None
        if active is not False or host.world_owned() is not None:
            # A world call was running when the fence was set: it may undo the stop (a step that unpauses first).
            if not host.wait_world_idle(profile.settle_timeout_s):
                raise unknown(f"a world call running at the stop did not end within {profile.settle_timeout_s:g} s",
                              {"owned": host.world_owned()})
            try:
                env.stop()
            except Exception as exc:  # noqa: BLE001
                raise unknown(f"the repeated simulator stop {profile.stop} did not complete "
                              f"({type(exc).__name__}: {exc})") from exc
        try:
            value = env.readback()
        except Exception as exc:  # noqa: BLE001
            raise unknown(f"the read-back {profile.readback_label} did not answer "
                          f"({type(exc).__name__}: {exc})") from exc
        if not profile.confirms(value):
            raise unknown(f"the read-back {profile.readback_label} returned {value!r}, not "
                          f"{profile.readback_equals!r}")
        if host.world_owned() is not None or not host.alive():
            raise unknown("the simulator host changed state during the stop")
        if not self._commit_stop_attempt(generation, None):
            raise unknown("a newer stop attempt superseded this confirmation")
        return {"stop": profile.stop, "readback": profile.readback_label, "confirmed": True}

    def host_status(self) -> dict[str, Any] | None:
        """Diagnostics of the simulator host; readable after close (no native admission)."""
        if self._host is None:
            return None
        return {**self._host.describe(), "fault": self._host_fault, "stop_unconfirmed": self._stop_unconfirmed,
                "close": self._close_outcome or self._host.close_outcome}

    def _seedable(self) -> bool:
        return self._reset_kwargs is None or "seed" in self._reset_kwargs

    def reset_inputs(self) -> tuple[str, ...]:
        """Reset inputs this environment honours (the legacy default is seed and options)."""
        return ("seed", "options") if self._reset_kwargs is None else tuple(self._reset_kwargs)

    def operating_notes(self) -> list[str]:
        if self._process is not None:
            return self._process.notes()
        if self._async is not None:
            return self._async.notes()
        if self._dm_env is not None:
            return self._dm_env.notes()
        return []

    def checkpoint_opt_out_reason(self) -> str | None:
        return self._checkpoint_opt_out

    def timing_descriptor(self) -> dict[str, Any] | None:
        return self._physics_timing.descriptor() if self._physics_timing is not None else None

    # -- availability ------------------------------------------------------
    @staticmethod
    def available() -> bool:
        for name in ("gymnasium", "gym"):
            try:
                importlib.import_module(name)
                return True
            except ImportError:
                continue
        return False

    def _import_gym(self) -> Any:
        if self._gym is not None:
            return self._gym
        for name in ("gymnasium", "gym"):
            try:
                self._gym = importlib.import_module(name)
                return self._gym
            except ImportError:
                continue
        raise make_mhs_error(
            "MHS.DEVICE.NOT_READY",
            "gymnasium/gym is not installed; the gymnasium bridge cannot open an environment",
            {
                "retryable": False,
                "remediation": "Install gymnasium to use this bridge, or pass a pre-built env object.",
            },
        )

    @_owns_native
    def _ensure_env(self) -> Any:
        self.ensure_open()
        if self._host is not None:
            from .sim_host import HostError
            try:
                self._host.start()   # idempotent; bounded by the profile's start_timeout_s
            except HostError as exc:
                raise make_mhs_error("MHS.DEVICE.NOT_READY", f"{exc}"[:300], {"retryable": False}) from exc
        if self._env is not None:
            return self._env
        if self._modules is not None:  # test injection
            self._env = self._build_env_from_module(self._modules)
            return self._env
        module = self._env_spec.get("module")
        if module:
            self._env = self._build_env_from_module(
                importlib.import_module(str(module)), attr=str(self._env_spec.get("attr", "make")),
                kwargs=self._env_spec.get("kwargs") or {},
            )
            return self._env
        gym = self._import_gym()
        if not self._env_id:
            raise make_mhs_error(
                "MHS.DEVICE.NOT_READY", "gymnasium bridge needs env_id, env_spec or a pre-built env",
                {"retryable": False},
            )
        kwargs = dict(self._env_spec.get("kwargs") or {})
        if self._render_mode is not None:
            kwargs.setdefault("render_mode", self._render_mode)
        try:
            self._env = gym.make(self._env_id, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise make_mhs_error(
                "MHS.DEVICE.NOT_READY", f"gym.make({self._env_id!r}) failed ({type(exc).__name__})",
                {"retryable": False},
            ) from exc
        return self._env

    def _build_env_from_module(self, module: Any, *, attr: str = "make", kwargs: Mapping[str, Any] | None = None) -> Any:
        factory = getattr(module, attr, None)
        if callable(factory):
            return factory(**dict(kwargs or {}))
        raise make_mhs_error(
            "MHS.DEVICE.NOT_READY", f"env factory {attr!r} is absent from the injected module", {"retryable": False}
        )

    @_owns_native
    def _env_attr(self, name: str) -> Any:
        """``name`` through ``get_wrapper_attr``, then ``unwrapped``, then the env itself."""

        env = self._ensure_env()
        getter = getattr(env, "get_wrapper_attr", None)
        if callable(getter):
            try:
                return getter(name)
            except AttributeError:
                pass
        unwrapped = getattr(env, "unwrapped", None)
        if unwrapped is not None and hasattr(unwrapped, name):
            return getattr(unwrapped, name)
        return getattr(env, name, None)

    @_owns_native
    def _checkpoint_access(self) -> tuple[Any, Any]:
        if self._checkpoint is None:
            raise make_mhs_error(
                "MHS.CAPABILITY.NOT_BOUND",
                "protocol snapshots require an explicit json_state_v1 checkpoint profile; "
                "declare snapshot_restore=false or configure a source-backed JSON getter/setter",
                {"retryable": False})
        try:
            return self._checkpoint.access(self._ensure_env())
        except Exception as exc:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"checkpoint methods unavailable: {exc}",
                                 {"retryable": False}) from exc

    @property
    def estop_native(self) -> str | None:
        """The declared stop of a simulator host or an asynchronous environment (``None``: software latch only)."""
        if self._process is not None:
            return self._process.stop
        return self._async.remote_stop if self._async is not None else None

    @property
    def snapshot_supported(self) -> bool:
        """Configured protocol support, not a claim about hidden native state/RNG."""
        return self._checkpoint is not None

    # -- spaces ------------------------------------------------------------
    @property
    @_owns_native
    def action_space(self) -> Any:
        return getattr(self._ensure_env(), "action_space", None)

    @property
    @_owns_native
    def observation_space(self) -> Any:
        return getattr(self._ensure_env(), "observation_space", None)

    def _field_schema(self, space: Any, depth: int = 0) -> dict[str, Any]:
        kind = _space_kind(space)
        if kind == "dict":
            if depth >= _MAX_SPACE_DEPTH:
                return {"not": {}}   # too deep to bound member by member: refuse, never pass unbounded
            properties = self._dict_properties(space, depth + 1)
            return {"type": "object", "properties": properties, "required": sorted(properties),
                    "additionalProperties": False}
        if kind == "tuple":
            count = len(space.spaces)
            return {"type": "array", "minItems": count, "maxItems": count}
        if kind == "discrete":
            low, high = _discrete_range(space)
            return {"type": "integer", "minimum": low, "maximum": high}
        if kind == "box":
            count = _box_count(space)
            # Only a space that says so (the dm_env adapter's integer-dtype specs) publishes integer items.
            item_type = "integer" if getattr(space, "mhs_integer_values", False) is True else "number"
            return {"type": "array", "items": {"type": item_type}, "minItems": count, "maxItems": count}
        if kind == "multidiscrete":
            lows, _highs = _multidiscrete_range(space)
            items: dict[str, Any] = {"type": "integer"}
            if lows:
                items["minimum"] = min(lows)
            return {"type": "array", "items": items, "minItems": len(lows), "maxItems": len(lows)}
        if kind == "multibinary":
            count = int(_box_count(space) or space.n)
            return {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 1},
                    "minItems": count, "maxItems": count}
        return {}

    def _dict_properties(self, space: Any, depth: int = 0) -> dict[str, Any]:
        properties = {}
        for alias, native_key, sub in _dict_items(space):
            field = self._field_schema(sub, depth)
            if alias != native_key:
                field = dict(field)
                field["description"] = "Native action key: " + json.dumps(native_key, ensure_ascii=True) + "."
            properties[alias] = field
        return properties

    @_owns_native
    def action_schema(self) -> dict[str, Any]:
        """The JSON schema of the ``action`` object derived from the action space."""

        space = self.action_space
        kind = _space_kind(space)
        if kind == "discrete":
            low, high = _discrete_range(space)
            properties = {"index": {"type": "integer", "minimum": low, "maximum": high}}
            return {"type": "object", "properties": properties, "required": ["index"], "additionalProperties": False}
        if kind in ("box", "multidiscrete", "multibinary"):
            return {"type": "object", "properties": {"values": self._field_schema(space)},
                    "required": ["values"], "additionalProperties": False}
        if kind == "dict":
            properties = self._dict_properties(space)
            return {"type": "object", "properties": properties, "required": sorted(properties),
                    "additionalProperties": False}
        if kind == "tuple":
            return {"type": "object", "properties": {"items": {"type": "array", "minItems": len(space.spaces),
                                                               "maxItems": len(space.spaces)}},
                    "required": ["items"], "additionalProperties": False}
        return {"type": "object", "properties": {}, "additionalProperties": True}

    def _space_provenance(self) -> dict[str, str]:
        """The ``source`` and ``ref`` (only a ``ref`` for a pre-built env) of every limit derived from the space."""

        if self._action_space_ref:
            return {"source": "upstream_code", "ref": self._action_space_ref}
        env = self._env
        name = type(getattr(env, "unwrapped", env)).__name__
        if not self._prebuilt:   # gym.make(env_id) or the env_spec factory built it
            return {"source": "upstream_code", "ref": f"{self._env_id or name}:action_space"}
        origin = self._env_origin or f"the {name} object passed to the bridge"
        return {"ref": f"action_space of {origin}"[:500]}

    @_owns_native
    def action_limits(self) -> dict[str, Any]:
        """Limits derived from the action space (``action.values`` per element, ``action.index``).

        ``values`` is the flattened action, so a ``Box`` of any shape gets its
        bounds per element (row-major, as ``low``/``high`` flatten);
        ``MultiDiscrete`` elements are bounded by ``start .. start + nvec - 1``
        and ``MultiBinary`` elements by ``0 .. 1``.  Every rule carries the
        provenance of the space (module docstring).
        """

        space = self.action_space
        kind = _space_kind(space)
        provenance = self._space_provenance()

        def rule_for(sub: Any) -> dict[str, Any] | None:
            sub_kind = _space_kind(sub)
            if sub_kind == "discrete":
                low, high = _discrete_range(sub)
                return {"min": low, "max": high, **provenance}
            if sub_kind == "box":
                lows, highs = _box_bounds(sub)
                if all(value == -_FLOAT_MAX for value in lows) and all(value == _FLOAT_MAX for value in highs):
                    return None
                if len(lows) != _box_count(sub) or len(highs) != len(lows):
                    # low/high do not flatten to one bound per element: bound every
                    # element by the tightest pair (never leave the action unbounded)
                    return {"min": max(lows), "max": min(highs), **provenance}
                return {"min": lows, "max": highs, **provenance}
            if sub_kind == "multidiscrete":
                lows, highs = _multidiscrete_range(sub)
                if not lows:
                    return None
                return {"min": lows, "max": highs, **provenance}
            if sub_kind == "multibinary":
                return {"min": 0, "max": 1, **provenance}
            return None

        out: dict[str, Any] = {}
        if kind == "discrete":
            rule = rule_for(space)
            if rule:
                out["action.index"] = rule
        elif kind in ("box", "multidiscrete", "multibinary"):
            rule = rule_for(space)
            if rule:
                out["action.values"] = rule
        elif kind == "dict":
            def members(prefix: str, dict_space: Any, depth: int) -> None:
                for alias, _native_key, sub in _dict_items(dict_space):
                    path = f"{prefix}.{alias}"
                    if _space_kind(sub) == "dict" and depth < _MAX_SPACE_DEPTH:
                        members(path, sub, depth + 1)   # a nested Dict: bound its members
                        continue
                    rule = rule_for(sub)
                    if rule:
                        out[path] = rule

            members("action", space, 0)
        return out

    @_owns_native
    def step_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "ticks": {"type": "integer", "minimum": 1, "maximum": self._max_ticks},
                "action": self.action_schema(),
            },
            "additionalProperties": False,
        }
        if self._physics_timing is not None:
            timing = self._physics_timing
            d = timing.decimation
            schema["properties"]["ticks"] = {
                "type": "integer", "minimum": d,
                "maximum": (min(self._max_ticks, 10000) // d) * d, "multipleOf": d,
                "description": (f"Physics ticks to advance, in whole multiples of {d}. Physics timestep "
                                f"{timing.timestep_ms:g} ms; control period {timing.timestep_ms*d:g} ms. "
                                "Receipt timing notes report actual completed ticks and duration."),
            }
            schema["properties"]["action"]["description"] = (
                f"Action held for each opaque control call of {d} physics ticks; repeated ticks/{d} times.")
            schema["required"] = ["ticks", "action"]
        return schema

    def _compiled_step_limits(self) -> _limits.EffectiveLimits:
        if self._step_limits is None:
            self._step_limits = _limits.compile_limits(
                self.step_input_schema(), [_limits.LimitSource("bridge.action_space", self.action_limits())]
            )
        return self._step_limits

    # -- JSON <-> native ---------------------------------------------------
    def _observation_json(self, value: Any, space: Any) -> Any:
        kind = _space_kind(space)
        if kind == "discrete":
            return {"index": int(_plain_scalar(value))}
        if kind in ("box", "multidiscrete", "multibinary"):
            return {"values": jsonable(value)}
        if kind == "dict" and isinstance(value, Mapping):
            return {str(key): self._observation_json(value[key], space.spaces.get(key)) for key in value}
        if kind == "tuple" and isinstance(value, (list, tuple)):
            return {"items": [self._observation_json(item, sub) for item, sub in zip(value, space.spaces)]}
        if space is not None and kind is None and isinstance(value, Mapping):
            return jsonable(dict(value))
        if isinstance(value, Mapping):
            return {str(key): self._observation_json(item, None) for key, item in value.items()}
        if isinstance(value, (list, tuple)) or hasattr(value, "tolist"):
            plain = jsonable(value)
            return {"values": plain} if isinstance(plain, list) else {"value": plain}
        return {"value": jsonable(value)}

    @_owns_native
    def observation_json(self) -> dict[str, Any]:
        if self._restored_observation is not None:
            return copy.deepcopy(self._restored_observation)
        if self._last_observation is None:
            return {}
        return self._observation_json(self._last_observation, self.observation_space)

    def _native_field(self, value: Any, space: Any) -> Any:
        kind = _space_kind(space)
        if kind == "discrete":
            return int(value)
        if kind in ("box", "multidiscrete", "multibinary"):
            return self._native_array(value, space)
        if kind == "dict" and isinstance(value, Mapping):
            return {key: self._native_field(value[alias], sub) for alias, key, sub in _dict_items(space)}
        if kind == "tuple" and isinstance(value, (list, tuple)):
            return tuple(self._native_field(item, sub) for item, sub in zip(value, space.spaces))
        return value

    @staticmethod
    def _native_array(values: Any, space: Any) -> Any:
        low = getattr(space, "low", None)
        if low is not None and type(low).__module__.startswith("numpy"):
            numpy = importlib.import_module("numpy")
            array = numpy.asarray(values, dtype=getattr(space, "dtype", None))
            shape = _shape(space)
            return array.reshape(shape) if shape else array
        return list(values)

    def _native_action(self, action: Any) -> Any:
        space = self.action_space
        kind = _space_kind(space)
        if kind == "discrete":
            return int(action["index"])
        if kind in ("box", "multidiscrete", "multibinary"):
            return self._native_array(action["values"], space)
        if kind == "dict":
            return {key: self._native_field(action[alias], sub) for alias, key, sub in _dict_items(space)}
        if kind == "tuple":
            return tuple(self._native_field(item, sub) for item, sub in zip(action["items"], space.spaces))
        if isinstance(action, Mapping) and len(action) == 1:
            # no recognised action space: unwrap the standard wrappers anyway
            if isinstance(action.get("index"), int) and not isinstance(action.get("index"), bool):
                return int(action["index"])
            if isinstance(action.get("values"), list):
                return list(action["values"])
        return action

    def _check_step_input(self, args: Mapping[str, Any]) -> None:
        from mhs.schema import validate  # local: the schema validator is only needed here

        effective = self._compiled_step_limits()
        structure = _limits.strip_bound_keywords(effective, self.step_input_schema())
        problems = validate(dict(args), structure)
        if problems:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "step input does not match the action space",
                                 {"retryable": False, "details": {"errors": problems[:20]}})
        violations = _limits.check(dict(args), effective)
        if violations:
            first = violations[0]
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                f"{first.message()} (action space of the environment); the step was not executed",
                {"retryable": False, "details": first.to_details(),
                 "violations": [item.to_details() for item in violations[:20]]},
            )
        problems = validate(dict(args), self.step_input_schema())
        if problems:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "step input does not match the action space",
                                 {"retryable": False, "details": {"errors": problems[:20]}})

    # -- adapter surface ---------------------------------------------------
    @_owns_native
    def capabilities(self) -> list[dict[str, Any]]:
        # An environment whose native reset takes no seed claims no seeded determinism.
        seeded = "seeded" if self._seedable() else "none"
        try:
            determinism = seeded
            step_extra: dict[str, Any] = {"input_schema": self.step_input_schema(), "limits": self.action_limits()}
            if self._physics_timing is not None:
                step_extra["x-vendor"] = {"openmhs_simulation_timing": self.timing_descriptor()}
        except Exception:  # noqa: BLE001 - the environment cannot open here: no derived contract
            determinism, step_extra = seeded, {}
        if self._async is not None:
            step_native = ("env.step(action) awaited on the owned event loop" if self._async.step == "coroutine"
                           else "env.step(action) on the owned event loop")
            reset_native = ("env.reset() awaited on the owned event loop" if self._async.reset == "coroutine"
                            else "env.reset() on the owned event loop")
        elif self._dm_env is not None:
            step_native, reset_native = "dm_env.Environment.step(action)", "dm_env.Environment.reset()"
        elif self._process is not None:
            step_native = "env.step(action) in the isolated simulator host process"
            reset_native = "env.reset() in the isolated simulator host process"
        else:
            step_native, reset_native = "gym.Env.step(action)", "gym.Env.reset(seed=..., options=...)"
        entries = [
            {
                "capability_id": "cap.world.step.v1",
                "resource": "world",
                "native": step_native,
                "description": ("Advance the environment by `ticks` physics ticks in whole control periods."
                                if self._physics_timing is not None else
                                "Advance the environment by `ticks` transitions with one action."),
                "determinism": determinism,
                **step_extra,
            },
            {
                "capability_id": "cap.world.reset.v1",
                "resource": "world",
                "native": reset_native,
                "description": "Reset the environment and return its initial observation.",
                "determinism": determinism,
            },
        ]
        if self._seedable():
            entries.append({
                "capability_id": "cap.world.seed.v1",
                "resource": "world",
                "native": "gym.Env.reset(seed=...)",
                "description": "Set the seed used by the next reset.",
                "determinism": determinism,
            })
        return entries

    def resources(self) -> list[dict[str, Any]]:
        return [{"resource_id": "world", "kind": "world.sim"}]

    @_owns_native
    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        if resource_id != "world":
            raise unsupported(resource_id, kind="resource")
        state = self.world_state()
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    @_owns_native
    def world_state(self) -> dict[str, Any]:
        if self._checkpoint is None:
            return self._public_world_state()
        # A native getter cannot produce a coherent checkpoint alongside an
        # opaque setter/step. Refuse promptly; never queue a receipt's read
        # behind a worker whose caller may already have timed out.
        if not self._lock.acquire(blocking=False):
            raise make_mhs_error("MHS.DEVICE.BUSY", "checkpoint state is being captured or mutated",
                                 {"retryable": True})
        try:
            state = self._public_world_state()
            state["native_checkpoint"] = self._capture_checkpoint()
            return self._checkpoint_json(state)
        finally:
            self._lock.release()

    def _public_world_state(self) -> dict[str, Any]:
        info: Any
        try:
            info = jsonable(dict(self._last_info))
        except MappingError:
            info = {}
        return {
            "observation": self.observation_json(),
            "reward": jsonable(self._last_reward) if self._last_reward is not None else None,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": self._tick,
            "episode": self._episode,
            "seed": self._seed,
            "info": info,
        }

    def _state_hash(self) -> str:
        if self._checkpoint is not None:
            return canonical.state_hash(self.world_state())
        return canonical.digest({
            "observation": self.observation_json(),
            "tick": self._tick,
            "episode": self._episode,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
        })

    @_owns_native
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        args = dict(args or {})
        context = BridgeContext.coerce(ctx)
        # Captured before any native work. The server cancels before it engages the e-stop.
        # A direct caller has no cancel event: the bridge latch refuses an effectful call
        # admitted after the e-stop, and an e-stop that lands later fails the epoch check.
        self._admitted.epoch = self.estop_epoch
        self._admitted.context = context
        if context.cancelled() or capability_id in _EFFECT_CALLS:
            self._raise_world_fence("cancelled before the environment call")
        self._ensure_env()
        if self._checkpoint_fault and capability_id in {"cap.world.step.v1", "cap.world.reset.v1", "cap.world.seed.v1"}:
            raise make_mhs_error("MHS.DEVICE.FAULTED", self._checkpoint_fault, {"retryable": False})
        if capability_id == "cap.world.step.v1":
            if self._async_fault:
                raise make_mhs_error("MHS.DEVICE.PRECONDITION_UNMET",
                                     f"{self._async_fault}; reset the environment first",
                                     {"retryable": False, "details": {"owned": self._owned_loop.owned()}})
            if self._host_fault:
                raise make_mhs_error("MHS.DEVICE.PRECONDITION_UNMET",
                                     f"{self._host_fault}; reset the environment first",
                                     {"retryable": False, "details": {"owned": self._host.world_owned()}})
            return self._step(args, context)
        if capability_id == "cap.world.reset.v1":
            return self._reset_call(args, context)
        if capability_id == "cap.world.seed.v1" and not self._seedable():
            raise unsupported(capability_id)
        if capability_id == "cap.world.seed.v1":
            seed = args.get("seed")
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer",
                                     {"retryable": False})
            with self._lock:
                self.ensure_open()
                self._raise_world_fence("cancelled before the environment call")
                self._pending_seed = seed
            return {"seed": seed, "accepted": True}
        if capability_id == "cap.world.state.v1":   # deprecated duplicate of mhs.resource.read
            state = self.world_state()
            return {"state": state, "state_hash": canonical.digest(state), "revision": int(context.revision or 0)}
        if capability_id == "cap.world.snapshot.v1":   # deprecated duplicate of mhs.snapshot
            snapshot = self.snapshot()
            return {"snapshot": snapshot, "snapshot_digest": canonical.digest(snapshot),
                    "revision": int(context.revision or 0)}
        if capability_id == "cap.world.restore.v1":   # deprecated duplicate of mhs.restore
            if not isinstance(args.get("snapshot"), Mapping):
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "snapshot must be an object",
                                     {"retryable": False})
            self.restore(args["snapshot"])
            return {"revision": int(context.revision or 0), "state_hash": self._state_hash()}
        # cap.world.render.v1 stays unbound until an artifact store exists (frames are not JSON).
        raise unsupported(capability_id)

    def _step(self, args: dict[str, Any], context: BridgeContext) -> dict[str, Any]:
        if self._physics_timing is not None:
            return self._step_physics(args, context)
        args.setdefault("ticks", 1)
        self._check_step_input(args)
        ticks = int(args["ticks"])
        native_action = self._native_action(args.get("action"))
        env = self._ensure_env()
        with self._lock:
            self.ensure_open()
            # Cancelled, or an e-stop, while it waited for the environment: no native call at all,
            # not even the implicit first reset. The epoch check does not need a cancel event.
            self._raise_world_fence("cancelled while waiting for the environment")
            if self._episode == 0:
                # gymnasium requires reset() before step(): the first step starts
                # the first episode with the configured seed (or 0)
                self._reset(None)
            if (self._terminated or self._truncated) and not self.autoreset:
                raise make_mhs_error(
                    "MHS.DEVICE.PRECONDITION_UNMET",
                    "the episode has ended (terminated or truncated); reset the environment first",
                    {"retryable": False, "details": {"tick": self._tick, "autoreset": False}},
                )
            if self._total_steps + ticks > self._max_steps:
                raise make_mhs_error(
                    "MHS.SAFETY.ENVELOPE_VIOLATION",
                    f"{ticks} ticks would exceed the bridge's limit of {self._max_steps} environment steps",
                    {"retryable": False},
                )
            reward_total = 0.0
            for _ in range(ticks):
                self.ensure_open()
                self._raise_world_fence("cancelled between environment ticks")
                if self._terminated or self._truncated:
                    if not self.autoreset:
                        break
                    self._reset(None)
                if self._checkpoint is not None:
                    self._total_steps += 1  # lifetime admission counts dispatched attempts
                try:
                    result = self._native_invoke("step", partial(env.step, native_action))
                except Exception as exc:  # noqa: BLE001
                    if getattr(exc, "mhs_bridge_outcome", False):
                        raise
                    raise make_mhs_error(
                        "MHS.DEVICE.FAULTED", f"env.step failed ({type(exc).__name__}: {str(exc)[:200]})",
                        {"retryable": False},
                    ) from exc
                reward_total += self._apply_step_result(result)
        output: dict[str, Any] = {
            "observation": self.observation_json(),
            "reward": reward_total,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": self._tick,
            "state_hash": self._state_hash(),
        }
        return output

    def _step_physics(self, args: dict[str, Any], context: BridgeContext) -> dict[str, Any]:
        from .simulation_timing import CONTEXT_KEY, SimulationTimingReport, report_from_context

        self._check_step_input(args)
        ticks = args["ticks"]
        timing = self._physics_timing
        calls = ticks // timing.decimation
        native_action = self._native_action(args.get("action"))
        report = report_from_context(context)
        if report is None:
            if context.operation_id is not None:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "physics timing requires matching step binding metadata on server dispatch",
                                     {"retryable": False})
            report = SimulationTimingReport(timing.descriptor(), ticks)
            context.extra[CONTEXT_KEY] = report
        if not report.matches(timing, ticks):
            raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", "receipt timing descriptor differs from backend",
                                 {"retryable": False})
        report.claim()
        reason = "failed"

        def reset_for_step() -> None:
            nonlocal reason
            report.begin_reset()
            verified, ticks = False, None
            try:
                ticks = self._reset(None)
                verified = True
            except BaseException:
                reason = "reset_fault"
                raise
            finally:
                if timing.reset_integrates:
                    report.end_reset(verified=verified, ticks=ticks)
                else:
                    report.end_reset(verified=verified)

        with self._lock:
            try:
                self.ensure_open()
                if self._timing_fault:
                    raise make_mhs_error("MHS.DEVICE.PRECONDITION_UNMET",
                                         "timing fault requires an explicit verified reset or reopen",
                                         {"retryable": False})
                try:
                    if timing.sample(self._env_attr) != self._timing_last_clock:
                        raise ValueError("physics clock changed outside a bridge step or reset")
                except Exception as exc:
                    self._timing_fault = str(exc)
                    raise make_mhs_error("MHS.DEVICE.FAULTED", f"physics timing unavailable: {exc}",
                                         {"retryable": False}) from exc
                if self._total_steps + calls > self._max_steps:
                    raise make_mhs_error("MHS.SAFETY.ENVELOPE_VIOLATION", "native control-call budget exceeded",
                                         {"retryable": False})
                fence = self._world_fence_exception("cancelled before environment mutation")
                if fence is not None:
                    reason = "cancelled" if isinstance(fence, signals.Cancelled) else "estop"
                    raise fence
                if self._episode == 0:
                    reset_for_step()
                if (self._terminated or self._truncated) and not self.autoreset:
                    raise make_mhs_error("MHS.DEVICE.PRECONDITION_UNMET", "episode ended; reset first",
                                         {"retryable": False})
                reward_total = 0.0
                for _ in range(calls):
                    fence = self._world_fence_exception("cancelled between opaque control calls")
                    if fence is not None:
                        reason = "cancelled" if isinstance(fence, signals.Cancelled) else "estop"
                        raise fence
                    if self._terminated or self._truncated:
                        if not self.autoreset:
                            break
                        reset_for_step()
                    try:
                        before = timing.sample(self._env_attr)
                        if before != self._timing_last_clock:
                            raise ValueError("physics clock changed between control calls")
                        timing.check_step_resolution(before)
                    except Exception as exc:
                        self._timing_fault = str(exc)
                        reason = "accounting_fault"
                        raise make_mhs_error("MHS.DEVICE.FAULTED", f"physics clock before step failed: {exc}",
                                             {"retryable": False}) from exc
                    report.begin_call()
                    self._total_steps += 1
                    result, native_error = None, None
                    try:
                        result = self._ensure_env().step(native_action)
                    except BaseException as exc:
                        native_error = exc
                    try:
                        after = timing.sample(self._env_attr)
                        completed = timing.ticks_between(before, after)
                    except Exception as exc:
                        report.end_call(None, returned=native_error is None)
                        self._timing_fault = str(exc)
                        reason = "accounting_fault"
                        raise make_mhs_error("MHS.DEVICE.FAULTED", f"physics clock after step failed: {exc}",
                                             {"retryable": False}) from exc
                    if completed > timing.decimation or (native_error is None and completed != timing.decimation):
                        # A reset/clock discontinuity may hide integration inside
                        # the opaque call. Its net clock delta is not a proven
                        # completed count when the declared period is violated.
                        report.end_call(None, returned=native_error is None)
                        self._timing_fault = "native step violated declared control decimation"
                        reason = "accounting_fault"
                        raise make_mhs_error("MHS.DEVICE.FAULTED", self._timing_fault, {"retryable": False})
                    report.end_call(completed, returned=native_error is None)
                    self._timing_last_clock = after
                    self._tick += completed
                    if native_error is not None:
                        self._timing_fault = "native step failed; observation may be stale"
                        raise make_mhs_error("MHS.DEVICE.FAULTED",
                                             f"env.step failed ({type(native_error).__name__})",
                                             {"retryable": False}) from native_error
                    try:
                        reward_total += self._apply_step_result(result, advance=False)
                        # Validate every control result before the next native
                        # call can overwrite an invalid observation or info.
                        self._validate_physics_state()
                        output = {"observation": self.observation_json(), "reward": reward_total,
                                  "terminated": bool(self._terminated), "truncated": bool(self._truncated),
                                  "tick": self._tick, "state_hash": self._state_hash()}
                        canonical.digest(output)
                    except Exception:
                        self._timing_fault = "invalid native result; observation may be stale"
                        reason = "invalid_result"
                        raise
                reason = "terminated" if self._terminated else "truncated" if self._truncated else "requested_ticks"
                return output
            finally:
                report.close(reason)

    def _validate_physics_state(self) -> None:
        """An enabled native result must have a serializable complete state."""
        canonical.digest(jsonable(self._last_info))
        canonical.digest(self.world_state())
        self._state_hash()

    def _apply_step_result(self, result: Any, *, advance: bool = True) -> float:
        if is_timestep_like(result):
            # A dm_env TimeStep has four fields: the legacy (obs, reward, done, info) path would read the
            # step type as the observation and the discount as done. Refuse; never guess.
            raise make_mhs_error("MHS.DEVICE.FAULTED",
                                 "env.step returned a dm_env TimeStep; declare the dm_env_v1 profile for this "
                                 "backend (the Gymnasium tuple path never reads a TimeStep)", {"retryable": False})
        try:
            observation, reward, terminated, truncated, info = result
        except (TypeError, ValueError):
            try:
                observation, reward, done, info = result
                terminated, truncated = bool(done), False
            except (TypeError, ValueError) as exc:
                raise make_mhs_error(
                    "MHS.DEVICE.FAULTED", "unexpected env.step result shape", {"retryable": False}
                ) from exc
        self._last_observation = observation
        self._restored_observation = None
        reward_value = float(_plain_scalar(reward)) if reward is not None else 0.0
        if not math.isfinite(reward_value):
            raise make_mhs_error("MHS.DEVICE.FAULTED", "env.step returned a non-finite reward", {"retryable": False})
        self._last_reward = reward_value
        self._terminated = bool(terminated)
        self._truncated = bool(truncated)
        self._last_info = dict(info or {}) if isinstance(info, Mapping) else {"info": info}
        if advance:
            self._tick += 1
            if self._checkpoint is None:
                self._total_steps += 1
        return reward_value

    def _reset_call(self, args: Mapping[str, Any], context: BridgeContext | None = None) -> dict[str, Any]:
        unknown = set(args) - {"seed", "options", "scenario"}
        if unknown:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"unknown reset inputs {sorted(unknown)}",
                                 {"retryable": False})
        if args.get("scenario") is not None:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID",
                                 "this environment does not declare named scenarios", {"retryable": False})
        seed = args.get("seed")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "seed must be a non-negative integer",
                                 {"retryable": False})
        options = args.get("options")
        if options is not None and not isinstance(options, Mapping):
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "options must be an object", {"retryable": False})
        if seed is not None and not self._seedable():
            # Accepted for the class contract only (the published input says so); never passed or recorded.
            seed = None
        if options and self._reset_kwargs is not None and "options" not in self._reset_kwargs:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "this environment's native reset accepts no options",
                                 {"retryable": False})
        timing = self._physics_timing
        if timing is not None and timing.reset_integrates:
            return self._reset_call_integrating(seed, options, context or BridgeContext())
        with self._lock:
            self.ensure_open()
            self._raise_world_fence("cancelled while waiting for the environment")
            self._reset(seed, options=dict(options) if options else None)
            self._async_fault = None
            self._host_fault = None
        return {"observation": self.observation_json(), "seed": int(self._seed or 0)}

    def _reset_call_integrating(self, seed: Any, options: Any, context: BridgeContext) -> dict[str, Any]:
        """An explicit reset that integrates physics: its measured ticks go to the reset receipt."""
        from .simulation_timing import CONTEXT_KEY, SimulationTimingReport, report_from_context

        report = report_from_context(context)
        if report is None:
            if context.operation_id is not None:
                raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                     "an integrating reset requires matching reset binding metadata on server dispatch",
                                     {"retryable": False})
            report = SimulationTimingReport(self.timing_descriptor(), None)
            context.extra[CONTEXT_KEY] = report
        report.claim()
        reason = "reset_fault"
        with self._lock:
            try:
                self.ensure_open()
                fence = self._world_fence_exception("cancelled while waiting for the environment")
                if fence is not None:
                    reason = "cancelled" if isinstance(fence, signals.Cancelled) else "estop"
                    raise fence
                report.begin_reset()
                verified, ticks = False, None
                try:
                    ticks = self._reset(seed, options=dict(options) if options else None)
                    verified = True
                finally:
                    report.end_reset(verified=verified, ticks=ticks)
                reason = "reset"
            finally:
                report.close(reason)
        return {"observation": self.observation_json(), "seed": int(self._seed or 0)}

    def _reset(self, seed: int | None, *, options: Mapping[str, Any] | None = None) -> int | None:
        """Reset; with physics timing, verify the clock and return the physics ticks the reset integrated."""
        self.ensure_open()
        timing = self._physics_timing
        if timing is None:
            self._reset_legacy(seed, options=options)
            return None
        if timing.reset_integrates:
            return self._reset_integrating(timing, seed, options)
        try:
            timing.check_timestep(self._env_attr)
            self._reset_legacy(seed, options=options)
            if timing.sample(self._env_attr) != 0.0:
                raise ValueError("physics_ticks_v1 reset must restore the native clock to zero without integration")
            self._timing_last_clock = 0.0
            self._timing_fault = None
            self._validate_physics_state()
        except Exception as exc:
            self._timing_fault = str(exc)
            raise make_mhs_error("MHS.DEVICE.FAULTED", f"timing reset verification failed: {exc}",
                                 {"retryable": False}) from exc
        return 0

    def _reset_integrating(self, timing: Any, seed: int | None, options: Mapping[str, Any] | None) -> int:
        """A reviewed reset that integrates physics (settling): measured, bounded, never an episode tick."""
        try:
            before = timing.sample(self._env_attr) if timing.reset_clock == "continue" else None
            timing.check_reset_resolution(before)
            self._reset_legacy(seed, options=options)
            after = timing.sample(self._env_attr)
            ticks = timing.reset_ticks(before, after)
            # Control ticks resume from here; the next control call must start exactly at this clock.
            timing.check_step_resolution(after)
            self._timing_last_clock = after
            self._timing_fault = None
            self._last_reset_ticks = ticks
            self._validate_physics_state()
        except Exception as exc:
            self._timing_fault = str(exc)
            raise make_mhs_error("MHS.DEVICE.FAULTED", f"timing reset verification failed: {exc}",
                                 {"retryable": False}) from exc
        return ticks

    def _reset_legacy(self, seed: int | None, *, options: Mapping[str, Any] | None = None) -> None:
        env = self._ensure_env()
        if self._reset_kwargs is not None:
            return self._reset_declared(env, seed, options)
        if seed is None and self._pending_seed is not None:
            seed, self._pending_seed = self._pending_seed, None
        if seed is None and self._episode == 0:
            seed = self._configured_seed if self._configured_seed is not None else 0
        kwargs: dict[str, Any] = {}
        if seed is not None:
            kwargs["seed"] = int(seed)
        if options:
            kwargs["options"] = dict(options)
        try:
            try:
                result = env.reset(**kwargs)
            except TypeError:
                if seed is not None and callable(getattr(env, "seed", None)):
                    env.seed(int(seed))   # legacy gym API
                result = env.reset()
        except Exception as exc:  # noqa: BLE001
            raise make_mhs_error("MHS.DEVICE.FAULTED", f"env.reset failed ({type(exc).__name__})",
                                 {"retryable": False}) from exc
        self._apply_reset_result(result, seed)

    def _reset_declared(self, env: Any, seed: int | None, options: Mapping[str, Any] | None) -> None:
        """Reset through an explicit, reviewed native signature: no keyword guessing, no retry."""
        allowed = self._reset_kwargs or ()
        kwargs: dict[str, Any] = {}
        if "seed" in allowed:
            if seed is None and self._pending_seed is not None:
                seed, self._pending_seed = self._pending_seed, None
            if seed is None and self._episode == 0:
                seed = self._configured_seed if self._configured_seed is not None else 0
            if seed is not None:
                kwargs["seed"] = int(seed)
        elif seed is not None:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "this environment's native reset accepts no seed",
                                 {"retryable": False})
        if options:
            if "options" not in allowed:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID",
                                     "this environment's native reset accepts no options", {"retryable": False})
            kwargs["options"] = dict(options)
        try:
            result = self._native_invoke("reset", partial(env.reset, **kwargs))
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "mhs_bridge_outcome", False):
                raise
            raise make_mhs_error("MHS.DEVICE.FAULTED", f"env.reset failed ({type(exc).__name__})",
                                 {"retryable": False}) from exc
        self._apply_reset_result(result, kwargs.get("seed"))

    def _apply_reset_result(self, result: Any, seed: int | None) -> None:
        if is_timestep_like(result):
            raise make_mhs_error("MHS.DEVICE.FAULTED",
                                 "env.reset returned a dm_env TimeStep; declare the dm_env_v1 profile for this "
                                 "backend (the Gymnasium tuple path never reads a TimeStep)", {"retryable": False})
        if isinstance(result, tuple) and result:
            observation = result[0]
            info = result[1] if len(result) > 1 and isinstance(result[1], Mapping) else {}
        else:
            observation, info = result, {}
        self._last_observation = observation
        self._restored_observation = None
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_info = dict(info or {})
        self._tick = 0
        self._episode += 1
        if seed is not None:
            self._seed = int(seed)

    # -- snapshot / restore ------------------------------------------------
    def _checkpoint_json(self, value: Any) -> Any:
        from .gym_checkpoint import bounded_json
        try:
            return bounded_json(value, self._checkpoint.max_bytes)
        except (ValueError, TypeError, OverflowError) as exc:
            raise make_mhs_error("MHS.RESOURCE.STATE_INVALID", str(exc), {"retryable": False}) from exc

    def _verified_checkpoint_clock(self) -> float | None:
        if self._physics_timing is None:
            return None
        try:
            clock = self._physics_timing.sample(self._env_attr)
            if self._timing_fault or clock != self._timing_last_clock:
                raise ValueError("physics state is not verified")
            return clock
        except Exception as exc:
            self._timing_fault = str(exc)
            raise make_mhs_error("MHS.DEVICE.FAULTED", "timing fault prevents a trustworthy checkpoint",
                                 {"retryable": False}) from exc

    def _capture_checkpoint(self) -> dict[str, Any]:
        if self._checkpoint_fault:
            raise make_mhs_error("MHS.DEVICE.FAULTED", self._checkpoint_fault, {"retryable": False})
        getter, _setter = self._checkpoint_access()
        clock = self._verified_checkpoint_clock()
        payload = self._checkpoint_json(getter())
        self._verified_checkpoint_clock()
        checkpoint = {"profile": "json_state_v1", "configuration_digest": self._checkpoint.digest,
                      "native_state": payload, "pending_seed": self._pending_seed}
        if self._physics_timing is not None:
            checkpoint.update(simulation_timing=canonical.digest(self.timing_descriptor()), physics_clock=clock)
        return checkpoint

    @_owns_native
    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            self.ensure_open()
            self._checkpoint_access()
            return {"world": self.world_state()}

    def validate_restore(self, snapshot: Any) -> dict[str, Any]:
        """Pure validation of submitted state, also called by the endpoint pre-effect."""
        if self._checkpoint is None:
            raise make_mhs_error("MHS.CAPABILITY.NOT_BOUND", "JSON checkpoint profile is not configured",
                                 {"retryable": False})
        if self._checkpoint_fault:
            raise make_mhs_error("MHS.DEVICE.FAULTED", self._checkpoint_fault, {"retryable": False})
        world = snapshot.get("world") if type(snapshot) is dict and set(snapshot) == {"world"} else None
        fields = {"observation", "reward", "terminated", "truncated", "tick", "episode", "seed", "info",
                  "native_checkpoint"}
        if type(world) is not dict or set(world) != fields:
            raise make_mhs_error("MHS.CONFLICT.SNAPSHOT_MISMATCH", "not a declared Gym JSON checkpoint state",
                                 {"retryable": False})
        world = self._checkpoint_json(world)
        checkpoint = world["native_checkpoint"]
        expected = {"profile", "configuration_digest", "native_state", "pending_seed"}
        if self._physics_timing is not None:
            expected |= {"simulation_timing", "physics_clock"}
        valid = (type(checkpoint) is dict and set(checkpoint) == expected
                 and checkpoint.get("profile") == "json_state_v1"
                 and checkpoint.get("configuration_digest") == self._checkpoint.digest
                 and type(world["observation"]) is dict and type(world["info"]) is dict
                 and all(type(world[k]) is bool for k in ("terminated", "truncated"))
                 and all(type(world[k]) is int and world[k] >= 0 for k in ("tick", "episode"))
                 and (world["reward"] is None or type(world["reward"]) in (int, float)))
        if valid:
            valid = all(value is None or (type(value) is int and value >= 0)
                        for value in (world["seed"], checkpoint["pending_seed"]))
        if self._physics_timing is not None and valid:
            clock = checkpoint["physics_clock"]
            valid = (checkpoint["simulation_timing"] == canonical.digest(self.timing_descriptor())
                     and world["tick"] % self._physics_timing.decimation == 0
                     and type(clock) in (int, float) and math.isfinite(clock) and clock >= 0)
        if not valid:
            raise make_mhs_error("MHS.CONFLICT.SNAPSHOT_MISMATCH", "Gym checkpoint fields/configuration differ",
                                 {"retryable": False})
        return world

    @contextmanager
    def restore_admission(self, stop_changed=None):
        """Own all restore preparation/effects; nested rollback retains the original stop epoch."""
        epoch = self.estop_epoch
        with self._native_admission(), self._lock:
            previous = self._restore_admission_epoch
            previous_check = self._restore_stop_check
            self._restore_admission_epoch = epoch if previous is None else previous
            self._restore_stop_check = previous_check or stop_changed
            try:
                self._check_restore_stop()
                yield
            finally:
                self._restore_admission_epoch = previous
                self._restore_stop_check = previous_check

    def _check_restore_stop(self) -> None:
        self.ensure_open()
        if self._effects_latched():
            raise make_mhs_error("MHS.SAFETY.ESTOP_ENGAGED",
                                 "checkpoint restore was not executed: the e-stop latch is engaged",
                                 {"retryable": False, "details": {"preempted_by_estop": True}})
        self._refuse_if_estopped(self._restore_admission_epoch, "checkpoint restore")
        if self._restore_stop_check is not None and self._restore_stop_check():
            raise make_mhs_error("MHS.SAFETY.ESTOP_ENGAGED",
                                 "checkpoint restore was preempted by the endpoint e-stop",
                                 {"retryable": False, "details": {"preempted_by_estop": True}})

    def restore(self, snapshot: Any) -> dict[str, Any]:
        if self._effects_latched():
            raise make_mhs_error("MHS.SAFETY.ESTOP_ENGAGED",
                                 "checkpoint restore was not executed: the e-stop latch is engaged",
                                 {"retryable": False, "details": {"preempted_by_estop": True}})
        with self.restore_admission():
            world = self.validate_restore(snapshot)
            _getter, setter = self._checkpoint_access()
            checkpoint = world["native_checkpoint"]
            self._check_restore_stop()
            if self._physics_timing is not None:
                if self._timing_fault:
                    raise make_mhs_error("MHS.DEVICE.PRECONDITION_UNMET",
                                         "timing fault requires explicit verified reset or reopen",
                                         {"retryable": False})
                self._physics_timing.check_timestep(self._env_attr)
            try:
                self._check_restore_stop()
                completion = setter(copy.deepcopy(checkpoint["native_state"]))
                if completion is not None:
                    self._checkpoint_fault = (
                        "json_state_v1 setter must complete synchronously and return None; "
                        "unsupported completion cannot be reconciled on this bridge")
                    raise ValueError(self._checkpoint_fault)
                # The normalized observation is adapter-owned. It is never fed to
                # a native setter or guessed back into a native array/tuple codec.
                self._restored_observation = world["observation"]
                self._last_reward = world["reward"]
                self._terminated = world["terminated"]
                self._truncated = world["truncated"]
                self._tick = world["tick"]
                self._episode = world["episode"]
                self._seed = world["seed"]
                self._pending_seed = checkpoint["pending_seed"]
                self._last_info = world["info"]
                # Lifetime admission budget is deliberately not restorable.
                if self._physics_timing is not None:
                    clock = self._physics_timing.sample(self._env_attr)
                    if clock != checkpoint["physics_clock"]:
                        raise ValueError("restored physics clock differs from the saved clock")
                    self._timing_last_clock = clock
                actual = self.world_state()
                self._check_restore_stop()
                if canonical.digest(actual) != canonical.digest(world):
                    raise ValueError("native getter did not reproduce the declared checkpoint")
            except Exception as exc:
                if self._physics_timing is not None:
                    self._timing_fault = str(exc)
                raise make_mhs_error("MHS.OUTCOME.UNKNOWN", f"checkpoint restore verification failed: {exc}",
                                     {"retryable": False, "details": {"may_have_effect": True}}) from exc
        return {"world": actual}

    def safety_status(self) -> dict[str, Any]:
        if self._closed or self._checkpoint_fault or self._restore_admission_epoch is not None:
            return {"safe_state": {"achieved": False}}
        if self._owned_loop is not None and (self._owned_loop.owns_any() or self._stop_unconfirmed):
            # Owned native work (in progress or abandoned after its bound) may still change the world.
            return {"safe_state": {"achieved": False}}
        if self._host is not None:
            state = self._host.state()
            # A world call in flight or owned, an unconfirmed stop, or a host that failed, died or broke: whatever
            # it launched may still run.
            if state["world"] is not None or self._stop_unconfirmed or state["state"] not in ("new", "ready"):
                return {"safe_state": {"achieved": False}}
        # Every native step, reset and checkpoint call holds the mutation lock. While one is in flight
        # the world may still change: never report the safe state then (non-blocking; e-stop attempts
        # first wait, bounded, through settle_native_work).
        if not self._lock.acquire(blocking=False):
            return {"safe_state": {"achieved": False}}
        self._lock.release()
        return {}

    def settle_native_work(self, timeout_s: float) -> bool:
        """Wait at most ``timeout_s`` for an in-flight native step, reset or checkpoint call to end.

        Called by the endpoint's e-stop attempt (never under the server lock). It
        takes the mutation lock only to observe that it is free and releases it
        at once; with an owned loop it then waits for owned work to settle.
        Returns True when nothing native is in flight; it never cancels anything.
        """
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        if not self._lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return False
        self._lock.release()
        if self._owned_loop is not None:
            return self._owned_loop.wait_idle(max(0.0, deadline - time.monotonic()))
        if self._host is not None:
            return self._host.wait_world_idle(max(0.0, deadline - time.monotonic()))
        return True

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        # The epoch, the latch and the pending mark move together, before any native
        # stop. A direct caller is refused even when this attempt later reports the
        # safe state unverified. The pending mark stays set until this call returns,
        # so reset cannot release the latch in the gap before the attempt publishes.
        with self._stop_state:
            self._engage_estop()  # independent of the native/checkpoint lock
            self._estop_latched = True
            self._stop_paths_pending += 1
        try:
            if self._owned_loop is not None:
                return self._estop_owned()
            if self._host is not None:
                return self._estop_hosted()
            return self.safe_state(ctx)
        finally:
            with self._stop_state:
                self._stop_paths_pending -= 1

    def safe_state(self, ctx: Any = None) -> Any:
        if self.safety_status().get("safe_state", {}).get("achieved") is False:
            loop = self._owned_loop
            owned = (loop.owned() or loop.owned_stop()) if loop is not None else None
            hosted = None
            if self._host is not None:
                state = self._host.state()
                if state["world"] is not None:
                    hosted = f"native {state['world'].get('op')} in the simulator host is still owned"
                elif state["state"] not in ("new", "ready"):
                    hosted = f"the simulator host is not running ({state['reason'] or state['state']})"
            reason = ("bridge is closed or closing" if self._closed else
                      self._checkpoint_fault or hosted or
                      (f"native {owned['kind']} is still owned" if owned else self._stop_unconfirmed) or
                      "native checkpoint/step work is still active")
            raise make_mhs_error("MHS.OUTCOME.UNKNOWN", "safe state is unverified: " + reason,
                                 {"retryable": False, "details": {"safe_state_achieved": False}})
        return {}

    def reset(self, ctx: Any = None) -> Any:
        # Taken before any hook an e-stop could re-enter. A newer e-stop keeps the latch.
        epoch = self.estop_epoch
        self.ensure_open()
        # An e-stop that already advanced the epoch and has not returned still owns
        # the latch. Owned work and ``_stop_unconfirmed`` are empty in the gap
        # before the native stop is submitted and between a hosted stop and its
        # read-back. Refuse before any unfence.
        self._refuse_pending_stop()
        # A safety reset must not unlatch an opaque checkpoint setter that can
        # still overwrite the stop state. E-stop itself never takes this lock.
        if self._checkpoint_fault:
            raise make_mhs_error("MHS.SAFETY.RESET_REFUSED", self._checkpoint_fault, {"retryable": False})
        if self._checkpoint is None:
            # The checkpoint branch below has always refused while native work runs; so does every bridge now.
            if not self._lock.acquire(blocking=False):
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED",
                                     "a native step or reset is still running; wait for it to end",
                                     {"retryable": False})
            self._lock.release()
        if self._owned_loop is not None:
            owned = self._owned_loop.owned() or self._owned_loop.owned_stop()
            if owned is not None:
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED",
                                     f"native {owned['kind']} is still owned; wait until it settles",
                                     {"retryable": False, "details": {"owned": owned}})
            if self._stop_unconfirmed:
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED",
                                     f"the remote stop is unconfirmed ({self._stop_unconfirmed}); engage the e-stop "
                                     "again until it is confirmed", {"retryable": False})
        if self._host is not None:
            state = self._host.state()
            if state["world"] is not None:
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED",
                                     f"native {state['world'].get('op')} in the simulator host is still owned; wait "
                                     "until it settles", {"retryable": False, "details": {"owned": state["world"]}})
            if self._stop_unconfirmed:
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED",
                                     f"the simulator stop is unconfirmed ({self._stop_unconfirmed}); engage the e-stop "
                                     "again until it is confirmed", {"retryable": False})
            if state["state"] not in ("new", "ready"):
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED",
                                     f"the simulator host is not running ({state['reason'] or state['state']})",
                                     {"retryable": False})
            if state["state"] == "ready" and state["fenced"]:
                if self.estop_epoch != epoch:
                    # An e-stop landed during this reset. Leave the fence and the latch.
                    return {}
                # Same epoch, stop still in flight: do not unfence.
                self._refuse_pending_stop()
                try:
                    self._host.unfence()   # world calls are accepted again; the simulator itself is not changed
                except Exception as exc:  # noqa: BLE001 - the latch stays until the host confirms
                    why = f"the simulator host did not lift its fence ({type(exc).__name__}: {exc})"
                    raise make_mhs_error("MHS.SAFETY.RESET_REFUSED", why[:300], {"retryable": False}) from exc
                if self.estop_epoch != epoch:
                    return {}
                self._refuse_pending_stop()
        if self._checkpoint is not None:
            if not self._lock.acquire(blocking=False):
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED",
                                     "checkpoint/step work is still running; wait for native completion",
                                     {"retryable": False})
            self._lock.release()
        with self._stop_state:
            # Re-check with the epoch. A stop still in flight for this epoch keeps
            # the latch. A newer epoch keeps it too, and reset still returns {}.
            pending_same_epoch = self._stop_paths_pending > 0 and self.estop_epoch == epoch
            if self.estop_epoch == epoch and not pending_same_epoch:
                self._estop_latched = False
        if pending_same_epoch:
            self._refuse_pending_stop()
        return {}

    def close(self) -> None:
        with self._lifecycle:
            # Irreversible admission fence, set before any native close call.
            self._closed = True
            cleanup = self._claim_cleanup()
        if cleanup:
            self._cleanup_native()

    def describe(self) -> dict[str, Any]:
        described = super().describe()
        described.update(
            {
                "env_id": self._env_id,
                "modules": None if self._modules is None else list(self._modules),
                "render_mode": self._render_mode,
                "seed": self._seed,
                "autoreset": self.autoreset,
                "snapshot_supported": self.snapshot_supported,
                "gym_available": self.available(),
            }
        )
        if self._checkpoint_opt_out is not None:
            described["checkpoint_opt_out"] = self._checkpoint_opt_out
        if self._async is not None:
            described["asynchronous"] = self.async_status()
        if self._host is not None:
            described["isolated_process"] = self.host_status()
        if self._dm_env is not None:
            described["dm_env"] = self._dm_env.descriptor()
        return described


def _plain_scalar(value: Any) -> Any:
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except (TypeError, ValueError):
            return value
    return value


def _is_json(value: Any) -> bool:
    try:
        jsonable(value)
    except MappingError:
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
