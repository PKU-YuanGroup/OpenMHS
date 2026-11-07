"""Pinned-source and recorded-wire checks for ROS family drivers (gate G7).

ROS nodes need not expose Python classes. Their declared topic, service and action
names and types are checked against cited source lines instead. This is
evidence that the endpoint and type occur in the pinned repository; it does
not prove ROS graph resolution, callback semantics or hardware behaviour.

Companion sources (user decision 2026-11-05): when the task card declares
``companions``, the e-stop binding, its read-back (``safety_bindings.safe_state``)
and the command of the one action declared ``reenable=True`` may cite a companion
clone at its pinned commit (``companion:<alias>/<path>:<LINE>``); every other
binding cites the package's clone. A companion-cited stop needs a read-back, a
service whose name cannot resolve to the stop's endpoint however either is
spelled (global, relative or private), that
reads a state field (``success.path`` not ``$``, a scalar ``equals``) and
``state_ref`` on both bindings: the callback that sets the stopped state and the
line that fills the field the read-back compares. What the read-back means is
checked too (verification F2 of phase 3): it lives in the stop's namespace (the
same simulator world), compares no acknowledgement field (``success``,
``status_message``, ...), and its ``state_ref`` line assigns the field from
something other than a constant.

Two read-back forms extend that rule (preflight 2, 2026-11-05). A list-element
predicate (E4, ``success: {path, where, field, equals}``) compares the ``field``
of the one element whose ``where`` keys match, or, when ``where`` is a list of
2 to 4 selectors, of each distinct element those selectors match: ``state_ref``
must show ``field`` and every key of every selector. A stall read-back (E1, ``stall: {path, samples,
interval_ms, unchanged}``) confirms a stopped world by a value that no longer
advances: it is allowed only on the read-back of a companion-cited stop, its
``state_ref`` must show the stall path's last segment, and a Fact must cite a
declared companion (the line where that value advances only while the world
steps; the reviewer reads which). The acknowledgement and assignment rules
apply to the state each form compares: the stall path, or the selected
element's field, including every element a where list selects (a stall
read-back's own success predicate only accepts each answer).

Two more extend it (preflight 2, items E2 and E3). A fresh-sample topic
read-back (E2, ``safety_bindings.safe_state = {topic, type, operation:
'subscribe', success: {path, equals: <boolean>}, fresh}``) confirms a stop whose
simulator reports its paused flag only on a topic (gz-sim
``WorldStatistics.paused``): it is allowed only on the read-back of a
companion-cited stop (``ROS_FRESH_SCOPE``), compares one boolean state field
that the cited ``state_ref`` line shows and that is not an acknowledgement
(``success``, ``status_message``), and its topic must share the stop's
namespace (the same world: ``/world/<name>/stats`` and
``/world/<name>/control``). The bridges the operator must run (E3,
``RosDriver.operator_bridges``: ros_gz parameter_bridge arguments, each citing a
line that shows its ROS type, companion citations allowed) must each serve a
declared binding with the same name, type and direction
(``ROS_OPERATOR_BRIDGE_REF``, ``ROS_OPERATOR_BRIDGE_UNUSED``); with an E2
read-back every companion-cited endpoint of the stop, the read-back and the
re-enable must be one of them (``ROS_OPERATOR_BRIDGE_MISSING``), because a
simulator's own transport names exist on the ROS graph only through a bridge
that the clone does not start.

A ROS 2 sensed-stop source's cited ``history`` must show the QoS it claims
(verification F1): a transient-local durability with its depth, or a publisher
created without one.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Mapping

from .upstream import is_companion_ref, parse_ref, parse_source_ref, safe_relpath

_TYPE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)/(?:(msg|srv|action)/)?([A-Za-z][A-Za-z0-9_]*)$")
_NAME = re.compile(r"^(?:/|~/|~)?[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*$")
_NAME_CHARS = r"A-Za-z0-9_/~"
#: E3: the absolute ROS name, the ROS type (``pkg/msg/Name`` or ``pkg/srv/Name``) and the Gazebo type
#: (``gz.msgs.Name`` or ``ignition.msgs.Name``) of one ros_gz parameter_bridge argument.
_BRIDGE_NAME = re.compile(r"/[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*")
_BRIDGE_ROS_TYPE = re.compile(r"[A-Za-z][A-Za-z0-9_]*/(msg|srv)/[A-Za-z][A-Za-z0-9_]*")
_BRIDGE_GZ_TYPE = re.compile(r"(?:gz|ignition)\.msgs\.[A-Za-z][A-Za-z0-9_]*")
_BRIDGE_DIRECTIONS = {"@": "both", "[": "gz_to_ros", "]": "ros_to_gz"}
#: E2: a read-back compares a state field, never the acknowledgement of a request.
_ACKNOWLEDGEMENT_FIELDS = frozenset({"success", "status_message", "message", "result", "accepted", "ok"})


def parse_operator_bridge(text: Any) -> dict[str, Any] | None:
    """One ros_gz ``parameter_bridge`` argument (E3), parsed as the bridge's own usage text states it
    (companion ros_gz ``ros_gz_bridge/src/parameter_bridge.cpp``), or ``None``.

    A service: ``<name>@<pkg/srv/Name>`` or ``<name>@<pkg/srv/Name>@<gz request>@<gz reply>`` (exposed as a ROS
    service). A topic: ``<name>@<pkg/msg/Name><d><gz type>`` where ``d`` is ``@`` (both directions), ``[`` (Gazebo to
    ROS) or ``]`` (ROS to Gazebo). Only absolute names, full ROS type names and ``gz.msgs``/``ignition.msgs`` types;
    no whitespace, no remapping, nothing else. Returns ``{name, kind, ros_type, direction, gz_types}``.
    """
    if not isinstance(text, str) or not text or len(text) > 512 or any(ch.isspace() for ch in text):
        return None
    name, separator, rest = text.partition("@")
    if not separator or not _BRIDGE_NAME.fullmatch(name):
        return None
    cut = min((rest.find(symbol) for symbol in _BRIDGE_DIRECTIONS if rest.find(symbol) >= 0), default=-1)
    ros_type = rest if cut < 0 else rest[:cut]
    match = _BRIDGE_ROS_TYPE.fullmatch(ros_type)
    if match is None:
        return None
    if match.group(1) == "srv":
        if cut < 0:
            return {"name": name, "kind": "service", "ros_type": ros_type, "direction": "service", "gz_types": ()}
        if rest[cut] != "@":
            return None
        types = rest[cut + 1:].split("@")
        if len(types) != 2 or not all(_BRIDGE_GZ_TYPE.fullmatch(item) for item in types):
            return None
        return {"name": name, "kind": "service", "ros_type": ros_type, "direction": "service",
                "gz_types": tuple(types)}
    if cut < 0:
        return None
    gz_type = rest[cut + 1:]
    if not _BRIDGE_GZ_TYPE.fullmatch(gz_type):
        return None
    return {"name": name, "kind": "topic", "ros_type": ros_type, "direction": _BRIDGE_DIRECTIONS[rest[cut]],
            "gz_types": (gz_type,)}


def _bridge_serves(bridge: Mapping[str, Any], key: str, spec: Mapping[str, Any]) -> bool:
    """Whether a parsed operator bridge carries a binding's endpoint: the same name and ROS type, a service bridge for a
    service, a bridge towards ROS for a subscription and one towards Gazebo for a publication."""
    if spec.get(key) != bridge["name"] or spec.get("type") != bridge["ros_type"]:
        return False
    if key == "service":
        return bridge["kind"] == "service"
    if key != "topic" or bridge["kind"] != "topic":
        return False
    subscribes = spec.get("operation") == "subscribe" or "fresh" in spec
    return bridge["direction"] in (("both", "gz_to_ros") if subscribes else ("both", "ros_to_gz"))


def _namespace(name: Any) -> tuple[str, ...] | None:
    """The segments of a global ROS name without its last one (``/world/x/stats`` -> ``('world', 'x')``)."""
    if not isinstance(name, str):
        return None
    kind, parts = _name_parts(name)
    if kind != "global" or len(parts) < 2:
        return None
    return parts[:-1]


def _bindings(cls: type, reenable: str | None = None) -> Iterator[tuple[str, Mapping[str, Any], str, bool]]:
    """``(label, spec, group, companion_ok)`` of every binding; ``companion_ok`` marks the bindings that may cite a
    declared companion source: the e-stop, its read-back and the command of the declared re-enable ``reenable``."""
    for group in ("commands", "reads", "writes"):
        for key, spec in dict(getattr(cls, group, {}) or {}).items():
            if isinstance(spec, Mapping):
                if group == "commands" and "cameras" in spec:
                    # Declaration validation checks shape; G7 must still inspect
                    # every static source even when a test invokes only one.
                    cameras = spec.get("cameras")
                    if isinstance(cameras, Mapping):
                        for camera, source in cameras.items():
                            if isinstance(source, Mapping):
                                yield f"{group}[{key!r}].cameras[{camera!r}]", source, group, False
                        continue
                yield f"{group}[{key!r}]", spec, group, group == "commands" and reenable is not None and key == reenable
                then = spec.get("then") if group == "commands" else None
                if isinstance(then, Mapping):
                    # A publish-then-step command: its step (a service call) and its observation (a read) are
                    # declarations of their own, each with its own citation, and the only wire operations allowed
                    # at their endpoints besides the publication's.
                    if isinstance(then.get("step"), Mapping):
                        yield f"{group}[{key!r}].then.step", then["step"], "commands", False
                    if isinstance(then.get("observe"), Mapping):
                        yield f"{group}[{key!r}].then.observe", then["observe"], "reads", False
    safety = dict(getattr(cls, "safety_bindings", {}) or {})
    for name in ("estop", "safe_state", "reset"):
        spec = safety.get(name)
        if isinstance(spec, Mapping):
            yield f"safety_bindings.{name}", spec, "safety", name in ("estop", "safe_state")
    for index, spec in enumerate(safety.get("interlocks") or []):
        if isinstance(spec, Mapping):
            yield f"safety_bindings.interlocks[{index}]", spec, "reads", False
    sensed = safety.get("sensed_stop")
    if isinstance(sensed, Mapping):
        # SAFE-049: every request step and every sensed source cites its endpoint and type like any binding.
        for index, spec in enumerate(sensed.get("request") or []):
            if isinstance(spec, Mapping):
                yield f"safety_bindings.sensed_stop.request[{index}]", spec, "sensed_request", False
        for name, spec in dict(sensed.get("sources") or {}).items():
            if isinstance(spec, Mapping):
                yield f"safety_bindings.sensed_stop.sources[{name!r}]", spec, "reads", False


def _reenable_capability(ctx: Any) -> str | None:
    """The capability declared ``reenable=True`` (CORE-086), from the resolved model or the declared actions."""
    model = getattr(ctx, "model", None)
    if model is not None:
        return getattr(model, "reenable", None)
    for capability_id, action in dict(getattr(ctx.cls, "actions", {}) or {}).items():
        if getattr(action, "reenable", False) is True:
            return str(capability_id)
    return None


def _source_text(ctx: Any, gate: Any, ref: Any, label: str, companion_ok: bool) -> str | None:
    """The cited text of ``ref``: the package clone's, or a declared companion's where the binding may cite one."""
    if not is_companion_ref(ref):
        return _cited_text(ctx.tree, gate, ref, label)
    parsed = parse_source_ref(ref)
    if parsed is None:
        gate.error("ROS_REF_FORMAT", f"{label} needs 'companion:<alias>/path:LINE' with a clean relative path", label,
                   str(ref))
        return None
    alias, _cited = parsed
    if not companion_ok:
        gate.error("ROS_COMPANION_SCOPE", f"{label} cites the companion source {alias!r}; only the e-stop, its "
                   "read-back (safety_bindings.safe_state) and the command of the action declared reenable=True may "
                   "cite a companion; every other binding cites the package's own clone", label, str(ref))
        return None
    source = dict(getattr(ctx, "companions", {}) or {}).get(alias)
    if source is None:
        gate.error("ROS_COMPANION_UNDECLARED", f"{label} cites companion {alias!r}, which task.json does not declare "
                   "(companions come only from a reviewed registry override)", label, str(ref))
        return None
    if source.tree is None or not source.tree.pinned:
        gate.error("ROS_REF_MISSING", f"{label}: the companion clone of {alias!r} cannot be read at its pinned commit "
                   "(G1, G2)", label, str(ref))
        return None
    return _cited_text(source.tree, gate, f"{_cited.path}:{_cited.line}-{_cited.end}", label, shown=str(ref))


def _cites_companion(spec: Mapping[str, Any]) -> bool:
    return any(is_companion_ref(spec.get(key)) for key in ("source_ref", "type_ref", "state_ref"))


_SCALAR = (bool, int, float, str)


def _name_parts(name: str) -> tuple[str, tuple[str, ...]]:
    """``(kind, segments)`` of a ROS graph name: ``global`` (``/a/b``), ``private`` (``~a/b``, ``~/a/b``) or
    ``relative`` (``a/b``), with empty segments dropped."""
    text = name.strip()
    if text.startswith("/"):
        kind, text = "global", text[1:]
    elif text.startswith("~"):
        kind, text = "private", text[1:]
    else:
        kind = "relative"
    return kind, tuple(segment for segment in text.split("/") if segment)


def _may_name_the_same_endpoint(first: Any, second: Any) -> bool:
    """Whether two ROS graph names can resolve to the same endpoint. Two global names, or two names of the same
    kind (resolved against the same node), do exactly when their segments are equal. A relative or private name
    resolves against a namespace or node name the gate cannot see, so it may name any name whose segments end with
    its own: ``gazebo/pause_physics`` and ``pause_physics`` may both be ``/gazebo/pause_physics``."""
    if not isinstance(first, str) or not isinstance(second, str):
        return False
    (kind_a, parts_a), (kind_b, parts_b) = _name_parts(first), _name_parts(second)
    if not parts_a or not parts_b:
        return first.strip() == second.strip()
    if kind_a == kind_b:
        return parts_a == parts_b
    shorter, longer = sorted((parts_a, parts_b), key=len)
    return longer[len(longer) - len(shorter):] == shorter


#: Fields that acknowledge a request instead of reporting state (std_srvs, gazebo_msgs, mavros_msgs, ... responses):
#: a read-back never compares one (verification F2 of phase 3).
_ACK_FIELDS = frozenset({"success", "succeeded", "status_message", "message", "result", "ok", "error", "error_code",
                         "error_message", "error_string", "errmsg", "ack", "acknowledged", "accepted",
                         # integrator edit I10 (Claude Sonnet review S4 of p3-hardening-3): status, done, code, sent and
                         # completed style fields report what became of the request, not the stopped state
                         "status", "status_code", "code", "return_code", "result_code", "done", "is_done", "sent",
                         "completed", "complete", "finished", "executed", "handled", "received"})
#: A right-hand side that reads the request (``req.x``, ``request->x``, ``goal->x``, ``req["x"]``, also through a
#: dereference or a cast): an echo of what the caller sent, never the stopped state (integrator edit I10, Claude
#: Sonnet review S4 of p3-hardening-3).
_FROM_REQUEST = re.compile(r"(?<![A-Za-z0-9_])_?(?:req|request|goal)_?\s*\)?\s*(?:->|\.|\[)")
#: A right-hand side that is a constant, not a read state: ``true``, a number, a string, a null.
_CONSTANT = re.compile(r"""\s*(?:true|false|True|False|TRUE|FALSE|nullptr|NULL|None|nil|[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?[fFuUlL]*
                           |"[^"\n]*"|'[^'\n]*')\s*(?:[;,)}\]]|//|\#|$)""", re.VERBOSE)


def _assigned_from_state(field: str, text: str) -> bool:
    """Whether ``text`` assigns ``field`` (``x.field = ...``, ``field=...``, ``"field": ...``, or a protobuf setter
    ``msg.set_field(...)``) from something other than a constant on at least one line: a response filled from the
    stopped state, not a fixed acknowledgement. A value that reads the request anywhere in its statement
    (``res.x = req.x``, ``res->x = request->x && ...``) is an echo of what the caller sent and never counts
    (integrator edit I10). The setter form is how a gz-msgs message (p3-companion-3's fresh read-back of
    ``WorldStatistics.paused``: ``msg.set_paused(this->currentInfo.paused);``) fills its field (integrator join
    R-V4-15)."""
    name = re.escape(field)
    pattern = re.compile(rf"""(?:(?<![A-Za-z0-9_]){name}\s*=(?!=)|(["']){name}\1\s*:|(?<![A-Za-z0-9_])set_{name}\s*\()""")
    for line in text.splitlines():
        for match in pattern.finditer(line):
            value = line[match.end():]
            statement = value.split(";", 1)[0]
            if _CONSTANT.match(value) is None and value.strip() and _FROM_REQUEST.search(statement) is None:
                return True
    return False


def _same_world(first: Any, second: Any) -> bool:
    """Whether two ROS graph names live in the same namespace (the same simulator world): both global, or both
    relative, or both private, with equal segments before the last. A pair written in different kinds resolves
    against namespaces the gate cannot see, so it is never shown to be the same world (verification F2)."""
    if not isinstance(first, str) or not isinstance(second, str):
        return False
    (kind_a, parts_a), (kind_b, parts_b) = _name_parts(first), _name_parts(second)
    return bool(parts_a) and bool(parts_b) and kind_a == kind_b and parts_a[:-1] == parts_b[:-1]


def _same_selector(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Type-strict equality of two E4 selectors (scalar values; key order does not matter)."""
    if set(left) != set(right):
        return False
    for key in left:
        one, other = left[key], right[key]
        if type(one) is not type(other) or one != other:
            return False
    return True


def _e4_where(where: Any) -> tuple[list[str] | None, str | None]:
    """``(keys, problem)`` of an E4 ``where``.

    A mapping returns its keys and no problem (the single-element form, unchanged). A list of 2 to 4 non-empty
    selector objects returns every key in first-seen order. Any other list is a problem and contributes no keys:
    one selector stays an object, and repeated selectors can never match two elements. Absent or any other shape
    is not a list-element predicate.
    """
    if isinstance(where, Mapping):
        return [str(key) for key in where], None
    if not isinstance(where, list):
        return None, None
    if not 2 <= len(where) <= 4 or not all(
            isinstance(item, Mapping) and 1 <= len(item) <= 4 and all(isinstance(key, str) for key in item)
            for item in where):
        return None, ("its list-element where list needs 2 to 4 selector objects of 1 to 4 fields each (one "
                      "selector stays an object)")
    seen: list[Mapping[str, Any]] = []
    keys: list[str] = []
    for item in where:
        if any(_same_selector(item, earlier) for earlier in seen):
            return None, ("its list-element where list repeats a selector; two equal selectors cannot match two "
                          "elements")
        seen.append(item)
        for key in item:
            if key not in keys:
                keys.append(str(key))
    return keys, None


def _check_readback(ctx: Any, gate: Any, safety: Mapping[str, Any], estop: Mapping[str, Any],
                    readback: Any) -> None:
    """A companion-cited stop is confirmed only by a read-back that reads a state field (user decision 2026-11-05).

    Verification F2 of phase 3: the read-back is in the stop's namespace (the same world), its predicate compares no
    acknowledgement field, and its ``state_ref`` line assigns the compared field from something other than a
    constant (the stopped state, as ``res.pause = world_->IsPaused();``).
    """
    label = "safety_bindings.safe_state"
    problems = []
    if not estop:
        gate.error("ROS_COMPANION_READBACK", "a read-back that cites a companion source confirms a stop: declare that "
                   "stop as safety_bindings.estop", "safety_bindings.estop")
        return
    if not isinstance(readback, Mapping):
        gate.error("ROS_COMPANION_READBACK", "a stop that cites a companion source needs safety_bindings.safe_state: a "
                   "service call that reads the stopped state back (an acknowledgement alone never confirms it)",
                   label)
        return
    fresh = "fresh" in readback
    if "service" not in readback and not (fresh and "topic" in readback):
        problems.append("the read-back must be a service call, or a fresh-sample topic read-back (E2: topic and fresh)")
    target = estop.get("service", estop.get("action", estop.get("topic")))
    if readback.get("service") is not None and _may_name_the_same_endpoint(readback.get("service"), target):
        problems.append("the read-back must be a call distinct from the stop request (the two names may resolve to "
                        "the same endpoint)")
    if readback.get("service") is not None and not _same_world(readback.get("service"), target):
        problems.append(f"the read-back {readback.get('service')!r} must be in the namespace of the stop {target!r} "
                        "(the same simulator world): both global, relative or private names with equal segments "
                        "before the last")
    success = readback.get("success")
    path = success.get("path") if isinstance(success, Mapping) else None
    equals = success.get("equals") if isinstance(success, Mapping) else None
    if not isinstance(path, str) or path == "$" or not isinstance(equals, _SCALAR):
        problems.append("its success predicate must compare one state field (path not '$') with a scalar value")
    if fresh:
        # E2: one boolean state flag of the world the stop paused, never the acknowledgement of a request.
        if not isinstance(equals, bool):
            problems.append("a fresh-sample topic read-back compares one boolean state flag (success.equals true or "
                            "false)")
        if isinstance(path, str) and path.split(".")[-1] in _ACKNOWLEDGEMENT_FIELDS:
            problems.append(f"a fresh-sample topic read-back compares a state field, not an acknowledgement field "
                            f"({path.split('.')[-1]!r})")
        stop_space, read_space = _namespace(target), _namespace(readback.get("topic"))
        if stop_space is None or stop_space != read_space:
            problems.append("a fresh-sample topic read-back must share the stop's namespace (global names that differ "
                            "only in their last segment, the same world: /world/<name>/stats and "
                            "/world/<name>/control)")
    where = success.get("where") if isinstance(success, Mapping) else None
    where_keys, where_problem = _e4_where(where)
    if where_problem:
        problems.append(where_problem)
    stall = readback.get("stall")
    if stall is not None:
        stall_path = stall.get("path") if isinstance(stall, Mapping) else None
        if not isinstance(stall_path, str) or stall_path in ("", "$"):
            problems.append("its stall must name the field that advances while the world runs (stall.path)")
        if not any(is_companion_ref(getattr(fact, "ref", None)) for fact in getattr(ctx.cls, "facts", None) or []):
            problems.append("a stall read-back needs a Fact that cites a declared companion: the line where the compared "
                            "value advances only while the world steps")
    # The state the read-back compares (integrator v4, R-V4-06: p3-companion-2's stall and list-element forms with
    # p3-hardening-3's acknowledgement rule): the value at stall.path for a stall read-back, whose own success
    # predicate only accepts each answer (GetModelList's success), the selected element's field for a list-element
    # predicate (one selector, or every selector of a where list), the path otherwise. That state is never an
    # acknowledgement field (verification F2 of phase 3).
    if isinstance(stall, Mapping):
        compared, compares = stall.get("path"), "its stall compares"
    elif where_problem:
        compared, compares = None, "its list-element predicate compares"
    elif where_keys is not None:
        compared, compares = success.get("field"), "its list-element predicate compares"
    else:
        compared, compares = path, "its success predicate compares"
    if isinstance(path, str) and path != "$" and isinstance(equals, _SCALAR) and isinstance(compared, str) \
            and any(part in _ACK_FIELDS for part in compared.split(".")):
        problems.append(f"{compares} {compared!r}, an acknowledgement of the request, not the stopped state (never "
                        f"one of {sorted(_ACK_FIELDS)})")
    for name, spec in (("safety_bindings.estop", estop), (label, readback)):
        if not isinstance(spec.get("state_ref"), str):
            problems.append(f"{name} needs state_ref: the line that sets (the stop) or reports (the read-back) the "
                            "stopped state")
    for problem in problems:
        gate.error("ROS_COMPANION_READBACK", f"{label}: {problem}", label)
    if problems or not isinstance(path, str):
        return
    # The word the state_ref line must show: the stall's advancing field, the selected element's field, or the
    # compared field itself; a list-element predicate's where keys must show too.
    if isinstance(stall, Mapping):
        words, what = [str(stall["path"]).split(".")[-1]], "its stall compares"
    elif where_problem:
        words, what = [], "its list-element predicate selects"
    elif where_keys is not None:
        words, what = [str(success.get("field")).split(".")[-1], *where_keys], "its list-element predicate selects"
    else:
        words, what = [path.split(".")[-1]], "its success predicate compares"
    text = _quiet_text(ctx, readback.get("state_ref"))  # its format, scope and lines are reported with the binding
    for index, field in enumerate(words):
        if text is not None and (field.isdigit() or re.search(rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])",
                                                              text) is None):
            gate.error("ROS_COMPANION_READBACK", f"{label}: the cited state_ref does not show the field {field!r} "
                       f"{what}", label, str(readback.get("state_ref")))
        elif index == 0 and text is not None and not _assigned_from_state(field, text):
            # the compared state only: a list-element predicate's where keys select the element, they report nothing
            gate.error("ROS_COMPANION_READBACK", f"{label}: the cited state_ref does not assign the field {field!r} "
                       "from the stopped state (only from a constant, or not at all): the read-back must report state, "
                       "never a fixed acknowledgement", label, str(readback.get("state_ref")))


def _quiet_text(ctx: Any, ref: Any) -> str | None:
    """The text ``ref`` cites (package clone or declared companion at its pin), ``None`` without a finding."""
    parsed = parse_source_ref(ref)
    if parsed is None:
        return None
    alias, cited = parsed
    if alias is None:
        tree = ctx.tree
    else:
        source = dict(getattr(ctx, "companions", {}) or {}).get(alias)
        tree = source.tree if source is not None and source.tree is not None and source.tree.pinned else None
    if tree is None or safe_relpath(cited.path) is None:
        return None
    document = tree.read_text(cited.path)
    lines = document.splitlines() if document is not None else []
    if document is None or cited.end > len(lines):
        return None
    return "\n".join(lines[cited.line - 1:cited.end])


def _cited_text(tree: Any, gate: Any, ref: Any, label: str, *, shown: str | None = None) -> str | None:
    parsed = parse_ref(ref)
    cited = str(ref) if shown is None else shown
    if parsed is None or safe_relpath(parsed.path) is None:
        gate.error("ROS_REF_FORMAT", f"{label} needs a relative path:LINE source citation", label, cited)
        return None
    document = tree.read_text(parsed.path)
    if document is None:
        gate.error("ROS_REF_MISSING", f"{label}: {parsed.path} is missing or is not readable text in the pinned "
                   "source tree", label, cited)
        return None
    lines = document.splitlines()
    if parsed.end > len(lines):
        gate.error("ROS_REF_LINE", f"{label}: cited line {parsed.end} exceeds the {len(lines)} lines in "
                   f"{parsed.path}", label, cited)
        return None
    return "\n".join(lines[parsed.line - 1:parsed.end])


def _source_name(endpoint: str, source: Any) -> str | None:
    """Explicit relative/private names can acquire a namespace; absolute names cannot."""
    if source is None:
        return endpoint
    if not isinstance(source, str) or not _NAME.fullmatch(source):
        return None
    if source.startswith("/"):
        return source if source == endpoint else None
    relative = source.lstrip("~").lstrip("/")
    return source if endpoint == relative or endpoint.endswith("/" + relative) else None


def _name_shown(name: str, text: str) -> bool:
    if name.startswith("/"):
        # Absolute names in prose or a table are unambiguous tokens too.
        return re.search(rf"(?<![{_NAME_CHARS}]){re.escape(name)}(?![{_NAME_CHARS}])", text) is not None
    # A relative name such as 'stop' must be a literal/code span, not an
    # arbitrary word in a sentence about stopping. Full private names count.
    return re.search(rf"(['\"`]){re.escape(name)}\1", text) is not None


def _type_parts(value: Any, kind: str) -> tuple[str, str, str] | None:
    if not isinstance(value, str):
        return None
    match = _TYPE.fullmatch(value)
    if match is None or (match.group(2) is not None and match.group(2) != kind):
        return None
    return match.group(1), kind, match.group(3)


def _type_shown(parts: tuple[str, str, str], text: str) -> bool:
    package, kind, name = parts
    forms = (f"{package}/{name}", f"{package}/{kind}/{name}", f"{package}::{name}",
             f"{package}::{kind}::{name}", f"{package}.{kind}.{name}")
    for form in forms:
        if re.search(rf"(?<![A-Za-z0-9_./:]){re.escape(form)}(?![A-Za-z0-9_./:])", text):
            return True
    # Explicit Python imports or C++ generated-message includes prove the
    # fully qualified type even if a use site employs only its short name.
    if re.search(rf"\bfrom\s+{re.escape(package)}\.{kind}\s+import\s+[^\n;]*\b{re.escape(name)}\b", text):
        return True
    snake = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", snake).lower()
    return re.search(rf"#\s*include\s*[<\"]{re.escape(package)}/(?:{kind}/)?"
                     rf"(?:{re.escape(name)}|{re.escape(snake)})\.(?:h|hpp)[>\"]", text) is not None


#: A transient-local (latched) durability as rclcpp, rclpy, rmw or ROS 1 code writes it.
_TRANSIENT = re.compile(r"(?i)transient[_ ]?local|\blatch(?:ed|ing)?\b")
#: A publisher created or configured on the cited line(s).
_PUBLISHER = re.compile(r"create_publisher|\bPublisher\b|\badvertise\b")
#: Predefined QoS profiles a create_publisher call may name without defining them (rclpy, rmw).
_QOS_PRESETS = frozenset({"qos_profile_sensor_data", "qos_profile_system_default", "qos_profile_services_default",
                          "qos_profile_parameters", "qos_profile_parameter_events", "rmw_qos_profile_default",
                          "rmw_qos_profile_sensor_data", "rmw_qos_profile_system_default"})
_QOS_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:(?:\.|::|->)[A-Za-z_][A-Za-z0-9_]*)*")


def _code_only(text: str) -> str:
    """The cited text without comments (``/* */`` and ``//`` of C and C++, ``#`` of Python and CMake): a durability
    word in a comment shows nothing (integrator edit I11, Claude Sonnet review S5 of p3-hardening-3)."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return "\n".join(re.split(r"//|#", line, maxsplit=1)[0] for line in text.splitlines())


def _qos_variables(code: str) -> list[str]:
    """The QoS arguments of the create_publisher calls in ``code`` that are plain names (not a literal, a constructed
    profile or a predefined one) defined nowhere in the cited text: such a QoS is set elsewhere, so the cited line
    does not show it (integrator edit I11). A call the cited lines do not close shows no QoS either."""
    out = []
    for match in re.finditer(r"create_publisher\s*(?:<[^()]*>)?\s*\(", code):
        depth, current, args = 1, [], []
        for char in code[match.end():]:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth == 0:
                    break
            if char == "," and depth == 1:
                args.append("".join(current))
                current = []
            else:
                current.append(char)
        else:
            out.append("<the call is not closed in the cited lines>")
            continue
        args.append("".join(current))
        qos = args[-1].strip()
        if _QOS_NAME.fullmatch(qos):
            name = re.split(r"\.|::|->", qos)[-1]
            if name not in _QOS_PRESETS and re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*(?:=(?!=)|\(|\{{)",
                                                     code) is None:
                out.append(qos)
    return out


def _check_operator_bridges(ctx: Any, gate: Any, declarations: list[tuple[str, Mapping[str, Any], str, bool]],
                            readback: Any) -> None:
    """E3: every declared operator bridge cites a line showing its ROS type and serves a declared binding; with an
    E2 read-back, every companion-cited endpoint of the stop, the read-back and the re-enable is one of them."""
    raw = getattr(ctx.cls, "operator_bridges", ()) or ()
    bridges: list[dict[str, Any]] = []
    for index, item in enumerate(raw if isinstance(raw, (list, tuple)) else ()):
        label = f"operator_bridges[{index}]"
        parsed = parse_operator_bridge(item.get("args")) if isinstance(item, Mapping) else None
        if parsed is None:
            continue  # a malformed entry is a definition problem (G3)
        bridges.append(parsed)
        parts = _type_parts(parsed["ros_type"], "srv" if parsed["kind"] == "service" else "msg")
        text = _source_text(ctx, gate, item.get("ref"), label + ".ref", True)
        if text is not None and (parts is None or not _type_shown(parts, text)):
            gate.error("ROS_OPERATOR_BRIDGE_REF", f"{label}: the cited line does not show the bridge's ROS type "
                       f"{parsed['ros_type']!r}", label, str(item.get("ref")))
        if not any(_bridge_serves(parsed, key, spec) for _label, spec, _group, _ok in declarations
                   for key in ("service", "topic") if key in spec):
            gate.error("ROS_OPERATOR_BRIDGE_UNUSED", f"{label} bridges {parsed['name']} ({parsed['ros_type']}, "
                       f"{parsed['direction']}), which no declared binding uses with that type and direction; the "
                       "operator runs only what the package needs", label)
    if not (isinstance(readback, Mapping) and "fresh" in readback):
        return
    for label, spec, _group, companion_ok in declarations:
        if not companion_ok or not is_companion_ref(spec.get("source_ref")):
            continue
        keys = [key for key in ("service", "topic") if key in spec]
        if not keys or not any(_bridge_serves(bridge, keys[0], spec) for bridge in bridges):
            gate.error("ROS_OPERATOR_BRIDGE_MISSING", f"{label} names a simulator endpoint cited in a companion; with a "
                       "fresh-sample read-back it exists on the ROS graph only through a bridge the operator runs, so "
                       "operator_bridges must carry it with the same name, type and direction", label)


def _check_history_refs(ctx: Any, gate: Any, sensed: Mapping[str, Any]) -> None:
    """Every cited ``history`` of a ROS 2 sensed source exists at the pin and shows the QoS it claims (verification
    F1 of phase 3).

    ``transient_local``: the cited lines show a transient-local durability and the depth. ``volatile``: they create
    or configure the publisher and show no transient-local durability, or say ``volatile`` outright. Comments show
    nothing, and a ``volatile`` publisher whose QoS is a variable the cited lines do not define (or whose call they
    do not close) shows nothing either (integrator edit I11). Whether the line is the source's publisher is the
    reviewer's reading; an ``operator_required`` history cites nothing.
    """
    for name, source in dict(sensed.get("sources") or {}).items():
        history = source.get("history") if isinstance(source, Mapping) else None
        if not isinstance(history, Mapping) or "ref" not in history:
            continue
        label = f"safety_bindings.sensed_stop.sources[{name!r}].history"
        text = _cited_text(ctx.tree, gate, history.get("ref"), label)
        if text is None:
            continue
        durability = history.get("durability")
        code = _code_only(text)  # integrator edit I11: a QoS word in a comment shows nothing
        if durability == "transient_local":
            depth = history.get("depth")
            if _TRANSIENT.search(code) is None or not isinstance(depth, int) or re.search(
                    rf"(?<![0-9.]){depth}(?![0-9.])", code) is None:
                gate.error("ROS_HISTORY_NOT_SHOWN", f"{label}: the cited line does not show a transient-local "
                           f"durability with depth {depth!r}", label, str(history.get("ref")))
        elif durability == "volatile":
            hidden = _qos_variables(code)
            if re.search(r"(?i)(?<![a-z])volatile(?![a-z])", code) is None and (
                    _TRANSIENT.search(code) is not None or _PUBLISHER.search(code) is None or hidden):
                gate.error("ROS_HISTORY_NOT_SHOWN", f"{label}: the cited line does not create a publisher without a "
                           "transient-local durability (nor say volatile)"
                           + (f"; it passes the QoS {hidden[0]!r}, which the cited lines do not define" if hidden else ""),
                           label, str(history.get("ref")))


def _check_fill_refs(ctx: Any, gate: Any, sensed: Mapping[str, Any]) -> None:
    """Every ``fill_refs`` line of a sensed source exists at the pin and shows the field it vouches for (SAFE-049).

    The line is where the producer assigns the field, where the clone's own code reads it from that topic, or a
    vendor document that states it; the gate checks that the line exists and shows the field's last name (an
    array index counts by its parent's name). Whether it proves what the term needs is the reviewer's reading.
    """
    for name, source in dict(sensed.get("sources") or {}).items():
        refs = source.get("fill_refs") if isinstance(source, Mapping) else None
        for path, ref in dict(refs or {}).items():
            label = f"safety_bindings.sensed_stop.sources[{name!r}].fill_refs[{path!r}]"
            text = _cited_text(ctx.tree, gate, ref, label)
            if text is None:
                continue
            names = [part for part in str(path).split(".") if part and not part.isdigit()]
            if names and re.search(rf"(?<![A-Za-z0-9_]){re.escape(names[-1])}(?![A-Za-z0-9_])", text) is None:
                gate.error("ROS_FILL_REF_NOT_SHOWN", f"{label}: the cited line does not show the field "
                           f"{names[-1]!r}", label, str(ref))


def _allow_exclusion(ctx: Any, gate: Any, sensed: Mapping[str, Any],
                     allowed: dict[tuple[str, str], set[tuple[str, str, str]]]) -> None:
    """Let a sensed-stop exclusion subscribe to the request topic it watches.

    The request binding already cites that topic and its type. The exclusion is not a confirmation source. Its
    ``source_ref`` must show each watched field, which is the competing publisher. Subscribe and unsubscribe on
    that topic are then declared wire operations.
    """
    exclusion = sensed.get("exclusion")
    if not isinstance(exclusion, Mapping):
        return
    label = "safety_bindings.sensed_stop.exclusion"
    topic = exclusion.get("topic")
    parts = _type_parts(exclusion.get("type"), "msg")
    published = allowed.get(("publish", topic)) if isinstance(topic, str) else None
    if parts is None or published is None or parts not in published:
        gate.error("ROS_EXCLUSION", f"{label} may subscribe only to a request topic, and its type must match "
                   "that request", label)
        return
    text = _cited_text(ctx.tree, gate, exclusion.get("source_ref"), label + ".source_ref")
    for path in exclusion.get("paths") or []:
        names = [part for part in str(path).split(".") if part and not part.isdigit()]
        if text is not None and names and re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(names[-1])}(?![A-Za-z0-9_])", text) is None:
            gate.error("ROS_EXCLUSION_NOT_SHOWN", f"{label}.source_ref does not show the watched field "
                       f"{names[-1]!r}", label, str(exclusion.get("source_ref")))
    for op in ("subscribe", "unsubscribe"):
        allowed.setdefault((op, topic), set()).add(parts)


def check_ros_surface(ctx: Any, gate: Any) -> None:
    """Check every declaration, then the messages actually observed by Recorder.

    ``source_name`` states an upstream relative/private name when the
    configured endpoint adds a namespace. ``type_ref`` optionally cites a
    separate import/include line. Neither permits arbitrary remapping or
    guessing the deployment's namespace.
    """
    allowed: dict[tuple[str, str], set[tuple[str, str, str]]] = {}
    action_roles: dict[tuple[str, str], tuple[str, str, str]] = {}
    declarations = list(_bindings(ctx.cls, _reenable_capability(ctx)))
    safety = dict(getattr(ctx.cls, "safety_bindings", {}) or {})
    estop = safety.get("estop")
    if (isinstance(estop, Mapping) and _cites_companion(estop)) or (
            isinstance(safety.get("safe_state"), Mapping) and _cites_companion(safety["safe_state"])):
        _check_readback(ctx, gate, safety, estop if isinstance(estop, Mapping) else {}, safety.get("safe_state"))
    readback = safety.get("safe_state")
    if isinstance(readback, Mapping) and "stall" in readback and not (isinstance(estop, Mapping)
                                                                       and _cites_companion(estop)):
        # E1 (preflight 2): a frozen value confirms a stop only where the stop is a world pause of a reviewed
        # companion; anywhere else a stall read-back is refused.
        gate.error("ROS_STALL_SCOPE", "safety_bindings.safe_state.stall: a stall read-back confirms only an e-stop "
                   "that cites a declared companion source (a simulator's world pause)", "safety_bindings.safe_state")
    if isinstance(readback, Mapping) and "fresh" in readback and not (isinstance(estop, Mapping)
                                                                       and _cites_companion(estop)):
        # E2 (preflight 2): a flag read from fresh topic samples confirms a stop only where the stop is a world pause
        # of a reviewed companion; anywhere else a fresh-sample read-back is refused.
        gate.error("ROS_FRESH_SCOPE", "safety_bindings.safe_state.fresh: a fresh-sample topic read-back confirms only "
                   "an e-stop that cites a declared companion source (a simulator's world pause)",
                   "safety_bindings.safe_state")
    _check_operator_bridges(ctx, gate, declarations, readback)
    for label, spec, group, companion_ok in declarations:
        endpoints = [name for name in ("service", "topic", "action") if name in spec]
        if len(endpoints) != 1:
            gate.error("ROS_ENDPOINT", f"{label} needs exactly one topic, service or action endpoint", label)
            continue
        key = endpoints[0]
        endpoint = spec.get(key)
        if not isinstance(endpoint, str) or not _NAME.fullmatch(endpoint):
            gate.error("ROS_ENDPOINT", f"{label} has no valid ROS topic, service or action name", label)
            continue
        profile = spec.get("profile") if key == "action" else None
        if key == "action":
            safety_stop = group == "safety" and label in ("safety_bindings.estop", "safety_bindings.safe_state")
            if profile not in ("ros1-actionlib", "ros2-native") or not (group == "commands" or safety_stop):
                gate.error("ROS_ACTION_PROFILE", f"{label} needs an explicit supported action profile in commands "
                           "or fixed safety stops", label)
                continue
            version = 1 if profile == "ros1-actionlib" else 2
            if getattr(ctx.cls, "ros_version", version) != version:
                gate.error("ROS_ACTION_PROFILE", f"{label} profile disagrees with ros_version", label)
                continue
        source_name = _source_name(endpoint, spec.get("source_name"))
        if source_name is None:
            gate.error("ROS_SOURCE_NAME", f"{label}.source_name must be the endpoint or an explicit relative/private "
                       "suffix of it; an absolute source name cannot be remapped by this check", label)
        text = _source_text(ctx, gate, spec.get("source_ref"), label + ".source_ref", companion_ok)
        if "state_ref" in spec:
            _source_text(ctx, gate, spec["state_ref"], label + ".state_ref", companion_ok)
        if text is not None and source_name is not None and not _name_shown(source_name, text):
            gate.error("ROS_ENDPOINT_NOT_UPSTREAM", f"{label}: the cited source does not show the exact endpoint "
                       f"literal {source_name!r}", label, spec.get("source_ref"))
        kind = "srv" if key == "service" else "action" if profile == "ros2-native" else "msg"
        parts = _type_parts(spec.get("type"), kind)
        if key == "action" and parts is not None:
            expected = (f"{parts[0]}/{parts[2]}" if profile == "ros1-actionlib"
                        else f"{parts[0]}/action/{parts[2]}")
            if spec.get("type") != expected or (profile == "ros1-actionlib" and not parts[2].endswith("Action")):
                parts = None
        if parts is None:
            syntax = ("package/NameAction" if profile == "ros1-actionlib" else "package/action/Name"
                      if profile == "ros2-native" else f"package/{kind}/Name (or ROS 1 package/Name)")
            gate.error("ROS_TYPE", f"{label} needs type '{syntax}'", label)
            continue
        type_text = text
        if "type_ref" in spec:
            type_text = _source_text(ctx, gate, spec["type_ref"], label + ".type_ref", companion_ok)
        if type_text is not None and not _type_shown(parts, type_text):
            gate.error("ROS_TYPE_NOT_UPSTREAM", f"{label}: the cited source does not show type {spec['type']!r}; "
                       "use type_ref for its explicit import/include when it is on another line", label,
                       spec.get("type_ref", spec.get("source_ref")))
        if key == "action":
            if profile == "ros2-native":
                for op, role in (("send_action_goal", "goal"), ("cancel_action_goal", "cancel")):
                    allowed.setdefault((op, endpoint), set()).add(parts)
                    action_roles[(op, endpoint)] = (profile, endpoint, role)
            else:
                # These are actionlib protocol endpoints and generated wrapper
                # types, derived from the cited action rather than invented refs.
                roles = {
                    "goal": (parts[0], "msg", parts[2] + "Goal"),
                    "cancel": ("actionlib_msgs", "msg", "GoalID"),
                    "status": ("actionlib_msgs", "msg", "GoalStatusArray"),
                    "result": (parts[0], "msg", parts[2] + "Result"),
                    "feedback": (parts[0], "msg", parts[2] + "Feedback"),
                }
                for role, wire_type in roles.items():
                    topic = endpoint.rstrip("/") + "/" + role
                    ops = ("advertise", "publish", "unadvertise") if role in ("goal", "cancel") else (
                        "subscribe", "unsubscribe")
                    for op in ops:
                        allowed.setdefault((op, topic), set()).add(wire_type)
                        if op == "publish":
                            action_roles[(op, topic)] = (profile, endpoint, role)
            continue
        operations = ("call_service",) if key == "service" else (
            ("subscribe", "unsubscribe") if group == "reads" or spec.get("operation") == "subscribe"
            or "fresh" in spec else ("advertise", "publish", "unadvertise"))
        for op in operations:
            allowed.setdefault((op, endpoint), set()).add(parts)

    sensed = dict(getattr(ctx.cls, "safety_bindings", {}) or {}).get("sensed_stop")
    if isinstance(sensed, Mapping):
        _check_fill_refs(ctx, gate, sensed)
        _check_history_refs(ctx, gate, sensed)
        _allow_exclusion(ctx, gate, sensed, allowed)

    sent = 0
    for log in ctx.logs:
        goal_ids: dict[str, set[str]] = {}
        for call in log.calls:
            if call.kind != "call" or call.name != "send":
                continue
            sent += 1
            message = call.args[0] if call.args else call.kwargs.get("message")
            if not isinstance(message, Mapping):
                gate.error("ROS_WIRE_FORMAT", "the ROS transport send must contain a JSON object", "send")
                continue
            op = message.get("op")
            key = "action" if op in ("send_action_goal", "cancel_action_goal") else (
                "service" if op == "call_service" else "topic")
            endpoint = message.get(key)
            if not isinstance(op, str) or not isinstance(endpoint, str) or (op, endpoint) not in allowed:
                gate.error("ROS_WIRE_UNDECLARED", f"recorded ROS operation {op!r} at {endpoint!r} has no declared "
                           "binding with this operation and endpoint", "send")
                continue
            type_key = "action_type" if op == "send_action_goal" else "type"
            if op in ("advertise", "subscribe", "send_action_goal") and type_key not in message:
                gate.error("ROS_WIRE_TYPE", f"recorded {op} {endpoint} omits its declared ROS type", "send")
            elif type_key in message:
                kind = "action" if key == "action" else "srv" if key == "service" else "msg"
                parts = _type_parts(message[type_key], kind)
                if parts not in allowed[(op, endpoint)]:
                    gate.error("ROS_WIRE_TYPE", f"recorded type {message[type_key]!r} disagrees with the declaration "
                               f"for {op} {endpoint}", "send")
            action_role = action_roles.get((op, endpoint))
            if action_role is not None:
                profile, action, role = action_role
                if profile == "ros2-native":
                    identifier = message.get("id")
                else:
                    body = message.get("msg")
                    goal = body.get("goal_id") if isinstance(body, Mapping) and role == "goal" else body
                    identifier = goal.get("id") if isinstance(goal, Mapping) else None
                    if role == "cancel" and (not isinstance(goal, Mapping)
                                             or goal.get("stamp") != {"secs": 0, "nsecs": 0}):
                        gate.error("ROS_CANCEL_SCOPE", "actionlib cancellation must carry a zero stamp and an "
                                   "exact goal id; a timestamp may cancel other clients' goals", "send")
                if not isinstance(identifier, str) or not identifier:
                    gate.error("ROS_GOAL_ID", "an action goal/cancel needs a nonempty exact goal id", "send")
                elif role == "goal":
                    goal_ids.setdefault(action, set()).add(identifier)
                elif identifier not in goal_ids.get(action, set()):
                    gate.error("ROS_CANCEL_SCOPE", "action cancellation must match a goal sent on this transport "
                               "to this action", "send")
    if not sent:
        gate.warning("ROS_NO_MESSAGES", "no ROS send was recorded: only cited declarations were checked, not wire "
                     "traffic (G6 must exercise the fake transport)")
