"""The sensed-confirmation stop of a simulated :class:`mhs.driver.RosDriver` (SAFE-049, CORE-088): its declaration.

``safety_bindings["sensed_stop"]`` of a ``mode = "simulated"`` RosDriver::

    "sensed_stop": {
        "request": [{"service": "/land", "type": "std_srvs/SetBool", "request": {"data": True},
                     "success": {"path": "success", "equals": True}, "timeout_ms": 2000,
                     "source_ref": "src/base.cpp:32", "type_ref": "src/base.cpp:12"}],
        "sources": {"state": {"topic": "/mavros/state", "type": "mavros_msgs/State",
                              "source_ref": "...", "fill_refs": {"armed": "src/base.cpp:167"}}},
        "predicate": [{"source": "state", "path": "armed", "equals": False},
                      {"source": "pose", "path": "pose.position.z", "name": "landed_z", "unit": "m",
                       "range": {"max": Limit.operator_required("no landed band in the clone")}}],
        "consecutive": 3, "min_span_ms": 200, "max_gap_ms": 500, "confirm_within_ms": 1500,
        "description": "landed and disarmed as sensed on /mavros/state within the confirmation window",
    }

Every threshold (``abs_max``, ``norm_max``, ``span_max``, a ``range`` side) is a
:class:`~mhs.driver.Limit`: cited (``vendor_doc``/``upstream_code`` with a
``ref`` whose line G4 checks) or ``Limit.operator_required(reason)``.  The
operator fills the latter for a live simulation in
``simulation_deployment["estop_confirmation"]["thresholds"]`` (narrow-only
against a cited value); the fake backend reads placeholders from the package's
``fixtures/estop-confirmation.json`` and nothing else does.  ``consecutive``,
``min_span_ms``, ``max_gap_ms``, ``confirm_within_ms``, ``throttle_ms`` and the
request timeouts are client execution bounds: a wrong value can only withhold
the confirmation, so they need no source (SDK floor ``consecutive >= 2``).

Every source of a ROS 2 driver declares its publisher's ``history``
(verification F1 of phase 3): a new subscription replays what a
transient-local publisher keeps, and the bridge discards exactly that many
samples (at least one), so only samples published after the subscription was
opened count.  It is cited (``{"durability": "volatile", "ref": "path:LINE"}``
or ``{"durability": "transient_local", "depth": N, "ref": "path:LINE"}``, the
line that creates the publisher with its QoS, checked by gate G7) or
``{"operator_required": reason}`` when the clone does not show it; the
operator states it for a live simulation in
``simulation_deployment["estop_confirmation"]["history"]`` and the fake
backend reads a placeholder from the fixture, each of which may only raise a
cited replay.  A ROS 1 source declares no history.  The bridge discards
every ROS 1 stamp sample.  A producer stamp, a latched message, an empty
queue, a socket poll, a client buffer, a continuation flag, and a fixed lead
are not a freshness proof.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, NamedTuple

from ..bridge import ros_sensed
from .spec import Limit
from .upstream import parse_ref, safe_relpath

__all__ = ["FIXTURE", "History", "Resolved", "SensedDeclaration", "declaration", "deployment_member",
           "fixture_history", "fixture_resolved", "fixture_values", "resolve", "resolve_history"]

#: The fake backend's placeholder thresholds and histories (never read by a live deployment).
FIXTURE = "fixtures/estop-confirmation.json"
_BOUND_KEYS = ("consecutive", "min_span_ms", "max_gap_ms", "confirm_within_ms")
_DEPLOYMENT_KEYS = {"thresholds", "history"} | set(_BOUND_KEYS)
_PLACEHOLDER = 0.0
#: A history placeholder for validation only (the validation bridge never does I/O).
_PLACEHOLDER_HISTORY = {"durability": "volatile"}


@dataclass(frozen=True)
class History:
    """The declared history of one ROS 2 source: cited (``cited`` and ``ref``) or operator_required (``reason``)."""

    source: str
    cited: dict[str, Any] | None = None
    ref: str | None = None
    reason: str | None = None

    @property
    def replay(self) -> int | None:
        """The cited replay bound (``None`` while operator_required)."""
        if self.cited is None:
            return None
        return ros_sensed.replay_bound(self.cited, where=f"sources[{self.source!r}].history")


class Resolved(NamedTuple):
    """The deployment's (or the fake backend's) values of a sensed stop: thresholds, client bounds and histories."""

    values: dict[str, float]
    bounds: dict[str, int]
    operator: frozenset[str]
    history: dict[str, dict[str, Any]]
    history_operator: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Threshold:
    """One numeric bound of a predicate term: ``key`` is the term name (or ``name.min``/``name.max`` of a range)."""

    key: str
    side: str          # "max" or "min"
    limit: Limit
    unit: str | None
    term: int          # index of the term in the predicate
    magnitude: bool = True   # abs_max, norm_max, span_max bound a magnitude (never negative); a range side does not

    @property
    def cited(self) -> float | None:
        if self.limit.is_operator_required:
            return None
        value = self.limit.max if self.side == "max" else self.limit.min
        return float(value)


@dataclass
class SensedDeclaration:
    """A checked ``sensed_stop`` declaration; :meth:`bridge_json` resolves it for :class:`mhs.bridge.ros.RosBridge`."""

    raw: dict[str, Any]
    thresholds: list[Threshold] = field(default_factory=list)
    timeout_s: float = 2.0
    #: source name -> its declared history (ROS 2 sources only)
    histories: dict[str, History] = field(default_factory=dict)

    @property
    def steps(self) -> list[dict[str, Any]]:
        return list(self.raw.get("request") or [])

    @property
    def sources(self) -> dict[str, Any]:
        return dict(self.raw.get("sources") or {})

    @property
    def terms(self) -> list[dict[str, Any]]:
        return list(self.raw.get("predicate") or [])

    def bound(self, name: str) -> Any:
        return self.raw.get(name, 3 if name == "consecutive" else 0 if name == "min_span_ms" else None)

    def request_timeout_ms(self) -> int:
        """The sum of the request steps' timeouts (each ``timeout_ms``, else the driver's ``timeout_s``)."""
        total = 0.0
        for step in self.steps:
            value = step.get("timeout_ms") if isinstance(step, Mapping) else None
            total += float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else (
                self.timeout_s * 1000.0)
        return int(math.ceil(total))

    def operator_required(self) -> list[Threshold]:
        return [item for item in self.thresholds if item.limit.is_operator_required]

    def bridge_json(self, ros_version: int, values: Mapping[str, float] | None,
                    bounds: Mapping[str, int] | None = None,
                    history: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
        """The bridge's JSON configuration; ``values`` resolves every threshold and ``history`` every ROS 2 source's
        history (``None``: validation placeholders, never used for I/O)."""
        sources = copy.deepcopy(self.sources)
        for name, item in self.histories.items():
            spec = sources.get(name)
            if isinstance(spec, dict):
                resolved = (history or {}).get(name) if history is not None else (item.cited or _PLACEHOLDER_HISTORY)
                spec["history"] = copy.deepcopy(dict(resolved)) if isinstance(resolved, Mapping) else None
        out: dict[str, Any] = {"ros_version": ros_version, "request": copy.deepcopy(self.steps),
                               "sources": sources, "description": self.raw.get("description")}
        for name in _BOUND_KEYS:
            value = (bounds or {}).get(name, self.raw.get(name))
            if value is not None:
                out[name] = value
        terms = []
        by_term: dict[int, list[Threshold]] = {}
        for item in self.thresholds:
            by_term.setdefault(item.term, []).append(item)
        for index, term in enumerate(self.terms):
            entry = {key: copy.deepcopy(value) for key, value in term.items() if key not in ros_sensed.TERMS}
            kind = next(kind for kind in ros_sensed.TERMS if kind in term)
            if kind == "equals":
                entry["equals"] = copy.deepcopy(term["equals"])
            elif kind == "range":
                entry["range"] = {item.side: _value(item, values) for item in by_term.get(index, [])}
            else:
                (item,) = by_term[index]
                entry[kind] = _value(item, values)
            terms.append(entry)
        out["predicate"] = terms
        if self.raw.get("exclusion") is not None:
            out["exclusion"] = copy.deepcopy(self.raw["exclusion"])
        return out

    def manifest(self, values: Mapping[str, float] | None = None, *, operator: frozenset[str] = frozenset(),
                 bounds: Mapping[str, int] | None = None, history: Mapping[str, Mapping[str, Any]] | None = None,
                 history_operator: frozenset[str] = frozenset()) -> dict[str, Any]:
        """``safety.estop.confirmation``: what the stop requests, what it senses and the bounds it confirms within.

        A ROS 2 source publishes its history as declared (cited with its ``ref``, or ``operator_required``), or as
        the deployment's operator value (``source: operator``); a ROS 1 source publishes none.
        """
        steps = []
        for step in self.steps:
            kind = "service" if "service" in step else "topic"
            item = {"kind": kind, "native": str(step[kind])[:512]}
            if isinstance(step.get("type"), str):
                item["type"] = step["type"][:256]
            steps.append(item)
        sources = []
        for name, spec in self.sources.items():
            entry = {"name": name, "topic": spec["topic"], "type": spec["type"]}
            if spec.get("freshness") == "arrival":
                entry["freshness"] = "arrival"
                if spec.get("min_interval_ms") is not None:
                    entry["min_interval_ms"] = spec["min_interval_ms"]
            else:
                entry["stamp_path"] = spec.get("stamp_path", "header.stamp")
            if spec.get("throttle_ms") is not None:
                entry["throttle_ms"] = spec["throttle_ms"]
            declared = self.histories.get(name)
            if declared is not None:
                filled = (history or {}).get(name)
                if name in history_operator and isinstance(filled, Mapping):
                    entry["history"] = {**copy.deepcopy(dict(filled)), "source": "operator"}
                elif declared.cited is not None:
                    entry["history"] = {**copy.deepcopy(declared.cited), "ref": str(declared.ref)[:512]}
                else:
                    entry["history"] = {"operator_required": str(declared.reason)[:500]}
            sources.append(entry)
        thresholds = []
        for item in self.thresholds:
            entry: dict[str, Any] = {"name": item.key, "bound": item.side}
            if item.unit:
                entry["unit"] = item.unit
            value = (values or {}).get(item.key)
            if item.key in operator and value is not None:
                entry.update({"source": "operator", "value": value})
            elif not item.limit.is_operator_required:
                entry.update({"source": item.limit.source, "ref": item.limit.ref,
                              "value": value if value is not None else item.cited})
            else:
                entry["operator_required"] = item.limit.reason
            thresholds.append(entry)
        out = {"kind": "sensed", "request": steps, "sources": sources,
               "predicate": [_summary(term) for term in self.terms], "thresholds": thresholds,
               "description": str(self.raw.get("description"))}
        for name in _BOUND_KEYS:
            out[name] = int((bounds or {}).get(name, self.bound(name)))
        return out


def _value(item: Threshold, values: Mapping[str, float] | None) -> float:
    if values is None:
        return item.cited if item.cited is not None else _PLACEHOLDER  # validation only: never used for I/O
    return float(values[item.key])


def _summary(term: Mapping[str, Any]) -> str:
    kind = next((kind for kind in ros_sensed.TERMS if kind in term), "?")
    source = term.get("source")
    target = (f"norm({', '.join(f'{source}.{path}' for path in term.get('paths') or [])})" if kind == "norm_max"
              else f"{source}.{term.get('path')}")
    name = term.get("name")
    if kind == "equals":
        return f"{target} equals {json.dumps(term['equals'])}"[:300]
    if kind == "range":
        sides = [f"{'>=' if side == 'min' else '<='} {name}.{side}" for side in ("min", "max")
                 if side in (term.get("range") or {})]
        return f"{target} {' and '.join(sides)}"[:300]
    if kind == "abs_max":
        return f"|{target}| <= {name}"[:300]
    if kind == "norm_max":
        return f"{target} <= {name}"[:300]
    return f"max - min of {target} over the window <= {name}"[:300]


def _limit_problem(limit: Any, side: str, unit: Any, where: str, *, magnitude: bool) -> str | None:
    if not isinstance(limit, Limit):
        return (f"{where}: a threshold is a Limit (cited with source='vendor_doc' or 'upstream_code' and "
                "ref='path:LINE') or Limit.operator_required(reason), got " + repr(limit)[:80])
    if limit.is_operator_required:
        return None
    if limit.source == "operator":
        return (f"{where}: an operator threshold belongs in simulation_deployment['estop_confirmation'] (the fake "
                f"backend's placeholder in {FIXTURE}), not in driver.py; cite a source or use operator_required")
    if limit.source not in ("vendor_doc", "upstream_code") or not isinstance(limit.ref, str) or not limit.ref.strip():
        return (f"{where}: a cited threshold needs source='vendor_doc' or 'upstream_code' and ref='path:LINE'; when "
                "no source states it use Limit.operator_required(reason)")
    value = limit.max if side == "max" else limit.min
    other = limit.min if side == "max" else limit.max
    if (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
            or other is not None or limit.allowed is not None):
        return f"{where}: the Limit states exactly one {side} (a finite number)"
    if magnitude and value < 0:
        return f"{where}: a threshold of a magnitude is not negative"
    if limit.unit is not None and limit.unit != unit:
        return f"{where}: the Limit's unit {limit.unit!r} differs from the term's unit {unit!r}"
    return None


def declaration(cls: type, problems: list[str]) -> SensedDeclaration | None:
    """The checked ``safety_bindings['sensed_stop']`` of a RosDriver class (``None`` when it declares none).

    Shape errors the bridge reports itself (it compiles the resolved form); this adds what only the driver
    can see: the Limits, the fill references of every field a term reads, the request and source topics, the
    e-stop latency and the simulated mode.
    """
    safety = getattr(cls, "safety_bindings", None) or {}
    raw = safety.get("sensed_stop") if isinstance(safety, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        problems.append("safety_bindings.sensed_stop must be an object (SAFE-049)")
        return None
    raw = dict(raw)
    decl = SensedDeclaration(raw, timeout_s=float(getattr(cls, "timeout_s", 2.0) or 2.0))
    if getattr(cls, "mode", "hardware") != "simulated":
        problems.append("safety_bindings.sensed_stop: a request plus a sensed confirmation is a stop of a simulated "
                        "device only (SAFE-049, the user's decision of 2026-11-05); declare mode = 'simulated' or "
                        "remove it")
    if "ros_version" in raw:
        problems.append("safety_bindings.sensed_stop.ros_version is set from the driver's ros_version; remove it")
    for name in ("estop", "safe_state"):
        if name in safety:
            problems.append(f"safety_bindings.sensed_stop excludes safety_bindings.{name}: a device with an "
                            "acknowledged stop does not need a sensed confirmation")
    from .spec import Action  # local: spec imports nothing from here

    for capability_id, action in dict(getattr(cls, "actions", None) or {}).items():
        if isinstance(action, Action) and action.safe_state:
            problems.append(f"{capability_id}: a device with safety_bindings.sensed_stop declares no safe_state "
                            "action; only the bounded sensed confirmation achieves its safe state")
    terms = raw.get("predicate") if isinstance(raw.get("predicate"), list) else []
    sources = raw.get("sources") if isinstance(raw.get("sources"), Mapping) else {}
    for index, term in enumerate(terms):
        if not isinstance(term, Mapping):
            continue
        kinds = [kind for kind in ros_sensed.TERMS if kind in term]
        if len(kinds) != 1 or kinds[0] == "equals":
            continue
        kind, name, unit = kinds[0], term.get("name"), term.get("unit")
        where = f"safety_bindings.sensed_stop.predicate[{index}].{kind}"
        if kind == "range":
            sides = term.get("range")
            if not isinstance(sides, Mapping) or not sides or set(sides) - {"min", "max"}:
                problems.append(f"{where} maps min and/or max to a Limit")
                continue
            for side, limit in sides.items():
                problem = _limit_problem(limit, side, unit, f"{where}.{side}", magnitude=False)
                if problem:
                    problems.append(problem)
                else:
                    decl.thresholds.append(Threshold(f"{name}.{side}", side, limit, unit, index, magnitude=False))
        else:
            problem = _limit_problem(term[kind], "max", unit, where, magnitude=True)
            if problem:
                problems.append(problem)
            else:
                decl.thresholds.append(Threshold(str(name), "max", term[kind], unit, index))
    request_topics = set()
    for index, step in enumerate(raw.get("request") if isinstance(raw.get("request"), list) else []):
        if isinstance(step, Mapping) and isinstance(step.get("topic"), str):
            request_topics.add(step["topic"])
    ros_version = getattr(cls, "ros_version", 2)
    for name, source in sources.items():
        if not isinstance(source, Mapping):
            continue
        where = f"safety_bindings.sensed_stop.sources[{name!r}]"
        if source.get("topic") in request_topics:
            problems.append(f"{where}: a source is never a topic the request publishes")
        freshness = source.get("freshness", "stamp")
        if freshness not in ("stamp", "arrival"):
            problems.append(f"{where}.freshness must be 'stamp' or 'arrival'")
        elif freshness == "arrival":
            if ros_version != 2:
                problems.append(f"{where}: arrival freshness is ROS 2 only")
            if "stamp_path" in source:
                problems.append(f"{where}: an arrival source has no stamp_path")
            interval = source.get("min_interval_ms")
            if type(interval) is not int or not 1 <= interval <= 1000:
                problems.append(f"{where}.min_interval_ms must be an integer from 1 to 1000")
            history = source.get("history")
            if (not isinstance(history, Mapping) or history.get("durability") != "volatile"
                    or "operator_required" in history or "depth" in history):
                problems.append(f"{where}: an arrival source requires a cited volatile history "
                                "({'durability': 'volatile', 'ref': 'path:LINE'}); a transient_local replay cannot "
                                "be told from live samples without a producer stamp")
        elif "min_interval_ms" in source:
            problems.append(f"{where}.min_interval_ms is only for freshness 'arrival'")
        if ros_version == 1:
            if "history" in source:
                problems.append(f"{where}.history is a ROS 2 durability: every ROS 1 stamp sample is discarded, and a "
                                "producer stamp is not a freshness proof; remove it")
        else:
            declared = _history(str(name), source.get("history"), f"{where}.history", problems)
            if declared is not None:
                decl.histories[str(name)] = declared
        refs = source.get("fill_refs")
        if not isinstance(refs, Mapping) or not refs:
            problems.append(f"{where}.fill_refs must cite, for every field a term reads, a line where the producer "
                            "assigns it, the clone's code reads it from this topic, or a vendor document states it")
            refs = {}
        for path, ref in refs.items():
            parsed = parse_ref(ref) if isinstance(ref, str) else None
            if parsed is None or safe_relpath(parsed.path) is None:
                problems.append(f"{where}.fill_refs[{path!r}] must be 'path/in/clone:LINE'")
        read = set()
        for term in terms:
            if isinstance(term, Mapping) and term.get("source") == name:
                read.update(term.get("paths") or [term.get("path")])
        for path in sorted(item for item in read if isinstance(item, str)):
            if not any(path == key or path.startswith(str(key) + ".") for key in refs):
                problems.append(f"{where}: field {path!r} has no fill_ref (a field the producer leaves at its default "
                                "is never a sensed state)")
    exclusion = raw.get("exclusion")
    if exclusion is not None:
        where = "safety_bindings.sensed_stop.exclusion"
        if not isinstance(exclusion, Mapping):
            problems.append(f"{where} must be an object")
        else:
            if exclusion.get("topic") not in request_topics:
                problems.append(f"{where}.topic must be a topic the request publishes")
            ref = exclusion.get("source_ref")
            parsed = parse_ref(ref) if isinstance(ref, str) else None
            if parsed is None or safe_relpath(parsed.path) is None:
                problems.append(f"{where}.source_ref must be 'path/in/clone:LINE' (the competing publisher)")
    latency = getattr(cls, "estop_latency_ms", None)
    confirm = raw.get("confirm_within_ms")
    if isinstance(confirm, int) and not isinstance(confirm, bool):
        needed = decl.request_timeout_ms() + confirm
        if not isinstance(latency, int) or isinstance(latency, bool) or latency < needed:
            problems.append(f"estop_latency_ms must cover the request steps' timeouts plus confirm_within_ms "
                            f"({needed} ms) so the e-stop's declared latency is truthful (SAFE-028, SAFE-040), got "
                            f"{latency!r}")
    return decl


_HISTORY_HINT = ("{'durability': 'volatile', 'ref': 'path:LINE'} or {'durability': 'transient_local', 'depth': N, "
                 "'ref': 'path:LINE'} citing the line that creates the source's publisher with its QoS, or "
                 "{'operator_required': reason} when the clone does not show it")


def _history(source: str, raw: Any, where: str, problems: list[str]) -> History | None:
    """The declared history of a ROS 2 source (verification F1 of phase 3), or ``None`` with a problem."""
    if raw is None:
        problems.append(f"{where}: a ROS 2 source declares its publisher's history, {_HISTORY_HINT}: a new "
                        "subscription replays what a transient-local publisher keeps, and only a declared bound shows "
                        "which samples were published after the request")
        return None
    if not isinstance(raw, Mapping) or not all(isinstance(key, str) for key in raw):
        problems.append(f"{where} must be {_HISTORY_HINT}")
        return None
    if "operator_required" in raw:
        reason = raw.get("operator_required")
        if set(raw) != {"operator_required"} or not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            problems.append(f"{where}: an operator_required history is {{'operator_required': reason}}, the reason a "
                            "short sentence saying why the clone does not show the publisher's QoS")
            return None
        return History(source, reason=reason)
    ref = raw.get("ref")
    parsed = parse_ref(ref) if isinstance(ref, str) else None
    if parsed is None or safe_relpath(parsed.path) is None:
        problems.append(f"{where}.ref must be 'path/in/clone:LINE' (the line that creates the publisher with its QoS); "
                        f"use {{'operator_required': reason}} when the clone does not show it")
        return None
    cited = {key: copy.deepcopy(value) for key, value in raw.items() if key != "ref"}
    try:
        ros_sensed.replay_bound(cited, where=where)
    except ros_sensed.SensedConfigError as exc:
        problems.append(str(exc))
        return None
    return History(source, cited=cited, ref=ref)


def resolve_history(decl: SensedDeclaration, given: Any, *, where: str) -> dict[str, dict[str, Any]]:
    """Every ROS 2 source's history: an operator value (it may only raise a cited replay), else the cited one.

    Raises ``ValueError`` naming every unfilled ``operator_required`` history, every unknown source and every value
    that lowers a cited replay: a device whose confirmation cannot show which samples are new does not construct.
    """
    if given is None:
        given = {}
    if not isinstance(given, Mapping):
        raise ValueError(f"{where} must map source names to histories")
    problems = [f"{where}: {key!r} is not a ROS 2 source of this sensed_stop (sources: {sorted(decl.histories)})"
                for key in given if key not in decl.histories]
    out: dict[str, dict[str, Any]] = {}
    for name, item in decl.histories.items():
        if name in given:
            value = given[name]
            try:
                replay = ros_sensed.replay_bound(value, where=f"{where}[{name!r}]")
            except ros_sensed.SensedConfigError as exc:
                problems.append(str(exc))
                continue
            cited = item.replay
            if cited is not None and replay < cited:
                problems.append(f"{where}[{name!r}] replays {replay} sample(s), fewer than the cited history "
                                f"({item.ref}, {cited}); an operator value may only raise it")
                continue
            out[name] = copy.deepcopy(dict(value))
        elif item.cited is not None:
            out[name] = copy.deepcopy(item.cited)
        else:
            problems.append(f"{where}: the history of source {name!r} is operator_required ({item.reason}) and has no "
                            "value")
    if problems:
        raise ValueError("sensed_stop histories: " + "; ".join(problems[:8]))
    return out


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def resolve(decl: SensedDeclaration, values: Mapping[str, Any] | None, *, where: str) -> dict[str, float]:
    """Every threshold's value: an operator value (narrow-only against a cited one), else the cited value.

    Raises ``ValueError`` naming every unfilled ``operator_required`` threshold, every unknown name and every value
    that widens a cited bound: a device without a confirmable stop does not construct.
    """
    given = dict(values or {})
    known = {item.key for item in decl.thresholds}
    problems = [f"{where}: {key!r} is not a threshold of this sensed_stop (thresholds: {sorted(known)})"
                for key in given if key not in known]
    out: dict[str, float] = {}
    for item in decl.thresholds:
        if item.key in given:
            value = _number(given[item.key])
            if value is None:
                problems.append(f"{where}: {item.key!r} must be a finite number")
                continue
            cited = item.cited
            if cited is not None and ((item.side == "max" and value > cited) or (item.side == "min" and value < cited)):
                problems.append(f"{where}: {item.key!r} = {value:g} widens the cited {item.side} {cited:g} "
                                f"({item.limit.ref}); an operator value may only narrow it")
                continue
            if item.magnitude and value < 0:
                problems.append(f"{where}: {item.key!r} bounds a magnitude and is not negative")
                continue
            out[item.key] = value
        elif item.cited is not None:
            out[item.key] = item.cited
        else:
            problems.append(f"{where}: {item.key!r} is operator_required ({item.limit.reason}) and has no value")
    for index, term in enumerate(decl.terms):
        if isinstance(term, Mapping) and isinstance(term.get("range"), Mapping):
            low, high = out.get(f"{term.get('name')}.min"), out.get(f"{term.get('name')}.max")
            if low is not None and high is not None and low > high:
                problems.append(f"{where}: {term.get('name')}.min exceeds {term.get('name')}.max")
    if problems:
        raise ValueError("sensed_stop thresholds: " + "; ".join(problems[:8]))
    return out


def _fixture_document(base_dir: Path) -> Mapping[str, Any] | None:
    """``fixtures/estop-confirmation.json`` (validated shape), or ``None`` when the package has none."""
    path = Path(base_dir) / FIXTURE
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{FIXTURE} is not readable JSON: {exc}") from exc
    if (not isinstance(document, Mapping) or set(document) - {"thresholds", "history", "note"}
            or not isinstance(document.get("thresholds"), Mapping)
            or not isinstance(document.get("history", {}), Mapping)):
        raise ValueError(f"{FIXTURE} must be {{'thresholds': {{name: value}}, 'history': {{source: history}} "
                         "(ROS 2 sources whose history is operator_required), 'note': '...'}")
    return document


def fixture_values(base_dir: Path, decl: SensedDeclaration) -> dict[str, float]:
    """The fake backend's placeholder thresholds from ``fixtures/estop-confirmation.json`` (validated)."""
    document = _fixture_document(base_dir)
    if document is None:
        if decl.operator_required():
            raise ValueError(f"{FIXTURE} is missing: the fake backend needs placeholder values for the "
                             f"operator_required thresholds {[item.key for item in decl.operator_required()]}")
        return resolve(decl, {}, where=FIXTURE)
    return resolve(decl, document["thresholds"], where=FIXTURE)


def fixture_history(base_dir: Path, decl: SensedDeclaration) -> dict[str, dict[str, Any]]:
    """The fake backend's ROS 2 source histories: cited, or placeholders from the fixture's ``history`` member.

    A placeholder models the fake's own replay on subscribe (never a device fact); like a deployment value it may
    only raise a cited one.
    """
    document = _fixture_document(base_dir)
    if document is None:
        missing = [name for name, item in decl.histories.items() if item.cited is None]
        if missing:
            raise ValueError(f"{FIXTURE} is missing: the fake backend needs placeholder histories for the "
                             f"operator_required sources {missing}")
        return resolve_history(decl, {}, where=f"{FIXTURE} history")
    return resolve_history(decl, document.get("history", {}), where=f"{FIXTURE} history")


def fixture_resolved(base_dir: Path, decl: SensedDeclaration) -> Resolved:
    """The fake backend's values: placeholder thresholds and histories (nothing operator-filled)."""
    return Resolved(fixture_values(base_dir, decl), {}, frozenset(), fixture_history(base_dir, decl))


def deployment_member(decl: SensedDeclaration | None, member: Any) -> Resolved:
    """``simulation_deployment['estop_confirmation']``: threshold values, client bounds, ROS 2 source histories and
    the operator-filled names."""
    if decl is None:
        raise ValueError("simulation_deployment.estop_confirmation is only for a driver with a sensed_stop")
    if member is None:
        member = {}
    if not isinstance(member, Mapping) or set(member) - _DEPLOYMENT_KEYS:
        raise ValueError("simulation_deployment.estop_confirmation must be an object with thresholds, the history of "
                         f"each ROS 2 source whose history is operator_required, and optional client bounds "
                         f"{list(_BOUND_KEYS)}")
    thresholds = member.get("thresholds", {})
    if not isinstance(thresholds, Mapping):
        raise ValueError("simulation_deployment.estop_confirmation.thresholds must map threshold names to numbers")
    values = resolve(decl, thresholds, where="simulation_deployment.estop_confirmation")
    histories = member.get("history", {})
    if not isinstance(histories, Mapping):
        raise ValueError("simulation_deployment.estop_confirmation.history must map ROS 2 source names to histories")
    # Verification F1: a live device whose source history is unstated does not construct (operator_required).
    history = resolve_history(decl, histories, where="simulation_deployment.estop_confirmation.history")
    bounds: dict[str, int] = {}
    for name in _BOUND_KEYS:
        if name not in member:
            continue
        value = member[name]
        floor = 0 if name == "min_span_ms" else 1
        if type(value) is not int or value < floor or value > ros_sensed.MAX_BOUND_MS:
            raise ValueError(f"simulation_deployment.estop_confirmation.{name} must be an integer from {floor} to "
                             f"{ros_sensed.MAX_BOUND_MS}")
        if name == "consecutive" and value < int(decl.bound("consecutive")):
            raise ValueError("simulation_deployment.estop_confirmation.consecutive may only rise above the declared "
                             f"{decl.bound('consecutive')}")
        bounds[name] = value
    return Resolved(values, bounds, frozenset(str(key) for key in thresholds), history,
                    frozenset(str(key) for key in histories))
