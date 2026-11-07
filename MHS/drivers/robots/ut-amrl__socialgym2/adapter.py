"""Shared ParallelEnv projection. No upstream imports or process creation."""
from collections.abc import Mapping
import math
import contextvars
import numbers
import threading

from mhs.bridge.base import BridgeContext, make_mhs_error
from mhs import signals
from mhs.bridge.gymnasium import GymnasiumBridge

_CONTEXT = contextvars.ContextVar("socialgym_call", default=None)

STOP = "x-cap.ut-amrl.fence.v1"
UNSEEDED_RESET = "x-cap.ut-amrl.reset_unseeded.v1"


def refuse(code, message):
    raise make_mhs_error(code, message, {"retryable": False})


class Dict:
    """Space metadata composed from the native per-agent spaces, not copied bounds."""
    def __init__(self, spaces):
        self.spaces = dict(spaces)


class ParallelAdapter:
    def __init__(self, native, *, simulated_external=False):
        self.native = native
        self.external = simulated_external
        names = tuple(native.possible_agents)
        if not names or len(names) != len(set(names)) or not all(isinstance(x, str) and x for x in names):
            raise ValueError("possible_agents must contain distinct nonempty agent names")
        self.names = names
        self.action_space = Dict({a: native.action_space(a) for a in names})
        self.observation_space = Dict({a: native.observation_space(a) for a in names})
        self._guard = threading.Lock()
        self._active = False
        self._halted = False
        self._closing = False
        self._closed = False
        self._cleanup_started = False
        self._close_error = None
        self._episode_agents = set()
        self._terms = {}
        self._truncs = {}

    def _begin(self):
        with self._guard:
            ctx = _CONTEXT.get()
            if ctx is not None and (ctx.cancelled() or ctx.remaining_ms() <= 0):
                raise signals.Cancelled("expired or cancelled before native environment call")
            if self._closing:
                refuse("MHS.DEVICE.NOT_READY", "environment is closing or closed")
            if self._halted:
                refuse("MHS.SAFETY.ESTOP_ENGAGED", "the adapter is fenced until safety reset")
            if self._active:
                refuse("MHS.DEVICE.NOT_READY", "another native call is still running")
            self._active = True

    def _end(self):
        with self._guard:
            self._active = False
            cleanup = self._claim_cleanup()
        if cleanup:
            self._cleanup()

    def fence(self):
        with self._guard:
            self._halted = True
            if self._closing:
                refuse("MHS.SAFETY.SAFE_STATE_UNREACHED", "environment is closing or closed")
            if self._active:
                refuse("MHS.SAFETY.SAFE_STATE_UNREACHED", "native reset/step is still running; latch retained")
            if self.external:
                refuse("MHS.SAFETY.SAFE_STATE_UNREACHED",
                       "upstream external simulator stop is unconfirmed; a local fence cannot acknowledge it")
        return {"idle": True, "scope": "local fake calls only"}

    def recover(self):
        with self._guard:
            if self._closing or self._active or self.external:
                refuse("MHS.SAFETY.SAFE_STATE_UNREACHED", "cannot resume an active or unconfirmed external simulator")
            self._halted = False
        return {"reset": True}

    def reset(self, seed=None, options=None):
        if self.external and seed is not None:
            refuse("MHS.CAPABILITY.INPUT_INVALID", "upstream seed/reset seed is a no-op; seeded replay is unsupported")
        if options:
            refuse("MHS.CAPABILITY.INPUT_INVALID", "upstream reset does not implement reset options")
        self._begin()
        try:
            value = self.native.reset() if self.external else self.native.reset(seed=seed)
            if not isinstance(value, tuple) or len(value) != 2:
                raise ValueError("ParallelEnv reset must return observations and infos")
            obs, infos = value
            if not isinstance(obs, Mapping) or not isinstance(infos, Mapping) or not obs or not set(obs) <= set(self.names):
                raise ValueError("reset returned invalid agent maps")
            self._episode_agents = set(obs)
            initial = getattr(self.native, "terminations", None)
            if initial is None:
                initial = dict.fromkeys(obs, False)
            if not isinstance(initial, Mapping) or not set(obs) <= set(initial) or not all(type(initial[a]) is bool for a in obs):
                raise ValueError("invalid initial terminal map")
            self._terms = {a: initial[a] for a in obs}
            self._truncs = dict.fromkeys(obs, False)
            return dict(obs), {"agents": dict(infos), "active_agents": sorted(
                a for a in obs if not self._terms[a])}
        finally:
            self._end()

    def step(self, action):
        if not isinstance(action, Mapping) or not set(action) <= set(self.names):
            raise ValueError("action must contain configured agent names")
        self._begin()
        try:
            active = set(self.native.agents or ())
            if not active <= self._episode_agents:
                raise ValueError("native introduced an agent outside the current episode")
            remaining = {a for a in self._episode_agents if not (self._terms[a] or self._truncs[a])}
            if not remaining <= active:
                raise ValueError("native removed an agent without a terminal result")
            if not remaining:
                refuse("MHS.DEVICE.PRECONDITION_UNMET", "episode has ended; reset before stepping")
            raw = self.native.step({a: action[a] for a in remaining if a in action})
            if not isinstance(raw, tuple) or len(raw) != 5 or not all(isinstance(v, Mapping) for v in raw):
                raise ValueError("ParallelEnv step must return five mappings")
            obs, rewards, terms, truncs, infos = raw
            keys = set(rewards)
            if keys != remaining or keys != set(terms) or keys != set(truncs) or keys != set(obs):
                raise ValueError("step agent maps must match the active unfinished agents")
            if not all(type(v) is bool for v in (*terms.values(), *truncs.values())):
                raise ValueError("per-agent terminal flags must be booleans")
            if any(isinstance(v, bool) or not isinstance(v, numbers.Real) or not math.isfinite(v)
                   for v in rewards.values()):
                raise ValueError("per-agent rewards must be finite numbers")
            # Completion is sticky across the upstream's changing active sets.
            for a in keys:
                self._terms[a] = self._terms[a] or terms[a]
                self._truncs[a] = self._truncs[a] or truncs[a]
            done = all(self._terms[a] or self._truncs[a] for a in self._episode_agents)
            terminated = done and all(self._terms.values())
            truncated = done and any(self._truncs.values())
            info = {"agents": dict(infos), "rewards": dict(rewards), "terminations": dict(terms),
                    "truncations": dict(truncs), "episode_terminations": dict(self._terms),
                    "episode_truncations": dict(self._truncs), "active_agents": sorted(
                        a for a in remaining if not (self._terms[a] or self._truncs[a]))}
            return dict(obs), math.fsum(rewards.values()), terminated, truncated, info
        finally:
            self._end()

    def close(self):
        with self._guard:
            self._halted = True
            self._closing = True
            cleanup = self._claim_cleanup()
        if cleanup:
            self._cleanup()

    def _claim_cleanup(self):
        if self._closing and not self._active and not self._cleanup_started:
            self._cleanup_started = True
            return True
        return False

    def _cleanup(self):
        # Source close() is a no-op; this is not an external shutdown claim.
        error = None
        try:
            self.native.close()
        except Exception as exc:
            error = str(exc)
        finally:
            with self._guard:
                self._closed = True
                self._close_error = error


class ParallelBridge(GymnasiumBridge):
    def __init__(self, native, *, external=False, **kwargs):
        self.parallel = ParallelAdapter(native, simulated_external=external)
        self.external = external
        super().__init__(env=self.parallel, **kwargs)

    def capabilities(self):
        values = super().capabilities()
        if self.external:
            values = [v for v in values if v["capability_id"] not in ("cap.world.seed.v1", "cap.world.reset.v1")]
            values = [dict(v, determinism="none") for v in values]
        return values + [{"capability_id": STOP, "resource": "world", "input_schema": {
            "type": "object", "properties": {}, "additionalProperties": False}},
                         {"capability_id": UNSEEDED_RESET, "resource": "world", "input_schema": {
                             "type": "object", "properties": {}, "additionalProperties": False},
                          "determinism": "none"}]

    def call(self, capability_id, args=None, ctx=None):
        context = BridgeContext.coerce(ctx)
        token = _CONTEXT.set(context)
        try:
            return self._dispatch(capability_id, args, context)
        finally:
            _CONTEXT.reset(token)

    def _dispatch(self, capability_id, args=None, ctx=None):
        if capability_id == STOP:
            return self.parallel.fence()
        if capability_id == UNSEEDED_RESET:
            if args:
                refuse("MHS.CAPABILITY.INPUT_INVALID", "unseeded reset accepts no arguments")
            with self._lock:
                self._unseeded_reset()
            return {"observation": self.observation_json()}
        if self.external and capability_id in ("cap.world.seed.v1", "cap.world.reset.v1"):
            refuse("MHS.CAPABILITY.NOT_BOUND", "the real environment does not implement seeded reset")
        return super().call(capability_id, args, ctx)

    def _reset(self, seed, *, options=None):
        if not self.external:
            return super()._reset(seed, options=options)
        if seed is not None:
            refuse("MHS.CAPABILITY.NOT_BOUND", "seeded reset is not implemented upstream")
        if options:
            refuse("MHS.CAPABILITY.INPUT_INVALID", "upstream reset options are unsupported")
        self._unseeded_reset()

    def _unseeded_reset(self):
        observation, info = self.parallel.reset()
        self._last_observation, self._last_info = observation, info
        self._last_reward, self._terminated, self._truncated = 0.0, False, False
        self._tick = 0
        self._episode += 1
        self._seed = None

    def reset(self, ctx=None):
        return self.parallel.recover()
