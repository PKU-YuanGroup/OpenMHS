"""Sensed-confirmation stop of a simulated ROS device: the pure confirmation logic (SAFE-049, CORE-088).

A simulated device whose only stop is a request (a LAND, a zero velocity, a
motor cut) may declare ``safety_bindings["sensed_stop"]``: the request steps,
then a bounded confirmation over topic samples.  The request proves
nothing by itself; the e-stop is achieved only when every source delivers
``consecutive`` fresh samples that satisfy every predicate term within
``confirm_within_ms`` of the request.  This module holds what does not need a
transport: the declaration of the sources, the predicate and the bounds, the
producer-stamp reader (ROS 1 ``secs``/``nsecs``, ROS 2 ``sec``/``nanosec``),
the arrival-time reader of a source whose producer does not stamp, the
per-source window and the reason of an unconfirmed attempt.
:class:`mhs.bridge.ros.RosBridge` sends the request, opens the subscriptions
and feeds the samples in arrival order.

Fail-closed rules of one source (one subscription, opened after the request):

* the samples a new subscription can receive that were published before it
  existed are discarded.  On ROS 1 the bridge has no proven offset between a
  producer clock and its wall clock, so a producer stamp is not a freshness
  proof: every ROS 1 stamp sample is discarded and does not refresh counted
  freshness.  That includes a stamp one second ahead, a ROS simulation clock,
  a delayed latch, a frame already in a client buffer, a replay spaced out
  from before the request, and a sample from a transport that cannot report
  its buffer.  An empty queue, a socket poll, a client library buffer, a
  continuation flag, and a fixed lead are not that proof.  On ROS 2 it is the
  publisher's declared history (``history``:
  ``volatile`` keeps nothing for a late subscriber, ``transient_local``
  replays up to its ``depth``), never fewer than one sample.  The newest
  stamp the discarded samples carry is the baseline a counted sample must
  exceed (verification F1 of phase 3: a transient-local history deeper than
  one sample replays several pre-request samples on subscribe).  They are
  counted by arrival ordinal, numbered before the bridge's ring drops
  anything: a sample the ring lost still counts towards the replay, so live
  samples after a lossy replay are not discarded with it (a window that only
  counted what it saw would discard more, never fewer);
* a source with ``freshness`` ``arrival`` (ROS 2 only, a cited volatile
  publisher, no ``stamp_path``) is fresh by arrival after that discard.  A
  later sample closer than ``min_interval_ms`` to the one before it restarts
  the count (the same burst rule as a fresh topic read-back).  A
  transient-local history is refused: once the first sample is discarded, a
  replay spaced at least ``min_interval_ms`` apart cannot be told from a live
  stream.  ``min_span_ms`` is arrival time.  A missing or non-finite field
  is still ``sensed_invalid``;
* a sample that arrived before the request is not counted;
* a missing, malformed, zero or decreasing producer stamp, and a missing,
  non-numeric or non-finite field (or a field of another JSON type than an
  ``equals`` term expects) is ``sensed_invalid``: the attempt ends;
* an equal stamp is a duplicate (a node republishing a cached value): the
  count restarts;
* an arrival gap above ``max_gap_ms`` restarts the count (a stale stream), and
  so does a ring overflow of the bridge (a sample was lost);
* a per-sample term that does not hold restarts the count (still settling);
* a window term (``span_max``) is evaluated over the last ``consecutive``
  counted samples, which must span ``min_span_ms`` of producer time, or of
  arrival time when the source's freshness is ``arrival``.

A source confirms while its window holds and its newest sample arrived within
``max_gap_ms``.  Nothing here claims more than the confirmation window.

When the declaration names an exclusion on a request topic, silence, a
subscription error, a sample whose watched fields are not all zero, and a
sample the exclusion ring drops each refuse the confirmation.  A dropped
sample was not inspected, so the tail that remains is not a passive command.
Only a passive sample on that subscription, observed after it opened and still
fresh at the commit, is evidence the competing command is absent.
"""

from __future__ import annotations

import math
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

__all__ = ["DURABILITIES", "REASONS", "TERMS", "Profile", "Ring", "SensedConfigError", "SourceWindow",
           "compile_profile", "replay_bound", "stamp_text"]

#: The closed set of predicate terms.
TERMS = ("equals", "range", "abs_max", "norm_max", "span_max")
#: ``details.sensed.reason`` of an unconfirmed attempt (CORE-088); CORE-077's reasons are unchanged.
#: ``not_simulated``: the endpoint has not bound the bridge to a device it serves as simulated (no confirmation runs).
REASONS = ("request_not_sent", "sensed_missing", "sensed_stale", "sensed_invalid", "not_confirmed", "superseded",
           "not_simulated")
MAX_STEPS = 3
MAX_SOURCES = 3
MAX_TERMS = 16
MAX_NORM_PATHS = 8
MIN_CONSECUTIVE = 2
MAX_CONSECUTIVE = 64
MAX_BOUND_MS = 600_000
#: The deepest transient-local history a ROS 2 source may declare (its replay is discarded sample by sample).
MAX_HISTORY_DEPTH = 10_000
#: ``history.durability`` of a ROS 2 source: what its publisher keeps for a subscriber that joins later.
DURABILITIES = ("volatile", "transient_local")
#: How a counted sample shows it was published after the subscription opened.
FRESHNESS = ("stamp", "arrival")
#: ``min_interval_ms`` of an arrival source (the E2 floor of 10 ms would treat a ~500 Hz stream as a permanent burst).
MIN_INTERVAL_MS = 1
MAX_INTERVAL_MS = 1000
_NS = 1_000_000_000

_SOURCE_KEYS = {"topic", "type", "stamp_path", "throttle_ms", "fill_refs", "source_ref", "type_ref", "source_name",
                "description", "history", "freshness", "min_interval_ms"}
_TERM_KEYS = {"source", "path", "paths", "name", "unit", "description"} | set(TERMS)
_EXCLUSION_KEYS = {"topic", "type", "paths", "source_ref", "type_ref", "source_name", "description"}
_PROFILE_KEYS = {"ros_version", "request", "sources", "predicate", "consecutive", "min_span_ms", "max_gap_ms",
                 "confirm_within_ms", "description", "exclusion"}
_TOPIC = re.compile(r"/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*\Z")
_TYPE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)/(?:msg/)?([A-Za-z_][A-Za-z0-9_]*)\Z")
_FIELD = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+))*\Z")
_IDENT = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_THRESHOLD = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
#: Message types without a producer stamp: a node that republishes a cached value looks fresh on arrival.  The
#: runtime refuses every sample without a stamp at ``stamp_path`` anyway; these are refused at definition.
_HEADERLESS_GEOMETRY = frozenset({"Twist", "Pose", "Point", "Point32", "Quaternion", "Vector3", "Transform", "Wrench",
                                  "Accel", "Polygon", "Inertia", "Pose2D", "PoseWithCovariance",
                                  "TwistWithCovariance", "AccelWithCovariance"})


class SensedConfigError(ValueError):
    """A sensed-stop declaration the bridge refuses (``MHS.ADAPTER.MANIFEST_INVALID``)."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SensedConfigError(message)


def _int(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    _require(type(value) is int and minimum <= value <= maximum,
             f"sensed_stop.{label} must be an integer from {minimum} to {maximum}")
    return int(value)


def _finite(value: Any, label: str, *, non_negative: bool = False) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
             and (not non_negative or value >= 0), f"{label} must be a finite{' non-negative' if non_negative else ''}"
             " number")
    return float(value)


def headerless_type(ros_type: str) -> bool:
    """True for a message type known to carry no ``header`` (std_msgs other than Header, plain geometry types)."""
    match = _TYPE.fullmatch(ros_type) if isinstance(ros_type, str) else None
    if match is None:
        return False
    package, name = match.group(1), match.group(2)
    if package == "std_msgs":
        return name != "Header"
    return package == "geometry_msgs" and name in _HEADERLESS_GEOMETRY


def get_path(value: Any, path: str) -> Any:
    """The member of a message at a dot path of object keys and array indices; ``KeyError`` when absent."""
    for part in path.split("."):
        if isinstance(value, Mapping):
            if part not in value:
                raise KeyError(path)
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError(path)
    return value


@dataclass(frozen=True)
class Term:
    """One predicate term over the fields of one source (all terms must hold)."""

    kind: str
    source: str
    paths: tuple[str, ...]
    equals: Any = None
    minimum: float | None = None
    maximum: float | None = None
    name: str | None = None

    @property
    def per_sample(self) -> bool:
        return self.kind != "span_max"

    @property
    def numeric(self) -> bool:
        return self.kind != "equals"

    def holds(self, values: Mapping[str, Any]) -> bool:
        """A per-sample term on one sample's extracted fields (already type-checked)."""
        if self.kind == "equals":
            return _same(values[self.paths[0]], self.equals)
        if self.kind == "range":
            value = values[self.paths[0]]
            return ((self.minimum is None or value >= self.minimum)
                    and (self.maximum is None or value <= self.maximum))
        if self.kind == "abs_max":
            return abs(values[self.paths[0]]) <= self.maximum
        if self.kind == "norm_max":
            return math.sqrt(sum(values[path] ** 2 for path in self.paths)) <= self.maximum
        return True  # span_max is a window term

    def window_holds(self, window: Sequence[Mapping[str, Any]]) -> bool:
        if self.kind != "span_max":
            return True
        values = [sample[self.paths[0]] for sample in window]
        return (max(values) - min(values)) <= self.maximum

    def summary(self) -> str:
        """The term as one line of the manifest and the reference file."""
        target = f"{self.source}.{self.paths[0]}" if len(self.paths) == 1 else (
            f"norm({', '.join(f'{self.source}.{path}' for path in self.paths)})")
        label = f" [{self.name}]" if self.name else ""
        if self.kind == "equals":
            return f"{target} equals {_json_text(self.equals)}"
        if self.kind == "range":
            sides = []
            if self.minimum is not None:
                sides.append(f">= {self.minimum:g}")
            if self.maximum is not None:
                sides.append(f"<= {self.maximum:g}")
            return f"{target} {' and '.join(sides)}{label}"
        if self.kind == "abs_max":
            return f"|{target}| <= {self.maximum:g}{label}"
        if self.kind == "norm_max":
            return f"{target} <= {self.maximum:g}{label}"
        return f"max - min of {target} over the window <= {self.maximum:g}{label}"


def _json_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return repr(value)
    return f"{value:g}" if isinstance(value, float) else str(value)


def _same(left: Any, right: Any) -> bool:
    # True == 1 in Python; a predicate must not accept that (RosBridge._equal).
    return type(left) is type(right) and left == right


def replay_bound(history: Any, *, where: str) -> int:
    """The samples a new ROS 2 subscription can receive that its publisher sent before it existed.

    ``history`` is a resolved ROS 2 durability: ``{"durability": "volatile"}`` (the publisher keeps nothing for a
    late subscriber: 0) or ``{"durability": "transient_local", "depth": N}`` (it replays up to its last ``N``).
    Raises :class:`SensedConfigError` for anything else, so an undeclared or malformed history never confirms.
    """
    _require(isinstance(history, Mapping) and all(isinstance(key, str) for key in history),
             f"{where} must be an object: {{'durability': 'volatile'}} or {{'durability': 'transient_local', "
             f"'depth': N}}")
    durability = history.get("durability")
    _require(durability in DURABILITIES, f"{where}.durability must be one of {list(DURABILITIES)}")
    if durability == "volatile":
        _require(set(history) == {"durability"}, f"{where}: a volatile history has no other keys")
        return 0
    _require(set(history) == {"durability", "depth"}, f"{where}: a transient_local history states its depth")
    depth = history.get("depth")
    _require(type(depth) is int and 1 <= depth <= MAX_HISTORY_DEPTH,
             f"{where}.depth must be an integer from 1 to {MAX_HISTORY_DEPTH}")
    return int(depth)


@dataclass(frozen=True)
class Source:
    """One stamped topic subscription of the confirmation."""

    name: str
    topic: str
    type: str
    stamp_path: str
    throttle_ms: int | None
    #: every field a term reads, with whether it must be a finite number
    fields: tuple[tuple[str, bool], ...]
    #: the most samples a new subscription can receive that were published before it existed: on ROS 2, the
    #: declared history (0 for volatile, the depth for transient_local).  ROS 1 does not use this count.  Every
    #: ROS 1 stamp sample is discarded: a producer stamp is not a freshness proof.
    replay: int = 1
    #: ``stamp`` (a producer stamp) or ``arrival`` (ROS 2 volatile only; no producer stamp)
    freshness: str = "stamp"
    #: required for ``arrival``: a sample closer than this to the previous arrival restarts the count
    min_interval_ms: int | None = None

    @property
    def skip(self) -> int:
        """The samples a confirmation subscription discards before it counts any: the replay, at least one.

        ROS 1 does not use this count.  :meth:`SourceWindow.add` discards every ROS 1 stamp sample.  A producer
        stamp is not a freshness proof.
        """
        return max(1, self.replay)


@dataclass(frozen=True)
class Exclusion:
    """A watch on the request topic for a command published after the request.

    It is not a confirmation source.  Silence, a subscription error, a sample whose watched fields are
    not all finite zeros, and a sample the exclusion ring drops each leave the attempt unconfirmed.  A dropped
    sample was not inspected.  Only a passive sample observed after the subscription opened, and still fresh
    at the commit, is evidence the competing command is absent.
    """

    topic: str
    ros_type: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class Profile:
    """The compiled sources, predicate and client bounds (the bridge compiles the request steps)."""

    ros_version: int
    sources: dict[str, Source]
    terms: tuple[Term, ...]
    consecutive: int
    min_span_ms: int
    max_gap_ms: int
    confirm_within_ms: int
    description: str
    exclusion: Exclusion | None = None

    def terms_of(self, source: str) -> tuple[Term, ...]:
        return tuple(term for term in self.terms if term.source == source)


def exclusion_competes(exclusion: Exclusion, message: Any) -> bool:
    """True when a sample on the exclusion topic is not a passive (all-zero) command."""
    for path in exclusion.paths:
        try:
            value = get_path(message, path)
        except KeyError:
            return True
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value != 0:
            return True
    return False


def _term(raw: Any, index: int, sources: Mapping[str, Any]) -> Term:
    label = f"sensed_stop.predicate[{index}]"
    _require(isinstance(raw, Mapping) and all(isinstance(key, str) for key in raw), f"{label} must be an object")
    _require(not set(raw) - _TERM_KEYS, f"{label}: unknown keys {sorted(set(raw) - _TERM_KEYS)}")
    kinds = [kind for kind in TERMS if kind in raw]
    _require(len(kinds) == 1, f"{label} needs exactly one of {list(TERMS)}")
    kind = kinds[0]
    source = raw.get("source")
    _require(isinstance(source, str) and source in sources, f"{label}.source must name a declared source")
    if kind == "norm_max":
        paths = raw.get("paths")
        _require("path" not in raw and isinstance(paths, list) and 1 <= len(paths) <= MAX_NORM_PATHS
                 and len(set(map(str, paths))) == len(paths),
                 f"{label}: norm_max takes paths, a list of 1 to {MAX_NORM_PATHS} distinct field paths")
    else:
        _require("paths" not in raw and "path" in raw, f"{label}: {kind} takes one path")
        paths = [raw["path"]]
    for path in paths:
        _require(isinstance(path, str) and _FIELD.fullmatch(path) is not None,
                 f"{label}: a field path is dot-separated object keys and array indices")
    name = raw.get("name")
    if kind != "equals":
        _require(isinstance(name, str) and _THRESHOLD.fullmatch(name) is not None,
                 f"{label}: a threshold term needs a name ([a-z][a-z0-9_]*), the key of its operator value")
    elif name is not None:
        _require(isinstance(name, str) and _THRESHOLD.fullmatch(name) is not None, f"{label}.name is invalid")
    for key in ("unit", "description"):
        if key in raw:
            _require(isinstance(raw[key], str) and 0 < len(raw[key]) <= 200, f"{label}.{key} must be a short string")
    value = raw[kind]
    if kind == "equals":
        _require(isinstance(value, (bool, int, str)) or (isinstance(value, float) and math.isfinite(value)),
                 f"{label}.equals must be a boolean, an integer, a finite number or a string")
        return Term(kind, source, tuple(paths), equals=value, name=name)
    if kind == "range":
        _require(isinstance(value, Mapping) and set(value) <= {"min", "max"} and value,
                 f"{label}.range needs min and/or max")
        minimum = _finite(value["min"], f"{label}.range.min") if "min" in value else None
        maximum = _finite(value["max"], f"{label}.range.max") if "max" in value else None
        _require(minimum is None or maximum is None or minimum <= maximum, f"{label}.range: min exceeds max")
        return Term(kind, source, tuple(paths), minimum=minimum, maximum=maximum, name=name)
    maximum = _finite(value, f"{label}.{kind}", non_negative=True)
    return Term(kind, source, tuple(paths), maximum=maximum, name=name)


def _exclusion(raw: Any, request: Any) -> Exclusion | None:
    """The optional competing-command watch, or ``None`` when the declaration has none."""
    if raw is None:
        return None
    _require(isinstance(raw, Mapping) and all(isinstance(key, str) for key in raw),
             "sensed_stop.exclusion must be an object")
    _require(not set(raw) - _EXCLUSION_KEYS,
             f"sensed_stop.exclusion: unknown keys {sorted(set(raw) - _EXCLUSION_KEYS)}")
    topic, ros_type, paths = raw.get("topic"), raw.get("type"), raw.get("paths")
    _require(isinstance(topic, str) and _TOPIC.fullmatch(topic) is not None and len(topic) <= 512,
             "sensed_stop.exclusion.topic must be an absolute ROS topic name")
    _require(isinstance(ros_type, str) and _TYPE.fullmatch(ros_type) is not None,
             "sensed_stop.exclusion.type must be a ROS message type")
    _require(isinstance(paths, list) and 1 <= len(paths) <= 64 and len(set(paths)) == len(paths),
             "sensed_stop.exclusion.paths must be 1 to 64 distinct field paths")
    for path in paths:
        _require(isinstance(path, str) and _FIELD.fullmatch(path) is not None,
                 "sensed_stop.exclusion.paths entries are dot-separated object keys and array indices")
    request_topics = {step.get("topic") for step in request if isinstance(step, Mapping)} if isinstance(
        request, list) else set()
    _require(topic in request_topics,
             "sensed_stop.exclusion.topic must be a topic the request publishes: the watch reads a later "
             "competing command and is not a confirmation source")
    return Exclusion(topic, ros_type, tuple(paths))


def compile_profile(raw: Mapping[str, Any]) -> Profile:
    """The sources, predicate and bounds of a ``sensed_stop`` declaration (numbers already resolved)."""
    _require(isinstance(raw, Mapping) and all(isinstance(key, str) for key in raw),
             "safety_bindings.sensed_stop must be an object")
    _require(not set(raw) - _PROFILE_KEYS, f"safety_bindings.sensed_stop: unknown keys {sorted(set(raw) - _PROFILE_KEYS)}")
    ros_version = raw.get("ros_version")
    _require(type(ros_version) is int and ros_version in (1, 2),
             "sensed_stop.ros_version must be 1 or 2 (RosDriver sets it from its ros_version)")
    sources_raw = raw.get("sources")
    _require(isinstance(sources_raw, Mapping) and 1 <= len(sources_raw) <= MAX_SOURCES,
             f"sensed_stop.sources must map 1 to {MAX_SOURCES} source names to topic subscriptions")
    terms_raw = raw.get("predicate")
    _require(isinstance(terms_raw, list) and 1 <= len(terms_raw) <= MAX_TERMS,
             f"sensed_stop.predicate must be a list of 1 to {MAX_TERMS} terms")
    terms = tuple(_term(item, index, sources_raw) for index, item in enumerate(terms_raw))
    names = [term.name for term in terms if term.name is not None]
    _require(len(names) == len(set(names)), "sensed_stop.predicate: term names must be unique")
    sources: dict[str, Source] = {}
    for name, spec in sources_raw.items():
        label = f"sensed_stop.sources[{name!r}]"
        _require(isinstance(name, str) and _IDENT.fullmatch(name) is not None,
                 f"{label}: a source name is [a-z][a-z0-9_]* (at most 64 characters)")
        _require(isinstance(spec, Mapping) and not set(spec) - _SOURCE_KEYS,
                 f"{label} must be an object with only {sorted(_SOURCE_KEYS)}")
        topic, ros_type = spec.get("topic"), spec.get("type")
        _require(isinstance(topic, str) and _TOPIC.fullmatch(topic) is not None and len(topic) <= 512,
                 f"{label}.topic must be an absolute ROS topic name")
        _require(isinstance(ros_type, str) and _TYPE.fullmatch(ros_type) is not None,
                 f"{label}.type must be a ROS message type")
        freshness = spec.get("freshness", "stamp")
        _require(freshness in FRESHNESS, f"{label}.freshness must be one of {list(FRESHNESS)}")
        throttle = spec.get("throttle_ms")
        if throttle is not None:
            throttle = _int(throttle, f"sources[{name!r}].throttle_ms", minimum=1, maximum=60_000)
        min_interval: int | None = None
        if freshness == "arrival":
            # A producer that does not stamp cannot show that a transient-local replay, or a ROS 1 latch, is older
            # than the subscription.  Only a cited volatile ROS 2 publisher, plus the burst rule, is accepted.
            _require("stamp_path" not in spec, f"{label}: an arrival source has no stamp_path (freshness is the "
                     "arrival time)")
            _require(ros_version == 2, f"{label}: arrival freshness is ROS 2 only")
            interval = spec.get("min_interval_ms")
            _require(type(interval) is int and MIN_INTERVAL_MS <= interval <= MAX_INTERVAL_MS,
                     f"{label}.min_interval_ms must be an integer from {MIN_INTERVAL_MS} to {MAX_INTERVAL_MS}")
            min_interval = int(interval)
            stamp_path = ""
        else:
            _require("min_interval_ms" not in spec, f"{label}.min_interval_ms is only for freshness 'arrival'")
            _require(not headerless_type(ros_type), f"{label}: {ros_type} carries no producer stamp (no header); a "
                     "stamp source needs a stamped message type, or freshness 'arrival' on a cited volatile publisher")
            stamp_path = spec.get("stamp_path", "header.stamp")
            _require(isinstance(stamp_path, str) and _FIELD.fullmatch(stamp_path) is not None,
                     f"{label}.stamp_path must be a field path")
        fields: dict[str, bool] = {}
        for term in terms:
            if term.source != name:
                continue
            for path in term.paths:
                fields[path] = fields.get(path, False) or term.numeric
                if stamp_path:
                    _require(path != stamp_path and not path.startswith(stamp_path + "."),
                             f"{label}: a predicate term cannot read the producer stamp")
        _require(bool(fields), f"{label}: no predicate term reads this source")
        # Verification F1 (phase 3): only samples provably published after the subscription was opened count.
        # Every ROS 1 stamp sample is discarded: a producer stamp is not a freshness proof.
        # A ROS 2 one replays the history its publisher keeps for late subscribers, which only a declaration can show.
        if freshness == "arrival":
            _require("history" in spec and isinstance(spec.get("history"), Mapping)
                     and spec["history"].get("durability") == "volatile" and set(spec["history"]) == {"durability"},
                     f"{label}.history must be {{'durability': 'volatile'}}: a transient_local replay spaced at least "
                     "min_interval_ms apart cannot be told from live samples without a producer stamp")
            replay = 0
        elif ros_version == 1:
            _require("history" not in spec, f"{label}.history is a ROS 2 durability: every ROS 1 stamp sample is "
                     "discarded, and a producer stamp is not a freshness proof")
            replay = 1
        else:
            _require("history" in spec, f"{label}: a ROS 2 source declares its publisher's history (durability "
                     "'volatile', or 'transient_local' with its depth): a new subscription replays that history, "
                     "and without it no sample is provably newer than the request")
            replay = replay_bound(spec["history"], where=f"{label}.history")
        sources[name] = Source(name, topic, ros_type, stamp_path, throttle, tuple(sorted(fields.items())), replay,
                               freshness, min_interval)
    for term in terms:
        if term.kind == "equals" and dict(sources[term.source].fields).get(term.paths[0]):
            raise SensedConfigError(f"sensed_stop.predicate: {term.source}.{term.paths[0]} is compared with equals "
                                    "and with a numeric threshold; use one kind of term per field")
    consecutive = _int(raw.get("consecutive", 3), "consecutive", minimum=MIN_CONSECUTIVE, maximum=MAX_CONSECUTIVE)
    min_span_ms = _int(raw.get("min_span_ms", 0), "min_span_ms", minimum=0, maximum=MAX_BOUND_MS)
    max_gap_ms = _int(raw.get("max_gap_ms"), "max_gap_ms", minimum=1, maximum=MAX_BOUND_MS)
    confirm_within_ms = _int(raw.get("confirm_within_ms"), "confirm_within_ms", minimum=1, maximum=MAX_BOUND_MS)
    for source in sources.values():
        if source.freshness == "arrival" and source.min_interval_ms is not None:
            _require(confirm_within_ms >= consecutive * source.min_interval_ms,
                     f"sensed_stop.confirm_within_ms must hold {consecutive} samples of {source.name!r} spaced by "
                     f"min_interval_ms ({source.min_interval_ms})")
    description = raw.get("description")
    _require(isinstance(description, str) and description.strip() and len(description) <= 500,
             "sensed_stop.description states the sensed safe state in one sentence (at most 500 characters)")
    exclusion = _exclusion(raw.get("exclusion"), raw.get("request"))
    return Profile(ros_version, sources, terms, consecutive, min_span_ms, max_gap_ms, confirm_within_ms,
                   description, exclusion)


def read_stamp(message: Any, path: str, ros_version: int) -> int:
    """The producer stamp of a sample in integer nanoseconds; ``ValueError`` when missing, malformed or zero."""
    try:
        stamp = get_path(message, path)
    except KeyError as exc:
        raise ValueError("missing producer stamp") from exc
    keys = ("secs", "nsecs") if ros_version == 1 else ("sec", "nanosec")
    if not isinstance(stamp, Mapping) or set(stamp) != set(keys):
        raise ValueError(f"the producer stamp is not a ROS {ros_version} time ({keys[0]}, {keys[1]})")
    seconds, nanos = stamp[keys[0]], stamp[keys[1]]
    if type(seconds) is not int or type(nanos) is not int or seconds < 0 or not 0 <= nanos < _NS:
        raise ValueError("the producer stamp is not a non-negative integer time")
    total = seconds * _NS + nanos
    if total == 0:
        raise ValueError("the producer stamp is unset (zero)")
    return total


def stamp_text(stamp: int | None) -> str | None:
    """A stamp in nanoseconds as ``seconds.nanoseconds`` (exact)."""
    if stamp is None:
        return None
    return f"{stamp // _NS}.{stamp % _NS:09d}"


class Ring:
    """Bounded retention of one confirmation subscription's samples (arrival order); notes an overflow.

    Every sample gets its arrival ordinal on the subscription (1, 2, ...) before anything is dropped, so a sample
    the ring loses still counts towards the replay the window discards (verification F1), and live samples after
    a lossy replay are counted from their true position.
    """

    __slots__ = ("items", "capacity", "overflowed", "total")

    def __init__(self, capacity: int):
        # (message, received_at, ordinal, continuation). continuation: this sample was already queued when the
        # previous one was taken (BL-17). A 2-tuple append means continuation False.
        self.items: deque[tuple[Any, float, int, bool]] = deque()
        self.capacity = capacity
        self.overflowed = False
        #: samples the subscription delivered so far, retained or not
        self.total = 0

    def append(self, item: tuple[Any, float] | tuple[Any, float, bool]) -> None:
        self.total += 1
        continuation = bool(item[2]) if len(item) > 2 else False
        if len(self.items) >= self.capacity:
            self.items.popleft()
            self.overflowed = True  # a lost sample breaks the window: the count restarts
        self.items.append((item[0], item[1], self.total, continuation))


@dataclass
class SourceWindow:
    """The counted window of one source in one attempt (fed in arrival order)."""

    source: Source
    terms: tuple[Term, ...]
    profile: Profile
    not_before: float
    #: Recorded at subscribe.  A ROS 1 producer stamp is not compared with it: no proven clock offset exists.
    fresh_after_ns: int = 0
    #: the arrival ordinal of the latest sample on the subscription (samples the ring lost included)
    received: int = 0
    seen: int = 0
    last_stamp: int | None = None
    last_arrival: float | None = None
    counted: deque = field(default_factory=deque)
    last_reset: str | None = None
    invalid: str | None = None
    #: ROS 1 stamp samples discarded because a producer stamp is not a freshness proof
    replay_discarded: int = 0

    @property
    def discarded(self) -> int:
        """Samples never counted: the ROS 2 or arrival replay prefix, or every discarded ROS 1 stamp."""
        if self.profile.ros_version == 1 and self.source.freshness != "arrival":
            return self.replay_discarded
        return min(self.received, self.source.skip)

    def overflow(self) -> None:
        self.counted.clear()
        self.last_reset = "gap"

    def _opening_discard(self) -> bool:
        """True when this sample is the declared ROS 2 or arrival replay prefix and must not count.

        A ROS 1 stamp source does not use a prefix count or a queue flag.  ``_ros1_replay`` discards every ROS 1
        stamp sample: a producer stamp is not a freshness proof.
        """
        if self.profile.ros_version == 1 and self.source.freshness != "arrival":
            return False
        return self.received <= self.source.skip

    def _ros1_replay(self, message: Any) -> bool:
        """True when a ROS 1 stamp sample is not a freshness proof and must not count.

        The bridge has no proven offset between a producer clock and its wall clock.  A stamp after subscribe,
        including one a second ahead, a ROS simulation clock, a delayed latch, and a frame from a transport that
        cannot report its buffer, can be a pre-request sample.  A fixed lead is not that proof.  The sample is
        discarded, does not update ``last_stamp``, and does not refresh counted freshness.  ``continuation`` is
        not consulted.
        """
        if self.profile.ros_version != 1 or self.source.freshness == "arrival":
            return False
        try:
            read_stamp(message, self.source.stamp_path, 1)
        except ValueError:
            pass
        self.replay_discarded += 1
        return True

    def _read_values(self, message: Any) -> dict[str, Any] | None:
        """The predicate fields, or ``None`` after setting ``invalid``."""
        values: dict[str, Any] = {}
        for path, numeric in self.source.fields:
            try:
                value = get_path(message, path)
            except KeyError:
                self.invalid = f"{self.source.name}: field {path} is missing"
                return None
            if numeric:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    self.invalid = f"{self.source.name}: field {path} is not a finite number"
                    return None
            elif not isinstance(value, (bool, int, float, str)) or (
                    isinstance(value, float) and not math.isfinite(value)):
                self.invalid = f"{self.source.name}: field {path} is not a scalar"
                return None
            values[path] = value
        for term in self.terms:
            if term.kind == "equals" and type(values[term.paths[0]]) is not type(term.equals):
                self.invalid = f"{self.source.name}: field {term.paths[0]} has another type than the predicate"
                return None
        return values

    def add(self, message: Any, received_at: float, ordinal: int | None = None, *,
            continuation: bool = False) -> None:
        """Count one sample; sets ``invalid`` (the attempt then ends) on a sample that breaks the rules.

        ``ordinal`` is the sample's arrival ordinal on the subscription (:class:`Ring`); without one the window
        counts the samples it is given.  ``continuation`` is accepted and ignored: a queue flag is not a freshness
        proof for a ROS 1 latch.
        """
        del continuation  # a queued-or-not flag cannot prove a latch has or has not arrived
        if self.invalid is not None:
            return
        self.received = ordinal if ordinal is not None else self.received + 1
        previous_arrival = self.last_arrival
        if self._ros1_replay(message):
            return  # a discarded replay does not refresh the newest counted sample
        self.last_arrival = received_at
        if self._opening_discard():
            if self.source.freshness != "arrival":
                # The newest readable stamp among discarded samples is the baseline a counted sample must exceed.
                try:
                    stamp = read_stamp(message, self.source.stamp_path, self.profile.ros_version)
                except ValueError:
                    return
                if self.last_stamp is None or stamp > self.last_stamp:
                    self.last_stamp = stamp
            return
        if received_at < self.not_before:
            return  # arrived before the request: not counted
        self.seen += 1
        stamp: int | None
        if self.source.freshness == "arrival":
            # Every post-discard sample is validated before the burst rule.  A missing, mistyped or non-finite
            # field ends the attempt even when the arrival interval is shorter than min_interval_ms.
            values = self._read_values(message)
            if values is None:
                return
            interval = (self.source.min_interval_ms or 0) / 1000.0
            if previous_arrival is not None and received_at - previous_arrival < interval:
                self.counted.clear()
                self.last_reset = "burst"
                return
            stamp = None
        else:
            try:
                stamp = read_stamp(message, self.source.stamp_path, self.profile.ros_version)
            except ValueError as exc:
                self.invalid = f"{self.source.name}: {exc}"
                return
            values = self._read_values(message)
            if values is None:
                return
        if self.source.freshness != "arrival":
            assert stamp is not None
            if self.last_stamp is not None and stamp < self.last_stamp:
                self.invalid = f"{self.source.name}: the producer stamp went backwards"
                return
            if self.last_stamp is not None and stamp == self.last_stamp:
                self.counted.clear()
                self.last_reset = "duplicate"
                return
            self.last_stamp = stamp
        gap_s = self.profile.max_gap_ms / 1000.0
        if previous_arrival is not None and received_at - previous_arrival > gap_s:
            self.counted.clear()
            self.last_reset = "gap"
        if not all(term.holds(values) for term in self.terms if term.per_sample):
            self.counted.clear()
            self.last_reset = "term"
            return
        self.counted.append((stamp, received_at, values))
        while len(self.counted) > self.profile.consecutive:
            self.counted.popleft()

    def confirmed(self, now: float) -> bool:
        if self.invalid is not None or len(self.counted) < self.profile.consecutive:
            return False
        if self.last_arrival is None or now - self.last_arrival > self.profile.max_gap_ms / 1000.0:
            return False
        if self.source.freshness == "arrival":
            first_at, last_at = self.counted[0][1], self.counted[-1][1]
            if (last_at - first_at) * 1000.0 < self.profile.min_span_ms:
                return False
        else:
            first, last = self.counted[0][0], self.counted[-1][0]
            if (last - first) < self.profile.min_span_ms * 1_000_000:
                return False
        window = [item[2] for item in self.counted]
        return all(term.window_holds(window) for term in self.terms if not term.per_sample)

    def state_holds(self) -> bool:
        """False when the latest samples show the sensed state does not hold (a failing term), whatever the
        freshness: a per-sample term failed since the count restarted, or a full window fails a window term."""
        if self.last_reset == "term" and len(self.counted) < self.profile.consecutive:
            return False
        if len(self.counted) >= self.profile.consecutive:
            window = [item[2] for item in self.counted]
            return all(term.window_holds(window) for term in self.terms if not term.per_sample)
        return True

    def stale(self, now: float) -> bool:
        return (self.last_arrival is None or now - self.last_arrival > self.profile.max_gap_ms / 1000.0
                or self.last_reset in ("gap", "duplicate", "burst"))

    def report(self) -> dict[str, Any]:
        out: dict[str, Any] = {"topic": self.source.topic, "samples": len(self.counted), "seen": self.seen}
        if self.counted and self.counted[0][0] is not None:
            out["first_stamp"] = stamp_text(self.counted[0][0])
            out["last_stamp"] = stamp_text(self.counted[-1][0])
        if self.last_reset is not None:
            out["last_reset"] = self.last_reset
        if self.invalid is not None:
            out["invalid"] = self.invalid[:200]
        return out


def unconfirmed_reason(windows: Mapping[str, SourceWindow], now: float) -> str:
    """Why the bound expired without a confirmation (``sensed_invalid`` and ``superseded`` are decided earlier).

    ``sensed_missing``: a source delivered nothing that counted after its discarded replay (on ROS 1, every stamp
    sample, because a producer stamp is not a freshness proof without a proven clock offset; on ROS 2, the
    declared transient-local history).  ``not_confirmed``: a source's
    latest samples do not satisfy the predicate (the sensed state does not hold, whether or not its stream also
    stopped).  ``sensed_stale``: a stream repeated a stamp, arrived as a burst closer than ``min_interval_ms``,
    paused longer than ``max_gap_ms`` or stopped while its samples held.  Otherwise ``not_confirmed`` (too few
    samples or too short a window).
    """
    if any(window.seen == 0 for window in windows.values()):
        return "sensed_missing"
    if any(not window.state_holds() for window in windows.values()):
        return "not_confirmed"
    if any(window.stale(now) for window in windows.values()):
        return "sensed_stale"
    return "not_confirmed"
