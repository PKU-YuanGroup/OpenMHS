"""dm_env / dm_control composer environments behind the Gymnasium bridge (``dm_env_v1``).

A ``dm_env.Environment`` answers ``reset()`` and ``step(action)`` with a
``TimeStep(step_type, reward, discount, observation)``: four fields, so the
Gymnasium bridge's legacy ``(observation, reward, done, info)`` path would read
the step type as the observation and the discount as ``done``.  This adapter
maps the dm_env contract explicitly, and the bridge refuses a TimeStep that
reaches its tuple path without it.

Mapping (dm_env semantics; no dm_env or dm_control import is needed):

* ``reset()`` must return a ``FIRST`` step: ``(observation, info)``;
* ``step()`` must return ``MID`` or ``LAST``.  ``LAST`` with discount 0 is
  *terminated*; ``LAST`` with a positive discount is *truncated* (the episode
  was cut, as a time limit does).  A ``FIRST`` from ``step()`` (an environment
  that restarted on its own) is refused: the bridge resets explicitly;
* reward must be a finite scalar on ``MID``/``LAST``; discount a finite number
  in [0, 1] on ``LAST``;
* ``action_spec()`` maps to the action space: a ``BoundedArray`` to a Box with
  its ``minimum``/``maximum`` broadcast to its shape (the step bounds), a
  ``DiscreteArray`` to a Discrete, an unbounded ``Array`` to an unbounded Box
  (no limits), and a mapping of specs to a Dict;
* ``observation_spec()`` maps the same way for observation conversion;
* the native ``reset()`` takes no seed and no options: a dm_env environment is
  seeded when it is built (``random_state``), so the bridge serves no seed
  capability and claims no seeded determinism for it.

Actions are converted to the spec's dtype and shape (NumPy, when installed) and
validated by the spec's own ``validate`` when it has one, after the bridge's
envelope check.  Native code is never imported here.
"""

from __future__ import annotations

import importlib
import math
import operator
from typing import Any, Mapping

from .base import make_mhs_error

__all__ = ["DM_ENV_PROFILE", "DmEnvAdapter", "DmEnvProfile", "is_timestep_like"]

DM_ENV_PROFILE = "dm_env_v1"
_FIRST, _MID, _LAST = 0, 1, 2
_NAMES = {_FIRST: "FIRST", _MID: "MID", _LAST: "LAST"}
_MAX_SPEC_DEPTH = 8


class DmEnvError(ValueError):
    """A dm_env result or spec violates the adapter's mapping."""


def is_timestep_like(value: Any) -> bool:
    """True for a dm_env ``TimeStep`` (or any object carrying ``step_type`` and ``discount``)."""
    if isinstance(value, (str, bytes, Mapping)):
        return False
    fields = getattr(type(value), "_fields", None)
    if isinstance(fields, tuple) and "step_type" in fields and "discount" in fields:
        return True
    try:
        return hasattr(value, "step_type") and hasattr(value, "discount")
    except Exception:  # noqa: BLE001 - an exotic object is not a TimeStep
        return False


class DmEnvProfile:
    """A resolved ``dm_env_v1`` declaration: ``{"profile": "dm_env_v1", "source_refs": [...]}``."""

    def __init__(self, source_refs: tuple[str, ...] = ()):
        self.source_refs = tuple(source_refs)

    @classmethod
    def resolve(cls, config: Mapping[str, Any]) -> "DmEnvProfile":
        if not isinstance(config, Mapping) or set(config) - {"profile", "source_refs"}:
            raise DmEnvError("the dm_env profile takes only 'profile' and 'source_refs'")
        if config.get("profile") != DM_ENV_PROFILE:
            raise DmEnvError(f"profile must be {DM_ENV_PROFILE!r}")
        refs = config.get("source_refs", ())
        if not isinstance(refs, (list, tuple)) or len(refs) > 20 or any(
                not isinstance(ref, str) or not ref or len(ref) > 500 for ref in refs):
            raise DmEnvError("source_refs must be bounded strings; citations do not validate the backend")
        return cls(tuple(refs))

    def descriptor(self) -> dict[str, Any]:
        return {"profile": DM_ENV_PROFILE, "source_refs": list(self.source_refs)}

    def notes(self) -> list[str]:
        return ["dm_env environment (dm_env_v1): reset must return FIRST; a LAST step with discount 0 is "
                "terminated and with a positive discount truncated; action_spec bounds are the step bounds. "
                "The native reset takes no seed: seeding happens when the environment is built, so no seed "
                "capability is served and no seeded determinism is claimed."]


# -- specs -> duck-typed spaces --------------------------------------------------
# The bridge recognises a space family by its class name (Box, Discrete, Dict), as for Gymnasium's own.
class Box:
    """Duck-typed ``gymnasium.spaces.Box`` built from a dm_env spec.

    ``mhs_integer_values`` (an integer or boolean dtype) makes the bridge publish
    integer items, so a non-integral value is refused before any native call.
    """

    def __init__(self, low: list[float], high: list[float], shape: tuple[int, ...], dtype: Any):
        self.low, self.high, self.shape, self.dtype = low, high, shape, dtype
        self.mhs_integer_values = _integer_dtype(dtype)


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete`` built from a ``DiscreteArray`` spec."""

    def __init__(self, n: int):
        self.n, self.start, self.shape, self.dtype = int(n), 0, (), "int64"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict`` built from a mapping of specs."""

    def __init__(self, spaces: dict[str, Any]):
        self.spaces = spaces


def _integer_dtype(dtype: Any) -> bool:
    """True for an integer or boolean dtype (NumPy's kinds i, u, b; or their names without NumPy)."""
    if dtype is None:
        return False
    try:
        numpy = importlib.import_module("numpy")
        return numpy.dtype(dtype).kind in "iub"
    except ImportError:  # pragma: no cover - the validation environment has NumPy
        name = str(getattr(dtype, "name", dtype)).lower()
        return name.startswith(("int", "uint", "bool"))
    except TypeError:
        return False


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


def _shape(spec: Any) -> tuple[int, ...]:
    shape = getattr(spec, "shape", None)
    if shape is None:
        raise DmEnvError(f"spec {getattr(spec, 'name', '?')!r} has no shape")
    out = tuple(int(item) for item in shape)
    if any(item < 0 for item in out):
        raise DmEnvError("spec shapes must be non-negative")
    return out


def _count(shape: tuple[int, ...]) -> int:
    count = 1
    for item in shape:
        count *= item
    return count


def _broadcast(values: Any, count: int, what: str) -> list[float]:
    flat = _flat(values)
    if len(flat) == 1:
        flat = flat * count
    if len(flat) != count:
        raise DmEnvError(f"spec {what} has {len(flat)} values for {count} elements")
    if any(math.isnan(value) for value in flat):
        raise DmEnvError(f"spec {what} contains NaN")
    return flat


def space_from_spec(spec: Any, depth: int = 0) -> Any:
    """A duck-typed Gymnasium space for a dm_env spec (or a mapping of specs)."""
    if depth > _MAX_SPEC_DEPTH:
        raise DmEnvError("spec nesting is too deep")
    if isinstance(spec, Mapping):
        out = {}
        for key, sub in spec.items():
            if not isinstance(key, str):
                raise DmEnvError("spec mapping keys must be strings")
            out[key] = space_from_spec(sub, depth + 1)
        return Dict(out)
    if hasattr(spec, "num_values"):
        shape = _shape(spec)
        if shape not in ((), (1,)):
            raise DmEnvError("only scalar DiscreteArray specs are supported")
        return Discrete(int(spec.num_values))
    shape = _shape(spec)
    count = _count(shape)
    if hasattr(spec, "minimum") and hasattr(spec, "maximum"):
        low = _broadcast(spec.minimum, count, "minimum")
        high = _broadcast(spec.maximum, count, "maximum")
        if any(lo > hi for lo, hi in zip(low, high)):
            raise DmEnvError("spec minimum exceeds maximum")
    else:
        low, high = [-math.inf] * count, [math.inf] * count
    return Box(low, high, shape, getattr(spec, "dtype", None))


def _step_type(timestep: Any) -> int:
    if not is_timestep_like(timestep):
        raise DmEnvError(f"dm_env returned {type(timestep).__name__}, not a TimeStep")
    raw = timestep.step_type
    if isinstance(raw, (bool, float, str, bytes)):
        raise DmEnvError(f"TimeStep.step_type must be an integer StepType, not {type(raw).__name__}")
    try:
        # int, IntEnum (dm_env.StepType) or a NumPy integer; operator.index never truncates a float or parses text.
        value = operator.index(raw)
    except TypeError as exc:
        raise DmEnvError(f"TimeStep.step_type must be an integer StepType, not {type(raw).__name__}") from exc
    if value not in _NAMES:
        raise DmEnvError("TimeStep.step_type is not FIRST, MID or LAST")
    return value


def _scalar(value: Any, what: str) -> float:
    item = getattr(value, "item", None)
    if callable(item) and getattr(value, "shape", ()) in ((), (1,)):
        value = item()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DmEnvError(f"{what} must be a scalar number")
    value = float(value)
    if not math.isfinite(value):
        raise DmEnvError(f"{what} is not finite")
    return value


class DmEnvAdapter:
    """A Gymnasium-shaped view of one dm_env environment (see the module docstring).

    ``unwrapped`` is the dm_env environment itself, so the bridge's attribute
    lookups (``dt``, timing attributes) reach it.
    """

    def __init__(self, env: Any, profile: DmEnvProfile | None = None):
        self._env = env
        self.profile = profile or DmEnvProfile()
        self._action_spec = env.action_spec()
        self.action_space = space_from_spec(self._action_spec)
        self.observation_space = space_from_spec(env.observation_spec())
        self.last_step_type: str | None = None

    @property
    def unwrapped(self) -> Any:
        return self._env

    @property
    def dt(self) -> Any:
        control_timestep = getattr(self._env, "control_timestep", None)
        if callable(control_timestep):
            return control_timestep()
        return None

    def reset(self) -> tuple[Any, dict[str, Any]]:
        timestep = self._env.reset()
        kind = _step_type(timestep)
        if kind != _FIRST:
            raise DmEnvError(f"dm_env reset() returned a {_NAMES[kind]} step, expected FIRST")
        self.last_step_type = "FIRST"
        return timestep.observation, {"dm_env": {"step_type": "FIRST"}}

    def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        if self.last_step_type is None or self.last_step_type == "LAST":
            raise DmEnvError("dm_env step() needs a reset first; the adapter never steps past LAST")
        native = self._native_action(action)
        timestep = self._env.step(native)
        kind = _step_type(timestep)
        if kind == _FIRST:
            raise DmEnvError("dm_env step() returned FIRST (the environment restarted on its own)")
        reward = _scalar(timestep.reward, "TimeStep.reward") if timestep.reward is not None else None
        if reward is None:
            raise DmEnvError(f"TimeStep.reward is None on a {_NAMES[kind]} step")
        discount = timestep.discount
        terminated = truncated = False
        info: dict[str, Any] = {"step_type": _NAMES[kind]}
        if kind == _LAST:
            if discount is None:
                raise DmEnvError("TimeStep.discount is None on a LAST step")
            value = _scalar(discount, "TimeStep.discount")
            if not 0.0 <= value <= 1.0:
                raise DmEnvError("TimeStep.discount is outside [0, 1]")
            terminated, truncated = value == 0.0, value > 0.0
            info["discount"] = value
        elif discount is not None:
            info["discount"] = _scalar(discount, "TimeStep.discount")
        self.last_step_type = _NAMES[kind]
        return timestep.observation, reward, terminated, truncated, {"dm_env": info}

    def _native_action(self, action: Any) -> Any:
        spec = self._action_spec
        if isinstance(spec, Mapping):
            raise DmEnvError("nested action specs are not supported by dm_env_v1")
        dtype = getattr(spec, "dtype", None)
        value = action
        if _integer_dtype(dtype):
            # Never truncate: the envelope was checked on the value the caller sent.
            for item in _flat(action):
                if not math.isfinite(item) or not float(item).is_integer():
                    refused = make_mhs_error("MHS.CAPABILITY.INPUT_INVALID",
                                             f"the action spec has an integer dtype ({dtype}); {item!r} is not "
                                             "an integer and is never truncated", {"retryable": False})
                    refused.mhs_bridge_outcome = True
                    raise refused
        try:
            numpy = importlib.import_module("numpy")
        except ImportError:  # pragma: no cover - the validation environment has NumPy
            numpy = None
        if numpy is not None and dtype is not None:
            value = numpy.asarray(action, dtype=dtype).reshape(_shape(spec))
        validate = getattr(spec, "validate", None)
        if callable(validate):
            validate(value)
        return value

    def close(self) -> None:
        close = getattr(self._env, "close", None)
        if callable(close):
            close()
