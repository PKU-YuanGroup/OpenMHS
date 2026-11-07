"""Opt-in, fixed-decimation simulation timing and command-local receipt notes.

Configuration describes a source-reviewed backend contract; flags and citation
strings are not proof of native behavior. Runtime checks validate the observable
clock contract. No native code or wall-clock pacing is provided by this module.
"""
from __future__ import annotations

import copy
import math
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping

NAMESPACE = "openmhs_simulation_timing"
CONTEXT_KEY = "_mhs_simulation_timing"
_PATH = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*\Z")


class TimingError(ValueError):
    """A timing declaration or observed clock violates the opt-in contract."""


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimingError(f"{name} must be a positive finite number")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise TimingError(f"{name} must be a positive finite number")
    return value


def _attribute(getter: Callable[[str], Any], path: str) -> Any:
    parts = path.split(".")
    value = getter(parts[0])
    for part in parts[1:]:
        value = getattr(value, part)
    return value


#: Clock semantics of a reset that integrates physics: "restart" rewinds the clock to zero and then
#: integrates; "continue" integrates from the clock it found (the clock never rewinds).
RESET_CLOCKS = ("restart", "continue")
MAX_RESET_TICKS = 1_000_000


@dataclass(frozen=True)
class PhysicsTiming:
    decimation: int
    timestep_s: float
    timestep_attr: str
    clock_attr: str
    source_refs: tuple[str, ...] = ()
    #: None: reset must not integrate (the original contract). Otherwise RESET_CLOCKS member.
    reset_clock: str | None = None
    max_reset_ticks: int = 0

    @classmethod
    def resolve(cls, config: Mapping[str, Any], getter: Callable[[str], Any]) -> "PhysicsTiming":
        if not isinstance(config, Mapping):
            raise TimingError("timing must be a mapping")
        allowed = {"mode", "control_decimation", "physics_timestep_attr", "physics_clock_attr",
                   "native_autoreset", "reset_advances_physics", "reset_clock", "max_reset_ticks", "source_refs"}
        if set(config) - allowed or config.get("mode") != "physics_ticks_v1":
            raise TimingError("unsupported timing configuration or mode")
        d = config.get("control_decimation")
        if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 10000:
            raise TimingError("control_decimation must be an integer in 1..10000")
        if config.get("native_autoreset") is not False:
            raise TimingError("physics_ticks_v1 requires no native autoreset")
        integrates = config.get("reset_advances_physics")
        reset_clock, max_reset = None, 0
        if integrates is False:
            if "reset_clock" in config or "max_reset_ticks" in config:
                raise TimingError("reset_clock and max_reset_ticks apply only to resets that integrate physics")
        elif integrates is True:
            reset_clock, max_reset = config.get("reset_clock"), config.get("max_reset_ticks")
            if reset_clock not in RESET_CLOCKS:
                raise TimingError("a reset that integrates physics requires reset_clock 'restart' or 'continue'")
            if isinstance(max_reset, bool) or not isinstance(max_reset, int) or not 1 <= max_reset <= MAX_RESET_TICKS:
                raise TimingError(f"max_reset_ticks must be an integer in 1..{MAX_RESET_TICKS}")
        else:
            raise TimingError("reset_advances_physics must be a reviewed true or false")
        paths = [config.get("physics_timestep_attr"), config.get("physics_clock_attr")]
        if any(not isinstance(path, str) or len(path) > 200 or not _PATH.fullmatch(path) for path in paths):
            raise TimingError("timing attributes must be explicit ordinary attribute paths")
        refs = config.get("source_refs", ())
        if not isinstance(refs, (list, tuple)) or len(refs) > 20 or any(
                not isinstance(ref, str) or not ref or len(ref) > 500 for ref in refs):
            raise TimingError("source_refs must be bounded strings; citations do not validate the backend")
        p = _positive(_attribute(getter, paths[0]), "physics timestep")
        _positive(p * 1000.0 * d, "control period")
        _positive(p * 1000.0 * 10000, "maximum command duration")
        if reset_clock is not None:
            _positive(p * 1000.0 * max_reset, "maximum reset integration")
        result = cls(d, p, paths[0], paths[1], tuple(refs), reset_clock, max_reset)
        result.sample(getter)
        return result

    @property
    def reset_integrates(self) -> bool:
        return self.reset_clock is not None

    @property
    def timestep_ms(self) -> float:
        return self.timestep_s * 1000.0

    def check_timestep(self, getter: Callable[[str], Any]) -> None:
        if _positive(_attribute(getter, self.timestep_attr), "physics timestep") != self.timestep_s:
            raise TimingError("physics timestep changed; reopen and regenerate the manifest")

    def sample(self, getter: Callable[[str], Any]) -> float:
        self.check_timestep(getter)
        value = _attribute(getter, self.clock_attr)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TimingError("physics clock must be a finite non-negative number")
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise TimingError("physics clock must be a finite non-negative number")
        if math.ulp(value) * 8 >= self.timestep_s / 4:
            raise TimingError("physics clock precision cannot resolve a tick")
        return value

    def ticks_between(self, before: float, after: float) -> int:
        return self._grid_ticks(before, after, self.decimation, "one declared control period")

    def _grid_ticks(self, before: float, after: float, limit: int, what: str) -> int:
        delta = after - before
        ticks = round(delta / self.timestep_s)
        if delta < 0 or ticks < 0 or ticks > limit:
            raise TimingError(f"physics clock moved outside {what}")
        error_bound = self._addition_bound(before, after, ticks)
        if error_bound >= self.timestep_s / 4:
            raise TimingError("physics clock accumulation cannot resolve a tick")
        if abs(delta - ticks * self.timestep_s) > error_bound:
            raise TimingError("physics clock moved backwards or off its timestep grid")
        return ticks

    def reset_ticks(self, before: float | None, after: float) -> int:
        """Physics ticks a verified integrating reset advanced (0..max_reset_ticks).

        ``restart``: the clock was rewound to zero, so ``after`` alone counts the
        integration. ``continue``: the clock never rewinds; ``after - before``.
        """
        if self.reset_clock is None:
            raise TimingError("this timing declaration has no integrating reset")
        origin = 0.0 if self.reset_clock == "restart" else before
        if origin is None:
            raise TimingError("a continuing reset clock needs the clock sampled before the reset")
        return self._grid_ticks(origin, after, self.max_reset_ticks, "the declared reset integration bound")

    def check_reset_resolution(self, before: float | None) -> None:
        origin = 0.0 if self.reset_clock == "restart" or before is None else before
        after = origin + self.max_reset_ticks * self.timestep_s
        if (not math.isfinite(after)
                or self._addition_bound(origin, after, self.max_reset_ticks) >= self.timestep_s / 4):
            raise TimingError("physics clock cannot resolve the declared reset integration")

    def _addition_bound(self, before: float, after: float, ticks: int) -> float:
        # At most D positive additions, each rounded by <= half an ULP of
        # the largest endpoint. Account separately for subtraction/product
        # rounding; never derive an unbounded tolerance from a clock jump.
        additions = 0.5 * ticks * math.ulp(max(before, after))
        arithmetic = 4 * (math.ulp(before) + math.ulp(after) + math.ulp(after - before)
                          + math.ulp(ticks * self.timestep_s))
        return additions + arithmetic

    def check_step_resolution(self, before: float) -> None:
        after = before + self.decimation * self.timestep_s
        if (not math.isfinite(after)
                or self._addition_bound(before, after, self.decimation) >= self.timestep_s / 4):
            raise TimingError("physics clock cannot resolve the declared control period")

    def descriptor(self) -> dict[str, Any]:
        p, d = self.timestep_ms, self.decimation
        if self.reset_clock is None:
            reset_note = "Reset must return the clock to zero without integration; "
        else:
            rewinds = ("rewinds the clock to zero, then" if self.reset_clock == "restart"
                       else "keeps the clock running and")
            reset_note = (f"Reset {rewinds} may integrate up to {self.max_reset_ticks} physics ticks "
                          f"({self.max_reset_ticks * p:g} ms) of settling; the reset receipt reports the measured "
                          "reset ticks, which are not episode ticks; ")
        out = {"version": 1, "mode": "physics_ticks_v1", "tick_unit": "physics",
               "physics_timestep_ms": p, "control_decimation": d, "control_period_ms": p * d,
               "physics_clock_attr": self.clock_attr, "physics_timestep_attr": self.timestep_attr,
               "source_refs": list(self.source_refs),
               "notes": [f"Physics timestep {p:g} ms; control period {p*d:g} ms ({d} physics ticks). "
                         f"ticks is required and must be a positive multiple of {d}; action is held for each "
                         "opaque control call. Runtime clock deltas account completed physics ticks. "
                         + reset_note + "native autoreset and "
                         "external clock advancement are unsupported. No wall-clock pacing. "
                         "Source references are declarations, not validation evidence."]}
        if self.reset_clock is not None:
            out.update(reset_advances_physics=True, reset_clock=self.reset_clock,
                       max_reset_ticks=self.max_reset_ticks)
        return out


class SimulationTimingReport:
    """Bounded primitive ledger; no native lock is held while snapshots are read."""

    def __init__(self, descriptor: Mapping[str, Any], requested: Any):
        if descriptor.get("version") != 1 or descriptor.get("mode") != "physics_ticks_v1":
            raise TimingError("unsupported simulation timing descriptor")
        p = _positive(descriptor.get("physics_timestep_ms"), "physics timestep")
        d = descriptor.get("control_decimation")
        if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 10000:
            raise TimingError("invalid control decimation")
        if descriptor.get("control_period_ms") != p * d or descriptor.get("tick_unit") != "physics":
            raise TimingError("inconsistent simulation timing descriptor")
        integrates = descriptor.get("reset_advances_physics", False)
        if integrates is not False and (integrates is not True or descriptor.get("reset_clock") not in RESET_CLOCKS):
            raise TimingError("inconsistent reset integration in the timing descriptor")
        self._reset_ticks_reported = integrates is True
        self._reset_known = 0
        self._reset_exact = True
        self._base = {"version": 1, "tick_unit": "physics", "physics_timestep_ms": p,
                      "control_decimation": d, "control_period_ms": p * d,
                      "requested_ticks": requested if isinstance(requested, int) and not isinstance(requested, bool)
                      and 0 < requested <= 10000 else None}
        self._lock = threading.Lock()
        self._known = self._started = self._returned = 0
        self._resets_started = self._resets_verified = 0
        self._in_flight = self._closed = False
        self._exact = True
        self._reason = "pending"
        self._claimed = False

    def claim(self) -> None:
        with self._lock:
            if self._claimed or self._closed:
                raise TimingError("each command requires its own unused timing report")
            self._claimed = True

    def matches(self, timing: PhysicsTiming, ticks: int) -> bool:
        return (self._base["physics_timestep_ms"] == timing.timestep_ms
                and self._base["control_decimation"] == timing.decimation
                and self._base["requested_ticks"] == ticks)

    def begin_call(self) -> None:
        with self._lock:
            if self._closed or self._in_flight:
                raise TimingError("timing report already closed or executing")
            self._started += 1
            self._in_flight = True
            self._reason = "running"

    def end_call(self, ticks: int | None, *, returned: bool) -> None:
        with self._lock:
            if ticks is None:
                self._exact = False
            else:
                self._known += ticks
            self._returned += int(returned)
            self._in_flight = False

    def begin_reset(self) -> None:
        with self._lock:
            if self._closed or self._in_flight:
                raise TimingError("timing report already closed or executing")
            self._resets_started += 1
            self._in_flight = True
            self._reason = "resetting"

    def end_reset(self, *, verified: bool, ticks: int | None = None) -> None:
        with self._lock:
            self._resets_verified += int(verified)
            if not verified:
                # Reset can integrate before raising or failing verification.
                # A reset-to-zero clock cannot recover its elapsed tick count.
                self._exact = False
                self._reset_exact = False
            elif ticks is not None:
                self._reset_known += int(ticks)
            self._in_flight = False

    def close(self, reason: str) -> None:
        with self._lock:
            self._reason = reason
            self._closed = True

    def snapshot(self, *, final: bool = False) -> dict[str, Any]:
        with self._lock:
            exact = self._exact and not self._in_flight and (self._closed or final)
            p = self._base["physics_timestep_ms"]
            out = dict(self._base)
            out.update(completed_ticks=self._known if exact else None, known_completed_ticks=self._known,
                       simulated_duration_ms=self._known * p if exact else None,
                       known_simulated_duration_ms=self._known * p,
                       control_calls_started=self._started, control_calls_returned=self._returned,
                       reset_calls_started=self._resets_started, reset_calls_verified=self._resets_verified,
                       accounting="exact" if exact else "unknown" if not self._exact else "incomplete",
                       in_flight=self._in_flight, stop_reason=self._reason)
            out["notes"] = [f"{self._known} verified physics ticks; "
                            + (f"simulated duration {self._known*p:g} ms." if exact else
                               "exact completed total and simulated duration are unresolved.")
                            + " No wall-clock pacing."]
            if self._reset_ticks_reported:
                reset_exact = self._reset_exact and not self._in_flight and (self._closed or final)
                out.update(reset_integrated_ticks=self._reset_known if reset_exact else None,
                           known_reset_integrated_ticks=self._reset_known,
                           reset_integrated_duration_ms=self._reset_known * p if reset_exact else None)
                out["notes"].append(f"{self._reset_known} verified physics ticks were integrated by "
                                    f"{self._resets_verified} verified reset(s); they are not episode or "
                                    "control ticks.")
            return copy.deepcopy(out)

    def vendor(self, *, final: bool = False) -> dict[str, Any]:
        return {NAMESPACE: self.snapshot(final=final)}


def report_from_context(ctx: Any) -> SimulationTimingReport | None:
    value = (getattr(ctx, "extra", None) or {}).get(CONTEXT_KEY)
    return value if isinstance(value, SimulationTimingReport) else None


def report_for_binding(capability: Any, payload: Mapping[str, Any]) -> SimulationTimingReport | None:
    if capability is None or capability.capability_id not in ("cap.world.step.v1", "cap.world.reset.v1"):
        return None
    vendor = capability.manifest().get("x-vendor")
    descriptor = vendor.get(NAMESPACE) if isinstance(vendor, Mapping) else None
    if not isinstance(descriptor, Mapping):
        return None
    if capability.capability_id == "cap.world.reset.v1":
        # Only a reset that integrates physics carries a descriptor; it requests no control ticks.
        if descriptor.get("reset_advances_physics") is not True:
            return None
        return SimulationTimingReport(descriptor, None)
    return SimulationTimingReport(descriptor, payload.get("ticks"))
