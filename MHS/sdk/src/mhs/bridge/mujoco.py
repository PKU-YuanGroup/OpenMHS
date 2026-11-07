"""MuJoCo bridge family (MHS-000 section 9.3), aligned with the ``cap.world.*`` classes.

Maps a MuJoCo model/data pair onto:

* ``cap.world.step.v1``  -- input ``{ticks, action: {ctrl: [nu numbers]}}``:
  ``ctrl`` is checked against ``model.actuator_ctrlrange`` (the limits are
  generated from the model, per actuator) *before* ``data.ctrl`` is written,
  then ``mj_step`` runs ``ticks`` times; output ``{observation, tick,
  state_hash}`` with ``observation = {time, qpos, qvel}``.  An actuator the
  model gives no control range (MuJoCo then leaves its control unclamped) is
  never published as unbounded: its limit is ``operator_required``, so the
  endpoint refuses every step that sets it (``MHS.SAFETY.LIMITS_UNSET``)
  until the operator's ``site-limits.json`` bounds it (see
  :meth:`MujocoBridge.action_limits`);
* ``cap.world.reset.v1`` -- ``mj_resetData`` + ``mj_forward``; output
  ``{observation, seed}``.

Snapshots contain the declared world state and a bounded native checkpoint.
The integration profile preserves ``mjSTATE_INTEGRATION`` inputs, including
warm-start, without a forward pass during restore. It does not certify external
callback, plugin or RNG completeness. Engines without the complete state API
use an explicit basic profile for time/qpos/qvel/act/ctrl, not exact physics. The
time step is read from ``model.opt.timestep`` (also for a ``prebuilt=``
model/data pair), and ``mujoco`` is imported lazily on first use; inject a
module with ``mujoco=`` (tests use a fake).  ``n_steps`` is accepted as a
deprecated alias of ``ticks``.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
import importlib
import json
import math
import sys
import warnings
from pathlib import Path
from typing import Any, Mapping, Sequence

from mhs import canonical, signals
from mhs import limits as _limits
from mhs.bridge.base import Bridge, BridgeContext, make_mhs_error, unsupported
from mhs.bridge.base import main as _bridge_main

__all__ = ["MujocoBridge", "main"]

_FLOAT_MAX = sys.float_info.max
#: Reason of a bound the model's ``actuator_ctrlrange`` states.
_RANGE_REASON = "actuator ctrlrange of the model"
#: Reason of an ``operator_required`` control (the model states no range for it).
_UNRANGED_REASON = ("the model gives {what} no control range (ctrllimited false or no ctrlrange), so MuJoCo "
                    "leaves the control unclamped; site-limits.json must bound {path} before a step can set it")


def _floats(values: Any) -> list[float]:
    return [float(value) for value in values]


def _declared_bounds(rules: Sequence[Any], index: int) -> tuple[float | None, float | None]:
    """The tightest ``(min, max)`` the declared ``rules`` give control ``index`` (``None``: no rule bounds that side).

    A rule is a limit rule's JSON form (or ``"operator_required"``, which
    bounds nothing): scalar or per-element ``min``/``max``, and an
    ``allowed`` set, which bounds both sides by its smallest and largest
    number.  The engine enforces every rule, so the tightest values hold.
    """

    lows: list[float] = []
    highs: list[float] = []
    for rule in rules:
        if not isinstance(rule, Mapping):
            continue
        for kind, found in (("min", lows), ("max", highs)):
            value = rule.get(kind)
            if isinstance(value, (list, tuple)):
                value = value[index] if index < len(value) else None
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                found.append(float(value))
        allowed = rule.get("allowed")
        numbers = [float(item) for item in allowed if isinstance(item, (int, float)) and not isinstance(item, bool)
                   and math.isfinite(float(item))] if isinstance(allowed, (list, tuple)) else []
        if numbers:
            lows.append(min(numbers))
            highs.append(max(numbers))
    return (max(lows) if lows else None), (min(highs) if highs else None)


class MujocoBridge(Bridge):
    """Bridge a MuJoCo model onto the ``cap.world.*`` classes."""

    bridge_kind = "mujoco"
    bridge_id = "mhs.bridge.mujoco"

    def __init__(
        self,
        *,
        model_path: str | None = None,
        model_xml: str | None = None,
        model_name: str | None = None,
        prebuilt: Any = None,
        device_id: str | None = None,
        seed: int = 0,
        mujoco: Any = None,
        max_ticks: int = 10_000,
    ):
        super().__init__(device_id=device_id)
        # The name a manifest shows: model_name, else the file name (an absolute path names the host, not the model).
        self._model_name = model_name or (Path(model_path).name if model_path else None)
        self.bridge_id = f"mhs.bridge.mujoco:{self._model_name or 'xml'}"
        self._model_path = model_path
        self._model_xml = model_xml
        self._prebuilt = prebuilt
        self._seed = int(seed)
        self._mujoco: Any = mujoco
        self._model: Any = None
        self._data: Any = None
        self._ticks = 0
        self._timestep_s: float | None = None
        self._max_ticks = int(max_ticks)
        self._step_limits: _limits.EffectiveLimits | None = None
        self._checkpoint_identity: dict[str, Any] | None = None
        self._checkpoint_fault: str | None = None
        self._restore_depth = 0
        self._restore_stop_changed: Any = None
        self._restore_epoch = 0

    # -- availability ------------------------------------------------------
    @staticmethod
    def available() -> bool:
        try:
            importlib.import_module("mujoco")
            return True
        except ImportError:
            return False

    def _mj(self) -> Any:
        """The mujoco module: the injected one, else a lazy import."""

        if self._mujoco is None:
            try:
                self._mujoco = importlib.import_module("mujoco")
            except ImportError as exc:
                raise make_mhs_error(
                    "MHS.DEVICE.NOT_READY",
                    "mujoco is not installed; the MuJoCo bridge cannot step the model",
                    {
                        "retryable": False,
                        "remediation": "pip install mujoco in the endpoint's environment, or inject mujoco=.",
                    },
                ) from exc
        return self._mujoco

    def _ensure_loaded(self) -> tuple[Any, Any]:
        self.ensure_open()
        if self._data is not None:
            return self._model, self._data
        if self._prebuilt is not None:
            model, data = self._prebuilt
        else:
            mujoco = self._mj()
            try:
                if self._model_path:
                    model = mujoco.MjModel.from_xml_path(self._model_path)
                elif self._model_xml:
                    model = mujoco.MjModel.from_xml_string(self._model_xml)
                else:
                    raise make_mhs_error("MHS.DEVICE.NOT_READY", "mujoco bridge needs model_path or model_xml",
                                         {"retryable": False})
                data = mujoco.MjData(model)
                mujoco.mj_resetData(model, data)
                mujoco.mj_forward(model, data)
            except Exception as exc:  # noqa: BLE001
                if getattr(exc, "code", None):
                    raise
                raise make_mhs_error("MHS.DEVICE.NOT_READY", f"MuJoCo model load failed ({type(exc).__name__})",
                                     {"retryable": False}) from exc
        self._model, self._data = model, data
        opt = getattr(model, "opt", None)
        timestep = getattr(opt, "timestep", None)
        self._timestep_s = float(timestep) if timestep is not None else None
        return model, data

    # -- actuator limits ---------------------------------------------------
    def _nu(self) -> int:
        model, data = self._ensure_loaded()
        nu = getattr(model, "nu", None)
        return int(nu) if nu is not None else len(data.ctrl)

    def ctrl_ranges(self) -> list[tuple[float, float] | None]:
        """Per actuator, the finite ``(min, max)`` control range the model states, or ``None`` when it states none.

        A range counts when ``actuator_ctrllimited`` marks the actuator limited
        (a model without that array: when ``min < max``) and both ends are
        finite with ``min <= max``.  MuJoCo clamps such a control; it leaves
        every other control unclamped, so ``None`` never means "any value".
        """

        model, _data = self._ensure_loaded()
        nu = self._nu()
        ranges = getattr(model, "actuator_ctrlrange", None)
        limited = getattr(model, "actuator_ctrllimited", None)
        out: list[tuple[float, float] | None] = []
        for index in range(nu):
            span: tuple[float, float] | None = None
            if ranges is not None:
                pair = ranges[index]
                lo, hi = float(pair[0]), float(pair[1])
                is_limited = bool(limited[index]) if limited is not None else lo < hi
                if is_limited and lo <= hi and math.isfinite(lo) and math.isfinite(hi):
                    span = (lo, hi)
            out.append(span)
        return out

    def ctrl_limits(self) -> tuple[list[float], list[float]]:
        """Legacy per-actuator ``(min, max)`` lists of :meth:`ctrl_ranges`.

        An actuator without a control range shows ``-/+sys.float_info.max``
        here.  That is a placeholder, not a bound: :meth:`action_limits` never
        publishes it (such a control is ``operator_required``).
        """

        lows: list[float] = []
        highs: list[float] = []
        for span in self.ctrl_ranges():
            low, high = span if span is not None else (-_FLOAT_MAX, _FLOAT_MAX)
            lows.append(low)
            highs.append(high)
        return lows, highs

    def _model_ref(self) -> str:
        return f"{self._model_name or 'model'}:actuator_ctrlrange"

    def action_limits(self) -> dict[str, Any]:
        """The ``action.ctrl`` limits: the model's control ranges, ``operator_required`` where it states none.

        * every actuator has a range: one per-element rule on ``action.ctrl``
          (``upstream_code``, ``ref`` ``<model>:actuator_ctrlrange``);
        * no actuator has one: ``action.ctrl`` is ``operator_required`` (one
          group: the operator's overlay bounds the whole vector, a scalar or
          one value per element);
        * some have one: one rule per element, ``action.ctrl[N]`` -- the
          model's range where it states one, ``operator_required`` where it
          does not (a per-element ``min``/``max`` list cannot leave an element
          out, and a placeholder number would be a bound nobody stated).

        The endpoint refuses a step that sets an ``operator_required`` control
        with ``MHS.SAFETY.LIMITS_UNSET`` before any native call, until the
        operator's ``site-limits.json`` supplies the bound; a step without
        ``action`` keeps the controls as they are.  :meth:`action_limit_reasons`
        says why each such path has no bound.
        """

        spans = self.ctrl_ranges()
        if not spans:
            return {}
        if all(span is not None for span in spans):
            return {"action.ctrl": {"min": [span[0] for span in spans], "max": [span[1] for span in spans],
                                    "source": "upstream_code", "ref": self._model_ref(), "reason": _RANGE_REASON}}
        if all(span is None for span in spans):
            return {"action.ctrl": _limits.OPERATOR_REQUIRED}
        out: dict[str, Any] = {}
        for index, span in enumerate(spans):
            out[f"action.ctrl[{index}]"] = _limits.OPERATOR_REQUIRED if span is None else {
                "min": span[0], "max": span[1], "source": "upstream_code", "ref": self._model_ref(),
                "reason": _RANGE_REASON}
        return out

    def action_limit_reasons(self) -> dict[str, str]:
        """``{limit path: reason}`` of every ``operator_required`` path of :meth:`action_limits`."""

        spans = self.ctrl_ranges()
        if not spans or all(span is not None for span in spans):
            return {}
        if all(span is None for span in spans):
            return {"action.ctrl": _UNRANGED_REASON.format(what="none of its actuators", path="action.ctrl")}
        return {f"action.ctrl[{index}]": _UNRANGED_REASON.format(what=f"actuator {index}",
                                                                 path=f"action.ctrl[{index}]")
                for index, span in enumerate(spans) if span is None}

    def derive_step_limits(self, declared: Mapping[str, Any] | None = None
                           ) -> tuple[dict[str, Any], dict[str, str], list[str]]:
        """``(limits, reasons, problems)`` of ``cap.world.step.v1`` next to the rules a driver declares itself.

        Without a declared rule on ``action.ctrl`` (the whole vector, ``[*]``
        or one element ``[N]``) this is :meth:`action_limits` and
        :meth:`action_limit_reasons`.  A declared rule takes precedence:
        the bridge derives only the paths no declared rule covers.  A control
        is covered when the declared rules bound it on both sides (or declare
        it ``operator_required``); every other control keeps the model's
        range, or is ``operator_required`` when the model states none (fail
        closed).  A declared rule may only narrow a model range.  These are
        problems (the driver does not resolve): a bound outside the model's
        range, ``operator_required`` on an element the model ranges or on the
        whole vector of a model that ranges every actuator, and a one-sided
        element rule whose other side has no free path to derive.
        """

        whole, elements, problems = self._declared_ctrl(declared)
        if whole is None and not elements:
            return self.action_limits(), self.action_limit_reasons(), problems
        spans = self.ctrl_ranges()
        for index in sorted(elements):
            if index >= len(spans):
                problems.append(f"action.ctrl[{index}] is declared, but the model has {len(spans)} actuators")
        limits: dict[str, Any] = {}
        reasons: dict[str, str] = {}
        required = _limits.OPERATOR_REQUIRED
        if whole == required and spans and all(span is not None for span in spans):
            # As for one ranged element: the model states every bound, so deferring the vector to the operator says
            # nothing true (with some actuators unranged it defers those as one group and the ranges stay below).
            problems.append("action.ctrl: every actuator has the model's ctrlrange; Limit.operator_required on the "
                            "whole vector would defer bounds the model states (declare a Limit inside them, or none)")
        # Every actuator ranged and no declared whole-vector rule: the model's ranges stay one rule on action.ctrl,
        # next to the declared element rules (which may only narrow them).
        ranged_whole = whole is None and all(span is not None for span in spans)
        if ranged_whole:
            limits.update(self.action_limits())
        for index, span in enumerate(spans):
            path = f"action.ctrl[{index}]"
            element = elements.get(index)
            low, high = _declared_bounds((whole, element), index)
            if span is not None:
                lo, hi = span
                if element == required:
                    problems.append(f"{path}: actuator {index} has the model's ctrlrange {lo:g}..{hi:g}; "
                                    "Limit.operator_required there would drop it (declare a bound inside it, or none)")
                    continue
                if (low is not None and low < lo) or (high is not None and high > hi):
                    problems.append(f"action.ctrl (element {index}): the declared bound "
                                    f"{'-inf' if low is None else f'{low:g}'}..{'inf' if high is None else f'{high:g}'}"
                                    f" widens the model's ctrlrange {lo:g}..{hi:g}; a declared rule may only narrow it")
                    continue
                if ranged_whole or (low is not None and high is not None):
                    continue  # the model's whole-vector rule, or the declared bounds inside the range, cover it
                if element is not None:
                    problems.append(f"{path}: declare both min and max inside the model's ctrlrange {lo:g}..{hi:g} "
                                    "(the model's other side has no free path to stay on)")
                    continue
                limits[path] = {"min": lo, "max": hi, "source": "upstream_code", "ref": self._model_ref(),
                                "reason": _RANGE_REASON}
                continue
            if required in (whole, element) or (low is not None and high is not None):
                continue  # the declared rules bound it, or defer it to the operator themselves
            if element is not None:
                problems.append(f"{path}: the model gives actuator {index} no control range; declare both min and "
                                "max, or Limit.operator_required")
                continue
            limits[path] = required
            reasons[path] = _UNRANGED_REASON.format(what=f"actuator {index}", path=path)
        return limits, reasons, problems

    @staticmethod
    def _declared_ctrl(declared: Mapping[str, Any] | None) -> tuple[Any, dict[int, Any], list[str]]:
        """``(whole-vector rule, {element index: rule}, problems)`` of the declared rules on ``action.ctrl``."""

        whole: Any = None
        elements: dict[int, Any] = {}
        problems: list[str] = []
        for path, rule in (declared or {}).items():
            try:
                tokens = _limits.parse_path(str(path))
            except _limits.LimitConfigError:
                continue  # not a limit path: the model's own resolution reports it
            if tuple(tokens[:2]) != ("action", "ctrl"):
                continue
            rest = tokens[2:]
            if not rest or (len(rest) == 1 and rest[0] is _limits.WILDCARD):
                if whole is not None:
                    problems.append("action.ctrl: two declared rules for the whole control vector")
                whole = rule
            elif len(rest) == 1 and isinstance(rest[0], int):
                elements[rest[0]] = rule
        return whole, elements, problems

    def step_input_schema(self) -> dict[str, Any]:
        nu = self._nu()
        return {
            "type": "object",
            "properties": {
                "ticks": {"type": "integer", "minimum": 1, "maximum": self._max_ticks},
                "action": {
                    "type": "object",
                    "properties": {
                        "ctrl": {"type": "array", "items": {"type": "number"}, "minItems": nu, "maxItems": nu},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }

    def _compiled_step_limits(self) -> _limits.EffectiveLimits:
        if self._step_limits is None:
            self._step_limits = _limits.compile_limits(
                self.step_input_schema(), [_limits.LimitSource("bridge.actuator_ctrlrange", self.action_limits())]
            )
        return self._step_limits

    def _check_step_input(self, args: Mapping[str, Any]) -> None:
        from mhs.schema import validate  # local: the schema validator is only needed here

        effective = self._compiled_step_limits()
        schema = self.step_input_schema()
        problems = validate(dict(args), _limits.strip_bound_keywords(effective, schema))
        if problems:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "step input does not match the model",
                                 {"retryable": False, "details": {"errors": problems[:20]}})
        violations = _limits.check(dict(args), effective)
        if violations:
            first = violations[0]
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                f"{first.message()} (actuator ctrlrange); nothing was actuated",
                {"retryable": False, "details": first.to_details(),
                 "violations": [item.to_details() for item in violations[:20]]},
            )
        # A control without a model range has no rule above; the endpoint holds its
        # operator bound.  Whoever calls the bridge, MuJoCo never receives a value
        # that is not a finite double (it would integrate it into a non-finite state).
        action = args.get("action")
        ctrl = action.get("ctrl") if isinstance(action, Mapping) else None
        if isinstance(ctrl, (list, tuple)):
            for index, value in enumerate(ctrl):
                try:
                    finite = math.isfinite(float(value))
                except (TypeError, ValueError, OverflowError):
                    finite = False
                if not finite or isinstance(value, bool):
                    raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID",
                                         f"action.ctrl[{index}] is not a finite number; nothing was actuated",
                                         {"retryable": False, "details": {"path": f"action.ctrl[{index}]"}})
        problems = validate(dict(args), schema)
        if problems:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "step input does not match the model",
                                 {"retryable": False, "details": {"errors": problems[:20]}})

    # -- adapter surface ---------------------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        try:
            extra: dict[str, Any] = {"input_schema": self.step_input_schema(), "limits": self.action_limits()}
        except Exception:  # noqa: BLE001 - the model cannot load here: no derived contract
            extra = {}
        # A state API does not establish callback, plugin or RNG determinism.
        determinism = "none"
        return [
            {
                "capability_id": "cap.world.step.v1",
                "resource": "world",
                "native": "mujoco.mj_step(model, data)",
                "description": "Write data.ctrl (checked against actuator_ctrlrange) and integrate `ticks` steps.",
                "determinism": determinism,
                **extra,
            },
            {
                "capability_id": "cap.world.reset.v1",
                "resource": "world",
                "native": "mujoco.mj_resetData(model, data)",
                "description": "Reset the simulation data to the model defaults.",
                "determinism": determinism,
            },
        ]

    def resources(self) -> list[dict[str, Any]]:
        return [{"resource_id": "world", "kind": "world.sim"}]

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        if resource_id != "world":
            raise unsupported(resource_id, kind="resource")
        state = self.world_state()
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def observation(self) -> dict[str, Any]:
        with self._lock:
            _model, data = self._ensure_loaded()
            return {"time": float(data.time), "qpos": _floats(data.qpos), "qvel": _floats(data.qvel)}

    def world_state(self) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            raise signals.Busy("MuJoCo state is being changed or captured")
        try:
            return self._capture_world()
        finally:
            self._lock.release()

    def _capture_world(self) -> dict[str, Any]:
        _model, data = self._ensure_loaded()
        world = {
            "time_ms": int(round(float(data.time) * 1000.0)),
            "qpos": _floats(data.qpos),
            "qvel": _floats(data.qvel),
            "ctrl": _floats(getattr(data, "ctrl", [])),
            "tick": self._ticks,
            "timestep_ms": None if self._timestep_s is None else round(self._timestep_s * 1000.0, 9),
            "seed": self._seed,
        }
        identity = self._identity()
        if self.snapshot_exact:
            state = self._buffer(identity["state_size"])
            self._mj().mj_getState(_model, data, state, self._mj().mjtState.mjSTATE_INTEGRATION)
            native = {"values": _floats(state)}
        else:
            native = {"time": float(data.time), "act": _floats(getattr(data, "act", []))}
        world["native_checkpoint"] = {**identity, **native}
        self._validate_world(world)
        return world

    def _state_hash(self) -> str:
        return canonical.state_hash(self.world_state())

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        epoch = self.estop_epoch
        model, data = self._ensure_loaded()
        args = dict(args or {})
        context = BridgeContext.coerce(ctx)
        if context.cancelled():
            raise signals.Cancelled("cancelled before the mujoco call")
        if capability_id == "cap.world.step.v1":
            return self._step(args, context, epoch)
        if capability_id == "cap.world.reset.v1":
            mujoco = self._mj()
            with self._lock:
                self._admit(context, epoch)
                mujoco.mj_resetData(model, data)
                mujoco.mj_forward(model, data)
                self._ticks = 0
                return {"observation": self.observation(), "seed": self._seed}
        if capability_id == "cap.world.state.v1":   # deprecated duplicate of mhs.resource.read
            state = self.world_state()
            return {"state": state, "state_hash": canonical.digest(state), "revision": int(context.revision or 0)}
        if capability_id == "cap.world.snapshot.v1":   # deprecated duplicate of mhs.snapshot
            snapshot = self.snapshot()
            return {"snapshot": snapshot, "snapshot_digest": canonical.digest(snapshot),
                    "revision": int(context.revision or 0)}
        if capability_id == "cap.world.restore.v1":   # deprecated duplicate of mhs.restore
            snapshot = args.get("snapshot")
            if not isinstance(snapshot, Mapping):
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "snapshot must be an object",
                                     {"retryable": False})
            self.restore(snapshot)
            return {"revision": int(context.revision or 0), "state_hash": self._state_hash()}
        raise unsupported(capability_id)

    def _step(self, args: dict[str, Any], context: BridgeContext, epoch: int) -> dict[str, Any]:
        if "n_steps" in args:
            warnings.warn("'n_steps' is deprecated; use the class input 'ticks'", DeprecationWarning, stacklevel=3)
            if "ticks" in args:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "give 'ticks' or the legacy 'n_steps', not both",
                                     {"retryable": False})
            args["ticks"] = args.pop("n_steps")
        args.setdefault("ticks", 1)
        self._check_step_input(args)
        ticks = int(args["ticks"])
        ctrl = (args.get("action") or {}).get("ctrl")
        model, data = self._ensure_loaded()
        mujoco = self._mj()
        with self._lock:
            self._admit(context, epoch)
            if ctrl is not None:
                for index, value in enumerate(ctrl):
                    data.ctrl[index] = float(value)
            for _ in range(ticks):
                if context.cancelled():
                    raise signals.Cancelled("cancelled between simulation steps")
                self._refuse_if_estopped(epoch, "MuJoCo step")
                mujoco.mj_step(model, data)
                self._ticks += 1
            return {"observation": self.observation(), "tick": self._ticks, "state_hash": self._state_hash()}

    def _admit(self, context: BridgeContext, epoch: int) -> None:
        self.ensure_open()
        if self._checkpoint_fault:
            raise make_mhs_error("MHS.OUTCOME.UNKNOWN", self._checkpoint_fault, {"retryable": False})
        self._refuse_if_estopped(epoch, "MuJoCo mutation")
        if context.cancelled() or context.remaining_ms() == 0:
            raise signals.Cancelled("MuJoCo mutation expired before native dispatch")

    def reset(self, ctx: Any = None) -> Any:
        if self._checkpoint_fault:
            raise make_mhs_error("MHS.SAFETY.RESET_REFUSED", self._checkpoint_fault, {"retryable": False})
        if not self._lock.acquire(blocking=False):
            raise make_mhs_error("MHS.SAFETY.RESET_REFUSED", "MuJoCo native work has not settled",
                                 {"retryable": False})
        self._lock.release()
        return {}

    def safety_status(self) -> dict[str, Any]:
        settled = self._lock.acquire(blocking=False)
        if settled:
            self._lock.release()
        return {"safe_state": {"achieved": settled and self._checkpoint_fault is None}}

    def settle_native_work(self, timeout_s: float) -> bool:
        """Wait at most ``timeout_s`` for an in-flight native step, reset or restore to end (e-stop attempts).

        The lock is taken only to observe that it is free and released at once;
        nothing is cancelled. Returns True when nothing native is in flight.
        """
        if not self._lock.acquire(timeout=max(0.0, float(timeout_s))):
            return False
        self._lock.release()
        return True

    # -- snapshot / restore ------------------------------------------------
    @property
    def snapshot_exact(self) -> bool:
        """Full integration-state codec availability, not a determinism guarantee."""

        try:
            mujoco = self._mj()
        except Exception:  # noqa: BLE001
            return False
        return all(callable(getattr(mujoco, name, None)) for name in ("mj_getState", "mj_setState", "mj_stateSize")) \
            and all(hasattr(getattr(mujoco, "mjtState", None), name) for name in
                    ("mjSTATE_INTEGRATION", "mjSTATE_TIME", "mjSTATE_QPOS", "mjSTATE_QVEL", "mjSTATE_CTRL"))

    @staticmethod
    def _buffer(size: int) -> Any:
        try:
            numpy = importlib.import_module("numpy")
        except ImportError:
            return [0.0] * size
        return numpy.zeros(size, dtype=numpy.float64)

    @staticmethod
    def _array(values: Sequence[float]) -> Any:
        try:
            numpy = importlib.import_module("numpy")
        except ImportError:
            return list(values)
        return numpy.asarray(values, dtype=numpy.float64)

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            return {"world": self._capture_world()}

    def _identity(self) -> dict[str, Any]:
        model, data = self._ensure_loaded()
        full = self.snapshot_exact
        signature = int(self._mj().mjtState.mjSTATE_INTEGRATION) if full else 0
        dimensions = [len(data.qpos), len(data.qvel), len(getattr(data, "act", [])), len(data.ctrl)]
        size = int(self._mj().mj_stateSize(model, signature)) if full else 1 + sum(dimensions)
        if not 1 <= size <= 32768:
            raise make_mhs_error("MHS.MODE.SNAPSHOT_UNSUPPORTED", "MuJoCo checkpoint exceeds 32768 values",
                                 {"retryable": False})
        version = getattr(self._mj(), "__version__", "unversioned")
        if type(version) is not str or len(version) > 100 or any(0xD800 <= ord(c) <= 0xDFFF for c in version):
            raise make_mhs_error("MHS.MODE.SNAPSHOT_UNSUPPORTED", "invalid MuJoCo engine version identity",
                                 {"retryable": False})
        identity = {
            "profile": "mujoco_integration_v1" if full else "mujoco_basic_v1",
            "engine_version": version,
            "signature": signature, "state_size": size, "dimensions": dimensions,
        }
        # The bridge owns an immutable model/data configuration. This detects the
        # represented configuration changing; it is not a compiled-model hash.
        raw_timestep = getattr(getattr(model, "opt", None), "timestep", None)
        timestep = float(raw_timestep) if raw_timestep is not None else None
        if timestep is not None and (not math.isfinite(timestep) or timestep <= 0):
            raise make_mhs_error("MHS.DEVICE.NOT_READY", "MuJoCo model has an invalid timestep",
                                 {"retryable": False})
        current = {**identity, "model_identity": id(model), "data_identity": id(data), "timestep": timestep}
        if self._checkpoint_identity is None:
            self._checkpoint_identity = current
        elif current != self._checkpoint_identity:
            raise make_mhs_error("MHS.CONFLICT.SNAPSHOT_MISMATCH", "MuJoCo model configuration changed",
                                 {"retryable": False})
        return identity

    @staticmethod
    def _numbers(value: Any, length: int, label: str) -> list[float]:
        if (type(value) is not list or len(value) != length
                or any(type(x) not in (int, float) or (type(x) is int and abs(x) > 2**53 - 1)
                       or not math.isfinite(x) for x in value)):
            raise ValueError(f"{label} must contain exactly {length} finite numbers")
        return value

    def _validate_world(self, world: Any) -> dict[str, Any]:
        identity = self._identity()
        model, data = self._ensure_loaded()
        try:
            keys = {"time_ms", "qpos", "qvel", "ctrl", "tick", "timestep_ms", "seed", "native_checkpoint"}
            if type(world) is not dict or set(world) != keys:
                raise ValueError("checkpoint must contain the complete declared world state")
            for name in ("time_ms", "tick", "seed"):
                if type(world[name]) is not int or not 0 <= world[name] <= 2**53 - 1:
                    raise ValueError(f"{name} must be a nonnegative exactly representable JSON integer")
            if world["seed"] != self._seed:
                raise ValueError("checkpoint seed must match configured metadata; MuJoCo reset has no seed control")
            raw_timestep = getattr(getattr(model, "opt", None), "timestep", None)
            timestep = round(float(raw_timestep) * 1000.0, 9) if raw_timestep is not None else None
            if (world["timestep_ms"] != timestep
                    or (timestep is not None and type(world["timestep_ms"]) not in (int, float))):
                raise ValueError("checkpoint timestep does not match the owned model")
            for name in ("qpos", "qvel", "ctrl"):
                self._numbers(world[name], len(getattr(data, name)), name)
            checkpoint = world["native_checkpoint"]
            members = {"values"} if self.snapshot_exact else {"time", "act"}
            if type(checkpoint) is not dict or set(checkpoint) != set(identity) | members:
                raise ValueError("checkpoint profile has missing or unknown fields")
            for name, value in identity.items():
                if type(checkpoint[name]) is not type(value) or checkpoint[name] != value:
                    raise ValueError(f"checkpoint {name} does not match the owned model")
            if any(type(x) is not int for x in checkpoint["dimensions"]):
                raise ValueError("checkpoint dimensions must be integers")
            if self.snapshot_exact:
                values = self._numbers(checkpoint["values"], identity["state_size"], "integration state")
                mj = self._mj()
                # mj_setState converts equality activation entries from mjtNum
                # to mjtByte. Only documented boolean activation values belong
                # to this profile; reject before any native setter dispatch.
                eq_bit = getattr(mj.mjtState, "mjSTATE_EQ_ACTIVE", None)
                if eq_bit is not None:
                    eq_bit = int(eq_bit)
                    if eq_bit <= 0 or eq_bit & (eq_bit - 1):
                        raise ValueError("invalid equality activation signature")
                    if identity["signature"] & eq_bit:
                        eq_offset = int(mj.mj_stateSize(model, identity["signature"] & (eq_bit - 1)))
                        eq_count = int(mj.mj_stateSize(model, eq_bit))
                        if (eq_offset < 0 or eq_count < 0 or eq_offset + eq_count > len(values)
                                or any(value not in (0, 1) for value in values[eq_offset:eq_offset + eq_count])):
                            raise ValueError("equality activation state must contain only numeric 0 or 1")
                for public, native in (("qpos", "QPOS"), ("qvel", "QVEL"), ("ctrl", "CTRL"), ("time_ms", "TIME")):
                    bit = int(getattr(mj.mjtState, "mjSTATE_" + native))
                    if bit <= 0 or bit & (bit - 1) or not identity["signature"] & bit:
                        raise ValueError("invalid native component signature")
                    offset = int(mj.mj_stateSize(model, identity["signature"] & (bit - 1)))
                    count = int(mj.mj_stateSize(model, bit))
                    selected = values[offset:offset + count]
                    if public == "time_ms":
                        if len(selected) != 1 or selected[0] < 0 or int(round(selected[0] * 1000)) != world[public]:
                            raise ValueError("public time does not match integration state")
                    elif count != len(world[public]) or selected != world[public]:
                        raise ValueError(f"public {public} does not match integration state")
            else:
                stamp = checkpoint["time"]
                if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp < 0:
                    raise ValueError("native time must be finite and nonnegative")
                if int(round(stamp * 1000)) != world["time_ms"]:
                    raise ValueError("public time does not match basic state")
                self._numbers(checkpoint["act"], len(getattr(data, "act", [])), "act")
            encoded = json.dumps(world, allow_nan=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > 1_048_576:
                raise ValueError("checkpoint world exceeds 1 MiB")
            return json.loads(encoded)
        except (ValueError, TypeError, OverflowError, KeyError) as exc:
            raise make_mhs_error("MHS.CONFLICT.SNAPSHOT_MISMATCH", str(exc), {"retryable": False}) from exc

    def validate_restore(self, snapshot: Any) -> dict[str, Any]:
        with self._lock:
            if self._checkpoint_fault:
                raise make_mhs_error("MHS.OUTCOME.UNKNOWN", self._checkpoint_fault, {"retryable": False})
            if type(snapshot) is not dict or set(snapshot) != {"world"}:
                raise make_mhs_error("MHS.CONFLICT.SNAPSHOT_MISMATCH", "checkpoint must contain only world",
                                     {"retryable": False})
            return {"world": self._validate_world(snapshot["world"])}

    @contextmanager
    def restore_admission(self, stop_changed: Any = None):
        epoch = self.estop_epoch
        with self._lock:
            if self._restore_depth == 0:
                self._restore_epoch = epoch
                self._restore_stop_changed = stop_changed
            self._restore_depth += 1
            try:
                self._check_restore_admission()
                yield
            finally:
                self._restore_depth -= 1
                if self._restore_depth == 0:
                    self._restore_stop_changed = None

    def _check_restore_admission(self) -> None:
        self.ensure_open()
        self._refuse_if_estopped(self._restore_epoch, "MuJoCo restore")
        if self._restore_stop_changed is not None and self._restore_stop_changed():
            raise make_mhs_error("MHS.SAFETY.ESTOP_ENGAGED", "stop interrupted MuJoCo restore admission",
                                 {"retryable": False})
        if self._checkpoint_fault:
            raise make_mhs_error("MHS.OUTCOME.UNKNOWN", self._checkpoint_fault, {"retryable": False})

    def restore(self, snapshot: Any) -> dict[str, Any]:
        with self.restore_admission():
            model, data = self._ensure_loaded()
            world = self.validate_restore(snapshot)["world"]
            checkpoint = world["native_checkpoint"]
            if self.snapshot_exact:
                mujoco = self._mj()
                spec = mujoco.mjtState.mjSTATE_INTEGRATION
                setter = mujoco.mj_setState
                values = self._array(checkpoint["values"])
                self._check_restore_admission()
                completion = setter(model, data, values, spec)
                if completion is not None:
                    self._checkpoint_fault = "MuJoCo setter did not finish synchronously; replace this endpoint"
                    raise make_mhs_error("MHS.OUTCOME.UNKNOWN", self._checkpoint_fault,
                                         {"retryable": False, "details": {"may_have_effect": True}})
                # Forward can invoke callbacks and overwrite warm-start inputs.
                # The public fields read below require no derived-state refresh.
            else:
                self._check_restore_admission()
                data.qpos[:] = _floats(world["qpos"])
                data.qvel[:] = _floats(world["qvel"])
                data.ctrl[:] = _floats(world["ctrl"])
                if len(getattr(data, "act", [])):
                    data.act[:] = _floats(checkpoint["act"])
                data.time = float(checkpoint["time"])
            self._ticks = world["tick"]
            return self.snapshot()

    def describe(self) -> dict[str, Any]:
        described = super().describe()
        described.update(
            {
                "model_path": self._model_path,
                "loaded": self._data is not None,
                "mujoco_available": self.available(),
                "snapshot_exact": self.snapshot_exact,
                "timestep_ms": None if self._timestep_s is None else round(self._timestep_s * 1000.0, 9),
            }
        )
        return described


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
