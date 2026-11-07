"""Python-object bridge family (MHS-000 section 9.3).

An adapter declares a target object and a declarative capability map; this
bridge imports the target lazily, applies field/unit/enum/limit/constant
transforms in both directions, maps native exceptions onto stable MHS error
codes, and refuses every call the adapter did not declare.

The default grammar is the canonical MHS-006 §4/§7 binding (the shape of
``mhs/bindings.json`` entries); every ``config["capabilities"]`` value is one
canonical ``binding`` object (``bridge`` defaults to ``"python-object"``)::

    {
      "target": "julabo:JulaboCF",
      "factory": {"kind": "class", "kwargs": {"port": "/dev/ttyUSB0"}},
      "setup": "open",                       # may be ``async``
      "close": "close",                      # may be ``async``
      "capabilities": {
        "cap.measure.temperature.v1": {
          "native": "bath_temperature",      # an ``async def`` is awaited
          "result": {"map": {"temperature": "output.$"}},
          "concurrency": "shared", "timeout_ms": 2000
        },
        "x-cap.julabo.setpoint.v1": {
          "native": "set_point_1", "invoke": "await",
          "args": {"value": {"from": "input.setpoint", "type": "number"}},
          "clamp": {"input.setpoint": {"min": -20, "max": 150}},
          "result": {"map": {"setpoint": "output.$"}},
          "errors": [{"native": "ValueError", "mhs_code": "MHS.CAPABILITY.INPUT_INVALID"}],
          "concurrency": "exclusive", "timeout_ms": 5000
        }
      },
      "reads": {"bath": {"fields": {"temperature": "bath_temperature"}}},
      "writes": {"bath": {"params": {"setpoint": {"native": "set_point_1", "invoke": "await"}}}},
      "safety_bindings": {
        "estop": {"native": "stop", "invoke": "await", "timeout_ms": 1000},
        "safe_state": {"native": "stop", "description": "circulation off"},
        "reset": {"native": "clear"},
        "interlocks": [{"id": "lid", "native": "lid_closed", "invoke": "get"}]
      }
    }

Invocation forms (``invoke``): ``call`` (default; awaitables, futures and
Status-like returns are awaited), ``get``/``set`` (property getter/setter),
``await`` (the native must return an awaitable), ``status`` (the native must
return a Status-like object or an awaitable), ``query``/``write`` (the native
is the target's request method, called with the formatted ``command``
template; ``parse`` turns a text response into a value).

``result.map`` paths are rooted at ``output``; ``output`` and ``output.$``
name the raw native return, so a getter returning ``22.0`` maps with
``{"temperature": "output.$"}``, while ``output.result`` is the native's
``result`` field.  A mapped path that is absent in the native return is
``MHS.CAPABILITY.OUTPUT_INVALID`` unless the capability's ``output_schema``
(``capability_schemas=``) makes the target optional.  With an output schema,
targets it does not define are refused at load (unless it is marked
``x-mhs-open``), and so is a map that leaves a required property unmapped --
except ``sampled_at``, which the bridge stamps with the time the native
returned, and ``revision``, which the server adds.

Every clamp is a rejection (``MHS.SAFETY.ENVELOPE_VIOLATION`` before the
native call), every native call is bounded (``timeout_ms`` and the request
deadline; expiry is an unknown outcome, never a retryable failure), and
``safety_bindings`` connect ``mhs.safety.estop``/``reset``, interlocks and the
safe state to native calls without taking the lock held by a running call.
An exclusive call or write that was waiting for that lock when ``estop()`` ran
is refused with ``MHS.SAFETY.ESTOP_ENGAGED`` and never reaches the native.
Effectful calls remain tracked after the caller times out or cancels, through
synchronous return, Status/future completion, coroutine cancellation cleanup
and native cancellation callbacks. New control/write/restore calls are fenced
while native work remains active or uncertain. Reads, snapshots and interlocks
remain observational. A stop may run immediately but cannot acknowledge safety
while earlier native work can still mutate state. After settlement, a fresh
stop acknowledgment and explicit safety reset are required; no native thread
is killed and cancellation dispatch is never a stop acknowledgment. Closing is
irreversible and defers owned cleanup until retained calls terminate.
An interlock whose value is not recognised -- an error reply under the strict
``bool`` parse, a reply that is not *wholly* the number (or the declared
pattern) under an ``int``/``float``/``regex`` parse (``'ERR 0'`` never reads
0), or a non-boolean where ``closed_when`` is ``true``/``false`` -- reads
``unknown``, so ``reset()`` is refused.

The deprecated in-process SDK shape (``const``, ``enum``, ``scale``, errors as
an object, ``unit: [from, to]``) needs the explicit marker
``"grammar": "legacy"`` and emits a ``DeprecationWarning``; its clamps reject
too.  Bindings documents come from ``bindings=``, ``config["bindings"]`` or
``config["bindings_ref"]`` (a path relative to ``base_dir``) and are loaded by
:func:`mhs.bridge.bindings.load_bindings`.
"""

from __future__ import annotations

import concurrent.futures
import asyncio
import copy
import inspect
import os
import threading
import time
import warnings
from typing import Any, Callable, Mapping, Sequence

from mhs import signals
from mhs.bridge.base import (
    Bridge,
    BridgeContext,
    ErrorMap,
    FieldMapping,
    MappingError,
    UnitError,
    _Rule,
    call_bounded,
    driver_failed,
    format_command,
    is_status_like,
    jsonable,
    load_object,
    make_mhs_error,
    outcome_unknown,
    parse_text,
    resolve_native,
    unsupported,
)
from mhs.bridge.base import main as _bridge_main
from mhs.bridge.bindings import (
    BindingDocument,
    INVOKE_FORMS,
    command_template_errors,
    load_bindings,
    normalize_binding,
    parse_spec_errors,
)
from mhs.errors import MHSError
from mhs.bridge.python_execution import RetainedCall

__all__ = ["PythonObjectBridge", "main"]

CONFIGURE_CAPABILITY = "cap.device.configure.v1"

_ALLOWED_CONFIG = {
    "target",
    "factory",
    "setup",
    "close",
    "capabilities",
    "reads",
    "writes",
    "snapshot",
    "restore",
    "resources",
    "description",
    "metadata",
    "bindings",
    "bindings_ref",
    "safety_bindings",
    "grammar",
    "strict",
}
_GRAMMARS = ("canonical", "legacy")

#: Keys of one deprecated legacy capability entry (``"grammar": "legacy"``).
_LEGACY_KEYS = {
    "resource", "native", "method", "args", "result", "errors", "positional", "description",
    "advertise", "exclusive", "timeout_ms", "invoke", "command", "parse",
}
_HOOK_KEYS = {"native", "args", "timeout_ms", "description"}
_READ_KEYS = {"method", "native", "invoke", "args", "result", "fields", "timeout_ms", "errors", "parse",
              "command", "description"}
_WRITE_KEYS = {"method", "native", "args", "errors", "timeout_ms", "params", "description"}
_PARAM_KEYS = {"native", "invoke", "command", "timeout_ms", "errors", "type", "unit", "units", "clamp",
               "enum_map", "map", "description"}
_SAFETY_KEYS = {"estop", "reset", "safe_state", "interlocks"}
_SAFETY_CALL_KEYS = {"native", "invoke", "args", "command", "timeout_ms", "description", "errors"}
_INTERLOCK_KEYS = {"id", "native", "invoke", "args", "command", "parse", "closed_when", "timeout_ms",
                   "description"}

#: Required output properties the server adds itself (never mapped by a binding).
_SERVER_OUTPUT_FIELDS = frozenset({"revision"})

_DEFAULT_TIMEOUT_MS = {"estop": 1000, "safe_state": 5000, "reset": 5000, "interlock": 500,
                       "read": 5000, "write": 5000, "setup": 30000, "close": 5000}


def _manifest_invalid(message: str, errors: Sequence[str] = (), **details: Any) -> Exception:
    payload: dict[str, Any] = {"errors": list(errors) or [message]}
    payload.update(details)
    return make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", message, {"retryable": False, "details": payload})


def _positive_ms(value: Any, label: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > 86_400_000:
        raise _manifest_invalid(f"{label} must be a positive integer number of milliseconds")
    return int(value)


class _Call:
    """One compiled native invocation (capability, read, write, hook or safety call)."""

    __slots__ = ("native", "invoke", "args", "positional", "command", "parse", "whole_reply", "timeout_ms",
                 "errors", "label", "separators")

    def __init__(self, *, native: str, invoke: str = "call", args: FieldMapping | None = None,
                 positional: Sequence[str] = (), command: str | None = None,
                 parse: Mapping[str, Any] | None = None, timeout_ms: int | None = None,
                 errors: ErrorMap | None = None, label: str = "native call"):
        self.native = native
        self.invoke = invoke
        self.args = args if args is not None else FieldMapping({}, direction="input")
        self.positional = list(positional)
        self.command = command
        self.parse = dict(parse) if parse is not None else None
        # An interlock reading parses the whole reply (``parse_text(whole=True)``).
        self.whole_reply = False
        self.timeout_ms = timeout_ms
        self.errors = errors if errors is not None else ErrorMap()
        self.label = label
        self.separators = ""


class PythonObjectBridge(Bridge):
    """Bridge a Python object behind a declarative capability map."""

    bridge_kind = "python-object"

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        device_id: str | None = None,
        bridge_id: str | None = None,
        load: bool = True,
        bindings: Mapping[str, Any] | None = None,
        strict: bool | None = None,
        capability_schemas: Mapping[str, Mapping[str, Any]] | None = None,
        safe_state_capabilities: Sequence[str] = (),
        base_dir: str | os.PathLike[str] | None = None,
    ):
        super().__init__(device_id=device_id)
        if not isinstance(config, Mapping):
            raise _manifest_invalid("bridge config must be an object")
        unknown = set(config) - _ALLOWED_CONFIG
        if unknown:
            raise _manifest_invalid(
                f"unknown bridge config keys: {sorted(unknown)}", allowed=sorted(_ALLOWED_CONFIG)
            )
        self.config = copy.deepcopy(dict(config))
        self.bridge_id = bridge_id or f"mhs.bridge.python-object:{self.config.get('target', '?')}"
        self._target_spec: str = str(self.config.get("target", ""))
        if ":" not in self._target_spec:
            raise _manifest_invalid("python-object bridge requires a 'module:attr' target")
        self.strict = bool(self.config.get("strict", False)) if strict is None else bool(strict)
        self.grammar = str(self.config.get("grammar", "canonical"))
        if self.grammar not in _GRAMMARS:
            raise _manifest_invalid(f"grammar must be one of {list(_GRAMMARS)}, got {self.grammar!r}")
        if self.grammar == "legacy":
            warnings.warn(
                "the legacy in-process capability grammar is deprecated; use canonical "
                "MHS-006 binding objects (they are the default)",
                DeprecationWarning,
                stacklevel=2,
            )
        self._schemas = {str(key): copy.deepcopy(dict(value)) for key, value in dict(capability_schemas or {}).items()}
        self._base_dir = os.fspath(base_dir) if base_dir is not None else os.getcwd()
        self._factory = dict(self.config.get("factory") or {})
        self.bindings_document: BindingDocument | None = self._load_document(bindings)
        self._caps = self._compile_capabilities()
        # Only the resolved Driver model grants this role. Config/BridgeContext
        # metadata never authorizes a caller to bypass the ordinary actuation fence.
        if (isinstance(safe_state_capabilities, (str, bytes))
                or not isinstance(safe_state_capabilities, (list, tuple, frozenset, set))
                or any(not isinstance(item, str) for item in safe_state_capabilities)):
            raise _manifest_invalid("safe_state_capabilities must be an explicit collection of capability ids")
        self._safe_caps = frozenset(safe_state_capabilities)
        for capability in self._safe_caps:
            binding = self._caps.get(capability)
            if binding is None:
                raise _manifest_invalid("safe-state role names an unbound capability")
            native_call = binding["call"]
            if native_call.args or native_call.positional or native_call.invoke not in ("call", "await", "status"):
                raise _manifest_invalid("safe-state actions require an argument-free native call/await/status")
        self._reads = self._compile_reads(self.config.get("reads"))
        self._writes = self._compile_writes(self.config.get("writes"))
        self._setup = self._compile_hook("setup", self.config.get("setup"))
        self._close_hook = self._compile_hook("close", self.config.get("close"))
        self._safety = self._compile_safety(self.config.get("safety_bindings"))
        self._safe_state_achieved = False
        self._safe_state_at: str | None = None
        self._target: Any = None
        self._loaded = False
        self._load_lock = threading.Lock()
        self._activity = threading.Condition(threading.RLock())
        self._executions: dict[RetainedCall, str] = {}
        self._uncertain = False
        self._activity_version = 0
        self._safe_version: tuple[int, int] | None = None
        self._closing = False
        self._cleanup_started = False
        self._cleanup_done = threading.Event()
        self._cleanup_error: str | None = None
        if load:
            self._ensure_loaded()

    # -- compilation -------------------------------------------------------
    def _load_document(self, bindings: Any) -> BindingDocument | None:
        sources = [
            name for name, present in (
                ("bindings=", bindings is not None),
                ("config.bindings", self.config.get("bindings") is not None),
                ("config.bindings_ref", self.config.get("bindings_ref") is not None),
            ) if present
        ]
        if len(sources) > 1:
            raise _manifest_invalid(f"declare the bindings document once (got {', '.join(sources)})")
        raw: Any = bindings if bindings is not None else self.config.get("bindings")
        ref = self.config.get("bindings_ref")
        if ref is not None:
            if not isinstance(ref, str) or not ref.strip():
                raise _manifest_invalid("bindings_ref must be a path to a bindings.json document")
            raw = ref if os.path.isabs(ref) else os.path.join(self._base_dir, ref)
        if raw is None:
            return None
        return load_bindings(raw, strict=self.strict)

    def _compile_capabilities(self) -> dict[str, dict[str, Any]]:
        raw = self.config.get("capabilities") or {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("capabilities must be an object keyed by capability id")
        entries: dict[str, tuple[str, Mapping[str, Any]]] = {}
        if self.bindings_document is not None:
            for entry in self.bindings_document.bindings:
                capability_id = str(entry.get("capability_id"))
                if capability_id in entries:
                    raise _manifest_invalid(f"duplicate capability binding {capability_id!r}")
                entries[capability_id] = ("normalized", entry)
        for capability_id, binding in raw.items():
            if capability_id in entries:
                raise _manifest_invalid(
                    f"capability {capability_id!r} is declared by both the bindings document "
                    "and the in-process capabilities map"
                )
            if not isinstance(binding, Mapping):
                raise _manifest_invalid(f"binding for {capability_id!r} must be an object")
            entries[str(capability_id)] = (self.grammar, binding)
        compiled: dict[str, dict[str, Any]] = {}
        for capability_id, (shape, binding) in entries.items():
            if shape == "normalized":
                item = self._compile_normalized(capability_id, binding)
            elif shape == "canonical":
                try:
                    normalized = normalize_binding(self._canonical_entry(capability_id, binding),
                                                   strict=self.strict)
                except MHSError as exc:
                    data = dict(exc.data)
                    details = dict(data.get("details") or {})
                    details.setdefault("hint", "capabilities entries use the canonical MHS-006 binding "
                                       "grammar; set config 'grammar': 'legacy' for the deprecated "
                                       "in-process shape")
                    data["details"] = details
                    raise make_mhs_error(exc.code, f"{capability_id}: {exc.message}", data) from exc
                item = self._compile_normalized(capability_id, normalized)
            else:
                item = self._compile_legacy(capability_id, binding)
            compiled[capability_id] = item
        return compiled

    def _canonical_entry(self, capability_id: str, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        """Wrap an in-process canonical ``binding`` object in a document entry."""

        device_id = self.device_id or "mhs://localhost/python-object"
        if isinstance(binding.get("binding"), Mapping):
            entry = copy.deepcopy(dict(binding))
            entry.setdefault("capability_id", capability_id)
            if entry.get("capability_id") != capability_id:
                raise _manifest_invalid(
                    f"binding entry capability_id {entry.get('capability_id')!r} does not "
                    f"match its config key {capability_id!r}"
                )
            entry.setdefault("device_id", device_id)
            entry.setdefault("resource", "default")
            entry["binding"].setdefault("bridge", "python-object")
            return entry
        inner = copy.deepcopy(dict(binding))
        resource = inner.pop("resource", None)
        inner.setdefault("bridge", "python-object")
        return {
            "device_id": device_id,
            "capability_id": capability_id,
            "resource": str(resource or "default"),
            "binding": inner,
        }

    def _output_contract(self, capability_id: str) -> tuple[Mapping[str, Any] | None, set[str] | None, set[str]]:
        """(output schema, allowed targets or None, required properties) from ``capability_schemas``.

        Whenever the output schema declares ``properties``, a result target it
        does not define is refused -- unless the schema is explicitly open
        (``x-mhs-open: true``); a missing ``additionalProperties: false`` is not
        an opt-out (FIT-ROS-08).
        """

        schema = (self._schemas.get(capability_id) or {}).get("output_schema")
        if not isinstance(schema, Mapping):
            return None, None, set()
        properties = schema.get("properties")
        required = {str(name) for name in (schema.get("required") or [])}
        if not isinstance(properties, Mapping) or schema.get("x-mhs-open") is True:
            return schema, None, required
        return schema, {str(name) for name in properties}, required

    def _compile_normalized(self, capability_id: str, binding: Mapping[str, Any]) -> dict[str, Any]:
        if binding.get("kind") == "shim":
            raise make_mhs_error(
                "MHS.CAPABILITY.NOT_BOUND",
                f"binding for {capability_id!r} is a shim; PythonObjectBridge only runs "
                "declarative bindings (use the shim runner)",
                {"retryable": False},
            )
        family = binding.get("bridge") or "python-object"
        if family != "python-object":
            raise _manifest_invalid(
                f"binding for {capability_id!r} targets the {family!r} bridge family, not python-object"
            )
        item = dict(binding)
        item.setdefault("resource", "default")
        native = item.get("native")
        if not isinstance(native, str) or not native:
            raise _manifest_invalid(f"binding for {capability_id!r} needs a precise 'native' symbol")
        timeout = item.get("timeout_ms")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0 or timeout > 86_400_000:
            raise _manifest_invalid(
                f"binding for {capability_id!r} requires a positive integer timeout_ms (ADPT-025) "
                "within the 24 h sanity bound",
                timeout_ms=timeout,
            )
        concurrency = str(item.get("concurrency") or "exclusive")
        if concurrency not in ("exclusive", "shared", "serialized"):
            raise _manifest_invalid(f"binding for {capability_id!r} has invalid concurrency {concurrency!r}")
        invoke = str(item.get("invoke") or "call")
        if invoke not in INVOKE_FORMS:
            raise _manifest_invalid(f"binding for {capability_id!r} has invalid invoke {invoke!r}")
        schema, allowed, required = self._output_contract(capability_id)
        result_spec = item.get("result")
        result_targets = list(result_spec) if isinstance(result_spec, Mapping) else []
        if allowed is not None:
            stray = sorted(set(result_targets) - allowed)
            if stray:
                raise _manifest_invalid(
                    f"result.map of {capability_id!r} maps targets the capability output_schema "
                    f"does not define: {stray}",
                    targets=stray, allowed=sorted(allowed),
                )
        stamp_sampled_at = False
        if schema is not None and result_targets:
            unmapped = required - set(result_targets) - _SERVER_OUTPUT_FIELDS
            if "sampled_at" in unmapped and _is_timestamp_property(schema, "sampled_at"):
                # The bridge knows when it sampled: it stamps the time the native returned.
                unmapped.discard("sampled_at")
                stamp_sampled_at = True
            if unmapped:
                raise _manifest_invalid(
                    f"result.map of {capability_id!r} leaves required output properties unmapped: "
                    f"{sorted(unmapped)}",
                    unmapped=sorted(unmapped), required=sorted(required),
                )
        optional = [target for target in result_targets if schema is not None and target not in required]
        try:
            args = FieldMapping(item.get("args"), direction="input")
            result = FieldMapping(result_spec, direction="output", required_by_default=True, optional=optional)
            errors = ErrorMap(item.get("errors"), strict=self.strict)
        except (MappingError, UnitError) as exc:
            raise _manifest_invalid(f"binding for {capability_id!r} is invalid: {exc}") from exc
        positional = self._positional(capability_id, item)
        call = _Call(native=native, invoke=invoke, args=args, positional=positional,
                     command=item.get("command"), parse=item.get("parse"), timeout_ms=timeout,
                     errors=errors, label=capability_id)
        return {
            "capability_id": capability_id,
            "resource": str(item.get("resource") or "default"),
            "native": native,
            "invoke": invoke,
            "description": item.get("description", ""),
            "concurrency": concurrency,
            "timeout_ms": timeout,
            "kind": str(item.get("kind", "declarative")),
            "call": call,
            "result": result,
            "grammar": "canonical",
            "stamp_sampled_at": stamp_sampled_at,
        }

    def _compile_legacy(self, capability_id: str, binding: Mapping[str, Any]) -> dict[str, Any]:
        # Deprecated in-process SDK shape, reachable only with "grammar": "legacy"
        # in config["capabilities"].  Its clamps reject like canonical ones
        # (ADPT-024); every external document goes through load_bindings().
        unknown = set(binding) - _LEGACY_KEYS
        if unknown:
            raise _manifest_invalid(f"unknown legacy binding keys for {capability_id!r}: {sorted(unknown)}")
        native = binding.get("native") or binding.get("method")
        if not isinstance(native, str) or not native:
            raise _manifest_invalid(f"binding for {capability_id!r} needs a 'native' method path")
        invoke = str(binding.get("invoke") or "call")
        if invoke not in INVOKE_FORMS:
            raise _manifest_invalid(f"binding for {capability_id!r} has invalid invoke {invoke!r}")
        timeout = binding.get("timeout_ms")
        if timeout is not None:
            timeout = _positive_ms(timeout, f"timeout_ms of {capability_id!r}", 0)
        try:
            args = FieldMapping(binding.get("args"), direction="input")
            result = FieldMapping(_legacy_result_spec(binding.get("result")), direction="output")
            errors = ErrorMap(binding.get("errors"), strict=self.strict)
        except (MappingError, UnitError) as exc:
            raise _manifest_invalid(f"binding for {capability_id!r} is invalid: {exc}") from exc
        call = _Call(native=native, invoke=invoke, args=args, positional=self._positional(capability_id, binding),
                     command=binding.get("command"), parse=binding.get("parse"), timeout_ms=timeout,
                     errors=errors, label=capability_id)
        item = {
            "capability_id": capability_id,
            "resource": str(binding.get("resource") or "default"),
            "native": native,
            "invoke": invoke,
            "description": binding.get("description", ""),
            "concurrency": "exclusive",
            "timeout_ms": timeout,
            "kind": "declarative",
            "call": call,
            "result": result,
            "grammar": "legacy",
        }
        if "exclusive" in binding:
            item["exclusive"] = bool(binding["exclusive"])
        if isinstance(binding.get("advertise"), Mapping):
            item["advertise"] = copy.deepcopy(dict(binding["advertise"]))
        return item

    @staticmethod
    def _positional(capability_id: str, item: Mapping[str, Any]) -> list[str]:
        positional = item.get("positional") or []
        if not isinstance(positional, (list, tuple)) or not all(
            isinstance(name, str) for name in positional
        ):
            raise _manifest_invalid(
                f"binding for {capability_id!r}: 'positional' must be a list of argument names"
            )
        return list(positional)

    def _call_spec(self, spec: Mapping[str, Any], *, label: str, keys: set[str], default_invoke: str,
                   default_timeout: int, require_args_constant: bool = False) -> _Call:
        unknown = set(spec) - keys
        if unknown:
            raise _manifest_invalid(f"unknown keys in {label}: {sorted(unknown)}")
        native = spec.get("native") or spec.get("method")
        if not isinstance(native, str) or not native.strip():
            raise _manifest_invalid(f"{label} needs a 'native' symbol")
        invoke = str(spec.get("invoke") or default_invoke)
        if invoke not in INVOKE_FORMS:
            raise _manifest_invalid(f"{label}: invoke {invoke!r} must be one of {list(INVOKE_FORMS)}")
        args_spec = spec.get("args")
        try:
            args = FieldMapping(args_spec, direction="input")
            errors = ErrorMap(spec.get("errors"), strict=self.strict)
        except (MappingError, UnitError) as exc:
            raise _manifest_invalid(f"{label} is invalid: {exc}") from exc
        if require_args_constant:
            for rule in args.rules:
                if rule.source is not None:
                    raise _manifest_invalid(f"{label}: arguments of a safety call must be constants ('value')")
        command = spec.get("command")
        if invoke in ("query", "write"):
            problems = command_template_errors(command, [rule.target for rule in args.rules], f"{label}.command")
            if problems:
                raise _manifest_invalid(f"{label} has an invalid command", problems)
        elif command is not None:
            raise _manifest_invalid(f"{label}: 'command' needs invoke 'query' or 'write'")
        if invoke == "get" and args.rules:
            raise _manifest_invalid(f"{label}: invoke 'get' takes no arguments")
        if "parse" in spec:
            problems = parse_spec_errors(spec.get("parse"), f"{label}.parse")
            if problems:
                raise _manifest_invalid(f"{label} has an invalid parse spec", problems)
        timeout = _positive_ms(spec.get("timeout_ms"), f"{label}.timeout_ms", default_timeout)
        return _Call(native=str(native), invoke=invoke, args=args, command=command, parse=spec.get("parse"),
                     timeout_ms=timeout, errors=errors, label=label)

    def _compile_hook(self, name: str, spec: Any) -> _Call | None:
        if spec is None:
            return None
        if isinstance(spec, str):
            spec = {"native": spec}
        if not isinstance(spec, Mapping):
            raise _manifest_invalid(f"{name} must be a native method name or an object")
        return self._call_spec(spec, label=name, keys=_HOOK_KEYS, default_invoke="call",
                               default_timeout=_DEFAULT_TIMEOUT_MS[name], require_args_constant=True)

    def _compile_reads(self, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("reads must be an object keyed by resource id")
        compiled: dict[str, dict[str, Any]] = {}
        for resource_id, spec in raw.items():
            label = f"reads[{resource_id!r}]"
            if isinstance(spec, str):
                spec = {"method": spec}
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"{label} must be an object")
            unknown = set(spec) - _READ_KEYS
            if unknown:
                raise _manifest_invalid(f"unknown keys in {label}: {sorted(unknown)}")
            entry: dict[str, Any] = {"raw": dict(spec)}
            try:
                entry["result"] = FieldMapping(spec.get("result"), direction="output") if spec.get("result") else None
            except (MappingError, UnitError) as exc:
                raise _manifest_invalid(f"{label}.result is invalid: {exc}") from exc
            if spec.get("fields"):
                fields = spec["fields"]
                if not isinstance(fields, Mapping):
                    raise _manifest_invalid(f"{label}.fields must be an object")
                compiled_fields: dict[str, Any] = {}
                for name, path in fields.items():
                    if isinstance(path, str):
                        compiled_fields[str(name)] = path
                    elif isinstance(path, Mapping):
                        compiled_fields[str(name)] = self._call_spec(
                            path, label=f"{label}.fields[{name!r}]",
                            keys={"native", "invoke", "args", "command", "parse", "timeout_ms", "errors"},
                            default_invoke="call", default_timeout=_DEFAULT_TIMEOUT_MS["read"])
                    else:
                        raise _manifest_invalid(f"{label}.fields[{name!r}] must be a path or a native call")
                entry["fields"] = compiled_fields
                entry["timeout_ms"] = _positive_ms(spec.get("timeout_ms"), f"{label}.timeout_ms",
                                                   _DEFAULT_TIMEOUT_MS["read"])
            elif spec.get("method") or spec.get("native"):
                call_keys = {"method", "native", "invoke", "args", "command", "parse", "timeout_ms", "errors"}
                entry["call"] = self._call_spec(
                    {key: value for key, value in spec.items() if key in call_keys},
                    label=label, keys=call_keys, default_invoke="call",
                    default_timeout=_DEFAULT_TIMEOUT_MS["read"])
            else:
                raise _manifest_invalid(f"{label} needs 'method'/'native' or 'fields'")
            compiled[str(resource_id)] = entry
        return compiled

    def _compile_writes(self, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("writes must be an object keyed by resource id")
        compiled: dict[str, dict[str, Any]] = {}
        for resource_id, spec in raw.items():
            label = f"writes[{resource_id!r}]"
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"{label} must be an object")
            unknown = set(spec) - _WRITE_KEYS
            if unknown:
                raise _manifest_invalid(f"unknown keys in {label}: {sorted(unknown)}")
            if spec.get("params") is not None:
                params = spec["params"]
                if not isinstance(params, Mapping) or not params:
                    raise _manifest_invalid(f"{label}.params must be a non-empty object")
                compiled_params: dict[str, dict[str, Any]] = {}
                for name, param in params.items():
                    plabel = f"{label}.params[{name!r}]"
                    if not isinstance(param, Mapping):
                        raise _manifest_invalid(f"{plabel} must be an object")
                    unknown = set(param) - _PARAM_KEYS
                    if unknown:
                        raise _manifest_invalid(f"unknown keys in {plabel}: {sorted(unknown)}")
                    invoke = str(param.get("invoke") or "set")
                    call_spec = {key: param[key] for key in ("native", "invoke", "command", "timeout_ms", "errors")
                                 if key in param}
                    call_spec["invoke"] = invoke
                    if invoke in ("query", "write"):
                        call_spec["args"] = {"value": {"from": "input.value"}}
                    call = self._call_spec(call_spec, label=plabel,
                                           keys={"native", "invoke", "command", "timeout_ms", "errors", "args"},
                                           default_invoke="set", default_timeout=_DEFAULT_TIMEOUT_MS["write"])
                    if invoke in ("call", "await", "status"):
                        call.positional = ["value"]   # the value is the native's single argument
                    rule_spec: dict[str, Any] = {"from": "$"}
                    rule_spec.update({key: param[key] for key in ("type", "unit", "units", "clamp", "enum_map", "map")
                                      if key in param})
                    try:
                        value_rule = _Rule("value", rule_spec, direction="input")
                    except (MappingError, UnitError) as exc:
                        raise _manifest_invalid(f"{plabel} is invalid: {exc}") from exc
                    compiled_params[str(name)] = {"call": call, "rule": value_rule}
                compiled[str(resource_id)] = {"params": compiled_params}
            elif spec.get("method") or spec.get("native"):
                call = self._call_spec({key: spec[key] for key in ("method", "native", "args", "errors", "timeout_ms")
                                        if key in spec},
                                       label=label, keys={"method", "native", "args", "errors", "timeout_ms"},
                                       default_invoke="call", default_timeout=_DEFAULT_TIMEOUT_MS["write"])
                compiled[str(resource_id)] = {"call": call}
            else:
                raise _manifest_invalid(f"{label} needs 'params' or a 'method'")
        return compiled

    def _compile_safety(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("safety_bindings must be an object")
        unknown = set(raw) - _SAFETY_KEYS
        if unknown:
            raise _manifest_invalid(f"unknown safety_bindings keys: {sorted(unknown)}", allowed=sorted(_SAFETY_KEYS))
        compiled: dict[str, Any] = {}
        for name in ("estop", "safe_state", "reset"):
            spec = raw.get(name)
            if spec is None:
                continue
            if isinstance(spec, str):
                spec = {"native": spec}
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"safety_bindings.{name} must be an object")
            call = self._call_spec(spec, label=f"safety_bindings.{name}", keys=_SAFETY_CALL_KEYS,
                                   default_invoke="call", default_timeout=_DEFAULT_TIMEOUT_MS[name],
                                   require_args_constant=True)
            compiled[name] = {"call": call, "description": spec.get("description")}
        interlocks = raw.get("interlocks")
        if interlocks is not None:
            if not isinstance(interlocks, (list, tuple)):
                raise _manifest_invalid("safety_bindings.interlocks must be an array")
            seen: set[str] = set()
            compiled_interlocks = []
            for index, spec in enumerate(interlocks):
                label = f"safety_bindings.interlocks[{index}]"
                if not isinstance(spec, Mapping):
                    raise _manifest_invalid(f"{label} must be an object")
                unknown = set(spec) - _INTERLOCK_KEYS
                if unknown:
                    raise _manifest_invalid(f"unknown keys in {label}: {sorted(unknown)}")
                interlock_id = spec.get("id")
                if not isinstance(interlock_id, str) or not interlock_id.strip():
                    raise _manifest_invalid(f"{label} needs an 'id'")
                if interlock_id in seen:
                    raise _manifest_invalid(f"{label} repeats interlock id {interlock_id!r}")
                seen.add(interlock_id)
                closed_when = spec.get("closed_when", True)
                parse = spec.get("parse")
                text_valued = parse is not None or str(spec.get("invoke") or "get") in ("query", "write")
                bool_parse = isinstance(parse, Mapping) and parse.get("kind") == "bool"
                if isinstance(closed_when, bool) and text_valued and not bool_parse:
                    raise _manifest_invalid(
                        f"{label}: closed_when {str(closed_when).lower()} only matches a boolean, so this "
                        "interlock could never read closed; use parse kind 'bool' or declare "
                        "closed_when for the parsed value"
                    )
                if bool_parse and not isinstance(closed_when, bool):
                    raise _manifest_invalid(
                        f"{label}: a 'bool' parse reads true or false, so closed_when must be true or "
                        f"false (not {closed_when!r})"
                    )
                call = self._call_spec(
                    {key: spec[key] for key in ("native", "invoke", "args", "command", "parse", "timeout_ms")
                     if key in spec},
                    label=label, keys={"native", "invoke", "args", "command", "parse", "timeout_ms"},
                    default_invoke="get", default_timeout=_DEFAULT_TIMEOUT_MS["interlock"],
                    require_args_constant=True)
                # An error reply must never read as the closed value: the
                # parse has to match the whole reply (no first-number search).
                call.whole_reply = True
                compiled_interlocks.append({
                    "id": interlock_id,
                    "call": call,
                    "closed_when": closed_when,
                    "description": str(spec.get("description") or interlock_id),
                })
            compiled["interlocks"] = compiled_interlocks
        return compiled

    def _ensure_loaded(self) -> Any:
        self.ensure_open()
        if self._loaded:
            return self._target
        with self._load_lock:
            if self._loaded:
                return self._target
            target = load_object(self._target_spec, self._factory)
            if inspect.isawaitable(target):
                target = self.async_runner.run(target, timeout_ms=_DEFAULT_TIMEOUT_MS["setup"],
                                               label=f"{self._target_spec} factory")
            self._target = target
            if self._setup is not None:
                try:
                    self._perform(self._setup, {}, None, effect="setup")
                except Exception as exc:
                    self.close()
                    raise make_mhs_error(
                        "MHS.DEVICE.NOT_READY",
                        f"setup hook {self._setup.native!r} failed ({type(exc).__name__})",
                        {"retryable": False},
                    ) from exc
            self._loaded = True
        return self._target

    # -- adapter surface ---------------------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        entries = []
        for capability_id, binding in self._caps.items():
            entry = {
                "capability_id": capability_id,
                "resource": binding["resource"],
                "native": binding["native"],
                "invoke": binding["invoke"],
                "description": binding.get("description", ""),
                "exclusive": bool(binding.get("exclusive", binding.get("concurrency", "exclusive") != "shared")),
                "concurrency": binding.get("concurrency", "exclusive"),
            }
            if binding.get("timeout_ms"):
                entry["timeout_ms"] = int(binding["timeout_ms"])
            if isinstance(binding.get("advertise"), Mapping):
                entry.update(copy.deepcopy(dict(binding["advertise"])))
            entries.append(entry)
        if CONFIGURE_CAPABILITY not in self._caps:
            for resource_id, spec in self._writes.items():
                entries.append({
                    "capability_id": CONFIGURE_CAPABILITY,
                    "resource": resource_id,
                    "native": ",".join(sorted(spec["params"])) if "params" in spec else spec["call"].native,
                    "invoke": "set" if "params" in spec else "call",
                    "description": "Write the resource's writable parameters.",
                    "exclusive": True,
                    "concurrency": "exclusive",
                })
        return entries

    def resources(self) -> list[dict[str, Any]]:
        declared = self.config.get("resources")
        if isinstance(declared, list):
            return copy.deepcopy(declared)
        resource_ids = {binding["resource"] for binding in self._caps.values()}
        resource_ids.update(str(rid) for rid in self._reads)
        resource_ids.update(str(rid) for rid in self._writes)
        return [{"resource_id": rid} for rid in sorted(resource_ids)]

    # -- contract-plane operations -----------------------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self._ensure_loaded()
        binding = self._caps.get(str(capability_id))
        context = BridgeContext.coerce(ctx)
        if binding is None:
            if str(capability_id) == CONFIGURE_CAPABILITY and self._writes:
                return self._configure(dict(args or {}), context)
            raise unsupported(capability_id)
        if context.cancelled():
            raise signals.Cancelled("operation cancelled before the native call")
        call: _Call = binding["call"]
        try:
            mapped = call.args.map(dict(args or {}))
        except (MappingError, UnitError, TypeError, ValueError) as exc:
            raise make_mhs_error(
                "MHS.CAPABILITY.INPUT_INVALID",
                f"cannot map input for {capability_id!r}: {exc}",
                {"retryable": False, "details": {"capability_id": capability_id}},
            ) from exc
        if str(capability_id) in self._safe_caps:
            if args:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "safe-state actions accept no caller input",
                                     {"retryable": False})
            return self._safe_action(binding, context)
        epoch = self.estop_epoch
        if binding.get("concurrency") == "shared":
            raw = self._perform(call, mapped, context, epoch=epoch)
        else:
            epoch = self.estop_epoch   # taken before waiting for the lock
            with self._lock:
                self._refuse_if_estopped(epoch, f"call {capability_id!r}")
                if context.cancelled():
                    raise signals.Cancelled("operation cancelled while it waited for the device")
                raw = self._perform(call, mapped, context, epoch=epoch)
        return self._map_result(binding, raw)

    def _safe_action(self, binding: Mapping[str, Any], context: BridgeContext) -> Any:
        """Independently execute the declared no-input stop, then revalidate safety.

        A completed stop cannot confirm a safe state while an earlier setter or
        cancellation continuation can still mutate the device. Unknown outcomes
        retain their native worker exactly as safety_bindings do.
        """
        with self._activity:
            stamp = (self._activity_version, self.estop_epoch)
        try:
            raw = self._perform(binding["call"], {}, context, effect="safety")
            result = self._map_result(binding, raw)
            # achieved_by calls bypass the server's ordinary output validator.
            # Validate the complete resolved contract here before publishing a
            # safety stamp, including nested types and required properties.
            from mhs.schema import validate
            schema = (self._schemas.get(binding["capability_id"]) or {}).get("output_schema")
            try:
                errors = validate(result, schema) if isinstance(schema, Mapping) and schema else ["missing output contract"]
            except Exception:
                errors = ["output contract could not be evaluated"]
            if errors:
                raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", "safe-state action output violates its contract",
                                    details={"errors": errors[:8]})
            with self._activity:
                if self._executions or self._closing or stamp != (self._activity_version, self.estop_epoch):
                    raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "native work remains unsettled")
                self._safe_state_achieved = True
                self._safe_state_at = _now()
                self._safe_version = stamp
            return result
        except BaseException:
            with self._activity:
                self._safe_state_achieved = False
                self._safe_state_at = None
                self._safe_version = None
            raise

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> Any:
        self._ensure_loaded()
        spec = self._reads.get(str(resource_id))
        if spec is None:
            raise unsupported(resource_id, kind="resource")
        context = BridgeContext.coerce(ctx) if ctx is not None else None
        with self._lock:
            if "call" in spec:
                raw = self._perform(spec["call"], spec["call"].args.map({}), context, effect="read")
            else:
                raw = {}
                deadline = time.monotonic() + spec["timeout_ms"] / 1000.0
                for external, path in spec["fields"].items():
                    try:
                        if isinstance(path, _Call):
                            raw[external] = self._perform(path, path.args.map({}), context, effect="read")
                        else:
                            remaining = max(1, int((deadline - time.monotonic()) * 1000))
                            raw[external] = self._get(path, timeout_ms=remaining)
                    except signals.Cancelled:
                        raise
                    except Exception:  # noqa: BLE001 - an unreadable field is left out
                        continue
        mapping = spec.get("result")
        try:
            if mapping is not None and mapping:
                state = mapping.map(raw)
            elif isinstance(raw, Mapping):
                state = dict(raw)
            else:
                state = {"value": raw}
            state = jsonable(state)
        except MappingError as exc:
            raise make_mhs_error(
                "MHS.RESOURCE.STATE_INVALID",
                f"cannot map the native state of {resource_id!r}: {exc}",
                {"retryable": False},
            ) from exc
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        self._ensure_loaded()
        spec = self._writes.get(str(resource_id))
        if spec is None:
            raise unsupported(resource_id, kind="resource")
        if not isinstance(patch, Mapping) or not patch:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "a write needs a non-empty parameter patch",
                                 {"retryable": False})
        context = BridgeContext.coerce(ctx)
        if context.cancelled():
            raise signals.Cancelled("write cancelled before the native call")
        epoch = self.estop_epoch   # taken before waiting for the lock
        if "params" in spec:
            params = spec["params"]
            stray = sorted(str(key) for key in patch if key not in params)
            if stray:
                raise make_mhs_error(
                    "MHS.RESOURCE.NOT_WRITABLE",
                    f"parameters {stray} of {resource_id!r} are not writable",
                    {"retryable": False, "details": {"parameters": stray, "writable": sorted(params)}},
                )
            # map and check every value before the first native call
            prepared = []
            for name, value in patch.items():
                rule: _Rule = params[name]["rule"]
                try:
                    native_value = rule.apply(value)
                except (MappingError, UnitError, TypeError, ValueError) as exc:
                    raise make_mhs_error(
                        "MHS.CAPABILITY.INPUT_INVALID", f"cannot map parameter {name!r}: {exc}",
                        {"retryable": False, "details": {"parameter": name}},
                    ) from exc
                prepared.append((name, value, native_value))
            applied: dict[str, Any] = {}
            with self._lock:
                for name, value, native_value in prepared:
                    call: _Call = params[name]["call"]
                    try:
                        self._refuse_if_estopped(epoch, f"write of {name!r}")
                    except MHSError as exc:
                        if applied:
                            exc.data.setdefault("details", {})["applied"] = dict(applied)
                        raise
                    try:
                        self._perform(call, {"value": native_value}, context, epoch=epoch)
                    except signals.DriverSignal as exc:
                        if applied:
                            if isinstance(exc, signals.OutcomeUnknown):
                                raise outcome_unknown(
                                    f"writing {name!r} is unknown after {sorted(applied)} were applied",
                                    details={"applied": dict(applied), "uncertain": name},
                                ) from exc
                            raise driver_failed(
                                exc.code or "MHS.DEVICE.FAULTED",
                                f"writing {name!r} failed after {sorted(applied)} were applied",
                                details={"applied": dict(applied), "failed": name},
                            ) from exc
                        raise
                    applied[name] = jsonable(value)
            return {"applied": applied}
        call = spec["call"]
        try:
            mapped = call.args.map({"patch": dict(patch), "$": dict(patch), **dict(patch)})
        except (MappingError, UnitError, TypeError, ValueError) as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"cannot map the write: {exc}",
                                 {"retryable": False}) from exc
        with self._lock:
            self._refuse_if_estopped(epoch, f"write of {resource_id!r}")
            self._perform(call, mapped, context, epoch=epoch)
        return {"applied": jsonable(dict(patch))}

    def _configure(self, patch: dict[str, Any], context: BridgeContext) -> dict[str, Any]:
        resource = context.resource
        if resource is None or resource not in self._writes:
            if len(self._writes) != 1:
                raise make_mhs_error(
                    "MHS.CAPABILITY.NOT_BOUND",
                    f"{CONFIGURE_CAPABILITY} needs the target resource (writable: {sorted(self._writes)})",
                    {"retryable": False},
                )
            resource = next(iter(self._writes))
        return self.write(resource, patch, context)

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        self._ensure_loaded()
        spec = self.config.get("snapshot")
        if isinstance(spec, str):
            spec = {"method": spec}
        if isinstance(spec, Mapping):
            if spec.get("method"):
                raw = self.resolve_native(
                    self._resolve(str(spec["method"]))(**self._map_args(spec.get("args"), {})),
                    timeout_ms=_DEFAULT_TIMEOUT_MS["read"], label="snapshot")
            elif spec.get("fields"):
                raw = {
                    str(external): self._get(str(path))
                    for external, path in dict(spec["fields"]).items()
                }
            else:
                raise _manifest_invalid("snapshot spec needs 'method' or 'fields'")
            mapping = FieldMapping(spec.get("result"), direction="output") if spec.get("result") else None
            if mapping is not None and mapping:
                return jsonable(mapping.map(raw))
            if isinstance(raw, Mapping):
                return jsonable(dict(raw))
            return {"value": jsonable(raw)}
        # Default: gather every declared readable resource.
        snapshot: dict[str, Any] = {}
        for resource_id in self._reads:
            try:
                snapshot[resource_id] = self.read(resource_id)
            except Exception:  # noqa: BLE001 - resources without a read spec are not in the snapshot
                continue
        if not snapshot:
            raise unsupported("snapshot", kind="snapshot")
        return snapshot

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self._ensure_loaded()
        spec = self.config.get("restore")
        if isinstance(spec, str):
            spec = {"method": spec}
        if not isinstance(spec, Mapping) or not spec.get("method"):
            raise unsupported("restore", kind="restore")
        args = self._map_args(spec.get("args"), {"$": snapshot, "snapshot": snapshot})
        if not args:
            args = {"snapshot": snapshot}
        epoch = self.estop_epoch
        call = _Call(native=str(spec["method"]), timeout_ms=_DEFAULT_TIMEOUT_MS["write"],
                     errors=ErrorMap(spec.get("errors")), label="restore")
        try:
            with self._lock:
                raw = self._perform(call, args, None, epoch=epoch)
        except (signals.DriverSignal, MHSError):
            raise
        except Exception as exc:  # noqa: BLE001
            code, message = ErrorMap(spec.get("errors")).translate(exc)
            if code == "MHS.ADAPTER.SHIM_FAILED":
                message = f"native {type(exc).__name__} raised an unmapped error"
            raise driver_failed(code, message) from exc
        if isinstance(raw, Mapping):
            return jsonable(dict(raw))
        return {}

    def close(self) -> None:
        with self._activity:
            self._closing = self._closed = True
            cleanup = self._claim_cleanup()
        if cleanup:
            threading.Thread(target=self._cleanup, name="mhs-python-close", daemon=True).start()
            budget = self._close_hook.timeout_ms if self._close_hook else 1000
            self._cleanup_done.wait(float(budget or 1000) / 1000.)

    def _claim_cleanup(self) -> bool:
        if self._closing and not self._executions and not self._cleanup_started:
            self._cleanup_started = True
            return True
        return False

    def _cleanup(self) -> None:
        try:
            if self._close_hook is not None and self._target is not None:
                self._perform(self._close_hook, {}, None, cancellable=False, effect="close")
        except BaseException as exc:
            self._cleanup_error = type(exc).__name__
        finally:
            self._target = None
            self._loaded = False
            super().close()
            self._cleanup_done.set()

    # -- safety bindings ---------------------------------------------------
    @property
    def estop_native(self) -> str | None:
        spec = self._safety.get("estop")
        return spec["call"].native if spec else None

    def _run_safety(self, name: str, ctx: Any) -> str | None:
        spec = self._safety.get(name)
        if spec is None:
            return None
        call: _Call = spec["call"]
        context = BridgeContext.coerce(ctx) if ctx is not None else None
        # Never take self._lock: a running call may hold it (the e-stop preempts).
        self._perform(call, call.args.map({}), context, cancellable=False,
                      effect="reset" if name == "reset" else "safety")
        return call.native

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        with self._activity:
            self._engage_estop()
            if self._executions:
                self._mark_uncertain()
            stamp = (self._activity_version, self.estop_epoch)
        if not any(name in self._safety for name in ("estop", "safe_state")):
            with self._activity:
                if self._executions or self._uncertain:
                    raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                        "unresolved native work has no independent stop binding")
            return {}
        self._ensure_loaded()
        performed: list[str] = []
        failed: list[dict[str, str]] = []
        for name in ("estop", "safe_state"):
            if name not in self._safety:
                continue
            try:
                native = self._run_safety(name, ctx)
                if native:
                    performed.append(native)
            except Exception as exc:  # noqa: BLE001 - try every step, then report
                failed.append({"step": name, "error": type(exc).__name__})
        with self._activity:
            settled = not self._executions and stamp == (self._activity_version, self.estop_epoch)
            if not settled or self._closing:
                failed.append({"step": "native_completion", "error": "unsettled or changed native execution"})
            self._safe_state_achieved = not failed
            self._safe_state_at = _now() if not failed else None
            self._safe_version = stamp if not failed else None
        if failed:
            raise driver_failed(
                "MHS.SAFETY.SAFE_STATE_UNREACHED",
                "the e-stop / safe-state native call failed: "
                + ", ".join(f"{item['step']} ({item['error']})" for item in failed),
                details={"failed": failed, "performed": performed},
            )
        return {
            "estop": "engaged",
            "native": self.estop_native,
            "performed": performed,
            "safe_state_achieved": True,
        }

    def safe_state(self, ctx: Any = None) -> Any:
        if "safe_state" not in self._safety and "estop" not in self._safety:
            with self._activity:
                if self._executions or self._uncertain:
                    raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                        "unresolved native work has no independent stop binding")
            return {}
        self._ensure_loaded()
        name = "safe_state" if "safe_state" in self._safety else "estop"
        with self._activity:
            stamp = (self._activity_version, self.estop_epoch)
        try:
            native = self._run_safety(name, ctx)
            with self._activity:
                if self._executions or self._closing or stamp != (self._activity_version, self.estop_epoch):
                    raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "native work remains unsettled")
                self._safe_state_achieved = True
                self._safe_state_at = _now()
                self._safe_version = stamp
        except Exception as exc:
            with self._activity:
                self._safe_state_achieved = False
                self._safe_state_at = None
                self._safe_version = None
            raise driver_failed(
                "MHS.SAFETY.SAFE_STATE_UNREACHED",
                f"the safe-state native call failed ({type(exc).__name__})",
                details={"step": name},
            ) from exc
        return {"achieved": True, "native": native}

    def interlocks(self) -> list[dict[str, str]]:
        declared = self._safety.get("interlocks") or []
        if not declared:
            return []
        try:
            self._ensure_loaded()
        except Exception:  # noqa: BLE001 - an unloadable target reads as unknown
            return [{"id": item["id"], "state": "unknown", "description": item["description"]}
                    for item in declared]
        states = []
        for item in declared:
            call: _Call = item["call"]
            try:
                value = self._perform(call, call.args.map({}), None, cancellable=False, effect="read")
                state = _interlock_state(value, item["closed_when"])
            except Exception:  # noqa: BLE001 - fail closed: unreadable means unknown
                state = "unknown"
            states.append({"id": item["id"], "state": state, "description": item["description"]})
        return states

    def safety_status(self) -> dict[str, Any]:
        with self._activity:
            if not self._safety and not self._uncertain and not self._executions:
                return {}
            status: dict[str, Any] = {"estop": {"native": self.estop_native}}
            safe_state = self._safety.get("safe_state")
            if safe_state is not None or "estop" in self._safety or self._uncertain or self._executions:
                achieved = (self._safe_state_achieved and not self._executions and not self._closing
                            and self._safe_version == (self._activity_version, self.estop_epoch))
                status["safe_state"] = {
                    "description": (safe_state or {}).get("description") or "e-stop native call completed",
                    "achieved": bool(achieved),
                    "achieved_at": self._safe_state_at if achieved else None,
                }
            return status

    def reset(self, ctx: Any = None) -> Any:
        with self._activity:
            self._reset_ready()
            epoch = self.estop_epoch
            version = self._activity_version
        blocked = [item for item in self.interlocks() if item["state"] != "closed"]
        if blocked:
            raise make_mhs_error(
                "MHS.SAFETY.INTERLOCK_OPEN",
                "reset refused: interlock not closed: " + ", ".join(item["id"] for item in blocked),
                {"retryable": False, "interlocks": blocked},
            )
        native = None
        if "reset" in self._safety:
            self._ensure_loaded()
            native = self._run_safety("reset", ctx)
            # The reset invocation itself has one admission and completion.
            version += 2
        with self._activity:
            if self.estop_epoch != epoch or self._activity_version != version or self._executions or self._closing:
                raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "native state changed while reset was pending")
            self._uncertain = False
            self._safe_state_achieved = False
            self._safe_state_at = None
            self._safe_version = None
        return {"reset": True, "native": native} if native else {}

    def _reset_ready(self) -> None:
        if self._closing or self._executions or (self._uncertain and self._safe_version != (
                self._activity_version, self.estop_epoch)):
            raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                "reset requires settled native calls and a fresh confirmed safe state")

    # -- internals ---------------------------------------------------------
    def _perform(self, call: _Call, mapped: Mapping[str, Any], context: BridgeContext | None, *,
                 cancellable: bool = True, effect: str = "actuation", epoch: int | None = None) -> Any:
        """Invoke one compiled native call and return its resolved raw value."""

        budget: float | None = call.timeout_ms
        if context is not None:
            remaining = float(context.remaining_ms())
            budget = remaining if budget is None else min(float(budget), remaining)
        if effect == "close":
            budget = None  # close() bounds its caller; owned cleanup remains tracked
        deadline = None if budget is None else time.monotonic() + budget / 1000.0
        cancel_event = context.cancel_event if (context is not None and cancellable) else None
        keyword = dict(mapped)
        positional_values = []
        for name in call.positional:
            if name not in keyword:
                raise make_mhs_error(
                    "MHS.CAPABILITY.INPUT_INVALID",
                    f"missing required positional argument {name!r} for {call.label!r}",
                    {"retryable": False},
                )
            positional_values.append(keyword.pop(name))
        try:
            if effect == "read":
                step = self._native_step(call, positional_values, keyword)
                raw = call_bounded(step, timeout_ms=budget, label=call.label)
                left = None if deadline is None else max(0.0, (deadline - time.monotonic()) * 1000.0)
                raw = self._finish_invoke(call, raw, left, cancel_event)
            else:
                raw = self._retained_invoke(call, positional_values, keyword, context, effect,
                                            deadline, cancel_event, epoch)
            if call.parse is not None:
                raw = parse_text(raw, call.parse, whole=call.whole_reply)
            return raw
        except MappingError as exc:
            raise driver_failed(
                "MHS.CAPABILITY.OUTPUT_INVALID",
                f"cannot parse the native response of {call.label!r}: {exc}",
            ) from exc
        except BaseException as exc:  # noqa: BLE001 - translate native failure
            self._raise_native_error(call, exc)
            raise  # pragma: no cover - _raise_native_error always raises

    def _mark_uncertain(self) -> None:
        with self._activity:
            self._uncertain = True
            self._activity_version += 1
            self._safe_state_achieved = False
            self._safe_state_at = None
            self._safe_version = None

    def _mark_execution_uncertain(self, item: RetainedCall) -> None:
        with self._activity:
            if not item.uncertainty_recorded:
                item.uncertainty_recorded = True
                self._mark_uncertain()

    def _retained_invoke(self, call: _Call, positional: list[Any], keyword: dict[str, Any],
                         context: BridgeContext | None, effect: str, deadline: float | None,
                         cancel_event: Any, epoch: int | None) -> Any:
        epoch = self.estop_epoch if epoch is None else epoch

        def execute(item: RetainedCall) -> Any:
            with self._activity:
                if effect not in ("safety", "close"):
                    self._refuse_if_estopped(epoch, call.label)
                    if self._closing:
                        raise make_mhs_error("MHS.DEVICE.NOT_READY", "bridge is closing", {"retryable": False})
                    if cancel_event is not None and cancel_event.is_set():
                        raise signals.Cancelled("cancelled before native dispatch")
                    if deadline is not None and time.monotonic() >= deadline:
                        raise make_mhs_error("MHS.DEVICE.NOT_READY", "deadline expired before native dispatch",
                                             {"retryable": False})
            raw = self._native_step(call, positional, keyword)()
            is_awaitable = inspect.isawaitable(raw)
            is_status = is_status_like(raw) or isinstance(raw, concurrent.futures.Future)
            result = self._resolve_retained(raw, label=call.label, item=item)
            # An invalid invocation profile must not discard an already-started
            # native completion object. Resolve it before reporting the mismatch.
            if call.invoke == "await" and not is_awaitable:
                raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "invoke await returned a non-awaitable")
            if call.invoke == "status" and not (is_awaitable or is_status):
                raise driver_failed("MHS.ADAPTER.SHIM_FAILED", "invoke status returned no Status-like object")
            return result

        def translated(item: RetainedCall) -> Any:
            try:
                return execute(item)
            except TimeoutError as exc:
                raise outcome_unknown(f"{call.label}: native timeout; device outcome is unknown",
                                      details={"native_error_type": type(exc).__name__}) from exc
            except BaseException as exc:
                self._raise_native_error(call, exc)
                raise

        item = RetainedCall(call.label, translated, self._execution_finished, deadline=deadline,
                            resolve_cancel=lambda value: self._resolve_retained(value, label="native cancellation"))
        with self._activity:
            if self._closing and effect != "close":
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "bridge is closing", {"retryable": False})
            if effect == "reset":
                self._reset_ready()
            elif effect == "safety":
                if sum(kind == "safety" for kind in self._executions.values()) >= 8:
                    raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "safety execution capacity is occupied")
            elif effect != "close" and (self._uncertain or self._executions):
                raise make_mhs_error("MHS.DEVICE.NOT_READY",
                                     "native work is unresolved; wait for completion, confirm stop, then reset",
                                     {"retryable": False})
            self._executions[item] = effect
            if effect not in ("safety", "close"):
                self._activity_version += 1
                self._safe_state_achieved = False
                self._safe_state_at = None
                self._safe_version = None
            item.thread.start()
        return item.wait(deadline=deadline, cancel_event=cancel_event,
                         abandoned=lambda: self._mark_execution_uncertain(item))

    def _resolve_retained(self, value: Any, *, label: str, item: RetainedCall | None = None) -> Any:
        """Resolve every native completion stage, including cancellation results."""
        seen = []
        while True:
            future = isinstance(value, concurrent.futures.Future)
            awaitable = inspect.isawaitable(value)
            status = is_status_like(value)
            if not (future or awaitable or status):
                return value
            if any(value is previous for previous in seen):
                raise outcome_unknown(f"{label}: cyclic native completion object")
            seen.append(value)
            if len(seen) > 32:
                seen.pop(0)
            if item is not None:
                value = item.track_awaitable(value)
            if future:
                value = value.result()
            elif awaitable:
                value = self.async_runner.run(value)
            else:
                return self._wait_retained_status(value, label=label)

    @staticmethod
    def _wait_retained_status(status: Any, *, label: str) -> dict[str, bool]:
        missing = object()
        def flag(name):
            try:
                value = getattr(status, name, missing)
                return value() if callable(value) else value
            except Exception:
                return None  # unreadable is not a terminal or successful state

        prior_error = None
        while True:
            before = flag("done")
            try:
                wait = getattr(status, "wait", None)
                if callable(wait):
                    result = wait(.01)
                else:
                    result = None
                    if before is not True:
                        time.sleep(.01)
            except Exception as exc:
                done = flag("done")
                timed_out = isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower()
                if timed_out:
                    # The done flag may have changed just after the wait slice
                    # expired. Poll again; a slice timeout is not an operation
                    # timeout, including wait-only completion interfaces.
                    if done is True and flag("success") is False:
                        raise outcome_unknown(f"{label}: native Status operation timed out") from exc
                    time.sleep(.01)
                    continue
                if done is missing or done is True:
                    # A terminal non-timeout native failure remains a failure.
                    raise
                prior_error = exc
                time.sleep(.01)
                continue
            done = flag("done")
            if (done is not missing and done is not True) or result is False:
                time.sleep(.01)
                continue
            success = flag("success")
            if success is False:
                raise driver_failed("MHS.DEVICE.FAULTED", f"{label}: Status reported failure")
            if success is not missing and success is not True:
                raise outcome_unknown(f"{label}: terminal Status success is unknown")
            if prior_error is not None:
                raise prior_error
            return {"done": True, "success": True}

    def _execution_finished(self, item: RetainedCall) -> None:
        with self._activity:
            # Fence before removing the worker, not later when its caller gets
            # scheduled and notices an expired deadline/native timeout.
            if isinstance(item.error, signals.OutcomeUnknown) or (
                    item.deadline is not None and item.done_at > item.deadline):
                self._mark_execution_uncertain(item)
            effect = self._executions.pop(item)
            if effect not in ("safety", "close"):
                self._activity_version += 1
                self._safe_state_achieved = False
                self._safe_state_at = None
                self._safe_version = None
            cleanup = self._claim_cleanup()
            self._activity.notify_all()
        if cleanup:
            threading.Thread(target=self._cleanup, name="mhs-python-close", daemon=True).start()

    def _native_step(self, call: _Call, positional: list[Any], keyword: dict[str, Any]) -> Callable[[], Any]:
        invoke = call.invoke
        if invoke in ("call", "await", "status"):
            fn = self._resolve(call.native)
            return lambda: fn(*positional, **keyword)
        if invoke == "get":
            def get() -> Any:
                value = self._attr(call.native)
                if callable(value) and not inspect.isawaitable(value):
                    raise driver_failed(
                        "MHS.ADAPTER.SHIM_FAILED",
                        f"native {call.native!r} is a method; bind it with invoke 'call'",
                    )
                return value

            return get
        if invoke == "set":
            if positional or len(keyword) != 1:
                raise _manifest_invalid(f"{call.label}: invoke 'set' needs exactly one argument")
            parent, name = self._attr_parent(call.native)
            value = next(iter(keyword.values()))

            def set_value() -> Any:
                setattr(parent, name, value)
                return value

            return set_value
        # query / write: the native is the request method, the command its argument
        fn = self._resolve(call.native)
        try:
            line = format_command(str(call.command), keyword, separators=call.separators)
        except MappingError as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"{call.label}: {exc}",
                                 {"retryable": False}) from exc
        return lambda: fn(line)

    def _finish_invoke(self, call: _Call, raw: Any, timeout_ms: float | None, cancel_event: Any) -> Any:
        label = call.label
        if call.invoke == "set":
            return raw
        if call.invoke == "await" and not inspect.isawaitable(raw):
            raise driver_failed("MHS.ADAPTER.SHIM_FAILED",
                                f"invoke 'await' but {call.native!r} returned a non-awaitable")
        if call.invoke == "status" and not (inspect.isawaitable(raw) or is_status_like(raw)
                                            or isinstance(raw, concurrent.futures.Future)):
            raise driver_failed("MHS.ADAPTER.SHIM_FAILED",
                                f"invoke 'status' but {call.native!r} returned no Status-like object")
        needs_loop = inspect.isawaitable(raw)
        return resolve_native(raw, runner=self.async_runner if needs_loop else None, timeout_ms=timeout_ms,
                              cancel_event=cancel_event, label=label)

    def _resolve(self, dotted: str) -> Callable[..., Any]:
        current = self._attr(dotted)
        if not callable(current):
            raise make_mhs_error(
                "MHS.CAPABILITY.NOT_BOUND", f"native symbol {dotted!r} is not callable", {"retryable": False}
            )
        return current

    def _attr(self, dotted: str) -> Any:
        current = self._target
        for part in dotted.split("."):
            if not part:
                continue
            try:
                current = getattr(current, part)
            except AttributeError as exc:
                raise make_mhs_error(
                    "MHS.CAPABILITY.NOT_BOUND",
                    f"native symbol {dotted!r} is absent on the bridge target",
                    {"retryable": False},
                ) from exc
        return current

    def _attr_parent(self, dotted: str) -> tuple[Any, str]:
        parts = [part for part in dotted.split(".") if part]
        if not parts:
            raise _manifest_invalid(f"invalid property path {dotted!r}")
        parent = self._attr(".".join(parts[:-1])) if len(parts) > 1 else self._target
        return parent, parts[-1]

    def _get(self, dotted: str, *, timeout_ms: float | None = None) -> Any:
        """Read an attribute path from the target, calling zero-argument methods."""

        current = self._target
        for part in dotted.split("."):
            if not part:
                continue
            current = getattr(current, part)
        if callable(current):
            try:
                signature = inspect.signature(current)
            except (TypeError, ValueError):  # pragma: no cover - C callables
                current = current()
            else:
                required = [
                    parameter
                    for parameter in signature.parameters.values()
                    if parameter.default is inspect.Parameter.empty
                    and parameter.kind
                    in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                if required:
                    return current
                current = current()
        return self.resolve_native(current, timeout_ms=timeout_ms or _DEFAULT_TIMEOUT_MS["read"],
                                   label=f"read {dotted}")

    def _map_args(self, spec: Any, source: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return FieldMapping(spec, direction="input").map(dict(source))
        except (MappingError, UnitError) as exc:
            raise make_mhs_error(
                "MHS.CAPABILITY.INPUT_INVALID", f"cannot map bridge arguments: {exc}", {"retryable": False}
            ) from exc

    def _map_result(self, binding: Mapping[str, Any], raw: Any) -> Any:
        mapping: FieldMapping = binding["result"]
        try:
            if mapping:
                output = jsonable(mapping.map(raw))
                if binding.get("stamp_sampled_at") and "sampled_at" not in output:
                    output["sampled_at"] = _now()
                return output
            if raw is None:
                return {}
            if isinstance(raw, Mapping):
                return jsonable(dict(raw))
            return {"value": jsonable(raw)}
        except (MappingError, UnitError) as exc:
            raise driver_failed(
                "MHS.CAPABILITY.OUTPUT_INVALID",
                f"cannot map the native result of {binding['capability_id']!r}: {exc}",
                details={"capability_id": binding["capability_id"]},
            ) from exc

    def _raise_native_error(self, call: _Call, exc: BaseException) -> None:
        if isinstance(exc, (signals.DriverSignal, MHSError)):
            raise exc
        if isinstance(exc, (asyncio.CancelledError, concurrent.futures.CancelledError)):
            raise signals.Cancelled(f"{call.label} was cancelled") from exc
        if _is_divergence(exc) or not isinstance(exc, Exception):
            raise exc
        code, message, retryable = call.errors.translate_exception(exc)
        details: dict[str, Any] = {"native_error_type": type(exc).__name__}
        if code == "MHS.ADAPTER.SHIM_FAILED":
            # ADPT-022: unmapped native exceptions surface with a redacted
            # message; the native text is not echoed into the error.
            message = f"native {type(exc).__name__} raised an unmapped error"
            details["redacted"] = True
        else:
            details["native_message"] = str(exc)[:500]
        raise driver_failed(code, message, details=details, retryable=retryable) from exc

    # -- introspection -----------------------------------------------------
    def describe(self) -> dict[str, Any]:
        described = super().describe()
        described.update(
            {
                "target": self._target_spec,
                "loaded": self._loaded,
                "grammar": self.grammar,
                "strict": self.strict,
                "config_keys": sorted(self.config),
                "bindings_adapter_id": (
                    self.bindings_document.adapter_id if self.bindings_document else None
                ),
                "safety_bindings": sorted(self._safety),
            }
        )
        return described


def _legacy_result_path(path: Any) -> Any:
    """``result.x``/``$.x`` of the legacy grammar read the native return (0.8 wrapper)."""

    if isinstance(path, str):
        for prefix in ("result.", "$."):
            if path.startswith(prefix):
                return "output." + path[len(prefix):]
    return path


def _legacy_result_spec(spec: Any) -> Any:
    """Rewrite the legacy ``result.``/``$.`` result paths to ``output.`` (same meaning as in 0.8)."""

    if not isinstance(spec, Mapping):
        return spec
    wrapped = set(spec) == {"map"} and isinstance(spec.get("map"), Mapping)
    rules = spec["map"] if wrapped else spec
    rewritten: dict[str, Any] = {}
    for target, rule in rules.items():
        if isinstance(rule, str):
            rewritten[target] = _legacy_result_path(rule)
        elif isinstance(rule, Mapping):
            rule = dict(rule)
            for key in ("from", "path"):
                if key in rule:
                    rule[key] = _legacy_result_path(rule[key])
            rewritten[target] = rule
        else:
            rewritten[target] = rule
    return {"map": rewritten} if wrapped else rewritten


def _interlock_state(value: Any, closed_when: Any) -> str:
    """``closed``/``open``/``unknown``; a boolean ``closed_when`` only matches a boolean.

    A strict ``bool`` parse raises on an unrecognised reply (read as
    ``unknown`` by the caller), so an error string never reads as ``False``.
    """

    if isinstance(closed_when, bool):
        if not isinstance(value, bool):
            return "unknown"
        return "closed" if value is closed_when else "open"
    if value is None or isinstance(value, bool):
        return "unknown"
    return "closed" if value == closed_when else "open"


def _is_timestamp_property(schema: Mapping[str, Any], name: str) -> bool:
    prop = (schema.get("properties") or {}).get(name)
    return isinstance(prop, Mapping) and prop.get("type", "string") == "string"


def _is_divergence(exc: BaseException) -> bool:
    return type(exc).__name__ == "TranscriptDivergence"


def _now() -> str:
    from mhs import canonical  # local import: canonical is only needed for timestamps

    return canonical.now_rfc3339()


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
