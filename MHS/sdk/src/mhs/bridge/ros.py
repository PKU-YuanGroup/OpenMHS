"""Declarative rosbridge topic/service/action adapter, without importing ROS.

This bridge uses the RobotWebTools rosbridge v2 JSON protocol. Topic messages
are observations; a publish reports transmission only, never goal completion.
Parameter access is an explicit service binding (ROS 1 and ROS 2 differ).
Safety bindings must call a genuine stop service or fixed action and check its
application response. Cancelling an action or closing a WebSocket is not a stop.
Explicit ROS 1 actionlib and ROS 2 native profiles require a correlated
terminal result and application success; uncertain goals are never replayed.

The server owns limits, permits, interlocks and latching. The wire epoch here
only prevents a request queued before an e-stop from being sent afterwards.
"""

from __future__ import annotations

import copy
from collections import deque
from contextlib import contextmanager
import itertools
import json
import math
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from mhs import signals
from mhs.errors import MHSError
from .base import (Bridge, BridgeContext, FieldMapping, MappingError, UnitError,
                   driver_failed, jsonable, make_mhs_error, outcome_unknown, unsupported)
from .base import _ROOT_AFTER_PREFIX, _ROOT_PREFIXES, _ROOT_WORDS, _tokenize
from .ros_transport import RecordingRosTransport, WebSocketTransport, _json_copy
from .ros_actions import (MAX_ACTIONS, MAX_SAFETY_ACTIONS, MAX_SAFETY_HISTORY, PROFILES,
                          PendingAction, SafetyActionTerminal, terminal_identity)
from .transcript import TranscriptDivergence
from . import ros_images, ros_pointcloud, ros_sensed
from ..artifacts import publisher_from_context

__all__ = ["RosBridge", "RecordingRosTransport", "WebSocketTransport"]

#: Provenance metadata of a binding, ignored at run time. ``state_ref`` cites the line that sets or reports the
#: stopped state of an e-stop and its read-back (companion sources, user decision 2026-11-05; gate G7).
_META = {"description", "source_ref", "source_name", "type_ref", "state_ref"}
_CONFIG = {"endpoint", "timeout_s", "max_message_bytes", "commands", "reads", "writes",
           "safety_bindings", "resources", "strict", "description", "metadata"}
_BINDING = {"service", "topic", "action", "profile", "feedback", "type", "request", "message", "args",
            "result", "success", "operation", "timeout_ms", "resource", "safe_state", "image", "point_cloud",
            "then"} | _META
_NAME = re.compile(r"/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*\Z")
_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*/(?:(?:msg|srv)/)?[A-Za-z_][A-Za-z0-9_]*\Z")
_PATH = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+))*\Z")
_SESSIONS = itertools.count(1)
#: A list-element success predicate's ``where`` key: one plain field name of the element (E4).
_FIELD_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
#: The keys of a stall read-back (E1): the field compared across samples, how many, how far apart, unchanged.
_STALL = {"path", "samples", "interval_ms", "unchanged"}
#: The keys of a fresh-sample topic read-back (E2): which samples count, how many in a row, within which bound, and
#: how far apart two counted samples must arrive.
_FRESH = {"after_request", "discard_first", "consecutive", "within_ms", "min_interval_ms"}
#: The keys a fresh-sample topic read-back may carry (with the provenance metadata of :data:`_META`).
_FRESH_BINDING = {"topic", "type", "operation", "success", "fresh"}
#: Samples one fresh-sample read-back subscription retains between two reads of its confirming thread; more is a lost
#: sample, and the attempt ends unconfirmed.
_FRESH_CAPACITY = 64


def _invalid(message: str) -> Exception:
    return make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", message, {"retryable": False})


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise _invalid(f"{label} must be an object with string keys")
    return dict(value)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise _invalid(f"{label} must be a finite positive number")
    return float(value)


def _path(value: Any) -> str:
    if not isinstance(value, str) or (value != "$" and not _PATH.fullmatch(value)):
        raise _invalid("ROS paths must be '$' or dot-separated object keys/array indices")
    return value


#: The raw output fields of a publish-then-step command (``_after_publication``); ``observation`` only with ``observe``.
_THEN_FIELDS = ("published", "confirmed", "step", "stepped")


def _check_then_result(result: FieldMapping | None, then: Mapping[str, Any], label: str) -> None:
    """Refuse a publish-then-step ``result`` path whose first field the command's raw output never carries.

    Such a rule could only fail after the publication and the step were sent, an unknown outcome on every call, so
    it is a declaration defect. The first field is read as ``get_path`` reads it (one ``input.``/``output.``/``args.``
    prefix stripped; a root word names the whole raw value, which is allowed).
    """
    if result is None:
        return
    allowed = set(_THEN_FIELDS) | ({"observation"} if then["observe"] is not None else set())
    for rule in result.rules:
        path = rule.source
        if path is None or path in _ROOT_WORDS:
            continue
        for prefix in _ROOT_PREFIXES:
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        if path in _ROOT_AFTER_PREFIX:
            continue
        try:
            tokens = _tokenize(path)
        except MappingError as exc:
            raise _invalid(f"{label}.result: {exc}") from exc
        if not tokens or tokens[0] not in allowed:
            raise _invalid(f"{label}.result maps {rule.source!r}, but the raw output of a publish-then-step command "
                           f"carries only {sorted(allowed)}")


def _get(value: Any, path: str) -> Any:
    if path == "$":
        return value
    for part in path.split("."):
        if isinstance(value, Mapping):
            value = value[part]
        elif isinstance(value, (list, tuple)) and part.isdigit():
            value = value[int(part)]
        else:
            raise KeyError(path)
    return value


def _put(value: dict[str, Any], path: str, item: Any) -> None:
    parts = path.split(".")
    target = value
    for part in parts[:-1]:
        if part not in target:
            target[part] = {}
        if not isinstance(target[part], dict):
            raise MappingError(f"ROS argument target {path!r} conflicts with a non-object field")
        target = target[part]
    target[parts[-1]] = item


def _equal(left: Any, right: Any) -> bool:
    # Python considers True == 1; an interlock or application success check must not.
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _json_scalar(value: Any) -> bool:
    """A JSON scalar a list-element selector may compare: string, boolean, integer or finite float, never null."""
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, str)


def _one_element(items: Any, selector: Mapping[str, Any]) -> list[int]:
    """Indexes of list elements that match every key of ``selector`` (type-strict)."""
    return [index for index, item in enumerate(items)
            if isinstance(item, Mapping)
            and all(key in item and _equal(item[key], want) for key, want in selector.items())]


def _passes_several(items: Any, selectors: Any, predicate: Mapping[str, Any]) -> bool:
    """Several named elements of one list, each exactly once, all holding ``field == equals``.

    Each selector must match exactly one element, and two selectors must not match the same element. An empty
    selector, a selector that is not an object, no match, several matches or a missing field fails closed.
    """
    if not isinstance(selectors, (list, tuple)) or not selectors:
        return False
    used: set[int] = set()
    for selector in selectors:
        if not isinstance(selector, Mapping) or not selector:
            return False
        chosen = _one_element(items, selector)
        if len(chosen) != 1 or chosen[0] in used:
            return False
        used.add(chosen[0])
        if not _equal(_get(items[chosen[0]], predicate["field"]), predicate["equals"]):
            return False
    return True


def _passes(values: Any, predicate: Mapping[str, Any]) -> bool:
    """The application success predicate on a service response or action result.

    ``{path, equals}``: the value at ``path`` equals ``equals`` (type-strict, :func:`_equal`). ``{path, where, field,
    equals}`` (E4): the value at ``path`` is a list. When ``where`` is one object, exactly one element is an object
    whose keys all equal their values, and that element's ``field`` equals ``equals``. When ``where`` is a list of
    selector objects, each selector matches exactly one distinct element and each of those elements' ``field`` equals
    ``equals``. No element, several for one selector, two selectors on one element, a value that is not a list or a
    missing field is a failure: the predicate never guesses an element.
    """
    try:
        if "where" not in predicate:
            return _equal(_get(values, predicate["path"]), predicate["equals"])
        items = _get(values, predicate["path"])
        if not isinstance(items, (list, tuple)):
            return False
        where = predicate["where"]
        if isinstance(where, (list, tuple)) and not isinstance(where, (str, bytes)):
            return _passes_several(items, where, predicate)
        chosen = [item for item in items if isinstance(item, Mapping)
                  and all(key in item and _equal(item[key], want) for key, want in predicate["where"].items())]
        return len(chosen) == 1 and _equal(_get(chosen[0], predicate["field"]), predicate["equals"])
    except (KeyError, IndexError, TypeError):
        return False


#: The two shapes of a ROS time as rosbridge carries it: ROS 2 ``builtin_interfaces/Time`` and ROS 1 ``time``.
_STAMP_KEYS = ({"sec", "nanosec"}, {"secs", "nsecs"})


def _stall_sample_ok(value: Any) -> bool:
    """Whether a stall read-back sample may confirm a stopped world (E1; integrator edit, Claude Sonnet safety F1).

    Only a finite number, or a ROS time (``{sec, nanosec}`` or ``{secs, nsecs}``, both members integers, the
    nanoseconds in ``[0, 10^9)``), shows a clock that would advance while the world runs. ``null``, an empty value,
    a string, a list, a boolean, any other object and a non-finite number never change in a way that shows anything,
    so they fail closed: the e-stop stays unconfirmed with the latch held.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, Mapping) and set(value) in _STAMP_KEYS:
        seconds, nanoseconds = (value["sec"], value["nanosec"]) if "sec" in value else (value["secs"], value["nsecs"])
        return type(seconds) is int and type(nanoseconds) is int and 0 <= nanoseconds < 1_000_000_000
    return False


def _context(ctx: Any) -> BridgeContext:
    """Pin a relative deadline once so a multi-field operation shares one budget."""
    context = BridgeContext.coerce(ctx)
    extra = dict(context.extra or {})
    extra.setdefault("deadline_at", time.monotonic() + context.remaining_ms() / 1000)
    return BridgeContext.coerce({**context.__dict__, "extra": extra})


@dataclass
class _Pending:
    service: str
    safety: bool
    effectful: bool = False
    sent: bool = False
    abandoned: bool = False
    received_at: float | None = None
    event: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None
    error: BaseException | None = None


@dataclass
class _Stream:
    """The samples of one fresh-sample read-back subscription (E2), in arrival order, bounded."""

    items: deque = field(default_factory=deque)
    #: a sample was dropped because the confirming thread did not read the stream in time
    overflowed: bool = False


@dataclass
class _StopFlight:
    """One stop request of the current e-stop (its ledger, keyed by the request's identity)."""

    stamp: tuple[int, int]
    #: "native" (the bridge's safety bindings) or the capability id of the safe-state command that sent it
    sender: str
    event: threading.Event = field(default_factory=threading.Event)
    ok: bool = False
    values: Any = None


class RosBridge(Bridge):
    """Compile immutable ROS bindings; connect only when a request is made.

    Service bindings: ``service``, optional ``type``, literal ``request``,
    mapped ``args`` and ``result``, and ``success={path, equals}``. Topic
    commands: ``topic``, ``type``, literal ``message`` and mapped ``args``.
    Reads use topic/type/path or service/request/path. Writes use service
    bindings with ``input.value`` and a required success predicate.
    Action commands declare ``action/type/profile``, literal ``request``,
    mapped ``args/result`` and required ``success``. Their lifetime uses the
    caller's execution budget; optional ``timeout_ms`` can narrow it. The
    profiles are ``ros1-actionlib`` and ``ros2-native``, never auto-detected.

    ``safety_bindings.sensed_stop`` (SAFE-049, CORE-088) is the stop of a
    simulated device whose only stop is a request: 1 to 3 fixed request
    steps (a service call with its success predicate, or a fixed topic
    publication), sent on the safety lane, then a bounded confirmation over
    stamped topic samples (:mod:`mhs.bridge.ros_sensed`).  The bridge compiles
    it only with ``device_mode="simulated"``, and that argument never grants
    it: a confirmation commits a safe state only after the endpoint bound the
    bridge to a device its served manifest declares ``simulated``
    (:meth:`_bind_served_mode`, called by :class:`mhs.server.MHSServer` on the
    SDK's own ROS route; verification F3 of phase 3).  It excludes the
    ``estop`` and ``safe_state`` bindings and safe-state commands.

    ``safety_bindings.safe_state`` may instead be a fresh-sample topic read-back
    (E2, :meth:`_fresh_read_back`): a subscription opened after the stop request
    whose boolean state flag must hold in ``consecutive`` fresh samples.
    """

    bridge_kind = "ros"
    bridge_id = "mhs.bridge.ros"

    def __init__(self, config: Mapping[str, Any], *, device_id: str | None = None, transport: Any = None,
                 capability_schemas: Mapping[str, Mapping[str, Any]] | None = None, device_mode: str | None = None):
        super().__init__(device_id=device_id)
        config = _object(config, "ROS config")
        if set(config) - _CONFIG:
            raise _invalid(f"unknown ROS config keys: {sorted(set(config) - _CONFIG)}")
        self.config = copy.deepcopy(config)
        # Trusted resolved capability contracts are constructor data, never
        # request/context metadata. Copy them before any native operation.
        self._schemas = {name: copy.deepcopy(_object(schema, f"capability_schemas[{name!r}]"))
                         for name, schema in _object(capability_schemas or {}, "capability_schemas").items()}
        self._timeout_s = _number(config.get("timeout_s", 2.0), "timeout_s")
        self._max_message_bytes = config.get("max_message_bytes", 1048576)
        if (isinstance(self._max_message_bytes, bool) or not isinstance(self._max_message_bytes, int)
                or self._max_message_bytes < 256):
            raise _invalid("max_message_bytes must be an integer of at least 256")
        endpoint = config.get("endpoint")
        if transport is None and endpoint is None:
            raise _invalid("ROS config needs endpoint or an injected transport")
        try:
            self._transport = transport if transport is not None else WebSocketTransport(
                endpoint, timeout_s=self._timeout_s, max_message_bytes=self._max_message_bytes)
        except (TypeError, ValueError) as exc:
            raise _invalid(str(exc)) from exc
        self._commands = {name: self._command(spec, name)
                          for name, spec in _object(config.get("commands", {}), "commands").items()}
        for name, binding in self._commands.items():
            if binding["image"] is not None and name != "cap.sensing.image.v1":
                raise _invalid("image conversion belongs to cap.sensing.image.v1")
            if binding["point_cloud"] is not None and name != "cap.sensing.point_cloud.v1":
                raise _invalid("point-cloud conversion belongs to cap.sensing.point_cloud.v1")
        self._reads = self._resource_map(config.get("reads", {}), "reads", "fields")
        self._writes = self._resource_map(config.get("writes", {}), "writes", "params")
        self._check_resources(config.get("resources"))
        raw_safety = _object(config.get("safety_bindings", {}), "safety_bindings")
        self._safety = self._compile_safety({name: spec for name, spec in raw_safety.items() if name != "sensed_stop"})
        #: the sensed-confirmation stop (SAFE-049): its request steps and the compiled confirmation profile
        self._sensed: ros_sensed.Profile | None = None
        self._sensed_steps: list[dict[str, Any]] = []
        if "sensed_stop" in raw_safety:
            self._compile_sensed(raw_safety["sensed_stop"], device_mode)
        #: confirmation subscription id -> its bounded sample ring (filled by the receiver)
        self._sensed_rings: dict[str, ros_sensed.Ring] = {}
        #: Exclusion subscription ids. A status error on one of them is not proof the competing command stopped.
        self._sensed_exclusion_ids: set[str] = set()
        self._sensed_faults: set[str] = set()
        #: Recorded for the receiver. A queue flag is not a ROS 1 freshness proof (BL-17): a producer stamp is not one either.
        self._next_already_queued = False
        #: the report of the last confirmation (an e-stop attempt or a reset's re-confirmation)
        self._sensed_last: dict[str, Any] | None = None
        #: SAFE-049 / CORE-088 (verification F3): the device mode the endpoint serves this bridge's device with, bound
        #: by the server from the served manifest; ``None`` until then. Only ``"simulated"`` lets a sensed
        #: confirmation commit a safe state; the constructor's ``device_mode`` never grants it.
        self._served_mode: str | None = None
        self._pending: dict[str, _Pending] = {}
        self._actions: dict[str, PendingAction] = {}
        self._safety_history: dict[str, SafetyActionTerminal] = {}
        self._safety_goal_prefix = "mhs-safety-" + uuid.uuid4().hex + "-"
        self._safety_goal_sequence = 0
        self._safety_retired_through = 0
        self._safety_reconciliation_needed = False
        self._safety_reconcile_generation = 0
        self._safety_history_error: BaseException | None = None
        self._safety_retirement_failed = False
        self._topics: dict[str, tuple[Any, float]] = {}
        self._topic_ids: dict[str, set[str]] = {}
        #: the open fresh-sample read-back subscriptions (E2), by subscription id: they keep every sample
        self._streams: dict[str, _Stream] = {}
        self._condition = threading.Condition()
        self._wire_lock = threading.Lock()
        self._txn_lock = threading.Lock()
        self._safety_action_lock = threading.Lock()
        self._has_action_safety = any(spec["kind"] == "action" for name, spec in self._safety.items()
                                      if name != "interlocks") or any(
            spec["safe_state"] and spec["kind"] == "action" for spec in self._commands.values())
        self._reader_lock = threading.Lock()
        self._reader: threading.Thread | None = None
        self._reader_entered = threading.Event()
        self._stop_reader = threading.Event()
        self._fatal: BaseException | None = None
        self._ids = itertools.count(1)
        self._prefix = f"mhs-{next(_SESSIONS)}-"
        self._safe_state_achieved = False
        self._native_activity = 0
        self._safe_stamp: tuple[int, int] | None = None
        self._safety_finished_epoch = 0
        self._safety_confirmed_epoch = 0
        #: the stop requests the current e-stop sent (opened by estop(); see _shared_stop)
        self._stop_ledger_epoch = -1
        self._stop_ledger: dict[str, _StopFlight] = {}

    def _command(self, raw: Any, capability_id: str) -> dict[str, Any]:
        label = f"commands[{capability_id!r}]"
        spec = _object(raw, label)
        if "cameras" not in spec:
            return self._binding(spec, label, command=True)
        if (capability_id != "cap.sensing.image.v1"
                or set(spec) - {"cameras", "resource", "safe_state", "description"}
                or spec.get("safe_state", False) is not False):
            raise _invalid("cameras requires an ordinary image command with only static source bindings")
        try:
            sources = ros_images.camera_sources(spec["cameras"])
        except ValueError as exc:
            raise _invalid(str(exc)) from exc
        cameras = {}
        for name, source in sources.items():
            if "resource" in source or "image" not in source:
                raise _invalid(f"{label}.cameras[{name!r}] needs an image subscription without a resource override")
            bound = self._binding({**source, "resource": spec.get("resource")},
                                  f"{label}.cameras[{name!r}]", command=True)
            if len(bound["name"]) > 512:
                raise _invalid("image source topic exceeds 512 characters")
            cameras[name] = bound
        return {"cameras": cameras, "image": None, "point_cloud": None, "safe_state": False, "kind": "topic",
                "operation": "subscribe", "resource": spec.get("resource"),
                "name": {name: bound["name"] for name, bound in cameras.items()}}

    def _where_list(self, raw: list[Any], label: str) -> list[dict[str, Any]]:
        """2 to 4 selector objects that each pick a different element of one list (E4, several elements).

        One selector stays an object, so a one-element list is refused. Five or more, an empty selector, a selector
        that is not an object, a dotted key, a non-scalar value and two equal selectors are refused: equal selectors
        can never both match a distinct element.
        """
        if not 2 <= len(raw) <= 4:
            raise _invalid(f"{label}.success.where list needs 2 to 4 selectors (one selector stays an object)")
        selectors: list[dict[str, Any]] = []
        for index, item in enumerate(raw):
            selector = _object(item, f"{label}.success.where[{index}]")
            if (not 1 <= len(selector) <= 4 or any(not _FIELD_NAME.fullmatch(key) for key in selector)
                    or any(not _json_scalar(value) for value in selector.values())):
                raise _invalid(f"{label}.success.where[{index}] needs 1 to 4 plain field names with JSON scalar "
                               "values")
            if any(_equal(selector, earlier) for earlier in selectors):
                raise _invalid(f"{label}.success.where repeats a selector; two equal selectors cannot match two "
                               "elements")
            selectors.append(dict(selector))
        return selectors

    def _binding(self, raw: Any, label: str, *, read: bool = False, success_required: bool = False,
                 command: bool = False, safety_stop: bool = False) -> dict[str, Any]:
        spec = _object(raw, label)
        if label == "safety_bindings.safe_state" and "fresh" in spec:
            return self._fresh_read_back(spec, label)
        allowed = (_BINDING | ({"path"} if read or spec.get("operation") == "subscribe" else set())
                   | ({"stall"} if label == "safety_bindings.safe_state" else set()))
        if set(spec) - allowed:
            raise _invalid(f"unknown {label} keys: {sorted(set(spec) - allowed)}")
        kinds = [name for name in ("service", "topic", "action") if name in spec]
        if len(kinds) != 1:
            raise _invalid(f"{label} needs exactly one service, topic or action")
        kind = kinds[0]
        if kind == "action" and (read or not (command or safety_stop)):
            raise _invalid(f"{label}: actions are commands or fixed safety stops, never reads, writes or reset")
        if kind != "action" and any(key in spec for key in ("profile", "feedback")):
            raise _invalid(f"{label}: profile and feedback belong only to action bindings")
        if "safe_state" in spec and type(spec["safe_state"]) is not bool:
            raise _invalid(f"{label}.safe_state must be boolean")
        if (spec.get("safe_state") or safety_stop) and (kind not in ("service", "action") or spec.get("args")):
            raise _invalid(f"{label}: a safe-state stop needs a service or action with fixed request arguments")
        success_required = success_required or spec.get("safe_state", False)
        operation = spec.get("operation", ("subscribe" if read else "publish") if kind == "topic" else
                             ("read" if read else "call"))
        allowed_ops = (("subscribe", "publish") if kind == "topic" else
                       (("call",) if kind == "action" else ("read", "call")))
        if operation not in allowed_ops:
            raise _invalid(f"{label}.operation must be one of {allowed_ops}")
        if spec.get("safe_state") and operation != "call":
            raise _invalid(f"{label}: safe_state requires a call, not an observation")
        if command and kind in ("service", "action") and operation != "read":
            success_required = True
        if read and kind == "topic" and operation != "subscribe":
            raise _invalid(f"{label}: a topic read must subscribe")
        if read and kind == "service" and operation != "read":
            raise _invalid(f"{label}: a service read must declare an observation")
        if success_required and operation != "call":
            raise _invalid(f"{label}: writes and safety bindings require a service call")
        if operation == "subscribe" and any(key in spec for key in ("message", "args")):
            raise _invalid(f"{label}: a subscription has no outbound message or mapped args")
        if not isinstance(spec[kind], str) or not _NAME.fullmatch(spec[kind]):
            raise _invalid(f"{label}.{kind} must be an absolute ROS name")
        if kind == "action":
            profile = spec.get("profile")
            if not isinstance(profile, str) or profile not in PROFILES:
                raise _invalid(f"{label}.profile must be ros1-actionlib or ros2-native")
            if not isinstance(spec.get("type"), str) or not PROFILES[profile].fullmatch(spec["type"]):
                raise _invalid(f"{label}.type must match the explicit action profile")
            if "feedback" in spec and type(spec["feedback"]) is not bool:
                raise _invalid(f"{label}.feedback must be boolean")
        elif "type" in spec and (not isinstance(spec["type"], str) or not _TYPE.fullmatch(spec["type"])):
            raise _invalid(f"{label}.type must be a ROS message/service type")
        if kind == "topic" and not read and "type" not in spec:
            raise _invalid(f"{label}: topic publishing needs a declared type")
        if kind == "topic" and any(key in spec for key in ("request", "success")):
            raise _invalid(f"{label}: a topic has no service request/response success")
        if kind in ("service", "action") and "message" in spec:
            raise _invalid(f"{label}: use request for a service or action")
        if read and any(key in spec for key in ("message", "args", "result")):
            raise _invalid(f"{label}: a read uses a literal request and path, not message/args/result")
        for key in _META:
            if key in spec and (not isinstance(spec[key], str) or not spec[key].strip()):
                raise _invalid(f"{label}.{key} must be a non-empty string")
        payload_key = "request" if kind in ("service", "action") else "message"
        try:
            payload = _json_copy(spec.get(payload_key, {}), max_bytes=self._max_message_bytes)
            args = FieldMapping(spec.get("args"), direction="input", required_by_default=True)
            for target in args.targets:
                if _path(target) == "$" or any(part.isdigit() for part in target.split(".")):
                    raise _invalid(f"{label}: argument targets must be object field paths")
            result = (FieldMapping(spec["result"], direction="output", required_by_default=True)
                      if "result" in spec else None)
        except (TypeError, ValueError, MappingError, UnitError) as exc:
            raise _invalid(f"{label}: invalid JSON or mapping: {exc}") from exc
        success = spec.get("success")
        if success is not None:
            success = _object(success, f"{label}.success")
            if set(success) not in ({"path", "equals"}, {"path", "where", "field", "equals"}):
                raise _invalid(f"{label}.success needs exactly path and equals, or path, where, field and equals (one "
                               "element of a list, or 2 to 4 elements, selected by the values of its fields)")
            _path(success["path"])
            if "where" in success:
                raw_where = success["where"]
                if isinstance(raw_where, list):
                    where_list = self._where_list(raw_where, label)
                else:
                    where = _object(raw_where, f"{label}.success.where")
                    if (not 1 <= len(where) <= 4 or any(not _FIELD_NAME.fullmatch(key) for key in where)
                            or any(not _json_scalar(value) for value in where.values())):
                        raise _invalid(f"{label}.success.where needs 1 to 4 plain field names with JSON scalar values")
                    where_list = None
                if not isinstance(success["field"], str) or success["field"] == "$" or _path(success["field"]) == "$":
                    raise _invalid(f"{label}.success.field must be a field path of the selected element")
                success = {"path": success["path"],
                           "where": where_list if where_list is not None else dict(where),
                           "field": success["field"], "equals": success["equals"]}
            try:
                _json_copy({"value": success["equals"]}, max_bytes=self._max_message_bytes)
            except (ValueError, TypeError) as exc:
                raise _invalid(f"{label}.success.equals must be JSON") from exc
        if success_required and (kind not in ("service", "action") or success is None):
            raise _invalid(f"{label} requires an explicit application success predicate")
        image = None
        if "image" in spec:
            if (not command or read or kind != "topic" or operation != "subscribe"
                    or spec.get("safe_state") or "result" in spec or spec.get("path", "$") != "$"):
                raise _invalid(f"{label}: image conversion requires a full topic subscription command")
            try:
                image = ros_images.image_config(spec["image"], spec.get("type"))
            except ValueError as exc:
                raise _invalid(str(exc)) from exc
        point_cloud = None
        if "point_cloud" in spec:
            if (not command or read or kind != "topic" or operation != "subscribe"
                    or spec.get("safe_state") or any(key in spec for key in ("image", "result", "message", "args"))
                    or spec.get("path", "$") != "$" or len(spec[kind]) > 512):
                raise _invalid(f"{label}: point_cloud requires a fixed full-topic subscription command")
            try:
                point_cloud = ros_pointcloud.pointcloud_config(spec["point_cloud"], spec.get("type"))
            except ValueError as exc:
                raise _invalid(str(exc)) from exc
        then = None
        if "then" in spec:
            if (not command or read or kind != "topic" or operation != "publish" or spec.get("safe_state")
                    or image is not None or point_cloud is not None):
                raise _invalid(f"{label}.then belongs only to an ordinary topic publication command")
            then = self._then(spec["then"], f"{label}.then")
            _check_then_result(result, then, label)
        timeout = (None if kind == "action" and "timeout_ms" not in spec else
                   _number(spec.get("timeout_ms", self._timeout_s * 1000), f"{label}.timeout_ms") / 1000)
        stall = self._stall(spec, label, kind, success) if "stall" in spec else None
        return {"kind": kind, "name": spec[kind], "type": spec.get("type"), "payload": payload, "stall": stall,
                "fresh": None, "operation": operation, "image": image, "point_cloud": point_cloud,
                "profile": spec.get("profile"), "feedback": spec.get("feedback", False),
                "safe_state": spec.get("safe_state", False),
                "args": args, "result": result, "success": success, "timeout": timeout,
                "path": _path(spec.get("path", "$")), "resource": spec.get("resource"),
                "description": spec.get("description", ""), "then": then}

    def _then(self, raw: Any, label: str) -> dict[str, Any]:
        """Compile the stages that follow a publication: a required ``step`` and an optional ``observe``.

        ``step`` is an effectful service call with a literal request and an application ``success`` predicate
        (it takes no mapped input: the command's input belongs to the publication). ``observe`` is a read
        binding, a fresh topic sample or an observational service, taken after the step was acknowledged.
        Neither stage may name a resource (routing belongs to the command) or carry its own ``then``.
        """
        spec = _object(raw, label)
        if "step" not in spec or set(spec) - {"step", "observe"}:
            raise _invalid(f"{label} needs a step and may add observe, nothing else")
        for name, stage in spec.items():
            stage = _object(stage, f"{label}.{name}")
            # The command's own result maps the stages' raw values; a stage-level result would be silently unused.
            if any(key in stage for key in ("resource", "safe_state", "then", "image", "point_cloud", "args", "result")):
                raise _invalid(f"{label}.{name} takes no resource, safe_state, then, image, point_cloud, args or "
                               "result (the command's result maps every stage)")
        step = self._binding(spec["step"], f"{label}.step", command=True)
        if step["kind"] != "service" or step["operation"] != "call" or step["success"] is None:
            raise _invalid(f"{label}.step must be an acknowledged service call with an application success predicate")
        observe = None
        if "observe" in spec:
            observe = self._binding(spec["observe"], f"{label}.observe", read=True)
        return {"step": step, "observe": observe}

    @staticmethod
    def _stall(spec: Mapping[str, Any], label: str, kind: str, success: Any) -> dict[str, Any]:
        """The stall read-back of ``safety_bindings.safe_state`` (E1): a service whose answer carries a value that
        advances while the world runs (gazebo_ros ``get_model_list``'s ``header.stamp``, the world's sim time).

        ``{path, samples, interval_ms, unchanged: true}``: the read-back is called ``samples`` (2 to 4) times, each
        call at least ``interval_ms`` (100 to 2000) after the previous answer arrived, every answer must satisfy the
        success predicate, and the value at ``path`` must be the same in all of them. Only a fixed service call with a
        success predicate takes one.
        """
        if kind != "service" or spec.get("operation", "call") != "call" or spec.get("args") or success is None:
            raise _invalid(f"{label}.stall needs a fixed service call with a success predicate")
        stall = _object(spec["stall"], f"{label}.stall")
        if set(stall) != _STALL:
            raise _invalid(f"{label}.stall needs exactly path, samples, interval_ms and unchanged")
        if _path(stall["path"]) == "$":
            raise _invalid(f"{label}.stall.path must name the field that advances while the world runs")
        samples, interval = stall["samples"], stall["interval_ms"]
        if type(samples) is not int or not 2 <= samples <= 4:
            raise _invalid(f"{label}.stall.samples must be an integer from 2 to 4")
        if (isinstance(interval, bool) or not isinstance(interval, (int, float)) or not math.isfinite(interval)
                or not 100 <= interval <= 2000):
            raise _invalid(f"{label}.stall.interval_ms must be a number from 100 to 2000")
        if stall["unchanged"] is not True:
            raise _invalid(f"{label}.stall.unchanged must be true (the value must not change between samples)")
        return {"path": stall["path"], "samples": samples, "interval_ms": float(interval), "unchanged": True}

    def _fresh_read_back(self, spec: Mapping[str, Any], label: str) -> dict[str, Any]:
        """The fresh-sample topic read-back of ``safety_bindings.safe_state`` (E2).

        Some simulators report their paused flag only on a topic: gz-sim publishes ``WorldStatistics.paused`` on
        ``/world/<name>/stats``, and the reply of its WorldControl request is true for any queued request. The
        read-back is then ``{topic, type, operation: 'subscribe', success: {path, equals: <boolean>}, fresh}``
        with ``fresh = {after_request: true, discard_first: true, consecutive: 2..5, within_ms: 200..5000,
        min_interval_ms: 10..1000}`` and the provenance metadata; no request, mapping, result or ``timeout_ms`` (the
        bound is ``within_ms``). Only one boolean state flag is compared: freshness is the arrival time, which suits a
        bridged header that carries no producer stamp, and never a motion standstill (a sensed stop keeps producer
        stamps). :meth:`_topic_read_back` runs it.
        """
        if set(spec) - (_FRESH_BINDING | _META):
            raise _invalid(f"unknown {label} keys: {sorted(set(spec) - (_FRESH_BINDING | _META))} (a fresh-sample "
                           "topic read-back takes topic, type, operation, success, fresh and provenance metadata)")
        missing = sorted({"topic", "type", "success", "fresh"} - set(spec))
        if missing:
            raise _invalid(f"{label}: a fresh-sample topic read-back needs {missing}")
        if spec.get("operation", "subscribe") != "subscribe":
            raise _invalid(f"{label}: a fresh-sample topic read-back subscribes (operation 'subscribe')")
        topic = spec["topic"]
        if not isinstance(topic, str) or not _NAME.fullmatch(topic) or len(topic) > 512:
            raise _invalid(f"{label}.topic must be an absolute ROS name")
        if (not isinstance(spec["type"], str) or not _TYPE.fullmatch(spec["type"])
                or "/srv/" in spec["type"]):
            raise _invalid(f"{label}.type must be a ROS message type")
        for key in _META:
            if key in spec and (not isinstance(spec[key], str) or not spec[key].strip()):
                raise _invalid(f"{label}.{key} must be a non-empty string")
        success = _object(spec["success"], f"{label}.success")
        if set(success) != {"path", "equals"}:
            raise _invalid(f"{label}.success needs exactly path and equals")
        if _path(success["path"]) == "$":
            raise _invalid(f"{label}.success.path must name the state flag, not the whole message")
        if type(success["equals"]) is not bool:
            raise _invalid(f"{label}.success.equals must be a boolean: a fresh-sample read-back compares one boolean "
                           "state flag")
        fresh = self._fresh(spec["fresh"], label)
        return {"kind": "topic", "name": topic, "type": spec["type"], "payload": {}, "stall": None, "fresh": fresh,
                "operation": "subscribe", "image": None, "point_cloud": None, "profile": None, "feedback": False,
                "safe_state": False, "args": FieldMapping(None, direction="input", required_by_default=True),
                "result": None, "success": {"path": success["path"], "equals": success["equals"]},
                "timeout": fresh["within_ms"] / 1000.0, "path": "$", "resource": None,
                "description": spec.get("description", "")}

    @staticmethod
    def _fresh(raw: Any, label: str) -> dict[str, Any]:
        """``fresh`` of a topic read-back (E2): which samples count, how many in a row and within which bounds."""
        fresh = _object(raw, f"{label}.fresh")
        if set(fresh) != _FRESH:
            raise _invalid(f"{label}.fresh needs exactly after_request, discard_first, consecutive, within_ms and "
                           "min_interval_ms")
        if fresh["after_request"] is not True or fresh["discard_first"] is not True:
            raise _invalid(f"{label}.fresh.after_request and discard_first must be true: only samples that arrive after "
                           "the stop request returned, after a discarded first sample, count")
        consecutive = fresh["consecutive"]
        if type(consecutive) is not int or not 2 <= consecutive <= 5:
            raise _invalid(f"{label}.fresh.consecutive must be an integer from 2 to 5")
        bounds = {"within_ms": (200, 5000), "min_interval_ms": (10, 1000)}
        for key, (low, high) in bounds.items():
            value = fresh[key]
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                    or not low <= value <= high):
                raise _invalid(f"{label}.fresh.{key} must be a number from {low} to {high}")
        if fresh["within_ms"] < (consecutive + 1) * fresh["min_interval_ms"]:
            raise _invalid(f"{label}.fresh.within_ms must hold the discarded first sample and {consecutive} samples "
                           "min_interval_ms apart: at least (consecutive + 1) x min_interval_ms")
        return {"after_request": True, "discard_first": True, "consecutive": consecutive,
                "within_ms": float(fresh["within_ms"]), "min_interval_ms": float(fresh["min_interval_ms"])}

    def _check_resources(self, raw: Any) -> None:
        """With a declared ``resources`` list, every command, read and write must name one of its resources.

        A composed driver package serves several typed resources through this one bridge; a binding routed to
        an undeclared resource is a configuration defect, refused before any transport use.  Without
        ``resources`` (a directly configured bridge) nothing changes.
        """
        if raw is None:
            return
        if not isinstance(raw, list) or not raw or len(raw) > 8:
            raise _invalid("resources must be a list of one to eight resource objects")
        declared: set[str] = set()
        for index, item in enumerate(raw):
            ident = item.get("resource_id") if isinstance(item, Mapping) else None
            if not isinstance(ident, str) or not ident or ident in declared:
                raise _invalid(f"resources[{index}] needs a unique non-empty resource_id")
            declared.add(ident)
        for name, binding in self._commands.items():
            if binding["resource"] is not None and binding["resource"] not in declared:
                raise _invalid(f"commands[{name!r}] names resource {binding['resource']!r}, which resources does "
                               "not declare")
        for label, mapping in (("reads", self._reads), ("writes", self._writes)):
            for resource in mapping:
                if resource not in declared:
                    raise _invalid(f"{label}[{resource!r}] names a resource that resources does not declare")

    def _resource_map(self, raw: Any, label: str, member: str) -> dict[str, Any]:
        out = {}
        for resource, raw_spec in _object(raw, label).items():
            spec = _object(raw_spec, f"{label}.{resource}")
            if set(spec) != {member}:
                raise _invalid(f"{label}.{resource} needs exactly {member}")
            out[resource] = {name: self._binding(value, f"{label}.{resource}.{name}",
                                               read=label == "reads", success_required=label == "writes")
                             for name, value in _object(spec[member], member).items()}
        return out

    def _compile_safety(self, raw: Any) -> dict[str, Any]:
        raw = _object(raw, "safety_bindings")
        if set(raw) - {"estop", "safe_state", "reset", "interlocks"}:
            raise _invalid("unknown ROS safety binding")
        out = {name: self._binding(spec, f"safety_bindings.{name}", success_required=True,
                                   safety_stop=name in ("estop", "safe_state"))
               for name, spec in raw.items() if name != "interlocks"}
        interlocks = raw.get("interlocks", [])
        if not isinstance(interlocks, list):
            raise _invalid("safety_bindings.interlocks must be an array")
        compiled = []
        seen = set()
        for index, item in enumerate(interlocks):
            item = _object(item, f"interlocks[{index}]")
            ident = item.get("id")
            if not isinstance(ident, str) or not ident or ident in seen:
                raise _invalid("each ROS interlock needs a unique non-empty id")
            seen.add(ident)
            read = {key: value for key, value in item.items() if key not in ("id", "closed_when")}
            closed_when = item.get("closed_when", True)
            if not isinstance(closed_when, (bool, str, int, float)) or (
                    isinstance(closed_when, float) and not math.isfinite(closed_when)):
                raise _invalid("interlock closed_when must be a finite scalar")
            compiled.append((ident, closed_when, self._binding(read, f"interlocks[{index}]", read=True)))
        if compiled:
            out["interlocks"] = compiled
        return out

    def _bind_served_mode(self, mode: Any) -> None:
        """Record the mode the endpoint serves this bridge's device with (SAFE-049, CORE-088; verification F3).

        Called by :class:`mhs.server.MHSServer` (``_bind_sensed_route``) when it serves the device through the SDK's
        own ROS route and the served manifest declares the device ``simulated`` with a sensed confirmation (start-up,
        or first use of a late device). A sensed confirmation commits a safe state only on a bridge bound
        to ``"simulated"``; any other value, or none, keeps it unconfirmed (``not_simulated``). The server never
        unbinds a bridge it serves.
        """
        with self._condition:
            self._served_mode = mode if isinstance(mode, str) else None

    def _compile_sensed(self, raw: Any, device_mode: str | None) -> None:
        """Compile ``safety_bindings.sensed_stop`` (simulated devices only; SAFE-049, CORE-088).

        ``device_mode`` can only refuse (anything but ``"simulated"``); it never grants the stop, which confirms
        only once the endpoint bound the bridge (:meth:`_bind_served_mode`).
        """
        if device_mode != "simulated":
            raise _invalid("safety_bindings.sensed_stop is for simulated devices only: a request plus a sensed "
                           "confirmation is a stop of a simulated RosDriver (device_mode='simulated'), never of "
                           "hardware or a raw adapter file")
        spec = _object(raw, "safety_bindings.sensed_stop")
        if any(name in self._safety for name in ("estop", "safe_state")):
            raise _invalid("safety_bindings.sensed_stop excludes the estop and safe_state bindings (a device with an "
                           "acknowledged stop does not need a sensed confirmation)")
        if any(binding["safe_state"] for binding in self._commands.values()):
            raise _invalid("a device with safety_bindings.sensed_stop declares no safe-state command: only the "
                           "bounded sensed confirmation achieves its safe state")
        steps = spec.get("request")
        if not isinstance(steps, list) or not 1 <= len(steps) <= ros_sensed.MAX_STEPS:
            raise _invalid(f"sensed_stop.request must be a list of 1 to {ros_sensed.MAX_STEPS} fixed request steps")
        compiled = []
        for index, step in enumerate(steps):
            label = f"safety_bindings.sensed_stop.request[{index}]"
            step = _object(step, label)
            if "action" in step:
                raise _invalid(f"{label}: an action goal is not a sensed-stop request step (services and fixed topic "
                               "publications only)")
            if "service" in step:
                binding = self._binding(step, label, success_required=True)
            elif "topic" in step:
                if step.get("operation", "publish") != "publish":
                    raise _invalid(f"{label}: a topic request step publishes a fixed message")
                binding = self._binding(step, label)
            else:
                raise _invalid(f"{label} needs a service or a topic")
            if binding["args"].targets or binding["result"] is not None or binding["image"] is not None:
                raise _invalid(f"{label}: a request step is fixed (no args, result or conversion)")
            compiled.append(binding)
        try:
            profile = ros_sensed.compile_profile(spec)
        except ros_sensed.SensedConfigError as exc:
            raise _invalid(str(exc)) from exc
        published = {binding["name"] for binding in compiled if binding["kind"] == "topic"}
        for source in profile.sources.values():
            if source.topic in published:
                raise _invalid(f"sensed_stop source {source.name!r} reads {source.topic}, a topic the request "
                               "publishes: a request is never its own confirmation")
        self._sensed, self._sensed_steps = profile, compiled

    def _next_id(self) -> str:
        return self._prefix + str(next(self._ids))

    def _start_reader(self) -> None:
        if self._stop_reader.is_set():
            return
        with self._reader_lock:
            if self._stop_reader.is_set():
                return
            if self._reader is None:
                try:
                    # Retain startup ownership even if start raises after the
                    # thread has begun. Close never waits for this startup lock.
                    self._reader = threading.Thread(target=self._receive, name="mhs-ros-receiver", daemon=True)
                    self._reader.start()
                except BaseException as exc:
                    self._stop_reader.set()
                    self._fail_connection(exc)
                    raise outcome_unknown("ROS receiver startup failed after transmission; no automatic reconnect") from exc

    def _fail_connection(self, exc: BaseException) -> None:
        with self._condition:
            self._fatal = exc
            self._invalidate_safety_locked()
            for item in self._pending.values():
                item.error = exc
                item.event.set()
            for item in self._actions.values():
                item.error = exc
            self._condition.notify_all()

    def _receive(self) -> None:
        # Target entry proves Thread bootstrap completed, so join is now legal.
        # Publication of _reader alone only proves ownership of a startup attempt.
        self._reader_entered.set()
        while not self._stop_reader.is_set():
            try:
                message = self._transport.recv(timeout_s=0.02)
                continuation = self._next_already_queued
                buffered = getattr(self._transport, "buffered", None)
                try:
                    # The queue flag is not a ROS 1 freshness proof. A missing or failing method leaves the flag
                    # false. SourceWindow ignores it: a ROS 1 producer stamp is not a freshness proof.
                    self._next_already_queued = bool(buffered()) if callable(buffered) else False
                except Exception:
                    self._next_already_queued = False
                message = _json_copy(message, max_bytes=self._max_message_bytes)
            except TimeoutError:
                continue
            except BaseException as exc:
                self._fail_connection(exc)
                return
            with self._condition:
                received_at = time.monotonic()
                op = message.get("op")
                for action in self._actions.values():
                    previous = (action.response, action.error)
                    if action.receive(message, received_at):
                        if previous != (action.response, action.error) and (
                                not action.safety or action.abandoned or action.error is not None):
                            self._invalidate_safety_locked()
                        self._condition.notify_all()
                for terminal in self._safety_history.values():
                    error = terminal.check(message)
                    if error is not None:
                        self._fault_safety_history_locked(error)
                ident = terminal_identity(message)
                serial = self._safety_goal_serial(ident)
                if (serial is not None and serial <= self._safety_retired_through
                        and ident not in self._actions and ident not in self._safety_history):
                    # A finite cache cannot prove that a very old duplicate is
                    # identical. Never silently accept an unverifiable result.
                    self._fault_safety_history_locked(ValueError(
                        "retired safety result is outside the bounded verification history"))
                if op == "service_response":
                    ident = message.get("id")
                    item = self._pending.get(ident) if isinstance(ident, str) else None
                    if item is None or item.event.is_set():
                        continue  # delayed response to a timed-out request is never reused
                    if (message.get("service") != item.service or type(message.get("result")) is not bool
                            or (message.get("result") is True and not isinstance(message.get("values", {}), dict))):
                        item.error = ValueError("malformed or mismatched service response")
                    else:
                        item.response = message
                    item.received_at = received_at
                    if item.effectful:
                        self._invalidate_safety_locked()
                    item.event.set()
                    self._condition.notify_all()
                elif op == "publish":
                    topic = message.get("topic")
                    ident = message.get("id")
                    active = self._topic_ids.get(topic, set()) if isinstance(topic, str) else set()
                    recipients = active if ident is None else ({ident} & active if isinstance(ident, str) else set())
                    if recipients and isinstance(message.get("msg"), dict):
                        for subscription in recipients:
                            ring = self._sensed_rings.get(subscription)
                            if ring is not None:
                                # A sensed-stop confirmation counts every sample of its own subscription.
                                ring.append((message["msg"], received_at, continuation))
                                continue
                            stream = self._streams.get(subscription)
                            if stream is not None:
                                # A fresh-sample read-back (E2) counts every sample in arrival order; a dropped
                                # one is remembered, and that attempt ends unconfirmed.
                                if len(stream.items) >= _FRESH_CAPACITY:
                                    stream.items.popleft()
                                    stream.overflowed = True
                                stream.items.append((message["msg"], received_at))
                                continue
                            # Retain the first matching arrival for each individual
                            # subscription, not another concurrent reader's sample.
                            self._topics.setdefault(subscription, (message["msg"], received_at))
                        self._condition.notify_all()
                elif op == "status" and message.get("level") == "error":
                    ident = message.get("id")
                    if isinstance(ident, str) and ident in self._sensed_exclusion_ids:
                        # Silence and a rejected exclusion subscription are not proof the competing command stopped.
                        self._sensed_faults.add(ident)
                        self._condition.notify_all()
                    item = self._pending.get(ident) if isinstance(ident, str) else None
                    if item is not None:
                        item.error = ValueError("rosbridge reported a protocol error")
                        item.event.set()
                elif op in ("fragment", "png"):
                    self._fail_connection(ValueError("compressed/fragmented rosbridge messages are unsupported"))
                    return

    def _deadline(self, spec: Mapping[str, Any], context: BridgeContext) -> float:
        remaining = context.remaining_ms() / 1000
        if spec["timeout"] is not None:
            remaining = min(float(spec["timeout"]), remaining)
        if remaining <= 0:
            raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS request deadline expired before send",
                                 {"retryable": False})
        return time.monotonic() + remaining

    def _send(self, message: dict[str, Any], deadline: float, context: BridgeContext, epoch: int | None,
              *, subscription: tuple[str, str] | None = None, action_goal: str | None = None,
              action_cancel: str | None = None, service_request: str | None = None,
              actuation: bool = False) -> None:
        self.ensure_open()
        if epoch is not None:
            self._refuse_if_estopped(epoch, "ROS request")
        if context.cancelled():
            raise signals.Cancelled("cancelled before preparing the ROS transport")
        # Connection establishment may block; it must not occupy the wire lock
        # or allow a request to retain permission across an intervening e-stop.
        prepare = getattr(self._transport, "prepare", None)
        if callable(prepare):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS request expired before connecting", {"retryable": False})
            try:
                prepare(timeout_s=remaining)
            except Exception as exc:
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "ROS transport connection was not established",
                                     {"retryable": False}) from exc
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self._wire_lock.acquire(timeout=max(0, remaining)):
            raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS request expired before wire access",
                                 {"retryable": False})
        try:
            self.ensure_open()
            if epoch is not None:
                self._refuse_if_estopped(epoch, "ROS request")
            if context.cancelled():
                raise signals.Cancelled("cancelled before the ROS request was sent")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS request expired before send",
                                     {"retryable": False})
            if self._fatal is not None:
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "ROS connection is unavailable; no automatic reconnect",
                                     {"retryable": False})
            if "ros_reconcile_actions" in context.extra:
                self._check_action_reconciliation(context.extra["ros_reconcile_actions"],
                                                  context.extra.get("ros_reconcile_services", []),
                                                  safety_generation=context.extra.get("ros_safety_reconcile_generation"),
                                                  ignore_service=service_request)
            if subscription is not None:
                # Activate at the actual send boundary, not before connection or
                # wire-lock waits. An earlier id-less publication must not satisfy
                # this read; an immediate in-send fake response must still match.
                topic, ident = subscription
                with self._condition:
                    self._topic_ids.setdefault(topic, set()).add(ident)
            if action_goal is not None:
                with self._condition:
                    action = self._actions[action_goal]
                    if not action.safety:
                        self._refuse_unresolved_actions()
                    else:
                        self._refuse_uncertain_safety_locked(ignore_action=action_goal)
                    if action.error is not None:
                        raise make_mhs_error("MHS.DEVICE.NOT_READY", "ROS action setup failed before goal transmission",
                                             {"retryable": False})
                    action.sent = True
                    if not action.safety:
                        self._invalidate_safety_locked()
            if action_cancel is not None:
                with self._condition:
                    self._invalidate_safety_locked()
            if service_request is not None:
                with self._condition:
                    item = self._pending[service_request]
                    if item.effectful and not item.safety:
                        self._refuse_unresolved_actions()
                    item.sent = True
                    if item.effectful:
                        self._invalidate_safety_locked()
            if actuation:
                with self._condition:
                    self._refuse_unresolved_actions()
                    self._invalidate_safety_locked()
            try:
                self._transport.send(message, timeout_s=remaining)
            except TranscriptDivergence:
                raise
            except Exception as exc:
                self._fail_connection(exc)
                raise outcome_unknown("ROS send failed; a partial transmission cannot be ruled out",
                                      details={"request_id": message.get("id"), "sent": "unknown"}) from exc
            self._start_reader()
        finally:
            self._wire_lock.release()

    def _service(self, spec: Mapping[str, Any], payload: dict[str, Any], context: BridgeContext,
                 deadline: float, epoch: int | None, *, safety: bool = False,
                 sent_at: list[float] | None = None) -> dict[str, Any]:
        ident = self._next_id()
        pending = _Pending(spec["name"], safety, effectful=(
            spec is self._safety.get("reset") or (not safety and spec["operation"] != "read")))
        with self._condition:
            same_kind = sum(item.safety == safety for item in self._pending.values())
            if same_kind >= (8 if safety else 128):
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "too many pending ROS requests", {"retryable": False})
            self._pending[ident] = pending
            if pending.effectful:
                self._invalidate_safety_locked()
        message = {"op": "call_service", "service": spec["name"], "args": payload, "id": ident}
        if spec["type"] is not None:
            message["type"] = spec["type"]
        observed_terminal = False
        try:
            self._send(message, deadline, context, epoch, service_request=ident)
            if sent_at is not None:
                sent_at.append(time.monotonic())  # the request is on the wire (a sensed-stop step)
            if time.monotonic() >= deadline:
                raise outcome_unknown("ROS send exceeded its deadline after transmission", details={"request_id": ident})
            while True:
                if (epoch is not None and epoch != self.estop_epoch) or context.cancelled():
                    raise outcome_unknown("ROS request interrupted after transmission; native outcome is unknown",
                                          details={"request_id": ident})
                if pending.event.is_set():
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise outcome_unknown("ROS service deadline expired after transmission",
                                          details={"request_id": ident})
                pending.event.wait(min(0.02, remaining))
            if pending.error is not None:
                raise outcome_unknown("ROS service response unavailable or invalid after transmission",
                                      details={"request_id": ident}) from pending.error
            if pending.received_at is None or pending.received_at > deadline:
                raise outcome_unknown("ROS response arrived after its deadline", details={"request_id": ident})
            response = pending.response
            if response is None or response["result"] is not True:
                raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "ROS service reported failure")
            observed_terminal = True
            values = response.get("values", {})
            predicate = spec["success"]
            if predicate is not None and not _passes(values, predicate):
                raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "ROS application success predicate was not satisfied")
            return values
        finally:
            with self._condition:
                if pending.effectful and pending.sent and (not observed_terminal or not self._service_settled(pending)):
                    pending.abandoned = True
                    self._invalidate_safety_locked()
                else:
                    self._pending.pop(ident, None)

    @staticmethod
    def _service_settled(item: _Pending) -> bool:
        return item.error is None and item.response is not None and item.response.get("result") is True

    def _payload(self, spec: Mapping[str, Any], args: Mapping[str, Any]) -> dict[str, Any]:
        payload = copy.deepcopy(spec["payload"])
        try:
            for target, value in spec["args"].map(dict(args)).items():
                _put(payload, target, value)
            return _json_copy(payload, max_bytes=self._max_message_bytes)
        except (MappingError, UnitError, TypeError, ValueError) as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "cannot map ROS request arguments",
                                 {"retryable": False}) from exc

    def _refuse_unresolved_actions(self) -> None:
        with self._condition:
            ids = [item.ident for item in self._actions.values() if item.abandoned]
            ids += [ident for ident, item in self._pending.items() if item.effectful and item.abandoned]
            archived = self._safety_reconciliation_needed or self._safety_history_error is not None
        if ids or archived:
            raise make_mhs_error("MHS.DEVICE.NOT_READY",
                                 "ROS native outcome requires terminal reconciliation and an explicit safety reset",
                                 {"retryable": False, "details": {"request_ids": ids,
                                                                  "retired_safety_requires_reset": archived}})

    def _check_action_reconciliation(self, ids: list[str], service_ids: list[str] | None = None,
                                     *, ignore_service: str | None = None,
                                     safety_generation: int | None = None) -> None:
        with self._condition:
            services = {ident: item for ident, item in self._pending.items()
                        if item.effectful and ident != ignore_service}
            if (self._safety_history_error is not None
                    or (safety_generation is not None and safety_generation != self._safety_reconcile_generation)
                    or set(services) != set(service_ids or [])
                    or any(not item.abandoned or not self._service_settled(item) for item in services.values())
                    or set(self._actions) != set(ids)
                    or any(not item.abandoned or item.error is not None or item.response is None
                           for item in self._actions.values())):
                raise make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                     "ROS native reconciliation changed or remains uncertain; reset is refused",
                                     {"retryable": False})

    def _acquire_transaction(self, context: BridgeContext, deadline: float, epoch: int) -> None:
        while True:
            self._refuse_if_estopped(epoch, "ROS transaction")
            if context.cancelled():
                raise signals.Cancelled("ROS transaction cancelled before dispatch")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS transaction expired while queued", {"retryable": False})
            if self._txn_lock.acquire(timeout=min(0.02, remaining)):
                return

    def _action_unknown(self, pending: PendingAction, message: str) -> Exception:
        return outcome_unknown(message, details={"request_id": pending.ident, "action": pending.name,
                                                 "profile": pending.profile, "retry": "never replay this goal"})

    def _cleanup_action(self, pending: PendingAction, *, deadline: float | None = None) -> bool:
        # Passive teardown has one small overall budget, not a fresh timeout per topic.
        deadline = min(deadline, time.monotonic() + 0.02) if deadline is not None else time.monotonic() + 0.02
        for message in pending.cleanup():
            try:
                self._send(message, deadline, BridgeContext(), None)
            except Exception:
                return False
        return True

    def _safety_goal_serial(self, ident: Any) -> int | None:
        if not isinstance(ident, str) or not ident.startswith(self._safety_goal_prefix):
            return None
        suffix = ident[len(self._safety_goal_prefix):]
        if (not re.fullmatch(r"[1-9][0-9]{0,18}", suffix)
                or int(suffix) > self._safety_goal_sequence):
            return None
        return int(suffix)

    def _fault_safety_history_locked(self, error: BaseException, *, retirement_failed: bool = False) -> None:
        self._safety_retirement_failed |= retirement_failed
        if self._safety_history_error is None:
            self._safety_history_error = error
            self._safety_reconciliation_needed = True
            self._safety_reconcile_generation += 1
            self._invalidate_safety_locked()
            self._condition.notify_all()

    def _archive_safety_locked(self, pending: PendingAction) -> None:
        serial = self._safety_goal_serial(pending.ident)
        if serial is None:
            self._fault_safety_history_locked(ValueError("safety goal has no local retirement lineage"),
                                              retirement_failed=True)
            return
        self._safety_history[pending.ident] = SafetyActionTerminal.from_pending(pending)
        self._safety_retired_through = max(self._safety_retired_through, serial)
        while len(self._safety_history) > MAX_SAFETY_HISTORY:
            self._safety_history.pop(next(iter(self._safety_history)))
        if pending.abandoned:
            self._safety_reconciliation_needed = True
            self._safety_reconcile_generation += 1

    def _reclaim_terminal_safety(self, deadline: float) -> None:
        # The owner releases a native call by marking it abandoned. Never evict
        # live, pending, erroneous or ordinary goals, even under capacity pressure.
        if not self._has_action_safety:
            return
        self.ensure_open()
        if time.monotonic() >= deadline:
            raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS safety retirement deadline expired", {"retryable": False})
        with self._condition:
            retired = [item for item in self._actions.values()
                       if item.safety and item.abandoned and item.sent
                       and item.response is not None and item.error is None]
            for item in retired:
                self._archive_safety_locked(item)
                self._actions.pop(item.ident)
        # Archive first so late data is still checked while passive teardown runs.
        # Finish before the next setup on the same topic; never send under the
        # receive condition, and share one small budget across the whole batch.
        cleanup_deadline = min(deadline, time.monotonic() + 0.02)
        for item in retired:
            if not self._cleanup_action(item, deadline=cleanup_deadline):
                with self._condition:
                    self._fault_safety_history_locked(ConnectionError("retired safety subscription cleanup was not transmitted"),
                                                      retirement_failed=True)
                break

    def _action_result(self, spec: Mapping[str, Any], pending: PendingAction, *,
                       cancellation: bool = False, safe: bool = False) -> dict[str, Any]:
        if pending.error is not None or pending.response is None:
            raise self._action_unknown(pending, "ROS action has no trustworthy terminal result")
        status = pending.response["status"]
        if status in pending.cancelled:
            if cancellation and safe:
                raise signals.Cancelled("ROS goal cancellation and independent safe state were confirmed")
            if cancellation:
                raise self._action_unknown(pending, "ROS goal cancelled but independent safe state was not confirmed")
            raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "ROS goal was cancelled by another actor",
                                details={"request_id": pending.ident, "native_status": status})
        if status != pending.succeeded:
            raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "ROS action ended without success",
                                details={"request_id": pending.ident, "native_status": status})
        values = pending.response["values"]
        if not _passes(values, spec["success"]):
            raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "ROS action application success predicate failed",
                                details={"request_id": pending.ident, "native_status": status})
        return values

    def _interrupt_action(self, spec: Mapping[str, Any], pending: PendingAction,
                          epoch: int | None, execution_deadline: float) -> dict[str, Any]:
        # Leave margin inside the server's 250 ms cancellation grace. These
        # controls get a new bounded context: the original cancellation/event
        # must not prohibit the very stop/cancel messages that it requested.
        deadline = time.monotonic() + 0.20
        context = BridgeContext(deadline_ms=200, extra={"deadline_at": deadline})
        changed_epoch = epoch is not None and epoch != self.estop_epoch
        if changed_epoch:
            stopping_epoch = self.estop_epoch
            # The e-stop thread owns the native stop. Never place action cancel
            # ahead of it or wait on the ordinary transaction lock from stop.
            with self._condition:
                while self._safety_finished_epoch < stopping_epoch and time.monotonic() < deadline - 0.05:
                    self._condition.wait(min(0.01, max(0, deadline - 0.05 - time.monotonic())))
                if self._safety_finished_epoch < stopping_epoch:
                    raise self._action_unknown(pending, "ROS e-stop confirmation remains pending")
        else:
            try:
                stop_context = BridgeContext(deadline_ms=150, extra={"deadline_at": deadline - 0.05})
                self.safe_state(stop_context)
            except Exception:
                pass  # cancellation is still required when the initial stop fails
        with self._condition:
            terminal = pending.response is not None and pending.error is None
        if not terminal:
            try:
                self._send(pending.cancel(), min(deadline, time.monotonic() + self._timeout_s), context, None,
                           action_cancel=pending.ident)
            except Exception as exc:
                raise self._action_unknown(pending, "ROS goal cancellation could not be transmitted") from exc
        with self._condition:
            while pending.response is None and pending.error is None and time.monotonic() < deadline:
                self._condition.wait(min(0.01, max(0, deadline - time.monotonic())))
        if pending.received_at is None or pending.received_at > deadline:
            raise self._action_unknown(pending, "ROS cancellation has no terminal confirmation within its budget")
        # A cancellation callback may re-arm or otherwise mutate native state
        # before publishing its terminal result. A pre-cancel stop cannot prove
        # the post-terminal state; obtain a new acknowledgement within the same
        # bounded interruption budget. This never waits on the transaction lock.
        try:
            remaining_ms = (deadline - time.monotonic()) * 1000
            if remaining_ms <= 0:
                raise self._action_unknown(pending, "no budget remains for post-terminal stop")
            fresh = BridgeContext(deadline_ms=remaining_ms, extra={"deadline_at": deadline})
            safe = bool(self.safe_state(fresh).get("achieved"))
        except Exception:
            safe = False
        if not safe:
            raise self._action_unknown(pending, "ROS terminal goal still requires a fresh confirmed safe state")
        if (pending.received_at > execution_deadline and pending.response is not None
                and pending.response["status"] not in pending.cancelled):
            raise self._action_unknown(pending, "ROS action terminal result arrived after its execution deadline")
        return self._action_result(spec, pending, cancellation=True, safe=safe)

    def _action(self, spec: Mapping[str, Any], payload: dict[str, Any], context: BridgeContext,
                deadline: float, epoch: int | None, *, safety: bool = False) -> dict[str, Any]:
        # ROS 1 servers may retain GoalIDs across client/process restarts. The
        # service/subscription counter is not sufficiently fresh for a goal.
        with self._condition:
            if safety:
                if self._safety_goal_sequence >= 2**63 - 1:
                    raise make_mhs_error("MHS.DEVICE.NOT_READY", "ROS safety identity space exhausted", {"retryable": False})
                self._safety_goal_sequence += 1
                ident = self._safety_goal_prefix + str(self._safety_goal_sequence)
            else:
                ident = "mhs-action-" + uuid.uuid4().hex
            pending = PendingAction(ident, spec["name"], spec["type"], spec["profile"], spec["feedback"], safety=safety)
            same_role = sum(item.safety == safety for item in self._actions.values())
            if same_role >= (MAX_SAFETY_ACTIONS if safety else MAX_ACTIONS):
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "too many retained ROS actions", {"retryable": False})
            self._actions[pending.ident] = pending
            if not safety:
                self._invalidate_safety_locked()
        settled = False
        try:
            for message in pending.setup():
                with self._condition:
                    pending.setup_sent.append(message)
                wire_deadline = min(deadline, time.monotonic() + self._timeout_s)
                self._send(message, wire_deadline, context, epoch)
                if time.monotonic() >= wire_deadline:
                    raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS action setup exceeded its wire deadline",
                                         {"retryable": False})
            wire_deadline = min(deadline, time.monotonic() + self._timeout_s)
            self._send(pending.goal(payload), wire_deadline, context, epoch, action_goal=pending.ident)
            if time.monotonic() >= wire_deadline:
                raise self._action_unknown(pending, "ROS action transmission exceeded its wire deadline")
            while True:
                with self._condition:
                    if pending.error is not None:
                        raise self._action_unknown(pending, "ROS action connection or response became uncertain")
                    response_ready = pending.response is not None
                    received_at = pending.received_at
                interrupted = context.cancelled() or (epoch is not None and epoch != self.estop_epoch)
                cancelled_result = response_ready and pending.response["status"] in pending.cancelled
                if response_ready and received_at is not None and received_at <= deadline and not (interrupted and cancelled_result):
                    result = self._action_result(spec, pending)
                    settled = True
                    return result
                if interrupted or time.monotonic() >= deadline:
                    if safety:
                        # A stop must never recursively invoke another stop or
                        # acquire a fresh cancellation budget after its deadline.
                        raise self._action_unknown(pending, "ROS safety action did not settle within its budget")
                    result = self._interrupt_action(spec, pending, epoch, deadline)
                    settled = True
                    return result
                with self._condition:
                    self._condition.wait(min(0.01, max(0, deadline - time.monotonic())))
        except (signals.Cancelled, signals.DriverFailed):
            settled = True
            raise
        finally:
            with self._condition:
                # Interpretation and retirement are separate receive windows.
                # A late error must not disappear with an earlier successful
                # result or a terminal DriverFailed/Cancelled interpretation.
                terminal_changed = settled and (pending.error is not None or pending.response is None)
                retained = pending.sent and (not settled or terminal_changed)
                if retained:
                    pending.abandoned = True
                    if safety:
                        self._invalidate_safety_locked()
                else:
                    if safety and pending.sent and pending.response is not None and pending.error is None:
                        self._archive_safety_locked(pending)
                    self._actions.pop(pending.ident, None)
            if retained and terminal_changed:
                raise self._action_unknown(pending, "ROS action terminal changed before retirement")
            if not retained:
                cleaned = self._cleanup_action(pending)
                if safety and not cleaned:
                    with self._condition:
                        self._fault_safety_history_locked(ConnectionError("safety subscription cleanup was not transmitted"),
                                                          retirement_failed=True)

    def _invoke(self, spec: Mapping[str, Any], args: Mapping[str, Any], context: BridgeContext,
                *, epoch: int | None = None, safety: bool = False) -> Any:
        deadline = self._deadline(spec, context)
        payload = self._payload(spec, args)
        if spec["kind"] == "action":
            return self._action(spec, payload, context, deadline, epoch, safety=safety)
        if spec["kind"] == "service":
            return self._service(spec, payload, context, deadline, epoch, safety=safety)
        if spec["operation"] == "subscribe":
            return self._read_value(spec, context)
        ident = self._next_id()
        self._send({"op": "advertise", "topic": spec["name"], "type": spec["type"], "id": ident},
                   deadline, context, epoch)
        self._send({"op": "publish", "topic": spec["name"], "msg": payload, "id": ident},
                   deadline, context, epoch, actuation=True)
        if spec.get("then") is not None:
            return self._after_publication(spec["then"], context, epoch)
        return {"published": True, "confirmed": False}

    def _after_publication(self, then: Mapping[str, Any], context: BridgeContext, epoch: int | None) -> dict[str, Any]:
        """Run the stages of a publish-then-step command once its publication was transmitted.

        The step is an ordinary effectful service call under the command's wire epoch, so it is never sent after an
        e-stop engaged; the observation is a fresh read (a new subscription, or an observational service) started only
        after the step was acknowledged. The publication cannot be recalled and is never acknowledged: from here on
        every failure, refusal, cancellation or interruption is an unknown outcome (the node may hold the published
        command, and the step may have run), never a failure that invites a blind retry. Nothing is retried. ``call``
        treats a failure to map the command's result the same way (``stage: result``).
        """
        out: dict[str, Any] = {"published": True, "confirmed": False}
        stage = "step"
        try:
            step = then["step"]
            out["step"] = self._service(step, copy.deepcopy(step["payload"]), context,
                                        self._deadline(step, context), epoch)
            out["stepped"] = True
            if then["observe"] is not None:
                stage = "observe"
                out["observation"] = self._read_value(then["observe"], context)
            return out
        except TranscriptDivergence:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            raise outcome_unknown(
                f"ROS publication was transmitted, but its {stage} did not complete; the published command may still "
                "take effect", details={"stage": stage, "published": True, "stepped": stage == "observe",
                                        "cause": code if isinstance(code, str) else type(exc).__name__}) from exc

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        context = _context(ctx)
        spec = self._commands.get(capability_id)
        if spec is None and capability_id == "cap.device.configure.v1":
            resource = context.resource if context.resource in self._writes else None
            if resource is None and len(self._writes) == 1:
                resource = next(iter(self._writes))
            if resource is not None:
                return self.write(resource, args or {}, context)
        if spec is None:
            raise unsupported(capability_id)
        if spec["resource"] is not None and context.resource is not None and context.resource != spec["resource"]:
            # Composed packages route each command to its declared resource; never serve it on another one.
            raise make_mhs_error("MHS.CAPABILITY.NOT_BOUND", f"{capability_id} is bound to resource "
                                 f"{spec['resource']!r}, not {context.resource!r}", {"retryable": False})
        camera = None
        if "cameras" in spec:
            if (not isinstance(args, Mapping) or set(args) != {"camera"}
                    or type(args["camera"]) is not str or args["camera"] not in spec["cameras"]):
                raise driver_failed("MHS.CAPABILITY.INPUT_INVALID", "select exactly one declared camera")
            camera = args["camera"]
            spec = spec["cameras"][camera]
            args = {}
        publisher = None
        if spec["image"] is not None:
            if args:
                raise driver_failed("MHS.CAPABILITY.INPUT_INVALID", "fixed-stream image capture takes no inputs")
            publisher = publisher_from_context(context)
            if publisher is None:
                raise driver_failed("MHS.CAPABILITY.NOT_BOUND", "image capture needs an endpoint artifact store")
            if spec["type"] in ros_images.COMPRESSED_TYPES:
                try:
                    ros_images.require_decoder()
                except ValueError as exc:
                    raise driver_failed("MHS.CAPABILITY.NOT_BOUND", str(exc)) from exc
        if spec["point_cloud"] is not None:
            if args:
                raise driver_failed("MHS.CAPABILITY.INPUT_INVALID", "fixed-stream point-cloud capture takes no inputs")
            publisher = publisher_from_context(context)
            if publisher is None:
                raise driver_failed("MHS.CAPABILITY.NOT_BOUND", "point-cloud capture needs an endpoint artifact store")
        if spec["safe_state"]:
            if args:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "fixed ROS safe-state action takes no inputs",
                                     {"retryable": False})
            # The server's e-stop passes a report list for this call (CORE-074): an identical request that this
            # e-stop already sent and saw confirmed successful answers this action, which still maps and validates
            # that response against its own output contract. Any other outcome of that request (failed, timed out,
            # not confirmed, or still unanswered once this call must send) and this call sends its own request: a
            # repeated stop is harmless, a lost safe-state path is not.
            shared = context.extra.get("estop_shared")
            identity = self._stop_request_identity(spec) if isinstance(shared, list) else None
            with self._safety_attempt(context, [spec]) as context:
                with self._condition:
                    stamp = (self._native_activity, self.estop_epoch)
                    self._safe_state_achieved = False
                    self._safe_stamp = None
                # The server's context carries an absolute deadline (``deadline_at``): a wait for the identical
                # request in flight spends this call's budget, and its own request gets what is left.
                reused = (self._shared_stop(identity, spec["timeout"], stamp, context)
                          if identity is not None else None)
                if reused is not None:
                    raw = reused[0]
                    shared.append({"capability_id": capability_id, "same_request_as": reused[1]})
                else:
                    flight = self._open_stop_flight(identity, stamp, capability_id)
                    try:
                        raw = self._invoke(spec, args or {}, context, safety=True)
                    except BaseException:
                        self._close_stop_flight(flight, ok=False)
                        raise
                    self._close_stop_flight(flight, ok=True, values=raw)
                try:
                    output = jsonable(spec["result"].map(raw)) if spec["result"] is not None else {}
                except (MappingError, UnitError, TypeError, ValueError) as exc:
                    raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", "cannot map ROS response") from exc
                from mhs.schema import validate
                schema = (self._schemas.get(capability_id) or {}).get("output_schema")
                try:
                    errors = (validate(output, schema) if isinstance(schema, Mapping) and schema
                              else ["missing resolved output contract"])
                except Exception:
                    errors = ["output contract could not be evaluated"]
                if errors:
                    raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", "ROS safe-state output violates its contract",
                                        details={"errors": errors[:8]})
                with self._condition:
                    if not self._commit_safe_state_locked(stamp):
                        raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                            "ROS native work remains active or changed during the safe-state call")
                return output
        epoch = self.estop_epoch
        deadline = self._deadline(spec, context)
        self._acquire_transaction(context, deadline, epoch)
        try:
            self._refuse_if_estopped(epoch, "ROS command")
            if spec["operation"] not in ("read", "subscribe"):
                self._refuse_unresolved_actions()
            context = BridgeContext.coerce({**context.__dict__, "extra": {**context.extra, "deadline_at": deadline}})
            raw = self._invoke(spec, args or {}, context, epoch=epoch)
            try:
                if spec["image"] is not None:
                    metadata = (ros_images.source_metadata(raw, spec["type"], camera=camera, topic=spec["name"])
                                if camera is not None else None)
                    data, width, height, media_type = ros_images.convert_image(
                        raw, spec["type"], spec["image"], max_output_bytes=publisher.max_bytes)
                    if context.cancelled():
                        raise signals.Cancelled("image capture cancelled before publication")
                    if time.monotonic() >= deadline:
                        raise driver_failed("MHS.OUTCOME.TIMEOUT", "image conversion exceeded its execution budget")
                    self._refuse_if_estopped(epoch, "ROS image publication")
                    descriptor = (publisher.publish(data, media_type, x_vendor=metadata) if metadata is not None
                                  else publisher.publish(data, media_type))
                    return {"image_ref": descriptor["uri"], "width": width,
                            "height": height, "media_type": media_type}
                if spec["point_cloud"] is not None:
                    data, count, frame, metadata = ros_pointcloud.convert_pointcloud(
                        raw, spec["type"], spec["point_cloud"], topic=spec["name"],
                        max_output_bytes=publisher.max_bytes)
                    if context.cancelled():
                        raise signals.Cancelled("point-cloud capture cancelled before publication")
                    if time.monotonic() >= deadline:
                        raise driver_failed("MHS.OUTCOME.TIMEOUT", "point-cloud conversion exceeded its execution budget")
                    self._refuse_if_estopped(epoch, "ROS point-cloud publication")
                    descriptor = publisher.publish(data, ros_pointcloud.MEDIA_TYPE,
                                                   output_field="artifact_ref", x_vendor=metadata)
                    output = {"artifact_ref": descriptor["uri"], "point_count": count}
                    if len(frame) <= 64:
                        output["frame"] = frame
                    return output
                if spec["result"] is not None:
                    return jsonable(spec["result"].map(raw))
                return raw if spec["kind"] == "topic" else {}
            except (MappingError, UnitError, TypeError, ValueError) as exc:
                if spec.get("then") is not None:
                    # The publication was sent and the step acknowledged: a result that cannot be mapped is an unknown
                    # outcome (the published command and the step may have taken effect), never a failure that
                    # invites a blind retry of the whole sequence.
                    raise outcome_unknown(
                        "ROS publication was transmitted and its step acknowledged, but the command's result could "
                        "not be mapped; the published command may have taken effect",
                        details={"stage": "result", "published": True, "stepped": True,
                                 "cause": "MHS.CAPABILITY.OUTPUT_INVALID"}) from exc
                raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", "cannot map ROS response") from exc
        finally:
            self._txn_lock.release()

    def _read_value(self, spec: Mapping[str, Any], context: BridgeContext) -> Any:
        if spec["kind"] == "service":
            value = self._invoke(spec, {}, context)
        else:
            deadline = self._deadline(spec, context)
            topic, ident = spec["name"], self._next_id()
            request = {"op": "subscribe", "topic": topic, "id": ident, "queue_length": 1}
            if spec["type"] is not None:
                request["type"] = spec["type"]
            subscribed = False
            try:
                self._send(request, deadline, context, None, subscription=(topic, ident))
                subscribed = True
                if time.monotonic() >= deadline:
                    raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS subscription send exceeded its deadline",
                                         {"retryable": False})
                with self._condition:
                    while ident not in self._topics:
                        if self._fatal is not None or self.closed:
                            raise make_mhs_error("MHS.DEVICE.NOT_READY", "ROS observation connection unavailable",
                                                 {"retryable": False})
                        if context.cancelled():
                            raise signals.Cancelled("ROS observation cancelled")
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise make_mhs_error("MHS.DEVICE.NOT_READY", "no fresh ROS topic observation before deadline",
                                                 {"retryable": False})
                        self._condition.wait(min(0.02, remaining))
                    value, received_at = self._topics[ident]
                    if received_at > deadline:
                        raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS observation arrived after deadline",
                                             {"retryable": False})
                    value = copy.deepcopy(value)
            finally:
                # Unsubscribe only this request's subscription. Teardown does not
                # invoke node shutdown and cannot report a hardware safe state.
                with self._condition:
                    self._topics.pop(ident, None)
                    active = self._topic_ids.get(topic)
                    if active is not None:
                        active.discard(ident)
                        if not active:
                            self._topic_ids.pop(topic)
                if subscribed:
                    try:
                        self._send({"op": "unsubscribe", "topic": topic, "id": ident},
                                   time.monotonic() + min(self._timeout_s, 0.05), BridgeContext(), None)
                    except Exception:
                        pass
        try:
            return _get(value, spec["path"])
        except (KeyError, IndexError, TypeError) as exc:
            raise make_mhs_error("MHS.RESOURCE.STATE_INVALID", "ROS observation path is absent",
                                 {"retryable": False}) from exc

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        specs = self._reads.get(resource_id)
        if specs is None:
            raise unsupported(resource_id, kind="resource")
        context = _context(ctx)
        return {name: self._read_value(specs[name], context) for name in (fields or list(specs)) if name in specs}

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        specs = self._writes.get(resource_id)
        if specs is None:
            raise unsupported(resource_id, kind="resource")
        if not isinstance(patch, Mapping) or not patch or any(name not in specs for name in patch):
            raise make_mhs_error("MHS.RESOURCE.NOT_WRITABLE", "ROS patch must name configured writable parameters",
                                 {"retryable": False})
        context = _context(ctx)
        epoch = self.estop_epoch
        self._acquire_transaction(context, time.monotonic() + context.remaining_ms() / 1000, epoch)
        try:
            self._refuse_if_estopped(epoch, "ROS write")
            self._refuse_unresolved_actions()
            applied = {}
            for name, value in patch.items():
                self._invoke(specs[name], {"value": value}, context, epoch=epoch)
                applied[name] = jsonable(value)
            return {"applied": applied}
        finally:
            self._txn_lock.release()

    @property
    def estop_native(self) -> str | None:
        if self._sensed is not None:
            return str(self._sensed_steps[0]["name"])  # the first request step of a sensed-confirmation stop
        spec = self._safety.get("estop") or self._safety.get("safe_state")
        return str(spec["name"]) if spec else None

    def _invalidate_safety_locked(self) -> None:
        self._native_activity += 1
        self._safe_state_achieved = False
        self._safe_stamp = None

    def _effects_settled_locked(self) -> bool:
        return (self._safety_history_error is None
                and all(item.response is not None and item.error is None for item in self._actions.values())
                and all(self._service_settled(item) for item in self._pending.values() if item.effectful))

    def _commit_safe_state_locked(self, stamp: tuple[int, int]) -> bool:
        achieved = (not self.closed and self._fatal is None and self._effects_settled_locked()
                    and stamp == (self._native_activity, self.estop_epoch))
        self._safe_state_achieved = achieved
        self._safe_stamp = stamp if achieved else None
        return achieved

    def _refuse_uncertain_safety_locked(self, *, ignore_action: str | None = None) -> None:
        # A history fault still forbids confirmation/reset, but cannot suppress
        # all protective attempts after the old stop's terminal and retirement.
        # Never preempt a possibly running stop on a single-goal action server.
        if (self._safety_retirement_failed
                or any(item.safety and ident != ignore_action
                       and (item.response is None or item.error is not None)
                       for ident, item in self._actions.items())):
            raise make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                 "a previously sent ROS safety goal or its retirement remains uncertain",
                                 {"retryable": False})

    @contextmanager
    def _safety_attempt(self, context: BridgeContext, specs: list[Mapping[str, Any]]):
        # Existing service-only drivers keep their independent service behavior.
        # Action-stop servers are commonly single-goal servers: serialize whole
        # confirmation attempts, never just their wire transmission. This lock
        # is separate from the ordinary transaction lock and has one deadline.
        if not self._has_action_safety:
            yield context
            return
        deadline = min((self._deadline(spec, context) for spec in specs),
                       default=time.monotonic() + context.remaining_ms() / 1000)
        context = BridgeContext.coerce({**context.__dict__,
                                       "extra": {**context.extra, "deadline_at": deadline}})
        while True:
            self.ensure_open()
            if context.cancelled():
                raise signals.Cancelled("ROS safety attempt cancelled before admission")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "ROS safety attempt expired before admission",
                                     {"retryable": False})
            if self._safety_action_lock.acquire(timeout=min(remaining, 0.02)):
                break
        try:
            self.ensure_open()
            self._reclaim_terminal_safety(deadline)
            if any(spec["kind"] == "action" for spec in specs):
                with self._condition:
                    self._refuse_uncertain_safety_locked()
            yield context
        finally:
            self._safety_action_lock.release()

    @staticmethod
    def _stop_request_identity(spec: Mapping[str, Any] | None) -> str | None:
        """The upstream request a fixed stop binding sends, as one string (``None``: not a fixed call).

        Two bindings with the same identity send the same service request or
        action goal (name, type, profile, literal request), accept the same
        answer (success predicate) and wait for it as long (timeout): once one
        of them succeeded, the e-stop need not send it again (CORE-074). A
        binding with another timeout sends its own request. A binding with
        mapped arguments is never a fixed stop.
        """
        if (not isinstance(spec, Mapping) or spec.get("kind") not in ("service", "action")
                or spec.get("operation") != "call" or spec.get("image") is not None
                or spec.get("point_cloud") is not None or spec["args"].targets):
            return None
        identity = {"kind": spec["kind"], "name": spec["name"], "type": spec["type"], "profile": spec["profile"],
                    "request": spec["payload"], "success": spec["success"], "timeout": spec["timeout"]}
        if spec.get("stall") is not None:
            identity["stall"] = spec["stall"]  # one answer never confirms a stall read-back
        return "ros:" + json.dumps(identity, sort_keys=True, separators=(",", ":"))

    def _open_stop_flight(self, identity: str | None, stamp: tuple[int, int], sender: str) -> "_StopFlight | None":
        """Register a stop request of the current e-stop in its ledger (``None`` outside an e-stop)."""
        if identity is None:
            return None
        with self._condition:
            if self._stop_ledger_epoch != self.estop_epoch:
                return None
            flight = _StopFlight(stamp, sender)
            self._stop_ledger[identity] = flight
            return flight

    @staticmethod
    def _close_stop_flight(flight: "_StopFlight | None", *, ok: bool, values: Any = None) -> None:
        if flight is not None:
            flight.ok, flight.values = ok, (copy.deepcopy(values) if ok else None)
            flight.event.set()

    def _shared_stop(self, identity: str, timeout: float | None, stamp: tuple[int, int],
                     context: BridgeContext) -> tuple[Any, str] | None:
        """The answer of the identical stop request this e-stop already sent, once it was confirmed successful.

        Only a confirmed success is reused (CORE-074). ``None``, and the command sends its own request at once,
        when this e-stop has not sent the request, when it failed, timed out or was not confirmed, when native work
        changed the state after it was sent (a fresh stop is due, as after an interrupted goal), or when it is still
        unanswered once the command must send to keep time for its own request: a request in flight is awaited
        until the command's budget is down to its own request's timeout or to half, whichever is less. A repeated
        stop is harmless; the safe-state path is never lost within an e-stop.
        """
        with self._condition:
            flight = self._stop_ledger.get(identity) if self._stop_ledger_epoch == self.estop_epoch else None
        if flight is None:
            return None
        if not flight.event.is_set():
            remaining = context.remaining_ms() / 1000
            keep = remaining / 2 if timeout is None else min(float(timeout), remaining / 2)
            flight.event.wait(max(0.0, remaining - keep))
        if not flight.event.is_set() or not flight.ok or flight.stamp != stamp:
            return None
        return copy.deepcopy(flight.values), flight.sender

    def _perform_safety(self, names: list[str], ctx: Any = None) -> dict[str, Any]:
        context = _context(ctx)
        specs = [self._safety[name] for name in names if name in self._safety]
        with self._safety_attempt(context, specs) as context:
            performed = []
            sent: set[str] = set()
            with self._condition:
                stamp = (self._native_activity, self.estop_epoch)
                self._safe_state_achieved = False
                self._safe_stamp = None
            for name in names:
                spec = self._safety.get(name)
                if spec is None:
                    continue
                identity = self._stop_request_identity(spec)
                if identity is not None and identity in sent:
                    # estop and safe_state bind one request: it succeeded already in this
                    # call; a second transmission may undo it (a LAND re-arms motors).
                    continue
                # The bridge's own stop never consults the ledger: it always sends. Should a safe-state
                # command of this e-stop ever send the identical request first (it would have to win the
                # safety lane before this native stop), the request goes out twice; a stop is never lost.
                flight = self._open_stop_flight(identity, stamp, "native")
                try:
                    raw = (self._stall_read_back(spec, context) if spec.get("stall") is not None
                           else self._topic_read_back(spec, context) if spec.get("fresh") is not None
                           else self._invoke(spec, {}, context, safety=True))
                except TranscriptDivergence:
                    self._close_stop_flight(flight, ok=False)
                    raise
                except Exception as exc:
                    self._close_stop_flight(flight, ok=False)
                    raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "ROS stop was not confirmed successful",
                                        details={"step": name, "performed": performed}) from exc
                except BaseException:
                    self._close_stop_flight(flight, ok=False)
                    raise
                self._close_stop_flight(flight, ok=True, values=raw)
                performed.append(spec["name"])
                if identity is not None:
                    sent.add(identity)
            with self._condition:
                achieved = bool(performed) and self._commit_safe_state_locked(stamp)
            return {"native": self.estop_native, "performed": performed,
                    "safe_state_achieved": achieved}

    # -- sensed-confirmation stop (SAFE-049, CORE-088) -------------------------------------------------------
    def _sensed_step(self, spec: Mapping[str, Any], context: BridgeContext,
                     bound: float) -> tuple[str, float | None]:
        """Send one request step on the safety lane: ``(outcome, transmission time or None)``.

        The safety lane is not fenced by the latch or the e-stop epoch, not refused by unresolved ordinary goals
        and never counted as native activity that invalidates the safety stamp. A refused, failed or unanswered
        step is recorded, never raised: achievement depends only on the sensed state.
        """
        sent: list[float] = []
        try:
            deadline = min(self._deadline(spec, context), bound)
            if deadline <= time.monotonic():
                raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "no budget left for the request step", {"retryable": False})
            payload = copy.deepcopy(spec["payload"])
            if spec["kind"] == "service":
                self._service(spec, payload, context, deadline, None, safety=True, sent_at=sent)
                return "succeeded", sent[0]
            ident = self._next_id()
            self._send({"op": "advertise", "topic": spec["name"], "type": spec["type"], "id": ident},
                       deadline, context, None)
            self._send({"op": "publish", "topic": spec["name"], "msg": payload, "id": ident}, deadline, context, None)
            return "published", time.monotonic()
        except TranscriptDivergence:
            raise
        except signals.DriverFailed:
            return ("refused" if sent else "not_sent"), (sent[0] if sent else None)
        except Exception:  # noqa: BLE001 - recorded; the confirmation decides
            return ("unknown" if sent else "not_sent"), (sent[0] if sent else None)

    def _sensed_cleanup(self, created: list[tuple[str, str]], subscribed: list[tuple[str, str]]) -> None:
        with self._condition:
            for topic, ident in created:
                self._sensed_rings.pop(ident, None)
                self._sensed_exclusion_ids.discard(ident)
                self._sensed_faults.discard(ident)
                active = self._topic_ids.get(topic)
                if active is not None:
                    active.discard(ident)
                    if not active:
                        self._topic_ids.pop(topic)
        for topic, ident in subscribed:
            try:
                self._send({"op": "unsubscribe", "topic": topic, "id": ident},
                           time.monotonic() + min(self._timeout_s, 0.05), BridgeContext(), None)
            except Exception:  # noqa: BLE001 - teardown never reports a safe state
                pass

    def _sensed_attempt(self, ctx: Any, *, request: bool) -> dict[str, Any]:
        """One sensed-confirmation attempt: the request steps (``request``), then the bounded confirmation.

        The e-stop and the background retry send the request; a reset re-confirms read-only (``request=False``:
        no request, no re-enable). New subscriptions are opened after the last step; the confirmation commits the
        safe state only when every source confirms before ``confirm_within_ms`` after the first transmission and the
        caller's deadline, with no native activity, new e-stop epoch or disconnect in between. A ROS 1 producer stamp
        is not a freshness proof: the bridge has no proven offset to its wall clock, so every ROS 1 stamp sample is
        discarded and does not refresh a counted sample. A fixed lead is not that proof. A ROS 2 subscription
        discards its declared history by arrival ordinal. An exclusion subscription on a request topic commits only
        after a passive sample observed on it and still fresh at the commit. Silence, a subscription error, a
        later command that is not passive, and a sample the exclusion ring drops each refuse the confirmation.
        A dropped sample was not inspected, so the passive tail that remains is not evidence. A bridge
        the endpoint has not bound to a device it serves as simulated still sends the request but opens no
        confirmation (``not_simulated``; verification F3). Anything else is reported unachieved with its reason, never
        raised.
        """
        profile = self._sensed
        assert profile is not None
        context = _context(ctx)
        started = time.monotonic()
        caller_deadline = started + context.remaining_ms() / 1000
        with self._condition:
            stamp = (self._native_activity, self.estop_epoch)
            self._safe_state_achieved = False
            self._safe_stamp = None
            served = self._served_mode
        report: dict[str, Any] = {"kind": "sensed", "attempt": "estop" if request else "reset",
                                  "required": profile.consecutive, "bound_ms": profile.confirm_within_ms}
        steps: list[dict[str, Any]] = []
        first_sent: float | None = started if not request else None
        if request:
            for spec in self._sensed_steps:
                outcome, sent_at = self._sensed_step(spec, context, caller_deadline)
                steps.append({"native": spec["name"], "kind": spec["kind"], "outcome": outcome})
                if sent_at is not None and first_sent is None:
                    first_sent = sent_at
            report["request"] = steps
        windows: dict[str, ros_sensed.SourceWindow] = {}
        achieved = False
        reason: str | None = None
        created: list[tuple[str, str]] = []
        subscribed: list[tuple[str, str]] = []
        if first_sent is None:
            reason = "request_not_sent"
        elif served != "simulated":
            # SAFE-049 / CORE-088 (verification F3): the request went out (it may stop the device), but only an
            # endpoint serving the device as simulated may let a sensed confirmation stand for its stop.
            reason = "not_simulated"
        else:
            bound = min(first_sent + profile.confirm_within_ms / 1000.0, caller_deadline)
            windows = {name: ros_sensed.SourceWindow(source, profile.terms_of(name), profile, first_sent)
                       for name, source in profile.sources.items()}
            capacity = min(64, max(16, 2 * profile.consecutive + 2))
            idents: dict[str, str] = {}
            exclusion_ident: str | None = None
            try:
                for name, source in profile.sources.items():
                    ident = self._next_id()
                    message: dict[str, Any] = {"op": "subscribe", "topic": source.topic, "type": source.type,
                                               "id": ident, "queue_length": 1}
                    if source.throttle_ms is not None:
                        message["throttle_rate"] = source.throttle_ms
                    with self._condition:
                        self._sensed_rings[ident] = ros_sensed.Ring(capacity)
                    created.append((source.topic, ident))
                    remaining = bound - time.monotonic()
                    if remaining <= 0:
                        raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "no budget left to subscribe", {"retryable": False})
                    # Recorded immediately before this subscription. A ROS 1 producer stamp is not compared with it.
                    windows[name].fresh_after_ns = time.time_ns() if profile.ros_version == 1 else 0
                    self._send(message, time.monotonic() + min(self._timeout_s, remaining), context, None,
                               subscription=(source.topic, ident))
                    subscribed.append((source.topic, ident))
                    idents[name] = ident
                if profile.exclusion is not None:
                    # After the request, so this subscription does not see the request itself. A later command
                    # whose watched fields are not all zero is a competing publisher.
                    ident = self._next_id()
                    exclusion_message: dict[str, Any] = {"op": "subscribe", "topic": profile.exclusion.topic,
                                                         "type": profile.exclusion.ros_type, "id": ident,
                                                         "queue_length": 1}
                    with self._condition:
                        self._sensed_rings[ident] = ros_sensed.Ring(capacity)
                        self._sensed_exclusion_ids.add(ident)
                    created.append((profile.exclusion.topic, ident))
                    remaining = bound - time.monotonic()
                    if remaining <= 0:
                        raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "no budget left to subscribe", {"retryable": False})
                    self._send(exclusion_message, time.monotonic() + min(self._timeout_s, remaining), context, None,
                               subscription=(profile.exclusion.topic, ident))
                    subscribed.append((profile.exclusion.topic, ident))
                    exclusion_ident = ident
            except TranscriptDivergence:
                self._sensed_cleanup(created, subscribed)
                raise
            except Exception:  # noqa: BLE001 - classified below
                reason = "superseded" if (self.closed or self._fatal is not None) else "sensed_missing"
            exclusion_passive_at: float | None = None
            competing = False
            exclusion_fault = False
            try:
                with self._condition:
                    while reason is None:
                        for name, ident in idents.items():
                            ring = self._sensed_rings.get(ident)
                            if ring is None:
                                continue
                            window = windows[name]
                            if ring.overflowed:
                                ring.overflowed = False
                                window.overflow()
                            while ring.items:
                                sample, received_at, ordinal, continuation = ring.items.popleft()
                                if received_at <= bound:  # an arrival after the bound is never counted
                                    window.add(sample, received_at, ordinal, continuation=continuation)
                        if exclusion_ident is not None and profile.exclusion is not None:
                            if exclusion_ident in self._sensed_faults:
                                exclusion_fault = True
                            ring = self._sensed_rings.get(exclusion_ident)
                            if ring is not None:
                                if ring.overflowed:
                                    # A sample this ring dropped was not inspected. The surviving tail cannot
                                    # prove that lost command was passive, so the attempt stays an observer fault.
                                    exclusion_fault = True
                                    ring.overflowed = False
                                while ring.items:
                                    sample, received_at, _ordinal, _continuation = ring.items.popleft()
                                    if received_at > bound:
                                        continue
                                    if ros_sensed.exclusion_competes(profile.exclusion, sample):
                                        competing = True
                                    else:
                                        exclusion_passive_at = received_at
                        now = time.monotonic()
                        exclusion_ready = profile.exclusion is None or (
                            not exclusion_fault and not competing and exclusion_passive_at is not None
                            and now - exclusion_passive_at <= profile.max_gap_ms / 1000.0)
                        if any(window.invalid is not None for window in windows.values()):
                            reason = "sensed_invalid"
                        elif exclusion_fault or competing:
                            # A subscription error, a dropped exclusion sample, or a non-passive command is not exclusion. Silence is handled below.
                            reason = "not_confirmed"
                        elif (self.closed or self._fatal is not None or context.cancelled()
                              or stamp != (self._native_activity, self.estop_epoch)):
                            reason = "superseded"
                        elif self._served_mode != "simulated":
                            reason = "not_simulated"  # never unbound while open; checked again before a commit
                        elif now <= bound and all(window.confirmed(now) for window in windows.values()) and exclusion_ready:
                            achieved = self._commit_safe_state_locked(stamp)
                            if not achieved:
                                reason = "superseded"
                            break
                        elif now >= bound:
                            if (profile.exclusion is not None and not exclusion_ready
                                    and all(window.seen > 0 for window in windows.values())):
                                reason = "not_confirmed"
                            else:
                                reason = ros_sensed.unconfirmed_reason(windows, now)
                        else:
                            self._condition.wait(min(0.02, max(0.0, bound - now)))
            finally:
                self._sensed_cleanup(created, subscribed)
            report["elapsed_ms"] = int(round((time.monotonic() - first_sent) * 1000))
        report["sources"] = {name: window.report() for name, window in windows.items()}
        report["confirmed"] = achieved
        if not achieved:
            report["reason"] = reason or "not_confirmed"
        with self._condition:
            self._sensed_last = copy.deepcopy(report)
        performed = [step["native"] for step in steps if step["outcome"] != "not_sent"]
        return {"native": self.estop_native, "performed": performed, "safe_state_achieved": achieved,
                "confirmation": report}

    def _stall_read_back(self, spec: Mapping[str, Any], context: BridgeContext) -> Any:
        """E1: confirm a stopped world by a value that no longer advances (``spec["stall"]``, :meth:`_stall`).

        The read-back is called ``samples`` times; each call after the first is sent at least ``interval_ms`` (on the
        monotonic clock) after the previous answer arrived, and only when that wait and the call's own timeout still
        fit in the caller's budget. Every answer must satisfy the success predicate (checked by the call) and hold the
        same value at ``stall.path`` (:func:`_equal`), and that value must be a finite number or a ROS time
        (:func:`_stall_sample_ok`). A missing value, a value of any other kind, a change, a failed call, a closed
        bridge, a cancellation or a budget that cannot hold the next sample raises, and the e-stop stays unconfirmed
        with the latch held (``MHS.SAFETY.SAFE_STATE_UNREACHED``, retried in the background). A frozen value is what a
        paused world shows, but also what a hung simulator shows: either way nothing advances in the world it reports
        on.
        """
        stall = spec["stall"]
        interval = stall["interval_ms"] / 1000.0
        first: Any = None
        values: Any = None
        for index in range(stall["samples"]):
            if index:
                timeout = float(spec["timeout"]) if spec["timeout"] is not None else 0.0
                if context.remaining_ms() / 1000.0 < interval + timeout:
                    raise make_mhs_error("MHS.OUTCOME.TIMEOUT", "the stall read-back's next sample does not fit in "
                                         "the remaining budget", {"retryable": False})
                until = time.monotonic() + interval
                while True:
                    self.ensure_open()
                    if context.cancelled():
                        raise signals.Cancelled("stall read-back cancelled between samples")
                    left = until - time.monotonic()
                    if left <= 0:
                        break
                    time.sleep(min(0.02, left))
            values = self._invoke(spec, {}, context, safety=True)
            try:
                sample = _get(values, stall["path"])
            except (KeyError, IndexError, TypeError):
                raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "the stall read-back answer has no value at "
                                    f"{stall['path']!r}") from None
            if not _stall_sample_ok(sample):
                raise driver_failed("MHS.ADAPTER.SHIM_FAILED", f"the stall read-back value at {stall['path']!r} is "
                                    "not a finite number or a ROS time ({sec, nanosec} or {secs, nsecs} integers), so "
                                    "it cannot show that the world stopped")
            if index == 0:
                first = copy.deepcopy(sample)
            elif not _equal(sample, first):
                raise driver_failed("MHS.ADAPTER.SHIM_FAILED", f"the stall read-back value at {stall['path']!r} "
                                    "changed between samples: the world is still advancing")
        return values

    def _topic_read_back(self, spec: Mapping[str, Any], context: BridgeContext) -> Any:
        """E2: confirm a stopped world by a boolean state flag on a topic, from fresh samples (:meth:`_fresh_read_back`).

        A new subscription (queue length 1, no throttle) is opened after the stop request returned, so every sample
        arrives after it; the first one is discarded (it may be a latched sample or one already in flight). Every later
        sample must arrive at least ``min_interval_ms`` after the sample before it, discarded or not: a history replayed
        on subscribe (a transient-local publisher keeps up to its depth) arrives as one burst, a live stream at the
        producer's rate, so a sample that arrives sooner restarts the count instead of counting. A sample whose flag at
        ``success.path`` is not ``success.equals`` restarts it too. ``consecutive`` samples in a row that hold the flag
        confirm the stop. Silence, a sample without a boolean at that path, a lost sample (the bounded stream
        overflowed), a closed bridge, a cancellation or the bound (``within_ms``, inside the caller's budget) raise, and
        the e-stop stays unconfirmed with the latch held (``MHS.SAFETY.SAFE_STATE_UNREACHED``, retried in the
        background). Freshness is by arrival only: the confirmation says the producer reported the flag in samples
        that arrived after the request, not that it still holds afterwards. A replay spaced at least
        ``min_interval_ms`` apart is not detected (BL-18): the discarded first sample and the burst rule cover a
        back-to-back history, not a history a publisher or an operator QoS override delivers at the live rate.
        Asking rosbridge for a volatile reader is not proof; an older rosbridge ignores that request.
        """
        fresh, success = spec["fresh"], spec["success"]
        deadline = self._deadline(spec, context)
        interval = fresh["min_interval_ms"] / 1000.0
        topic, ident = spec["name"], self._next_id()
        stream = _Stream()
        request = {"op": "subscribe", "topic": topic, "type": spec["type"], "id": ident, "queue_length": 1}
        with self._condition:
            self._streams[ident] = stream
        subscribed = False
        try:
            self._send(request, deadline, context, None, subscription=(topic, ident))
            subscribed = True
            discarded = False
            previous: float | None = None
            count = 0
            while True:
                with self._condition:
                    while not stream.items and not stream.overflowed:
                        if self._fatal is not None or self.closed:
                            raise make_mhs_error("MHS.DEVICE.NOT_READY", "ROS observation connection unavailable",
                                                 {"retryable": False})
                        if context.cancelled():
                            raise signals.Cancelled("topic read-back cancelled")
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise make_mhs_error(
                                "MHS.OUTCOME.TIMEOUT", f"the topic read-back {topic} confirmed {count} of "
                                f"{fresh['consecutive']} fresh samples within its bound", {"retryable": False})
                        self._condition.wait(min(0.02, remaining))
                    batch = list(stream.items)
                    stream.items.clear()
                    lost, stream.overflowed = stream.overflowed, False
                if lost:
                    raise driver_failed("MHS.ADAPTER.SHIM_FAILED", f"the topic read-back {topic} lost samples (its "
                                        "bounded stream overflowed)")
                for message, received_at in batch:
                    if received_at > deadline:
                        raise make_mhs_error("MHS.OUTCOME.TIMEOUT", f"the topic read-back {topic} sample arrived after "
                                             "its bound", {"retryable": False})
                    burst = previous is not None and received_at - previous < interval
                    previous = received_at
                    if not discarded:
                        discarded = True
                        continue
                    if burst:
                        count = 0
                        continue
                    try:
                        value = _get(message, success["path"])
                    except (KeyError, IndexError, TypeError):
                        raise driver_failed("MHS.ADAPTER.SHIM_FAILED", f"the topic read-back {topic} sample has no "
                                            f"value at {success['path']!r}") from None
                    if type(value) is not bool:
                        raise driver_failed("MHS.ADAPTER.SHIM_FAILED", f"the topic read-back {topic} value at "
                                            f"{success['path']!r} is not a boolean")
                    count = count + 1 if _equal(value, success["equals"]) else 0
                    if count >= fresh["consecutive"]:
                        return copy.deepcopy(message)
        finally:
            with self._condition:
                self._streams.pop(ident, None)
                active = self._topic_ids.get(topic)
                if active is not None:
                    active.discard(ident)
                    if not active:
                        self._topic_ids.pop(topic)
            if subscribed:
                try:
                    self._send({"op": "unsubscribe", "topic": topic, "id": ident},
                               time.monotonic() + min(self._timeout_s, 0.05), BridgeContext(), None)
                except Exception:
                    pass

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        with self._condition:
            self._engage_estop()
            epoch = self.estop_epoch
            # The e-stop's ledger of stop requests: one confirmed successful is not sent again (CORE-074).
            self._stop_ledger_epoch = epoch
            self._stop_ledger = {}
            self._condition.notify_all()
        result = None
        try:
            if self._sensed is not None:
                # SAFE-049: the request proves nothing; only the bounded fresh confirmation achieves the safe state.
                result = self._sensed_attempt(ctx, request=True)
            else:
                result = self._perform_safety(["estop", "safe_state"], ctx)
        finally:
            with self._condition:
                self._safety_finished_epoch = max(self._safety_finished_epoch, epoch)
                if result is not None and result["safe_state_achieved"]:
                    self._safety_confirmed_epoch = max(self._safety_confirmed_epoch, epoch)
                self._condition.notify_all()
        if result["performed"]:
            result["estop"] = "engaged"
        return result

    def safe_state(self, ctx: Any = None) -> Any:
        if self._sensed is not None:
            result = self._sensed_attempt(ctx, request=True)
            return {"achieved": result["safe_state_achieved"], "native": result["native"]}
        name = "safe_state" if "safe_state" in self._safety else "estop"
        result = self._perform_safety([name], ctx)
        return {"achieved": result["safe_state_achieved"], "native": result["native"]}

    def interlocks(self) -> list[dict[str, str]]:
        states = []
        for ident, closed_when, spec in self._safety.get("interlocks", []):
            state = "unknown"
            try:
                value = self._read_value(spec, BridgeContext())
                if type(value) is type(closed_when):
                    state = "closed" if _equal(value, closed_when) else "open"
            except Exception:
                pass
            states.append({"id": ident, "state": state, "description": spec["description"]})
        return states

    def reset(self, ctx: Any = None) -> Any:
        context = _context(ctx)
        # Retirement must precede this reset's identity/debt snapshot. The fresh
        # stop it invokes must not remove captured IDs and invalidate itself.
        # Use the same bounded lane as action safety while retiring. Otherwise
        # reset teardown can overtake a concurrent stop's new endpoint setup.
        # Release it before the later reset service so e-stop remains independent.
        with self._safety_attempt(context, []):
            pass
        with self._condition:
            epoch = self.estop_epoch
            safety_generation = self._safety_reconcile_generation
            safety_debt = self._safety_reconciliation_needed
            if self._safety_history_error is not None:
                raise make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED", "ROS safety history cannot be reconciled on this connection",
                                     {"retryable": False})
            retained = list(self._actions.values())
            services = {ident: item for ident, item in self._pending.items() if item.effectful}
            if any(not item.abandoned or not self._service_settled(item) for item in services.values()):
                raise make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                     "ROS service callbacks remain unresolved; reset cannot clear unknown execution",
                                     {"retryable": False})
            if any(not item.abandoned or item.error is not None or item.response is None for item in retained):
                raise make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                     "ROS goals remain unresolved; reset cannot clear unknown execution",
                                     {"retryable": False})
        if self._sensed is not None:
            # SAFE-049: a reset of a sensed-confirmation device re-confirms the sensed safe state read-only (new
            # subscriptions, the same rules, no request and no re-enable) and is refused, latch kept, when it no
            # longer holds; it never resumes anything (SAFE-042).
            result = self._sensed_attempt(context, request=False)
            if not result["safe_state_achieved"]:
                raise make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                     "the sensed safe state is not confirmed now; the reset is refused",
                                     {"retryable": False,
                                      "details": {"sensed_reason": result["confirmation"].get("reason")}})
        elif retained or services or safety_debt:
            confirmed = self.safe_state(context)
            if not confirmed.get("achieved"):
                raise make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                     "reconciled ROS goals still require an acknowledged safe state", {"retryable": False})
        blocked = [state for state in self.interlocks() if state["state"] != "closed"]
        if blocked:
            raise make_mhs_error("MHS.SAFETY.INTERLOCK_OPEN", "ROS interlock does not permit reset",
                                 {"retryable": False, "interlocks": blocked})
        spec = self._safety.get("reset")
        ids = [item.ident for item in retained]
        service_ids = list(services)
        self._check_action_reconciliation(ids, service_ids, safety_generation=safety_generation)
        if spec is not None:
            guarded = BridgeContext.coerce({**context.__dict__,
                                            "extra": {**context.extra, "ros_reconcile_actions": ids,
                                                      "ros_reconcile_services": service_ids,
                                                      "ros_safety_reconcile_generation": safety_generation}})
            self._invoke(spec, {}, guarded, epoch=epoch, safety=True)
        with self._condition:
            self._refuse_if_estopped(epoch, "ROS safety reset")
            self._check_action_reconciliation(ids, service_ids, safety_generation=safety_generation)
            for ident in service_ids:
                self._pending.pop(ident, None)
            for item in retained:
                self._actions.pop(item.ident, None)
            self._safety_reconciliation_needed = False
            self._safe_state_achieved = False
        for item in retained:
            self._cleanup_action(item)
        return {"reset": True} if spec is not None else {}

    def safety_status(self) -> dict[str, Any]:
        if self._sensed is not None:
            # Only the committed confirmation of the current attempt counts; any native activity, new epoch,
            # disconnect or close since then invalidates it (SAFE-044: no claim beyond the confirmation window).
            with self._condition:
                achieved = (self._safe_state_achieved and not self.closed and self._fatal is None
                            and self._effects_settled_locked()
                            and self._safe_stamp == (self._native_activity, self.estop_epoch))
                last = copy.deepcopy(self._sensed_last)
            return {"estop": {"native": self.estop_native},
                    "safe_state": {"description": self._sensed.description, "achieved": achieved,
                                   "confirmation": {"kind": "sensed", "last": last}}}
        spec = self._safety.get("safe_state") or self._safety.get("estop")
        if spec is None:
            # A declared safe-state Action is also an independent stop path.
            # Its call commits the same retained proof as an explicit binding.
            spec = next((item for item in self._commands.values() if item["safe_state"]), None)
        if spec is None:
            effectful = (any(item["operation"] not in ("read", "subscribe")
                             for item in self._commands.values())
                         or any(self._writes.values()) or "reset" in self._safety)
            if not effectful:
                return {}
            # Even a simulated deployment may retain a target in another ROS
            # process. The server's local latch cannot confirm that it stopped.
            return {"estop": {"native": None}, "safe_state": {
                "description": "No acknowledged stop is declared for the ROS control surface",
                "achieved": False}}
        with self._condition:
            achieved = (self._safe_state_achieved and not self.closed and self._fatal is None
                        and self._effects_settled_locked()
                        and self._safe_stamp == (self._native_activity, self.estop_epoch))
        return {"estop": {"native": self.estop_native},
                "safe_state": {"description": spec["description"], "achieved": achieved}}

    def capabilities(self) -> list[dict[str, Any]]:
        return [{"capability_id": name, "resource": spec["resource"], "native": spec["name"]}
                for name, spec in self._commands.items()]

    def resources(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.config.get("resources", []))

    def close(self) -> None:
        if self.closed:
            return
        self._stop_reader.set()
        super().close()
        self._fail_connection(ConnectionError("ROS bridge closed"))
        # A validation transport need not implement close. Do not create or
        # connect a transport during teardown of a never-opened driver.
        close = getattr(self._transport, "close", None)
        if callable(close):
            close()
        if (self._reader_entered.is_set() and self._reader is not None
                and self._reader is not threading.current_thread()):
            self._reader.join(timeout=0.1)

    def describe(self) -> dict[str, Any]:
        out = super().describe()
        out.update({"transport": type(self._transport).__name__,
                    "safety_bindings": sorted(self._safety) + (["sensed_stop"] if self._sensed is not None else []),
                    "publish_confirmation": "transmission only"})
        return out
