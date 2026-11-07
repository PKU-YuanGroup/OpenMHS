"""Serial-instrument bridge family (MHS-000 section 9.3).

Wraps a line-oriented serial instrument (pyserial) behind bounded
transactions.  Adapters declare, per capability, a command template, the
response parser and the argument mapping; the bridge never blocks unboundedly:
every transaction has a positive timeout, a bounded number of read attempts
and respects the deadline carried in the bridge context.  A transaction whose
response never arrives is an *unknown* outcome (the command was sent), never a
retryable failure.

``safety_bindings`` map the e-stop, the safe state, reset and interlocks onto
commands::

    "safety_bindings": {
      "estop": {"command": "STOP"},                         # written, no response read
      "safe_state": {"command": ["HEAT 0", "PUMP 0"], "description": "heater and pump off"},
      "reset": {"command": "RST", "response": true},
      "interlocks": [{"id": "door", "command": "DOOR?", "parse": {"kind": "int"}, "closed_when": 1}]
    }

The e-stop is written without waiting for a running transaction (only the short
write lock is taken) and aborts that transaction's wait for its response; a
capability or write transaction that has not put its command on the wire when
the e-stop fires -- still queued on the transaction lock, or already past it --
is refused with ``MHS.SAFETY.ESTOP_ENGAGED`` and never written: the e-stop
epoch is re-checked under the write lock, so no actuation follows the e-stop
command on the wire.  A boolean ``closed_when`` (``true`` by default, or
``false`` for an inverted query such as ``DOOR:OPEN?``) needs
``parse: {"kind": "bool"}`` and a ``bool`` parse needs a boolean
``closed_when``; any other parse must declare the closed value.  The ``bool``
parse is strict, so an error, empty or garbage reply reads ``unknown``
(never closed) and blocks a reset.  An interlock's ``int``, ``float`` or
``regex`` parse must match the *whole* reply (``DOOR?`` answering ``1`` reads
1; ``E1 bad`` or ``ERR 1: syntax`` reads ``unknown``, never the closed value).
String arguments may not contain line breaks or control characters, so an
input can never inject a second command.

The module is import-safe without pyserial: the dependency is resolved when the
bridge opens, and tests inject a fake port with ``serial_factory=...``
(:class:`FakeSerial`, or :meth:`mhs.bridge.transcript.Transcript.serial` to
replay a recorded exchange).
"""

from __future__ import annotations

import importlib
import re
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from mhs import signals
from mhs.bridge.base import (
    Bridge,
    BridgeContext,
    FieldMapping,
    MappingError,
    UnitError,
    _Rule,
    driver_failed,
    format_command,
    jsonable,
    make_mhs_error,
    outcome_unknown,
    parse_text,
    unsupported,
)
from mhs.bridge.base import main as _bridge_main
from mhs.bridge.bindings import parse_spec_errors
from mhs.errors import MHSError

__all__ = ["SerialBridge", "FakeSerial", "main"]

_MAX_READS_PER_TRANSACTION = 4096
CONFIGURE_CAPABILITY = "cap.device.configure.v1"

_CONFIG_KEYS = {
    "port", "baudrate", "timeout_s", "encoding", "terminator", "capabilities", "reads", "writes",
    "resources", "description", "metadata", "safety_bindings", "bytesize", "parity", "stopbits",
}
_CAPABILITY_KEYS = {"resource", "native", "command", "args", "parse", "response", "result", "description"}
_READ_KEYS = {"command", "parse", "fields", "description"}
_WRITE_KEYS = {"command", "args", "response", "params", "description"}
_PARAM_KEYS = {"command", "response", "type", "unit", "units", "clamp", "enum_map", "map", "description"}
_SAFETY_KEYS = {"estop", "reset", "safe_state", "interlocks"}
_SAFETY_COMMAND_KEYS = {"command", "response", "timeout_ms", "description"}
_INTERLOCK_KEYS = {"id", "command", "parse", "closed_when", "timeout_ms", "description"}


def _manifest_invalid(message: str) -> Exception:
    return make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", message,
                          {"retryable": False, "details": {"errors": [message]}})


class FakeSerial:
    """Small in-memory serial stand-in used by the bridge unit tests."""

    def __init__(self, responses: Mapping[str, str] | None = None, *, default: str = "OK\n", echo: bool = True):
        self.responses = dict(responses or {})
        self.default = default
        self.echo = echo
        self.is_open = True
        self.timeout = 0.1
        self.written: list[bytes] = []
        self._buffer = bytearray()
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        with self._lock:
            self.written.append(bytes(data))
            line = data.decode("ascii", "replace").strip()
            response = self.responses.get(line, self.default)
            self._buffer.extend(response.encode("ascii"))
        return len(data)

    def read(self, size: int = 1) -> bytes:
        with self._lock:
            if not self._buffer:
                return b""
            chunk = bytes(self._buffer[:size])
            del self._buffer[:size]
            return chunk

    def readline(self) -> bytes:
        with self._lock:
            newline = self._buffer.find(b"\n")
            if newline < 0:
                chunk = bytes(self._buffer)
                self._buffer.clear()
                return chunk
            chunk = bytes(self._buffer[: newline + 1])
            del self._buffer[: newline + 1]
            return chunk

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._buffer.clear()

    def close(self) -> None:
        self.is_open = False


def _commands(value: Any, label: str) -> list[str]:
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)) or not items or not all(
        isinstance(item, str) and item.strip() for item in items
    ):
        raise _manifest_invalid(f"{label} must be a command string or a non-empty list of them")
    for item in items:
        if any(ord(char) < 32 for char in item):
            raise _manifest_invalid(f"{label} {item!r} must be one line without control characters")
    return list(items)


class SerialBridge(Bridge):
    """Bridge a line-oriented serial instrument behind bounded transactions."""

    bridge_kind = "serial"
    bridge_id = "mhs.bridge.serial"

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        device_id: str | None = None,
        serial_factory: Callable[..., Any] | None = None,
    ):
        super().__init__(device_id=device_id)
        self.config = dict(config or {})
        unknown = set(self.config) - _CONFIG_KEYS
        if unknown:
            raise _manifest_invalid(f"unknown serial bridge config keys: {sorted(unknown)}")
        self.bridge_id = f"mhs.bridge.serial:{self.config.get('port', '?')}"
        self._port = self.config.get("port")
        self._baudrate = int(self.config.get("baudrate", 115200))
        self._timeout_s = float(self.config.get("timeout_s", 0.5))
        self._encoding = str(self.config.get("encoding", "ascii"))
        self._terminator = str(self.config.get("terminator", "\n"))
        self._factory = serial_factory
        self._serial: Any = None
        if self._timeout_s <= 0:
            raise make_mhs_error(
                "MHS.PROTOCOL.DEADLINE_INVALID", "serial timeout must be positive (bounded blocking)",
                {"retryable": False},
            )
        self._caps = self._compile_capabilities(self.config.get("capabilities"))
        self._reads = self._compile_reads(self.config.get("reads"))
        self._writes = self._compile_writes(self.config.get("writes"))
        self._safety = self._compile_safety(self.config.get("safety_bindings"))
        #: Serialises request/response transactions (never taken by the e-stop).
        self._txn_lock = threading.RLock()
        #: Held only while bytes are written; the e-stop shares the wire through it.
        self._write_lock = threading.Lock()
        self._abort = threading.Event()
        self._open_lock = threading.Lock()
        self._safe_state_achieved = False

    # -- compilation -------------------------------------------------------
    def _compile_capabilities(self, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("capabilities must be an object keyed by capability id")
        compiled: dict[str, dict[str, Any]] = {}
        for capability_id, spec in raw.items():
            label = f"capabilities[{capability_id!r}]"
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"{label} must be an object")
            unknown = set(spec) - _CAPABILITY_KEYS
            if unknown:
                raise _manifest_invalid(f"unknown keys in {label}: {sorted(unknown)}")
            if not isinstance(spec.get("command"), str) or not spec["command"].strip():
                raise _manifest_invalid(f"{label} needs a 'command' template")
            if spec.get("parse") is not None and not isinstance(spec["parse"], Mapping):
                raise _manifest_invalid(f"{label}.parse must be an object")
            try:
                args = FieldMapping(spec.get("args"), direction="input")
                result = FieldMapping(spec["result"], direction="output") if spec.get("result") else None
            except (MappingError, UnitError) as exc:
                raise _manifest_invalid(f"{label} is invalid: {exc}") from exc
            compiled[str(capability_id)] = {**dict(spec), "args": args, "result": result}
        return compiled

    def _compile_reads(self, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("reads must be an object keyed by resource id")
        for resource_id, spec in raw.items():
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"reads[{resource_id!r}] must be an object")
            unknown = set(spec) - _READ_KEYS
            if unknown:
                raise _manifest_invalid(f"unknown keys in reads[{resource_id!r}]: {sorted(unknown)}")
            if "fields" in spec:
                for name, field_spec in dict(spec["fields"]).items():
                    if not isinstance(field_spec, Mapping) or not isinstance(field_spec.get("command"), str):
                        raise _manifest_invalid(f"reads[{resource_id!r}].fields[{name!r}] needs a 'command'")
                    problems = parse_spec_errors(field_spec.get("parse", {"kind": "str"}),
                                                 f"reads[{resource_id!r}].fields[{name!r}].parse")
                    if problems:
                        raise _manifest_invalid("; ".join(problems))
            elif not isinstance(spec.get("command"), str):
                raise _manifest_invalid(f"reads[{resource_id!r}] needs a 'command' or 'fields'")
        return {str(key): dict(value) for key, value in raw.items()}

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
            entry: dict[str, Any] = {"response": spec.get("response", True)}
            if spec.get("params") is not None:
                params: dict[str, Any] = {}
                for name, param in dict(spec["params"]).items():
                    plabel = f"{label}.params[{name!r}]"
                    if not isinstance(param, Mapping) or not isinstance(param.get("command"), str):
                        raise _manifest_invalid(f"{plabel} needs a 'command' template with {{value}}")
                    unknown = set(param) - _PARAM_KEYS
                    if unknown:
                        raise _manifest_invalid(f"unknown keys in {plabel}: {sorted(unknown)}")
                    rule_spec = {"from": "$", **{key: param[key] for key in
                                                 ("type", "unit", "units", "clamp", "enum_map", "map")
                                                 if key in param}}
                    try:
                        rule = _Rule("value", rule_spec, direction="input")
                    except (MappingError, UnitError) as exc:
                        raise _manifest_invalid(f"{plabel} is invalid: {exc}") from exc
                    params[str(name)] = {"command": param["command"], "rule": rule,
                                         "response": param.get("response", True)}
                entry["params"] = params
            elif isinstance(spec.get("command"), str):
                try:
                    entry["args"] = FieldMapping(spec.get("args"), direction="input")
                except (MappingError, UnitError) as exc:
                    raise _manifest_invalid(f"{label} is invalid: {exc}") from exc
                entry["command"] = spec["command"]
            else:
                raise _manifest_invalid(f"{label} needs 'params' or a 'command'")
            compiled[str(resource_id)] = entry
        return compiled

    def _compile_safety(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("safety_bindings must be an object")
        unknown = set(raw) - _SAFETY_KEYS
        if unknown:
            raise _manifest_invalid(f"unknown safety_bindings keys: {sorted(unknown)}")
        compiled: dict[str, Any] = {}
        for name in ("estop", "safe_state", "reset"):
            spec = raw.get(name)
            if spec is None:
                continue
            if isinstance(spec, (str, list)):
                spec = {"command": spec}
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"safety_bindings.{name} must be an object")
            unknown = set(spec) - _SAFETY_COMMAND_KEYS
            if unknown:
                raise _manifest_invalid(f"unknown keys in safety_bindings.{name}: {sorted(unknown)}")
            compiled[name] = {
                "commands": _commands(spec.get("command"), f"safety_bindings.{name}.command"),
                "response": bool(spec.get("response", name == "reset")),
                "description": spec.get("description"),
            }
        interlocks = raw.get("interlocks")
        if interlocks is not None:
            if not isinstance(interlocks, (list, tuple)):
                raise _manifest_invalid("safety_bindings.interlocks must be an array")
            items = []
            for index, spec in enumerate(interlocks):
                label = f"safety_bindings.interlocks[{index}]"
                if not isinstance(spec, Mapping):
                    raise _manifest_invalid(f"{label} must be an object")
                unknown = set(spec) - _INTERLOCK_KEYS
                if unknown:
                    raise _manifest_invalid(f"unknown keys in {label}: {sorted(unknown)}")
                if not isinstance(spec.get("id"), str) or not spec["id"]:
                    raise _manifest_invalid(f"{label} needs an 'id'")
                problems = parse_spec_errors(spec.get("parse", {"kind": "str"}), f"{label}.parse")
                if problems:
                    raise _manifest_invalid("; ".join(problems))
                parse = dict(spec.get("parse") or {"kind": "str"})
                closed_when = spec.get("closed_when", True)
                if isinstance(closed_when, bool) and parse.get("kind") != "bool":
                    raise _manifest_invalid(
                        f"{label}: closed_when {str(closed_when).lower()} only matches a boolean, so a "
                        f"{parse.get('kind')!r} response could never read closed; use parse kind 'bool' "
                        "or declare closed_when as the whole reply's value (e.g. 1 or 'CLOSED')"
                    )
                if parse.get("kind") == "bool" and not isinstance(closed_when, bool):
                    raise _manifest_invalid(
                        f"{label}: a 'bool' parse reads true or false, so closed_when must be true or "
                        f"false (not {closed_when!r})"
                    )
                items.append({
                    "id": spec["id"],
                    "command": _commands(spec.get("command"), f"{label}.command")[0],
                    "parse": dict(spec.get("parse") or {"kind": "str"}),
                    "closed_when": spec.get("closed_when", True),
                    "timeout_s": float(spec.get("timeout_ms", 500)) / 1000.0,
                    "description": str(spec.get("description") or spec["id"]),
                })
            compiled["interlocks"] = items
        return compiled

    # -- availability / lifecycle -----------------------------------------
    @staticmethod
    def available() -> bool:
        try:
            importlib.import_module("serial")
            return True
        except ImportError:
            return False

    def _ensure_open(self) -> Any:
        self.ensure_open()
        if self._serial is not None:
            return self._serial
        with self._open_lock:
            if self._serial is not None:
                return self._serial
            options = {"port": self._port, "baudrate": self._baudrate, "timeout": self._timeout_s}
            for key in ("bytesize", "parity", "stopbits"):
                if key in self.config:
                    options[key] = self.config[key]
            if self._factory is not None:
                self._serial = self._factory(**options)
                return self._serial
            try:
                serial_module = importlib.import_module("serial")
            except ImportError as exc:
                raise make_mhs_error(
                    "MHS.DEVICE.NOT_READY",
                    "pyserial is not installed; the serial bridge cannot open a port",
                    {"retryable": False, "remediation": "pip install pyserial in the endpoint environment."},
                ) from exc
            if not self._port:
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "serial bridge needs a port", {"retryable": False})
            try:
                self._serial = serial_module.Serial(**options)
            except Exception as exc:  # noqa: BLE001
                raise make_mhs_error(
                    "MHS.DEVICE.NOT_READY", f"cannot open serial port {self._port!r} ({type(exc).__name__})",
                    {"retryable": False},
                ) from exc
            return self._serial

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._serial is not None:
                self._serial.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._serial = None
            super().close()

    # -- adapter surface ---------------------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        entries = []
        for capability_id, binding in self._caps.items():
            entries.append(
                {
                    "capability_id": capability_id,
                    "resource": binding.get("resource", "instrument"),
                    "native": binding.get("native") or f"serial:{binding.get('command')}",
                    "description": binding.get("description", "serial instrument transaction"),
                }
            )
        if CONFIGURE_CAPABILITY not in self._caps:
            for resource_id in self._writes:
                entries.append({"capability_id": CONFIGURE_CAPABILITY, "resource": resource_id,
                                "native": f"serial:{self._port}",
                                "description": "Write the resource's writable parameters."})
        return entries

    def resources(self) -> list[dict[str, Any]]:
        declared = self.config.get("resources")
        if isinstance(declared, list):
            return [dict(item) for item in declared]
        return [{"resource_id": "instrument", "kind": "instrument.serial"}]

    # -- transactions ------------------------------------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        context = BridgeContext.coerce(ctx)
        binding = self._caps.get(str(capability_id))
        if binding is None:
            if str(capability_id) == CONFIGURE_CAPABILITY and self._writes:
                resource = context.resource if context.resource in self._writes else None
                if resource is None and len(self._writes) == 1:
                    resource = next(iter(self._writes))
                if resource is None:
                    raise unsupported(capability_id)
                return self.write(resource, dict(args or {}), context)
            raise unsupported(capability_id)
        if context.cancelled():
            raise signals.Cancelled("cancelled before the serial transaction")
        epoch = self.estop_epoch   # taken before waiting for the transaction lock
        try:
            mapped = binding["args"].map(dict(args or {}))
        except (MappingError, UnitError) as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"cannot map serial arguments: {exc}",
                                 {"retryable": False}) from exc
        command = _format_command(binding.get("command"), mapped)
        if binding.get("response") is False:
            self._transact(command, context, expect_response=False, epoch=epoch)
            return {"command": command, "response": None}
        response = self._transact(command, context, epoch=epoch)
        try:
            parsed = _parse_response(binding.get("parse"), response)
            if binding.get("result") is not None:
                parsed = binding["result"].map(parsed)
            return jsonable(parsed)
        except (MappingError, UnitError) as exc:
            raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", f"cannot parse the serial response: {exc}") from exc

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        spec = self._reads.get(str(resource_id))
        if spec is None:
            raise unsupported(resource_id, kind="resource")
        context = BridgeContext.coerce(ctx)
        try:
            if "fields" in spec:
                parsed: dict[str, Any] = {}
                for name, field_spec in dict(spec["fields"]).items():
                    response = self._transact(_format_command(field_spec["command"], {}), context)
                    parsed[str(name)] = parse_text(response, field_spec.get("parse") or {"kind": "str"})
            else:
                response = self._transact(_format_command(spec.get("command"), {}), context)
                parsed = _parse_response(spec.get("parse"), response)
                if not isinstance(parsed, Mapping):
                    parsed = {"value": parsed}
            parsed = jsonable(dict(parsed))
        except MappingError as exc:
            raise make_mhs_error("MHS.RESOURCE.STATE_INVALID", f"cannot parse the serial state: {exc}",
                                 {"retryable": False}) from exc
        if fields:
            return {name: parsed.get(name) for name in fields if name in parsed}
        return parsed

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        spec = self._writes.get(str(resource_id))
        if spec is None:
            raise unsupported(resource_id, kind="resource")
        context = BridgeContext.coerce(ctx)
        if not isinstance(patch, Mapping) or not patch:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "a write needs a non-empty parameter patch",
                                 {"retryable": False})
        epoch = self.estop_epoch   # taken before waiting for the transaction lock
        if "params" in spec:
            params = spec["params"]
            stray = sorted(str(key) for key in patch if key not in params)
            if stray:
                raise make_mhs_error(
                    "MHS.RESOURCE.NOT_WRITABLE", f"parameters {stray} of {resource_id!r} are not writable",
                    {"retryable": False, "details": {"parameters": stray, "writable": sorted(params)}},
                )
            commands = []
            for name, value in patch.items():
                try:
                    native_value = params[name]["rule"].apply(value)
                except (MappingError, UnitError, TypeError, ValueError) as exc:
                    raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"cannot map parameter {name!r}: {exc}",
                                         {"retryable": False}) from exc
                commands.append((name, value, _format_command(params[name]["command"], {"value": native_value}),
                                 params[name]["response"]))
            applied: dict[str, Any] = {}
            for name, value, command, response in commands:
                try:
                    self._transact(command, context, expect_response=bool(response), epoch=epoch)
                except MHSError as exc:
                    if applied and exc.code == "MHS.SAFETY.ESTOP_ENGAGED":
                        exc.data.setdefault("details", {})["applied"] = dict(applied)
                    raise
                applied[name] = jsonable(value)
            return {"applied": applied}
        try:
            mapped = spec["args"].map({"patch": dict(patch), "$": dict(patch), **dict(patch)})
        except (MappingError, UnitError) as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"cannot map serial write: {exc}",
                                 {"retryable": False}) from exc
        command = _format_command(spec["command"], mapped)
        self._transact(command, context, expect_response=spec.get("response") is not False, epoch=epoch)
        return {"applied": jsonable(dict(patch))}

    def _transact(self, command: str, context: BridgeContext, *, expect_response: bool = True,
                  budget_s: float | None = None, epoch: int | None = None) -> str:
        """One write (+ response) under the transaction lock.

        ``epoch`` is :attr:`estop_epoch` taken when the operation started: an
        e-stop since then refuses the command before it is written (checked
        when the transaction lock is taken and again under the write lock).
        """
        payload = (command + self._terminator).encode(self._encoding, "replace")
        budget = min(self._timeout_s, max(0.001, context.remaining_ms() / 1000.0))
        if budget_s is not None:
            budget = min(budget, budget_s)
        deadline = time.monotonic() + budget
        serial_obj = self._ensure_open()
        terminator = self._terminator.encode(self._encoding)
        with self._txn_lock:
            if epoch is not None:
                self._refuse_if_estopped(epoch, f"serial command {command!r}")
            if context.cancelled():
                raise signals.Cancelled("cancelled before the serial transaction")
            self._abort.clear()
            try:
                flush = getattr(serial_obj, "reset_input_buffer", None)
                if callable(flush):
                    flush()
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ == "TranscriptDivergence":
                    raise
                raise driver_failed(
                    "MHS.DEVICE.FAULTED", f"serial input flush failed ({type(exc).__name__})",
                    details={"command": command},
                ) from exc
            with self._write_lock:
                # The e-stop advances the epoch before it takes this lock: a command
                # written here either precedes the e-stop command or is refused.
                if epoch is not None:
                    self._refuse_if_estopped(epoch, f"serial command {command!r}")
                try:
                    serial_obj.write(payload)
                except Exception as exc:  # noqa: BLE001
                    if type(exc).__name__ == "TranscriptDivergence":
                        raise
                    raise driver_failed(
                        "MHS.DEVICE.FAULTED", f"serial write failed ({type(exc).__name__})",
                        details={"command": command},
                    ) from exc
            if not expect_response:
                return ""
            buffer = bytearray()
            reads = 0
            interrupted = None
            try:
                while time.monotonic() < deadline and reads < _MAX_READS_PER_TRANSACTION:
                    if self._abort.is_set():
                        interrupted = "an e-stop interrupted the wait for the response"
                        break
                    if context.cancelled():
                        interrupted = "cancellation interrupted the wait for the response"
                        break
                    reads += 1
                    chunk = serial_obj.readline()
                    if chunk:
                        buffer.extend(chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode())
                        if terminator in buffer:
                            break
                    else:
                        time.sleep(0.001)
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ == "TranscriptDivergence":
                    raise
                raise outcome_unknown(
                    f"reading the response to {command!r} failed ({type(exc).__name__}); the command was sent",
                    details={"command": command},
                ) from exc
        if interrupted or not buffer:
            raise outcome_unknown(
                f"no response to {command!r} ({interrupted or f'none within {budget:.3g} s'}); "
                "the command was sent, its effect is unknown",
                details={"command": command, "timeout_s": round(budget, 6)},
            )
        return buffer.decode(self._encoding, "replace")

    # -- safety bindings ---------------------------------------------------
    @property
    def estop_native(self) -> str | None:
        spec = self._safety.get("estop")
        return spec["commands"][0] if spec else None

    def _write_safety(self, name: str) -> list[str]:
        spec = self._safety.get(name)
        if spec is None:
            return []
        serial_obj = self._ensure_open()
        written = []
        for command in spec["commands"]:
            payload = (command + self._terminator).encode(self._encoding, "replace")
            with self._write_lock:   # never the transaction lock: a running call may hold it
                serial_obj.write(payload)
            written.append(command)
        return written

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        self._engage_estop()   # transactions queued on the lock are refused from now on
        if "estop" not in self._safety and "safe_state" not in self._safety:
            return {}
        self._abort.set()   # a running transaction stops waiting for its response
        performed: list[str] = []
        failed: list[dict[str, str]] = []
        for name in ("estop", "safe_state"):
            try:
                performed.extend(self._write_safety(name))
            except Exception as exc:  # noqa: BLE001 - try every step, then report
                failed.append({"step": name, "error": type(exc).__name__})
        self._safe_state_achieved = not failed
        if failed:
            raise driver_failed(
                "MHS.SAFETY.SAFE_STATE_UNREACHED",
                "the e-stop / safe-state command could not be written: "
                + ", ".join(f"{item['step']} ({item['error']})" for item in failed),
                details={"failed": failed, "performed": performed},
            )
        return {"estop": "engaged", "native": self.estop_native, "performed": performed,
                "safe_state_achieved": True}

    def safe_state(self, ctx: Any = None) -> Any:
        name = "safe_state" if "safe_state" in self._safety else "estop"
        if name not in self._safety:
            return {}
        try:
            performed = self._write_safety(name)
        except Exception as exc:  # noqa: BLE001
            self._safe_state_achieved = False
            raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                f"the safe-state command could not be written ({type(exc).__name__})") from exc
        self._safe_state_achieved = True
        return {"achieved": True, "native": performed[0] if performed else None}

    def interlocks(self) -> list[dict[str, str]]:
        items = self._safety.get("interlocks") or []
        states = []
        for item in items:
            state = "unknown"
            if self._txn_lock.acquire(timeout=item["timeout_s"]):
                try:
                    context = BridgeContext(deadline_ms=max(1, int(item["timeout_s"] * 1000)))
                    response = self._transact(item["command"], context, budget_s=item["timeout_s"])
                    state = _interlock_state(parse_text(response, item["parse"], whole=True),
                                             item["closed_when"])
                except Exception:  # noqa: BLE001 - fail closed: unreadable means unknown
                    state = "unknown"
                finally:
                    self._txn_lock.release()
            states.append({"id": item["id"], "state": state, "description": item["description"]})
        return states

    def safety_status(self) -> dict[str, Any]:
        if not self._safety:
            return {}
        status: dict[str, Any] = {"estop": {"native": self.estop_native}}
        if "safe_state" in self._safety or "estop" in self._safety:
            description = (self._safety.get("safe_state") or {}).get("description")
            status["safe_state"] = {"description": description or "e-stop command written",
                                    "achieved": bool(self._safe_state_achieved)}
        return status

    def reset(self, ctx: Any = None) -> Any:
        blocked = [item for item in self.interlocks() if item["state"] != "closed"]
        if blocked:
            raise make_mhs_error(
                "MHS.SAFETY.INTERLOCK_OPEN",
                "reset refused: interlock not closed: " + ", ".join(item["id"] for item in blocked),
                {"retryable": False, "interlocks": blocked},
            )
        spec = self._safety.get("reset")
        self._safe_state_achieved = False
        if spec is None:
            return {}
        context = BridgeContext.coerce(ctx)
        for command in spec["commands"]:
            self._transact(command, context, expect_response=spec["response"])
        return {"reset": True, "native": spec["commands"][0]}

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        raise make_mhs_error(
            "MHS.CAPABILITY.NOT_BOUND",
            "serial instruments do not expose a normative state snapshot; declare snapshot_restore false",
            {"retryable": False},
        )

    def describe(self) -> dict[str, Any]:
        described = super().describe()
        described.update(
            {
                "port": self._port,
                "baudrate": self._baudrate,
                "timeout_s": self._timeout_s,
                "open": self._serial is not None,
                "pyserial_available": self.available(),
                "safety_bindings": sorted(self._safety),
            }
        )
        return described


def _interlock_state(value: Any, closed_when: Any) -> str:
    """``closed``/``open``/``unknown``; a boolean ``closed_when`` only matches a boolean."""

    if isinstance(closed_when, bool):
        if not isinstance(value, bool):
            return "unknown"
        return "closed" if value is closed_when else "open"
    if value is None or isinstance(value, bool):
        return "unknown"
    return "closed" if value == closed_when else "open"


def _format_command(template: Any, values: Mapping[str, Any]) -> str:
    if template is None:
        raise make_mhs_error("MHS.CAPABILITY.NOT_BOUND", "serial binding needs a 'command' template",
                             {"retryable": False})
    try:
        return format_command(str(template), values)
    except MappingError as exc:
        raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", str(exc), {"retryable": False}) from exc


def _parse_response(parse: Any, response: str) -> Any:
    if parse is None:
        return {"raw": response.strip()}
    if not isinstance(parse, Mapping):
        return {"raw": response.strip()}
    kind = parse.get("kind", "raw")
    text = response.strip()
    if kind == "raw":
        return {"raw": text}
    if kind in ("float", "int", "str", "bool"):
        spec = {key: parse[key] for key in ("kind", "pattern", "group", "true", "false") if key in parse}
        return {str(parse.get("field", "value")): parse_text(text, spec)}
    if kind == "regex":
        pattern = str(parse.get("pattern", ""))
        match = re.search(pattern, text)
        if not match:
            raise MappingError(f"serial response {text!r} does not match {pattern!r}")
        groups = match.groupdict()
        if groups:
            return {key: _coerce(value) for key, value in groups.items()}
        return {"match": match.group(0)}
    if kind == "lines":
        return {"lines": [line for line in text.splitlines() if line]}
    raise MappingError(f"unknown serial response parser {kind!r}")


def _coerce(value: str) -> Any:
    for caster in (int, float):
        try:
            return caster(value)
        except (TypeError, ValueError):
            continue
    return value


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
