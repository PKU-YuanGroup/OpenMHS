"""SCPI bridge family: stdlib TCP sockets, optional pyvisa, transcript fakes.

``ScpiBridge`` drives an instrument that speaks line-oriented SCPI (or any
query/write text protocol) from a command map, so a per-instrument driver is
configuration, not code::

    {
      "host": "192.168.1.20", "port": 5025, "terminator": "\\n", "timeout_s": 2.0,
      "idn": {"expect": "^Stanford_Research_Systems,SR860"},     # *IDN? probe on connect
      "error_query": "SYST:ERR?",                                 # optional, after writes
      "commands": {
        "x-cap.srs.frequency.v1": {"resource": "lockin", "query": "FREQ?",
                                   "parse": {"kind": "float"},
                                   "result": {"map": {"frequency": "output.$"}}},
        "x-cap.srs.set_frequency.v1": {"resource": "lockin", "write": "FREQ {value:g}",
                                       "args": {"value": {"from": "input.frequency", "type": "number"}}}
      },
      "reads": {"lockin": {"fields": {"frequency": {"query": "FREQ?", "parse": {"kind": "float"}}}}},
      "writes": {"lockin": {"params": {"frequency": {"write": "FREQ {value:g}", "type": "number"}}}},
      "safety_bindings": {"estop": {"write": "OUTP OFF"}, "safe_state": {"write": ["OUTP OFF", "SLVL 0"]}}
    }

Transports (``write/read/query(line, timeout_s=)``): :class:`SocketTransport`
(stdlib ``socket``; raw SCPI on port 5025), :class:`VisaTransport` (``pyvisa``
imported lazily; ``visa_resource`` plus an optional ``visa_backend`` such as
``"@sim"`` for pyvisa-sim) or any object passed as ``transport=`` -- typically
:meth:`mhs.bridge.transcript.Transcript.line_transport` in tests.

Command templates are ``str.format`` strings with plain named fields; a string
argument containing ``;``, a line break or a control character is refused
(``MHS.CAPABILITY.INPUT_INVALID``), so an input can never inject a command.  A
query whose response does not arrive in time is an unknown outcome (not
retryable).  The e-stop and safe-state commands are written without waiting
for a running query (only the bridge's short wire lock, held while one request
line is written); a command that is not on the wire yet when the e-stop fires
-- queued on the transaction lock or already past it -- is refused with
``MHS.SAFETY.ESTOP_ENGAGED`` and never sent: the e-stop epoch is re-checked
under the wire lock, so no actuating request follows the e-stop command.  (A
write that was already on the wire still sends its ``*OPC?`` and
``error_query`` follow-up queries; neither actuates.)  A query is therefore
written (under the wire lock) and read (outside it) as two steps when the
transport has ``read``.  A boolean ``closed_when`` (default ``true``;
``false`` for an inverted query such as ``DOOR:OPEN?``) needs
``parse: {"kind": "bool"}``, and a ``bool`` parse needs a boolean
``closed_when``; the ``bool`` parse is strict, so an error reply reads
``unknown``, never closed.  An interlock's ``int``, ``float`` or ``regex``
parse must match the whole reply, so ``'0,"No error"'`` or ``'ERR 0'`` reads
``unknown`` even where ``closed_when`` is 0.
"""

from __future__ import annotations

import importlib
import re
import socket
import threading
import time
from typing import Any, Mapping, Sequence

from mhs import signals
from mhs.bridge.base import (
    Bridge,
    BridgeContext,
    ErrorMap,
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
from mhs.bridge.bindings import command_template_errors, parse_spec_errors
from mhs.errors import MHSError

__all__ = ["ScpiBridge", "SocketTransport", "VisaTransport", "main"]

CONFIGURE_CAPABILITY = "cap.device.configure.v1"
_SEPARATORS = ";"

_CONFIG_KEYS = {
    "host", "port", "terminator", "timeout_s", "encoding", "visa_resource", "visa_backend", "idn",
    "error_query", "error_ok", "commands", "reads", "writes", "safety_bindings", "resources",
    "description", "metadata", "strict",
}
_COMMAND_KEYS = {"resource", "query", "write", "args", "parse", "result", "opc", "timeout_ms", "description",
                 "errors", "check_errors", "native"}
_PARAM_KEYS = {"write", "opc", "type", "unit", "units", "clamp", "enum_map", "map", "description"}
_FIELD_KEYS = {"query", "parse", "description"}
_SAFETY_KEYS = {"estop", "reset", "safe_state", "interlocks"}
_SAFETY_COMMAND_KEYS = {"write", "description"}
_INTERLOCK_KEYS = {"id", "query", "parse", "closed_when", "timeout_ms", "description"}


def _manifest_invalid(message: str, errors: Sequence[str] = ()) -> Exception:
    return make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID", message,
                          {"retryable": False, "details": {"errors": list(errors) or [message]}})


class SocketTransport:
    """Raw line-oriented TCP transport (stdlib ``socket``), e.g. SCPI on port 5025.

    Reads are bounded by ``timeout_s`` (``TimeoutError`` on expiry) and
    performed in short slices so :meth:`interrupt` (the e-stop) can end a
    pending read promptly.  The interrupt is cleared when a request begins
    (:meth:`begin_query`), not when its read starts, so an e-stop that lands
    between a query's write and its read still ends that read.  After a
    timeout the receive buffer is discarded on the next request so a late
    response cannot be mistaken for a new one.
    """

    def __init__(self, host: str, port: int, *, terminator: str = "\n", timeout_s: float = 2.0,
                 encoding: str = "ascii"):
        self.host = str(host)
        self.port = int(port)
        self.terminator = terminator
        self.timeout_s = float(timeout_s)
        self.encoding = encoding
        self._sock: socket.socket | None = None
        self._buffer = bytearray()
        self._send_lock = threading.Lock()
        self._interrupt = threading.Event()
        self._dirty = False

    def _connect(self) -> socket.socket:
        if self._sock is None:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
            sock.settimeout(0.05)
            self._sock = sock
        return self._sock

    def _discard_stale(self, sock: socket.socket) -> None:
        if not self._dirty:
            return
        self._buffer.clear()
        sock.settimeout(0.0)
        try:
            while sock.recv(65536):
                pass
        except (BlockingIOError, InterruptedError, OSError):
            pass
        finally:
            sock.settimeout(0.05)
        self._dirty = False

    def write(self, line: str, *, timeout_s: float | None = None) -> None:
        sock = self._connect()
        payload = (line + self.terminator).encode(self.encoding)
        with self._send_lock:
            sock.settimeout(timeout_s or self.timeout_s)
            try:
                sock.sendall(payload)
            finally:
                sock.settimeout(0.05)

    def read(self, *, timeout_s: float | None = None) -> str:
        sock = self._connect()
        deadline = time.monotonic() + float(timeout_s or self.timeout_s)
        marker = self.terminator.encode(self.encoding)
        while marker not in self._buffer:
            if self._interrupt.is_set():
                self._dirty = True
                raise InterruptedError("the read was interrupted (e-stop)")
            if time.monotonic() >= deadline:
                self._dirty = True
                raise TimeoutError(f"no response from {self.host}:{self.port} within {timeout_s or self.timeout_s} s")
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                self.close()
                raise ConnectionError(f"{self.host}:{self.port} closed the connection")
            self._buffer.extend(chunk)
        index = self._buffer.find(marker)
        line = bytes(self._buffer[:index]).decode(self.encoding, "replace")
        del self._buffer[: index + len(marker)]
        return line.rstrip("\r")

    def begin_query(self) -> None:
        """Start a request: forget earlier interrupts and discard a stale response (after a timeout)."""

        self._interrupt.clear()
        self._discard_stale(self._connect())

    def query(self, line: str, *, timeout_s: float | None = None) -> str:
        self.begin_query()
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def interrupt(self) -> None:
        self._interrupt.set()

    def close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:  # pragma: no cover - defensive
                pass

    def describe(self) -> dict[str, Any]:
        return {"kind": "socket", "host": self.host, "port": self.port}


class VisaTransport:
    """A pyvisa resource (``pyvisa`` is imported lazily; ``backend='@sim'`` for pyvisa-sim)."""

    def __init__(self, resource: str, *, backend: str | None = None, terminator: str = "\n",
                 timeout_s: float = 2.0):
        try:
            pyvisa = importlib.import_module("pyvisa")
        except ImportError as exc:
            raise make_mhs_error(
                "MHS.DEVICE.NOT_READY", "pyvisa is not installed; use host/port (stdlib socket) instead",
                {"retryable": False, "remediation": "pip install pyvisa (and pyvisa-sim for the simulator)"},
            ) from exc
        self._pyvisa = pyvisa
        manager = pyvisa.ResourceManager(backend) if backend else pyvisa.ResourceManager()
        self._resource = manager.open_resource(resource)
        self._resource.read_termination = terminator
        self._resource.write_termination = terminator
        self._resource.timeout = int(float(timeout_s) * 1000)
        self.name = resource
        self._send_lock = threading.Lock()

    def _timeout_error(self, exc: Exception) -> bool:
        errors = getattr(self._pyvisa, "errors", None)
        visa_error = getattr(errors, "VisaIOError", None) if errors is not None else None
        return visa_error is not None and isinstance(exc, visa_error) and "TMO" in str(getattr(exc, "abbreviation", exc))

    def _bounded(self, timeout_s: float | None) -> None:
        if timeout_s:
            self._resource.timeout = max(1, int(float(timeout_s) * 1000))

    def write(self, line: str, *, timeout_s: float | None = None) -> None:
        with self._send_lock:
            self._bounded(timeout_s)
            self._resource.write(line)

    def read(self, *, timeout_s: float | None = None) -> str:
        self._bounded(timeout_s)
        try:
            return str(self._resource.read()).rstrip("\r\n")
        except Exception as exc:  # noqa: BLE001
            if self._timeout_error(exc):
                raise TimeoutError(str(exc)) from exc
            raise

    def query(self, line: str, *, timeout_s: float | None = None) -> str:
        self._bounded(timeout_s)
        try:
            return str(self._resource.query(line)).rstrip("\r\n")
        except Exception as exc:  # noqa: BLE001
            if self._timeout_error(exc):
                raise TimeoutError(str(exc)) from exc
            raise

    def interrupt(self) -> None:
        """pyvisa reads are bounded by the resource timeout; nothing to interrupt."""

    def close(self) -> None:
        try:
            self._resource.close()
        except Exception:  # noqa: BLE001 - best effort
            pass

    def describe(self) -> dict[str, Any]:
        return {"kind": "visa", "resource": self.name}


class _InstrumentError(Exception):
    """An entry of the instrument's error queue (``SYST:ERR?``)."""


class ScpiBridge(Bridge):
    """Bridge a SCPI instrument from a declarative command map."""

    bridge_kind = "scpi"
    bridge_id = "mhs.bridge.scpi"

    def __init__(self, config: Mapping[str, Any], *, device_id: str | None = None, transport: Any = None,
                 strict: bool | None = None):
        super().__init__(device_id=device_id)
        if not isinstance(config, Mapping):
            raise _manifest_invalid("scpi bridge config must be an object")
        unknown = set(config) - _CONFIG_KEYS
        if unknown:
            raise _manifest_invalid(f"unknown scpi bridge config keys: {sorted(unknown)}")
        self.config = dict(config)
        self.strict = bool(self.config.get("strict", False)) if strict is None else bool(strict)
        self._timeout_s = float(self.config.get("timeout_s", 2.0))
        if self._timeout_s <= 0:
            raise _manifest_invalid("timeout_s must be positive (bounded blocking)")
        self._terminator = str(self.config.get("terminator", "\n"))
        self._encoding = str(self.config.get("encoding", "ascii"))
        if transport is None and not self.config.get("visa_resource") and not self.config.get("host"):
            raise _manifest_invalid("scpi bridge needs host/port, visa_resource or an injected transport")
        self.bridge_id = "mhs.bridge.scpi:" + str(
            self.config.get("visa_resource") or f"{self.config.get('host', 'transport')}:{self.config.get('port', 5025)}"
        )
        self._idn = self._compile_idn(self.config.get("idn", True))
        self._error_query = self.config.get("error_query")
        if self._error_query is not None and (not isinstance(self._error_query, str) or not self._error_query):
            raise _manifest_invalid("error_query must be a query string such as 'SYST:ERR?'")
        self._error_ok = re.compile(str(self.config.get("error_ok", r"^\s*\+?0\b")))
        self._commands = self._compile_commands(self.config.get("commands"))
        self._reads = self._compile_reads(self.config.get("reads"))
        self._writes = self._compile_writes(self.config.get("writes"))
        self._safety = self._compile_safety(self.config.get("safety_bindings"))
        self._transport = transport
        self._connected = False
        self.idn: str | None = None
        self._txn_lock = threading.RLock()
        #: Held only while one request line is written; the e-stop shares the wire through it.
        self._wire_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._safe_state_achieved = False

    # -- compilation -------------------------------------------------------
    @staticmethod
    def _compile_idn(raw: Any) -> dict[str, Any] | None:
        if raw is False or raw is None:
            return None
        if raw is True:
            return {"command": "*IDN?", "expect": None}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("idn must be true, false or {command, expect}")
        unknown = set(raw) - {"command", "expect", "probe"}
        if unknown:
            raise _manifest_invalid(f"unknown idn keys: {sorted(unknown)}")
        if raw.get("probe") is False:
            return None
        expect = raw.get("expect")
        try:
            compiled = re.compile(expect) if expect else None
        except re.error as exc:
            raise _manifest_invalid(f"idn.expect is not a regex: {exc}") from exc
        return {"command": str(raw.get("command", "*IDN?")), "expect": compiled}

    def _compile_commands(self, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("commands must be an object keyed by capability id")
        compiled: dict[str, dict[str, Any]] = {}
        for capability_id, spec in raw.items():
            label = f"commands[{capability_id!r}]"
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"{label} must be an object")
            unknown = set(spec) - _COMMAND_KEYS
            if unknown:
                raise _manifest_invalid(f"unknown keys in {label}: {sorted(unknown)}")
            forms = [key for key in ("query", "write") if key in spec]
            if len(forms) != 1:
                raise _manifest_invalid(f"{label} needs exactly one of 'query' or 'write'")
            form = forms[0]
            try:
                args = FieldMapping(spec.get("args"), direction="input")
            except (MappingError, UnitError) as exc:
                raise _manifest_invalid(f"{label}.args is invalid: {exc}") from exc
            problems = command_template_errors(spec[form], [rule.target for rule in args.rules], f"{label}.{form}")
            if spec.get("parse") is not None:
                if form != "query":
                    problems.append(f"{label}.parse needs a 'query'")
                problems.extend(parse_spec_errors(spec["parse"], f"{label}.parse"))
            if problems:
                raise _manifest_invalid(f"{label} is invalid", problems)
            result_spec = spec.get("result")
            if isinstance(result_spec, Mapping) and result_spec.get("map") == {}:
                result_spec = None
            if result_spec is None and form == "query":
                result_spec = {"map": {"value": "output.$"}}
            try:
                result = FieldMapping(result_spec, direction="output", required_by_default=True) \
                    if result_spec is not None else None
                errors = ErrorMap(spec.get("errors"), strict=self.strict) if spec.get("errors") is not None else None
            except (MappingError, UnitError) as exc:
                raise _manifest_invalid(f"{label} is invalid: {exc}") from exc
            timeout_ms = spec.get("timeout_ms")
            if timeout_ms is not None and (isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int)
                                           or timeout_ms <= 0):
                raise _manifest_invalid(f"{label}.timeout_ms must be a positive integer")
            compiled[str(capability_id)] = {
                "resource": str(spec.get("resource") or "instrument"),
                "form": form,
                "template": str(spec[form]),
                "args": args,
                "parse": dict(spec.get("parse") or {"kind": "str"}),
                "result": result,
                "opc": bool(spec.get("opc", False)),
                "timeout_s": (timeout_ms / 1000.0) if timeout_ms else self._timeout_s,
                "errors": errors,
                "check_errors": bool(spec.get("check_errors", form == "write")),
                "description": spec.get("description", ""),
            }
        return compiled

    def _compile_reads(self, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("reads must be an object keyed by resource id")
        compiled: dict[str, dict[str, Any]] = {}
        for resource_id, spec in raw.items():
            label = f"reads[{resource_id!r}]"
            if not isinstance(spec, Mapping) or not isinstance(spec.get("fields"), Mapping):
                raise _manifest_invalid(f"{label} needs 'fields': {{name: {{query, parse}}}}")
            fields: dict[str, dict[str, Any]] = {}
            for name, field_spec in spec["fields"].items():
                flabel = f"{label}.fields[{name!r}]"
                if not isinstance(field_spec, Mapping):
                    raise _manifest_invalid(f"{flabel} must be an object")
                unknown = set(field_spec) - _FIELD_KEYS
                if unknown:
                    raise _manifest_invalid(f"unknown keys in {flabel}: {sorted(unknown)}")
                problems = command_template_errors(field_spec.get("query"), [], f"{flabel}.query")
                problems += parse_spec_errors(field_spec.get("parse", {"kind": "str"}), f"{flabel}.parse")
                if problems:
                    raise _manifest_invalid(f"{flabel} is invalid", problems)
                fields[str(name)] = {"query": field_spec["query"], "parse": dict(field_spec.get("parse") or {"kind": "str"})}
            compiled[str(resource_id)] = {"fields": fields}
        return compiled

    def _compile_writes(self, raw: Any) -> dict[str, dict[str, Any]]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise _manifest_invalid("writes must be an object keyed by resource id")
        compiled: dict[str, dict[str, Any]] = {}
        for resource_id, spec in raw.items():
            label = f"writes[{resource_id!r}]"
            if not isinstance(spec, Mapping) or not isinstance(spec.get("params"), Mapping) or not spec["params"]:
                raise _manifest_invalid(f"{label} needs 'params': {{name: {{write: 'CMD {{value}}'}}}}")
            params: dict[str, dict[str, Any]] = {}
            for name, param in spec["params"].items():
                plabel = f"{label}.params[{name!r}]"
                if not isinstance(param, Mapping):
                    raise _manifest_invalid(f"{plabel} must be an object")
                unknown = set(param) - _PARAM_KEYS
                if unknown:
                    raise _manifest_invalid(f"unknown keys in {plabel}: {sorted(unknown)}")
                problems = command_template_errors(param.get("write"), ["value"], f"{plabel}.write")
                if problems:
                    raise _manifest_invalid(f"{plabel} is invalid", problems)
                rule_spec = {"from": "$", **{key: param[key] for key in
                                             ("type", "unit", "units", "clamp", "enum_map", "map") if key in param}}
                try:
                    rule = _Rule("value", rule_spec, direction="input")
                except (MappingError, UnitError) as exc:
                    raise _manifest_invalid(f"{plabel} is invalid: {exc}") from exc
                params[str(name)] = {"write": str(param["write"]), "rule": rule, "opc": bool(param.get("opc", False))}
            compiled[str(resource_id)] = {"params": params}
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
                spec = {"write": spec}
            if not isinstance(spec, Mapping):
                raise _manifest_invalid(f"safety_bindings.{name} must be an object")
            unknown = set(spec) - _SAFETY_COMMAND_KEYS
            if unknown:
                raise _manifest_invalid(f"unknown keys in safety_bindings.{name}: {sorted(unknown)}")
            commands = spec.get("write")
            commands = [commands] if isinstance(commands, str) else commands
            if not isinstance(commands, (list, tuple)) or not commands:
                raise _manifest_invalid(f"safety_bindings.{name}.write must be a command or a list of commands")
            problems = []
            for command in commands:
                problems += command_template_errors(command, [], f"safety_bindings.{name}.write")
            if problems:
                raise _manifest_invalid(f"safety_bindings.{name} is invalid", problems)
            compiled[name] = {"commands": [str(command) for command in commands],
                              "description": spec.get("description")}
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
                problems = command_template_errors(spec.get("query"), [], f"{label}.query")
                problems += parse_spec_errors(spec.get("parse", {"kind": "str"}), f"{label}.parse")
                parse_kind = (spec.get("parse") or {"kind": "str"}).get("kind") \
                    if isinstance(spec.get("parse") or {"kind": "str"}, Mapping) else None
                closed_when = spec.get("closed_when", True)
                if isinstance(closed_when, bool) and parse_kind != "bool":
                    problems.append(
                        f"{label}: closed_when {str(closed_when).lower()} only matches a boolean, so a "
                        f"{parse_kind!r} response could never read closed; use parse kind 'bool' or "
                        "declare closed_when as the whole reply's value (e.g. 1 or 'CLOSED')"
                    )
                if parse_kind == "bool" and not isinstance(closed_when, bool):
                    problems.append(
                        f"{label}: a 'bool' parse reads true or false, so closed_when must be true or "
                        f"false (not {closed_when!r})"
                    )
                if problems:
                    raise _manifest_invalid(f"{label} is invalid", problems)
                items.append({"id": spec["id"], "query": str(spec["query"]),
                              "parse": dict(spec.get("parse") or {"kind": "str"}),
                              "closed_when": spec.get("closed_when", True),
                              "timeout_s": float(spec.get("timeout_ms", 500)) / 1000.0,
                              "description": str(spec.get("description") or spec["id"])})
            compiled["interlocks"] = items
        return compiled

    # -- connection --------------------------------------------------------
    @staticmethod
    def available() -> bool:
        return True   # the socket transport is stdlib; pyvisa is optional

    def _ensure_connected(self) -> Any:
        self.ensure_open()
        if self._connected:
            return self._transport
        with self._connect_lock:
            if self._connected:
                return self._transport
            if self._transport is None:
                try:
                    if self.config.get("visa_resource"):
                        self._transport = VisaTransport(
                            str(self.config["visa_resource"]), backend=self.config.get("visa_backend"),
                            terminator=self._terminator, timeout_s=self._timeout_s)
                    else:
                        self._transport = SocketTransport(
                            str(self.config["host"]), int(self.config.get("port", 5025)),
                            terminator=self._terminator, timeout_s=self._timeout_s, encoding=self._encoding)
                except Exception as exc:  # noqa: BLE001
                    if getattr(exc, "code", None):
                        raise
                    raise make_mhs_error("MHS.DEVICE.NOT_READY",
                                         f"cannot open the SCPI transport ({type(exc).__name__})",
                                         {"retryable": True}) from exc
            if self._idn is not None:
                with self._txn_lock:
                    try:
                        identity = self._transport.query(self._idn["command"], timeout_s=self._timeout_s)
                    except Exception as exc:  # noqa: BLE001
                        if _is_divergence(exc):
                            raise
                        raise make_mhs_error("MHS.DEVICE.NOT_READY",
                                             f"the instrument did not answer {self._idn['command']} "
                                             f"({type(exc).__name__})", {"retryable": True}) from exc
                expect = self._idn["expect"]
                if expect is not None and not expect.search(identity):
                    raise make_mhs_error(
                        "MHS.DEVICE.NOT_READY",
                        f"the instrument identifies as {identity[:120]!r}, which does not match the configured identity",
                        {"retryable": False, "details": {"idn": identity[:200], "expect": expect.pattern}},
                    )
                self.idn = identity.strip()
            self._connected = True
            return self._transport

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._transport is not None:
                self._transport.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._connected = False
            super().close()

    # -- adapter surface ---------------------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        entries = [
            {
                "capability_id": capability_id,
                "resource": spec["resource"],
                "native": spec["template"],
                "invoke": spec["form"],
                "description": spec["description"] or f"SCPI {spec['form']} {spec['template']}",
                "exclusive": spec["form"] == "write",
            }
            for capability_id, spec in self._commands.items()
        ]
        if CONFIGURE_CAPABILITY not in self._commands:
            for resource_id, spec in self._writes.items():
                entries.append({"capability_id": CONFIGURE_CAPABILITY, "resource": resource_id,
                                "native": ", ".join(param["write"] for param in spec["params"].values()),
                                "invoke": "write", "description": "Write the instrument's settable parameters.",
                                "exclusive": True})
        return entries

    def resources(self) -> list[dict[str, Any]]:
        declared = self.config.get("resources")
        if isinstance(declared, list):
            return [dict(item) for item in declared]
        ids = {spec["resource"] for spec in self._commands.values()} | set(self._reads) | set(self._writes)
        return [{"resource_id": rid} for rid in sorted(ids or {"instrument"})]

    # -- operations --------------------------------------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        context = BridgeContext.coerce(ctx)
        spec = self._commands.get(str(capability_id))
        if spec is None:
            if str(capability_id) == CONFIGURE_CAPABILITY and self._writes:
                resource = context.resource if context.resource in self._writes else None
                if resource is None and len(self._writes) == 1:
                    resource = next(iter(self._writes))
                if resource is None:
                    raise unsupported(capability_id)
                return self.write(resource, dict(args or {}), context)
            raise unsupported(capability_id)
        if context.cancelled():
            raise signals.Cancelled("cancelled before the SCPI exchange")
        epoch = self.estop_epoch   # taken before waiting for the transaction lock
        try:
            mapped = spec["args"].map(dict(args or {}))
        except (MappingError, UnitError, TypeError, ValueError) as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"cannot map input for {capability_id!r}: {exc}",
                                 {"retryable": False}) from exc
        line = self._format(spec["template"], mapped)
        timeout_s = min(spec["timeout_s"], max(0.001, context.remaining_ms() / 1000.0))
        response = self._exchange(spec["form"], line, timeout_s, opc=spec["opc"],
                                  check_errors=spec["check_errors"], errors=spec["errors"], epoch=epoch)
        if spec["form"] == "write" and spec["result"] is None:
            return {}
        try:
            value = parse_text(response, spec["parse"]) if spec["form"] == "query" else None
            output = spec["result"].map(value) if spec["result"] is not None else {}
            return jsonable(output)
        except (MappingError, UnitError) as exc:
            raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID",
                                f"cannot parse the response to {line!r}: {exc}") from exc

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        spec = self._reads.get(str(resource_id))
        if spec is None:
            raise unsupported(resource_id, kind="resource")
        context = BridgeContext.coerce(ctx)
        wanted = list(fields) if fields else list(spec["fields"])
        state: dict[str, Any] = {}
        for name in wanted:
            field_spec = spec["fields"].get(name)
            if field_spec is None:
                continue
            timeout_s = min(self._timeout_s, max(0.001, context.remaining_ms() / 1000.0))
            response = self._exchange("query", field_spec["query"], timeout_s)
            try:
                state[name] = parse_text(response, field_spec["parse"])
            except MappingError as exc:
                raise make_mhs_error("MHS.RESOURCE.STATE_INVALID",
                                     f"cannot parse {field_spec['query']!r}: {exc}", {"retryable": False}) from exc
        return jsonable(state)

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        spec = self._writes.get(str(resource_id))
        if spec is None:
            raise unsupported(resource_id, kind="resource")
        if not isinstance(patch, Mapping) or not patch:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "a write needs a non-empty parameter patch",
                                 {"retryable": False})
        params = spec["params"]
        stray = sorted(str(key) for key in patch if key not in params)
        if stray:
            raise make_mhs_error("MHS.RESOURCE.NOT_WRITABLE", f"parameters {stray} of {resource_id!r} are not writable",
                                 {"retryable": False, "details": {"parameters": stray, "writable": sorted(params)}})
        context = BridgeContext.coerce(ctx)
        epoch = self.estop_epoch   # taken before waiting for the transaction lock
        lines = []
        for name, value in patch.items():
            try:
                native_value = params[name]["rule"].apply(value)
            except (MappingError, UnitError, TypeError, ValueError) as exc:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"cannot map parameter {name!r}: {exc}",
                                     {"retryable": False}) from exc
            lines.append((name, value, self._format(params[name]["write"], {"value": native_value}),
                          params[name]["opc"]))
        applied: dict[str, Any] = {}
        for name, value, line, opc in lines:
            timeout_s = min(self._timeout_s, max(0.001, context.remaining_ms() / 1000.0))
            try:
                self._exchange("write", line, timeout_s, opc=opc, check_errors=True, epoch=epoch)
            except MHSError as exc:
                if applied and exc.code == "MHS.SAFETY.ESTOP_ENGAGED":
                    exc.data.setdefault("details", {})["applied"] = dict(applied)
                raise
            applied[name] = jsonable(value)
        return {"applied": applied}

    def _format(self, template: str, values: Mapping[str, Any]) -> str:
        try:
            return format_command(template, values, separators=_SEPARATORS)
        except MappingError as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", str(exc), {"retryable": False}) from exc

    def _put_request(self, transport: Any, line: str, timeout_s: float, epoch: int | None, *,
                     query: bool = False) -> None:
        """Write one request line under the wire lock, re-checking the e-stop epoch there.

        :meth:`estop` advances the epoch before it takes the wire lock, so a
        line written here either precedes the e-stop command or is refused.
        """

        with self._wire_lock:
            if epoch is not None:
                self._refuse_if_estopped(epoch, f"SCPI command {line!r}")
            try:
                begin = getattr(transport, "begin_query", None) if query else None
                if callable(begin):
                    begin()
                transport.write(line, timeout_s=timeout_s)
            except Exception as exc:  # noqa: BLE001
                self._transport_failed(exc, line, timeout_s)

    def _transport_failed(self, exc: BaseException, line: str, timeout_s: float) -> None:
        """Raise the outcome of a transport failure during ``line`` (always raises)."""

        if _is_divergence(exc):
            raise exc
        if isinstance(exc, (TimeoutError, InterruptedError, socket.timeout)):
            raise outcome_unknown(
                f"no response to {line!r} within {timeout_s:.3g} s ({type(exc).__name__}); "
                "the command was sent, its effect is unknown",
                details={"command": line},
            ) from exc
        self._connected = False   # reconnect (and re-probe) on the next exchange
        raise outcome_unknown(
            f"the SCPI transport failed during {line!r} ({type(exc).__name__}); its effect is unknown",
            details={"command": line},
        ) from exc

    def _exchange(self, form: str, line: str, timeout_s: float, *, opc: bool = False, check_errors: bool = False,
                  errors: ErrorMap | None = None, epoch: int | None = None) -> str | None:
        """One query/write under the transaction lock (``epoch``: see :meth:`Bridge._refuse_if_estopped`)."""

        if epoch is not None:
            self._refuse_if_estopped(epoch, f"SCPI command {line!r}")
        transport = self._ensure_connected()
        response: str | None = None
        with self._txn_lock:
            if epoch is not None:
                self._refuse_if_estopped(epoch, f"SCPI command {line!r}")
            split_query = form == "query" and callable(getattr(transport, "read", None))
            if form == "write" or split_query:
                self._put_request(transport, line, timeout_s, epoch, query=split_query)
            try:
                if form == "query":
                    if split_query:
                        response = transport.read(timeout_s=timeout_s)
                    else:   # a query-only transport: the whole exchange under the wire lock
                        with self._wire_lock:
                            if epoch is not None:
                                self._refuse_if_estopped(epoch, f"SCPI command {line!r}")
                            response = transport.query(line, timeout_s=timeout_s)
                else:
                    if opc:
                        done = transport.query("*OPC?", timeout_s=timeout_s)
                        if parse_text(done, {"kind": "int"}) != 1:
                            raise _InstrumentError(f"*OPC? returned {done!r}")
                error_text = None
                if self._error_query and check_errors:
                    error_text = transport.query(self._error_query, timeout_s=timeout_s)
            except _InstrumentError as exc:
                raise driver_failed("MHS.DEVICE.FAULTED", str(exc), details={"command": line}) from exc
            except MHSError as exc:
                if exc.code == "MHS.SAFETY.ESTOP_ENGAGED":
                    raise
                self._transport_failed(exc, line, timeout_s)
            except Exception as exc:  # noqa: BLE001
                self._transport_failed(exc, line, timeout_s)
        if error_text is not None and not self._error_ok.search(error_text):
            instrument_error = _InstrumentError(error_text.strip())
            code = "MHS.DEVICE.FAULTED"
            retryable = False
            if errors is not None:
                mapped, _message, retryable = errors.translate_exception(instrument_error)
                if mapped != "MHS.ADAPTER.SHIM_FAILED":
                    code = mapped
            raise driver_failed(code, f"the instrument reported {error_text.strip()[:200]!r} after {line!r}",
                                details={"command": line, "instrument_error": error_text.strip()[:200]},
                                retryable=retryable, native_code=error_text.strip()[:64])
        return response

    # -- safety bindings ---------------------------------------------------
    @property
    def estop_native(self) -> str | None:
        spec = self._safety.get("estop")
        return spec["commands"][0] if spec else None

    def _write_safety(self, name: str) -> list[str]:
        spec = self._safety.get(name)
        if spec is None:
            return []
        # an open transport is used as is: no identity re-probe, never the transaction lock
        transport = self._transport if self._transport is not None else self._ensure_connected()
        interrupt = getattr(transport, "interrupt", None)
        if callable(interrupt):
            interrupt()   # a pending query stops waiting
        written = []
        for command in spec["commands"]:
            with self._wire_lock:   # never the transaction lock: a running query may hold it
                transport.write(command, timeout_s=self._timeout_s)
            written.append(command)
        return written

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        self._engage_estop()   # commands queued on the transaction lock are refused from now on
        if "estop" not in self._safety and "safe_state" not in self._safety:
            return {}
        performed: list[str] = []
        failed: list[dict[str, str]] = []
        for name in ("estop", "safe_state"):
            try:
                performed.extend(self._write_safety(name))
            except Exception as exc:  # noqa: BLE001
                if _is_divergence(exc):
                    raise
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
        states = []
        for item in self._safety.get("interlocks") or []:
            state = "unknown"
            try:
                if self._txn_lock.acquire(timeout=item["timeout_s"]):
                    try:
                        response = self._exchange("query", item["query"], item["timeout_s"])
                        state = _interlock_state(parse_text(response, item["parse"], whole=True),
                                                 item["closed_when"])
                    finally:
                        self._txn_lock.release()
            except Exception:  # noqa: BLE001 - fail closed
                state = "unknown"
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
            raise make_mhs_error("MHS.SAFETY.INTERLOCK_OPEN",
                                 "reset refused: interlock not closed: " + ", ".join(item["id"] for item in blocked),
                                 {"retryable": False, "interlocks": blocked})
        spec = self._safety.get("reset")
        self._safe_state_achieved = False
        if spec is None:
            return {}
        for command in spec["commands"]:
            self._exchange("write", command, self._timeout_s)
        return {"reset": True, "native": spec["commands"][0]}

    def describe(self) -> dict[str, Any]:
        described = super().describe()
        transport = self._transport
        described.update({
            "idn": self.idn,
            "transport": transport.describe() if hasattr(transport, "describe") else type(transport).__name__,
            "safety_bindings": sorted(self._safety),
        })
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


def _is_divergence(exc: BaseException) -> bool:
    return type(exc).__name__ == "TranscriptDivergence"


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
