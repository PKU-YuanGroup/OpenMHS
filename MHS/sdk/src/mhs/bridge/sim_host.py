"""Isolated simulator host (``isolated_process_v1``): a Gymnasium environment that lives in a child process.

Some simulator environments cannot share the endpoint's process: their constructor launches ROS and Gazebo, their
``close`` signals a global ``rospy`` shutdown and calls ``sys.exit``, and a failed service call can end in
``sys.exit`` too.  A source-reviewed backend can therefore declare, per backend, that its environment is built and
driven in a child process this endpoint starts and owns (:class:`ProcessHost`; the child is
:mod:`mhs.bridge.sim_host_child`), and how that environment's simulator is stopped and how the stop is read back::

    process_by_backend = {"sim": {
        "mode": "isolated_process_v1",
        "reset_kwargs": ["seed", "options"],      # the exact keywords the native reset accepts
        "start_timeout_s": 600.0,                  # child start, construction and the space description
        "step_timeout_s": 60.0, "reset_timeout_s": 300.0, "close_timeout_s": 60.0,
        "stop": "gazebo.pause_proxy",              # a public attribute path, called with no argument in the child
        "readback": {"path": "gazebo.get_physics_properties", "field": "pause", "equals": True},
        "stop_timeout_s": 2.0,                     # each stop, read-back and unfence round trip
        "settle_timeout_s": 10.0,                  # a world call in flight at the stop must end within this
        "source_refs": ["src/.../gazebo_connection.py:143", ...],
    }}

The backend's ``backends`` entry (a package-relative ``.module:attribute``) is imported and called in the child, never
in the endpoint.  The declaration is a contract about the backend: the paths, bounds and citation strings configure
the SDK; they prove nothing about the simulator.  What the SDK guarantees:

* Isolation.  The child's standard streams are ``/dev/null``; the protocol uses two private pipes.  A ``SystemExit``,
  ``KeyboardInterrupt`` or global ROS shutdown inside the environment ends a call in the child, never the endpoint;
  ``os._exit`` or a crash ends the child, which the endpoint sees as a dead host.
* Bounded calls.  Every request waits at most its declared bound.  A world call that outlives its bound is never
  cancelled: its outcome is ``unknown``, it stays *owned* (new world calls are refused ``MHS.DEVICE.BUSY``, the safety
  status is unachieved, safety reset is refused) until the child answers; the late answer is recorded, never applied.
* Fail-closed e-stop (:meth:`ProcessHost.stop`, used by :class:`mhs.bridge.gymnasium.GymnasiumBridge`).  The endpoint
  latches first; the host is fenced before the stop request is written (no world call is sent after it, and the
  child refuses one it receives after it); the stop runs in the child; a world call that was in flight is waited for
  and the stop is sent again; then the read-back must return exactly the declared value.  Anything else (a dead,
  broken or unresponsive host, a stop or read-back that raises or times out, another value) is an unreached safe
  state: the latch stays and the endpoint retries.
* Close sends the stop, waits for a world call in flight, closes the environment in the child, closes the request
  pipe and waits for the child to exit, each bounded; a child that does not exit is sent SIGTERM and then its process
  group SIGKILL, and the outcome says so (``unsettled``): processes the environment launched outside that group can
  survive it.

Standard library only; POSIX (descriptor passing, sessions, process-group signals).  ``MHS_SIM_HOST_PYTHON`` (an
absolute path) selects the child's interpreter, for a simulator whose Python is not the endpoint's (ROS Noetic: 3.8);
the default is the endpoint's own interpreter.  A host is closed by its bridge's close or, failing that, at the
endpoint's exit; a host whose endpoint died stops and closes its environment by itself.
"""

from __future__ import annotations

import atexit
import itertools
import json
import math
import os
import re
import select
import signal
import subprocess
import sys
import threading
import time
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

__all__ = ["PROCESS_MODE", "ProcessProfile", "ProcessProfileError", "ProcessHost", "HostError", "HostTimeout",
           "HostBusy", "HostFenced", "HostUnavailable", "HostAfterEffect", "ChildCallError", "PYTHON_ENV"]

PROCESS_MODE = "isolated_process_v1"
PROTOCOL = "mhs-sim-host/1"
#: Selects the child's interpreter (an absolute path); default: the endpoint's own interpreter.
PYTHON_ENV = "MHS_SIM_HOST_PYTHON"
FDS_ENV = "MHS_SIM_HOST_FDS"
GUARD_ENV = "MHS_SIM_HOST_GUARD"
GUARDED_ENV = "MHS_PROCESS_GUARDED"
CHILD_SCRIPT = Path(__file__).with_name("sim_host_child.py")
MAX_LINE = 16 * 1024 * 1024
#: A request (an action, a reset) that cannot be written within this bound means the child does not read.
WRITE_BOUND_S = 2.0
#: After a close bound: SIGTERM, then this long, then SIGKILL of the child's process group, then this long.
KILL_GRACE_S = 2.0
_MAX_LATE = 16
_SEGMENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_ENTRY = re.compile(r"\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*"
                    r"(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_RESET_KWARGS = ("seed", "options")
#: A read-back must read a state, never an acknowledgement of the request: these field names are refused.
ACKNOWLEDGEMENT_FIELDS = frozenset({"success", "status_message", "ok", "ack", "acknowledged", "accepted", "result",
                                    "response", "message", "status"})


class ProcessProfileError(ValueError):
    """An isolated-process declaration violates the profile."""


class HostError(Exception):
    """A simulator host outcome; ``sent`` says whether the request reached the child."""

    sent = False


class HostTimeout(HostError):
    """The child did not answer within the bound; the request stays owned (never cancelled)."""

    def __init__(self, op: str, timeout_s: float, *, sent: bool = True):
        super().__init__(f"the simulator host did not answer {op} within {timeout_s:g} s; it remains owned"
                         if sent else f"the simulator host did not accept {op} within {timeout_s:g} s")
        self.op, self.timeout_s, self.sent = op, timeout_s, sent


class HostBusy(HostError):
    """Earlier work of the same lane is still owned; nothing was sent."""

    def __init__(self, owned: Mapping[str, Any]):
        super().__init__(f"earlier simulator host {owned.get('op')} is still owned "
                         f"({'abandoned after its bound' if owned.get('abandoned') else 'in progress'})")
        self.owned = dict(owned)


class HostFenced(HostError):
    """A stop fenced the host: the world call was not run (nothing reached the environment)."""

    def __init__(self, op: str, where: str = "endpoint"):
        super().__init__(f"{op} was not run: a stop fenced the simulator host ({where} side) until a safety reset")
        self.op, self.where = op, where


class HostUnavailable(HostError):
    """The host is not running (never started, failed to start, exited, broken or closed)."""

    def __init__(self, reason: str, *, sent: bool = False):
        super().__init__(reason)
        self.sent = sent


class HostAfterEffect(HostError):
    """The environment call ran in the child, but its result could not be returned: it took effect, outcome unknown."""

    sent = True


class ChildCallError(HostError):
    """The environment raised in the child (``exit_requested``: a contained SystemExit or KeyboardInterrupt)."""

    sent = True

    def __init__(self, error: Mapping[str, Any]):
        self.error = dict(error)
        self.type_name = str(self.error.get("type") or "Exception")[:80]
        self.exit_requested = self.error.get("exit") is True
        super().__init__(f"{self.type_name}: {str(self.error.get('message') or '')[:300]}")


def _bound(config: Mapping[str, Any], name: str, low: float, high: float) -> float:
    if name not in config:
        raise ProcessProfileError(f"{name} is required")
    value = config[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProcessProfileError(f"{name} must be a number of seconds")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ProcessProfileError(f"{name} must be within {low:g}..{high:g} s")
    return value


def _path(value: Any, name: str) -> str:
    if (not isinstance(value, str) or len(value) > 200
            or not all(_SEGMENT.match(part) for part in value.split("."))):
        raise ProcessProfileError(f"{name} must be a public attribute path such as 'gazebo.pause_proxy'")
    return value


@dataclass(frozen=True)
class ProcessProfile:
    """A resolved ``isolated_process_v1`` declaration (see the module docstring)."""

    reset_kwargs: tuple[str, ...]
    start_timeout_s: float
    step_timeout_s: float
    reset_timeout_s: float
    close_timeout_s: float
    stop: str
    readback_path: str
    readback_field: str | None
    readback_equals: Any
    stop_timeout_s: float
    settle_timeout_s: float
    source_refs: tuple[str, ...] = ()

    @classmethod
    def resolve(cls, config: Mapping[str, Any]) -> "ProcessProfile":
        if not isinstance(config, Mapping):
            raise ProcessProfileError("the isolated-process profile must be a mapping")
        allowed = {"mode", "reset_kwargs", "start_timeout_s", "step_timeout_s", "reset_timeout_s", "close_timeout_s",
                   "stop", "readback", "stop_timeout_s", "settle_timeout_s", "source_refs"}
        unknown = set(config) - allowed
        if unknown:
            raise ProcessProfileError(f"unknown isolated-process profile keys {sorted(map(str, unknown))}")
        if config.get("mode") != PROCESS_MODE:
            raise ProcessProfileError(f"mode must be {PROCESS_MODE!r}")
        kwargs = config.get("reset_kwargs")
        if (not isinstance(kwargs, (list, tuple)) or len(set(kwargs)) != len(kwargs)
                or any(name not in _RESET_KWARGS for name in kwargs)):
            raise ProcessProfileError("reset_kwargs must list the distinct native reset keywords (a subset of "
                                      "['seed', 'options'])")
        stop = _path(config.get("stop"), "stop")
        readback = config.get("readback")
        if not isinstance(readback, Mapping) or set(readback) - {"path", "field", "equals"} \
                or "path" not in readback or "equals" not in readback:
            raise ProcessProfileError("readback must be {'path': ..., 'field': ... (optional), 'equals': ...}: the "
                                      "simulator state that confirms the stop")
        path = _path(readback.get("path"), "readback.path")
        field = readback.get("field")
        if field is not None:
            field = _path(field, "readback.field")
        if path == stop:
            raise ProcessProfileError("readback.path must differ from stop: what a stop call returns acknowledges "
                                      "the request, it does not read the simulator's state")
        last = (field or path).rsplit(".", 1)[-1]
        if last.lower() in ACKNOWLEDGEMENT_FIELDS:
            raise ProcessProfileError(f"readback reads {last!r}, an acknowledgement of the request; it must read a "
                                      "state the simulator's stepping depends on")
        equals = readback.get("equals")
        if isinstance(equals, float) or not isinstance(equals, (bool, int, str)):
            raise ProcessProfileError("readback.equals must be a boolean, an integer or a string (compared exactly)")
        refs = config.get("source_refs", ())
        if not isinstance(refs, (list, tuple)) or len(refs) > 20 or any(
                not isinstance(ref, str) or not ref or len(ref) > 500 for ref in refs):
            raise ProcessProfileError("source_refs must be bounded strings; citations do not validate the backend")
        return cls(
            reset_kwargs=tuple(kwargs),
            start_timeout_s=_bound(config, "start_timeout_s", 0.1, 3600.0),
            step_timeout_s=_bound(config, "step_timeout_s", 0.001, 600.0),
            reset_timeout_s=_bound(config, "reset_timeout_s", 0.001, 3600.0),
            close_timeout_s=_bound(config, "close_timeout_s", 0.001, 600.0),
            stop=stop, readback_path=path, readback_field=field, readback_equals=equals,
            stop_timeout_s=_bound(config, "stop_timeout_s", 0.001, 60.0),
            settle_timeout_s=_bound(config, "settle_timeout_s", 0.0, 600.0),
            source_refs=tuple(refs),
        )

    def confirms(self, value: Any) -> bool:
        """True only for exactly the declared value (``True`` is not ``1``; ``1`` is not ``True``)."""
        expected = self.readback_equals
        return type(value) is type(expected) and value == expected

    @property
    def readback_label(self) -> str:
        return f"{self.readback_path}(){'.' + self.readback_field if self.readback_field else ''}"

    def descriptor(self) -> dict[str, Any]:
        return {"mode": PROCESS_MODE, "reset_kwargs": list(self.reset_kwargs),
                "start_timeout_s": self.start_timeout_s, "step_timeout_s": self.step_timeout_s,
                "reset_timeout_s": self.reset_timeout_s, "close_timeout_s": self.close_timeout_s,
                "stop": self.stop, "readback": {"path": self.readback_path, "field": self.readback_field,
                                                "equals": self.readback_equals},
                "stop_timeout_s": self.stop_timeout_s, "settle_timeout_s": self.settle_timeout_s,
                "source_refs": list(self.source_refs)}

    def notes(self) -> list[str]:
        """Operating notes for the manifest profile (plain sentences, no claim beyond the declaration)."""
        out = [f"Isolated simulator host ({PROCESS_MODE}): the environment is built and driven in a child process "
               f"that this endpoint starts and owns (construction bound {self.start_timeout_s:g} s); an exit, "
               "KeyboardInterrupt or global ROS shutdown inside the environment ends a call in that process, never "
               f"the endpoint. Local bounds step {self.step_timeout_s:g} s, reset {self.reset_timeout_s:g} s, close "
               f"{self.close_timeout_s:g} s. A call that exceeds its bound is not cancelled: its outcome is unknown, "
               "it stays owned, new world calls and safety reset are refused until it settles, and an explicit world "
               "reset is required afterwards.",
               f"E-stop: the endpoint latches and fences the host, then {self.stop} runs in the host (bound "
               f"{self.stop_timeout_s:g} s); a world call in flight must end within {self.settle_timeout_s:g} s and "
               f"the stop is sent again; the stop is confirmed only when {self.readback_label} returns "
               f"{self.readback_equals!r}. A dead or unresponsive host, a failed or late stop or read-back, or another "
               "value is an unreached safe state: the latch stays and the stop is retried.",
               "Close sends the stop, closes the environment in the host and waits for the host to exit; a host that "
               "does not exit is terminated, which can leave processes the environment launched running."]
        if "seed" not in self.reset_kwargs:
            out.append("The native reset accepts no seed: no seed capability is served and no seeded determinism is "
                       "claimed.")
        return out


# -- duck-typed spaces (the bridge dispatches on these class names) --------------------------------------------------
class Box:
    def __init__(self, low: list[float], high: list[float], shape: tuple[int, ...], dtype: str, integer: bool):
        self.low, self.high, self.shape, self.dtype = list(low), list(high), tuple(shape), dtype
        if integer:
            self.mhs_integer_values = True   # integer items: a non-integral value is refused before the host


class Discrete:
    def __init__(self, n: int, start: int):
        self.n, self.start, self.shape = int(n), int(start), ()


class MultiDiscrete:
    def __init__(self, nvec: list[int], start: list[int] | None, shape: tuple[int, ...], dtype: str):
        self.nvec, self.shape, self.dtype = list(nvec), tuple(shape), dtype
        if start is not None:
            self.start = list(start)


class MultiBinary:
    def __init__(self, n: Any, shape: tuple[int, ...]):
        self.n, self.shape = n, tuple(shape)


class Dict:
    def __init__(self, spaces: Mapping[str, Any]):
        self.spaces, self.shape = dict(spaces), ()


class Tuple:
    def __init__(self, spaces: list[Any]):
        self.spaces, self.shape = tuple(spaces), ()


def space_from(doc: Any, depth: int = 0) -> Any:
    """The duck-typed space of a description the child sent (validated; anything else is refused)."""
    if depth > 8 or not isinstance(doc, Mapping):
        raise ValueError("invalid space description")
    kind = doc.get("kind")

    def ints(values: Any) -> list[int]:
        if not isinstance(values, list) or any(isinstance(v, bool) or not isinstance(v, int) for v in values):
            raise ValueError(f"invalid {kind} description")
        return list(values)

    shape = tuple(ints(doc.get("shape", [])))
    if kind == "Box":
        low, high = doc.get("low"), doc.get("high")
        if not isinstance(low, list) or not isinstance(high, list) or len(low) != len(high) or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) for v in low + high):
            raise ValueError("invalid Box description")
        return Box([float(v) for v in low], [float(v) for v in high], shape, str(doc.get("dtype") or ""),
                   doc.get("integer") is True)
    if kind == "Discrete":
        n, start = doc.get("n"), doc.get("start", 0)
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (n, start)) or n < 1:
            raise ValueError("invalid Discrete description")
        return Discrete(n, start)
    if kind == "MultiDiscrete":
        start = doc.get("start")
        return MultiDiscrete(ints(doc.get("nvec")), ints(start) if start is not None else None, shape,
                             str(doc.get("dtype") or ""))
    if kind == "MultiBinary":
        n = doc.get("n")
        return MultiBinary(ints(n) if isinstance(n, list) else ints([n])[0], shape)
    if kind == "Dict":
        pairs = doc.get("spaces")
        if not isinstance(pairs, list) or any(not isinstance(p, list) or len(p) != 2 or not isinstance(p[0], str)
                                              for p in pairs):
            raise ValueError("invalid Dict description")
        return Dict({key: space_from(sub, depth + 1) for key, sub in pairs})
    if kind == "Tuple":
        items = doc.get("spaces")
        if not isinstance(items, list):
            raise ValueError("invalid Tuple description")
        return Tuple([space_from(sub, depth + 1) for sub in items])
    raise ValueError(f"unsupported space kind {kind!r}")


# -- the host -------------------------------------------------------------------------------------------------------
class _Request:
    __slots__ = ("rid", "op", "lane", "started", "done", "result", "error", "abandoned")

    def __init__(self, rid: int, op: str, lane: str):
        self.rid, self.op, self.lane = rid, op, lane
        self.started = time.monotonic()
        self.done = False
        self.result: Any = None
        self.error: BaseException | None = None
        self.abandoned = False

    def describe(self) -> dict[str, Any]:
        return {"op": self.op, "lane": self.lane, "abandoned": self.abandoned,
                "age_s": round(max(0.0, time.monotonic() - self.started), 3)}


_LIVE: "weakref.WeakSet[ProcessHost]" = weakref.WeakSet()


def _gate_guard_file() -> str | None:
    """The gate's process guard module when this process runs under it (its children must apply it too)."""
    guard = sys.modules.get(f"{__package__.rsplit('.', 1)[0]}.driver._repotests") if __package__ else None
    if getattr(guard, "GUARDED", False) is True or os.environ.get(GUARDED_ENV) == "1":
        path = Path(__file__).resolve().parents[1] / "driver" / "_repotests.py"
        return str(path) if path.is_file() else ""
    return None


class ProcessHost:
    """The endpoint side of one isolated simulator host process (see the module docstring).

    ``action_space``, ``observation_space``, ``reset(**kwargs)``, ``step(action)`` and ``close()`` give the
    environment interface the Gymnasium bridge drives; ``stop()``, ``readback()`` and ``unfence()`` are the safety
    path; ``state()``, ``world_owned()``, ``wait_world_idle()`` and ``describe()`` are bookkeeping that never blocks
    on the child (``wait_world_idle`` waits at most its bound).
    """

    #: Members the bridge calls on the host that are not environment members (gate G7 does not look them up upstream).
    HOST_API = frozenset({"start", "stop", "readback", "unfence", "ping", "state", "world_owned", "wait_world_idle",
                          "describe", "profile", "label"})

    def __init__(self, *, package_dir: str | os.PathLike[str], entry: str, options: Mapping[str, Any] | None = None,
                 profile: ProcessProfile | Mapping[str, Any], label: str = "sim-host"):
        if not isinstance(entry, str) or not _ENTRY.fullmatch(entry):
            raise ProcessProfileError(f"the backend entry {entry!r} must be a package-relative '.module:attribute' "
                                      "(it is imported and called in the host process only)")
        directory = Path(package_dir).resolve()
        if not directory.is_dir():
            raise ProcessProfileError(f"{directory} is not a package directory")
        try:
            json.dumps(dict(options or {}), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ProcessProfileError(f"the backend options must be JSON values for the host process ({exc})") from exc
        self.package_dir = str(directory)
        self.entry = entry
        self.options = dict(options or {})
        self.profile = profile if isinstance(profile, ProcessProfile) else ProcessProfile.resolve(profile)
        self.label = str(label)[:80]
        self._cond = threading.Condition()
        self._send_lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._ids = itertools.count(1)
        self._state = "new"            # new, starting, ready, failed, dead, broken, closing, closed
        self._reason: str | None = None
        self._proc: subprocess.Popen | None = None
        self._write_fd: int | None = None
        self._read_fd: int | None = None
        self._reader: threading.Thread | None = None
        self._pending: dict[int, _Request] = {}
        self._lanes: dict[str, _Request | None] = {"world": None, "control": None}
        self._fenced = False
        self._exit_requested: str | None = None
        self._exit_code: int | None = None
        self._spaces: tuple[Any, Any] | None = None
        self._info: dict[str, Any] = {}
        self._close_outcome: str | None = None
        self.late: list[dict[str, Any]] = []

    # -- state ------------------------------------------------------------------------------------------------------
    @property
    def started(self) -> bool:
        with self._cond:
            return self._state != "new"

    def alive(self) -> bool:
        """The child runs and the protocol is intact (non-blocking)."""
        with self._cond:
            proc, state = self._proc, self._state
        return state in ("ready", "closing") and proc is not None and proc.poll() is None

    def world_owned(self) -> dict[str, Any] | None:
        with self._cond:
            request = self._lanes["world"]
            return request.describe() if request is not None else None

    def control_owned(self) -> dict[str, Any] | None:
        with self._cond:
            request = self._lanes["control"]
            return request.describe() if request is not None else None

    def state(self) -> dict[str, Any]:
        """A non-blocking snapshot for safety decisions."""
        with self._cond:
            proc = self._proc
            exited = proc is not None and proc.poll() is not None
            return {"state": "dead" if exited and self._state in ("ready",) else self._state,
                    "reason": self._reason, "fenced": self._fenced,
                    "world": self._lanes["world"].describe() if self._lanes["world"] is not None else None,
                    "control": self._lanes["control"].describe() if self._lanes["control"] is not None else None,
                    "exit_requested": self._exit_requested, "exit_code": self._exit_code if proc is None or not
                    exited else proc.returncode, "close": self._close_outcome}

    def describe(self) -> dict[str, Any]:
        out = self.state()
        out.update({"profile": self.profile.descriptor(), "entry": self.entry,
                    "late": [dict(item) for item in self.late], "pid": self._info.get("pid"),
                    "python": self._info.get("python")})
        return out

    def wait_world_idle(self, timeout_s: float) -> bool:
        """Wait (bounded) until no world call is owned; True when none is."""
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        with self._cond:
            while self._lanes["world"] is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)
            return True

    # -- start ------------------------------------------------------------------------------------------------------
    def start(self) -> None:
        """Start the child and construct the environment there (bounded by ``start_timeout_s``); idempotent."""
        with self._cond:
            if self._state == "ready":
                return
            if self._state not in ("new",):
                raise HostUnavailable(self._unusable_reason())
        if not self._start_lock.acquire(timeout=self.profile.start_timeout_s):
            raise HostUnavailable("the simulator host is still starting")
        try:
            with self._cond:
                if self._state == "ready":
                    return
                if self._state != "new":
                    raise HostUnavailable(self._unusable_reason())
                self._state = "starting"
            try:
                self._spawn()
                result = self._roundtrip("init", {
                    "protocol": PROTOCOL, "package_dir": self.package_dir, "entry": self.entry,
                    "kwargs": self.options, "stop": self.profile.stop,
                    "readback": {"path": self.profile.readback_path, "field": self.profile.readback_field}},
                    lane="world", timeout_s=self.profile.start_timeout_s, starting=True)
                if not isinstance(result, Mapping) or result.get("protocol") != PROTOCOL:
                    raise HostUnavailable("the simulator host answered with another protocol")
                spaces = (space_from(result.get("action_space")), space_from(result.get("observation_space")))
            except BaseException as exc:
                reason = (f"the environment could not be built in the simulator host ({exc})"
                          if isinstance(exc, ChildCallError) else f"the simulator host did not start ({exc})")
                with self._cond:
                    self._state, self._reason = "failed", reason[:500]
                # A child that reported the failure exits by itself (its atexit cleanup runs); one that is still
                # constructing gets SIGTERM, which ends construction with an ordinary exit, then SIGKILL.
                self._close_write_end()
                if not self._wait_exit(min(self.profile.close_timeout_s, 30.0) if isinstance(exc, ChildCallError)
                                       else 0.0):
                    self._terminate("start failed", grace_s=min(self.profile.close_timeout_s, 30.0))
                if isinstance(exc, HostError):
                    raise HostUnavailable(reason[:500]) from exc
                raise
            with self._cond:
                self._spaces = spaces
                self._info = {"pid": result.get("pid"), "python": result.get("python")}
                if self._state == "starting":
                    self._state = "ready"
                else:   # the child died during the reply
                    raise HostUnavailable(self._unusable_reason())
            _LIVE.add(self)
        finally:
            self._start_lock.release()

    def _spawn(self) -> None:
        python = os.environ.get(PYTHON_ENV) or sys.executable
        if not python or not os.path.isabs(python) or not os.access(python, os.X_OK):
            raise HostUnavailable(f"the host interpreter {python!r} is not an executable absolute path "
                                  f"({PYTHON_ENV})")
        guard = _gate_guard_file()
        if guard == "":
            raise HostUnavailable("this process runs under the gate's process guard, which the host cannot apply")
        to_child, from_child = os.pipe(), os.pipe()
        env = dict(os.environ)
        env[FDS_ENV] = f"{to_child[0]},{from_child[1]}"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if guard:
            env[GUARD_ENV], env[GUARDED_ENV] = guard, "1"
        try:
            proc = subprocess.Popen([python, str(CHILD_SCRIPT)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, pass_fds=(to_child[0], from_child[1]), close_fds=True,
                                    start_new_session=True, env=env)
        except BaseException:
            for fd in (*to_child, *from_child):
                os.close(fd)
            raise
        os.close(to_child[0])
        os.close(from_child[1])
        os.set_blocking(to_child[1], False)
        with self._cond:
            self._proc, self._write_fd, self._read_fd = proc, to_child[1], from_child[0]
        reader = threading.Thread(target=self._read, args=(from_child[0], proc), daemon=True,
                                  name=f"mhs-sim-host-reader-{proc.pid}")
        self._reader = reader
        reader.start()

    # -- protocol ---------------------------------------------------------------------------------------------------
    def _unusable_reason(self) -> str:
        if self._state == "new":
            return "the simulator host has not been started"
        if self._state == "starting":
            return "the simulator host is still starting"
        if self._state in ("closing", "closed"):
            return "the simulator host is closed or closing"
        return self._reason or f"the simulator host is {self._state}"

    def _read(self, fd: int, proc: subprocess.Popen) -> None:
        buffer = bytearray()
        problem = None
        try:
            while problem is None:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                buffer += chunk
                while problem is None:
                    index = buffer.find(b"\n")
                    if index < 0:
                        if len(buffer) > MAX_LINE:
                            problem = "the simulator host sent an oversized reply"
                        break
                    line = bytes(buffer[:index])
                    del buffer[:index + 1]
                    if line.strip():
                        problem = self._on_line(line)
        except OSError:
            pass
        finally:
            self._on_eof(proc, problem)

    def _on_line(self, line: bytes) -> str | None:
        try:
            document = json.loads(line.decode("utf-8"))
        except ValueError:
            return "the simulator host sent a reply that is not JSON"
        if not isinstance(document, dict) or not isinstance(document.get("id"), int) \
                or isinstance(document.get("id"), bool):
            return "the simulator host sent a reply without a request id"
        with self._cond:
            request = self._pending.pop(document["id"], None)
            if request is None:
                return "the simulator host answered a request it was not sent"
            if document.get("ok") is True:
                request.result = document.get("result")
            else:
                request.error = self._error(document.get("error"))
            request.done = True
            if self._lanes.get(request.lane) is request:
                self._lanes[request.lane] = None
            if request.abandoned:
                self.late.append({"op": request.op, "outcome": "returned" if request.error is None else
                                  f"raised {type(request.error).__name__}",
                                  "after_s": round(max(0.0, time.monotonic() - request.started), 3)})
                del self.late[:-_MAX_LATE]
            self._cond.notify_all()
        return None

    def _error(self, error: Any) -> BaseException:
        if not isinstance(error, Mapping):
            return HostUnavailable("the simulator host sent an invalid error", sent=True)
        refused = error.get("refused")
        message = str(error.get("message") or "")[:300]
        if refused == "fenced":
            return HostFenced("the world call", "host")
        if refused == "busy":
            return HostBusy({"op": "an earlier call", "abandoned": False})
        if refused in ("exited", "invalid"):
            return HostUnavailable(f"the simulator host refused the call: {message}", sent=False)
        if error.get("after_effect") is True:
            return HostAfterEffect(message)
        failure = ChildCallError(error)
        if failure.exit_requested:
            self._exit_requested = f"{failure.type_name}({error.get('code')!r})"[:120]
        return failure

    def _on_eof(self, proc: subprocess.Popen, problem: str | None) -> None:
        try:
            proc.wait(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            pass
        with self._cond:
            self._exit_code = proc.returncode
            if self._state not in ("closing", "closed", "failed"):
                self._state = "broken" if problem else "dead"
                self._reason = problem or (f"the simulator host exited (status {proc.returncode})"
                                           if proc.returncode is not None else "the simulator host closed its pipe")
            for request in self._pending.values():
                request.error = HostUnavailable(self._reason or "the simulator host ended", sent=True)
                request.done = True
            self._pending.clear()
            self._lanes = {"world": None, "control": None}
            self._cond.notify_all()
        if self._read_fd is not None:
            try:
                os.close(self._read_fd)
            except OSError:
                pass

    def _write(self, document: Mapping[str, Any], deadline: float) -> None:
        """Write one request line; the caller holds the send lock (the write end is closed only under it)."""
        data = (json.dumps(document, separators=(",", ":")) + "\n").encode("utf-8")
        if len(data) > MAX_LINE:
            raise HostUnavailable(f"the request exceeds {MAX_LINE} bytes")
        fd = self._write_fd
        if fd is None:
            raise HostUnavailable("the request pipe of the simulator host is closed")
        view, written = memoryview(data), 0
        while written < len(data):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if written:
                    with self._cond:
                        self._state, self._reason = "broken", "a request was written only in part"
                raise HostTimeout(str(document.get("op")), WRITE_BOUND_S, sent=False)
            try:
                _readable, writable, _ = select.select([], [fd], [], remaining)
            except (OSError, ValueError) as exc:
                raise HostUnavailable(f"the simulator host pipe is closed ({type(exc).__name__})") from exc
            if not writable:
                continue
            try:
                written += os.write(fd, view[written:])
            except BlockingIOError:
                continue
            except OSError as exc:
                if written:
                    with self._cond:
                        self._state, self._reason = "broken", "a request was written only in part"
                raise HostUnavailable(f"the simulator host does not accept requests ({type(exc).__name__})") from exc

    def _roundtrip(self, op: str, payload: Mapping[str, Any], *, lane: str, timeout_s: float,
                   guard: Callable[[], None] | None = None, fence: bool = False, starting: bool = False) -> Any:
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        if fence:
            with self._cond:
                self._fenced = True   # before anything can block: no world call is sent from here on
        if not self._send_lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise HostTimeout(op, timeout_s, sent=False)
        try:
            with self._cond:
                if not (starting and self._state == "starting") and self._state != "ready" \
                        and not (self._state == "closing" and op in ("stop", "readback", "close")):
                    raise HostUnavailable(self._unusable_reason())
                if self._proc is not None and self._proc.poll() is not None:
                    raise HostUnavailable(self._reason or f"the simulator host exited (status "
                                          f"{self._proc.returncode})")
                if op in ("step", "reset") and self._fenced:
                    raise HostFenced(op)
                current = self._lanes[lane]
                if current is not None:
                    raise HostBusy(current.describe())
            if guard is not None:
                guard()
            request = _Request(next(self._ids), op, lane)
            with self._cond:
                self._pending[request.rid] = request
                self._lanes[lane] = request
            try:
                self._write({"id": request.rid, "op": op, **payload}, min(deadline, time.monotonic() + WRITE_BOUND_S))
            except BaseException:
                with self._cond:
                    self._pending.pop(request.rid, None)
                    if self._lanes[lane] is request:
                        self._lanes[lane] = None
                    self._cond.notify_all()
                raise
        finally:
            self._send_lock.release()
        with self._cond:
            while not request.done:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    request.abandoned = True
                    raise HostTimeout(op, timeout_s)
                self._cond.wait(remaining)
        if request.error is not None:
            raise request.error
        return request.result

    # -- the environment interface ----------------------------------------------------------------------------------
    @property
    def action_space(self) -> Any:
        self.start()
        return self._spaces[0]

    @property
    def observation_space(self) -> Any:
        self.start()
        return self._spaces[1]

    def step(self, action: Any, *, guard: Callable[[], None] | None = None) -> tuple:
        result = self._roundtrip("step", {"action": action}, lane="world", timeout_s=self.profile.step_timeout_s,
                                 guard=guard)
        items = result.get("result") if isinstance(result, Mapping) else None
        if not isinstance(items, list) or len(items) not in (4, 5):
            raise HostAfterEffect("the simulator host returned an invalid step result")
        return tuple(items)

    def reset(self, *, guard: Callable[[], None] | None = None, **kwargs: Any) -> Any:
        if set(kwargs) - set(self.profile.reset_kwargs):
            raise TypeError(f"the native reset accepts only {list(self.profile.reset_kwargs)}")
        result = self._roundtrip("reset", {"kwargs": kwargs}, lane="world", timeout_s=self.profile.reset_timeout_s,
                                 guard=guard)
        if not isinstance(result, Mapping) or "result" not in result:
            raise HostAfterEffect("the simulator host returned an invalid reset result")
        if result.get("pair") is True:
            value = result["result"]
            if not isinstance(value, list) or len(value) != 2:
                raise HostAfterEffect("the simulator host returned an invalid reset result")
            return tuple(value)
        return result["result"]

    # -- the safety path --------------------------------------------------------------------------------------------
    def stop(self) -> dict[str, Any]:
        """Fence the host, then run the declared stop in the child; ``{"world_active": bool}`` (bounded)."""
        result = self._roundtrip("stop", {}, lane="control", timeout_s=self.profile.stop_timeout_s, fence=True)
        if not isinstance(result, Mapping) or not isinstance(result.get("world_active"), bool):
            raise HostUnavailable("the simulator host sent an invalid stop reply", sent=True)
        return {"world_active": result["world_active"]}

    def readback(self) -> Any:
        """The declared read-back value, read in the child (bounded); the caller compares it."""
        result = self._roundtrip("readback", {}, lane="control", timeout_s=self.profile.stop_timeout_s)
        if not isinstance(result, Mapping) or "value" not in result:
            raise HostUnavailable("the simulator host sent an invalid read-back reply", sent=True)
        return result["value"]

    def unfence(self) -> None:
        """Lift the fence in the child and here (a safety reset; bounded)."""
        self._roundtrip("unfence", {}, lane="control", timeout_s=self.profile.stop_timeout_s)
        with self._cond:
            self._fenced = False

    def ping(self) -> dict[str, Any]:
        result = self._roundtrip("ping", {}, lane="control", timeout_s=self.profile.stop_timeout_s)
        return dict(result) if isinstance(result, Mapping) else {}

    # -- close ------------------------------------------------------------------------------------------------------
    def close(self) -> str:
        """Stop, close the environment, end the child; each bounded.  ``settled`` or ``unsettled: ...``; once."""
        with self._cond:
            if self._state == "closed" or self._state == "closing":
                return self._close_outcome or "unsettled: close is running"
            if self._state == "new":
                self._state, self._close_outcome = "closed", "settled"
                return self._close_outcome
            was = self._state
            self._state = "closing"
        notes: list[str] = []
        if was == "ready" and self.alive():
            try:
                self.stop()
                value = self.readback()
                if not self.profile.confirms(value):
                    notes.append(f"the read-back before close returned {value!r}, not the stopped value")
            except BaseException as exc:  # noqa: BLE001 - recorded; the environment is closed anyway
                notes.append(f"the stop before close was not confirmed ({type(exc).__name__})")
            if not self.wait_world_idle(self.profile.close_timeout_s):
                notes.append("a world call was still running at close")
            try:
                self._roundtrip("close", {}, lane="world", timeout_s=self.profile.close_timeout_s)
            except ChildCallError as exc:
                if not exc.exit_requested:
                    notes.append(f"env.close raised {exc.type_name}")
                # An exit requested by close (a global ROS shutdown and sys.exit) is the environment's own close.
            except BaseException as exc:  # noqa: BLE001
                notes.append(f"env.close did not complete ({type(exc).__name__})")
        else:
            notes.append(self._reason or f"the simulator host was {was} at close")
        self._close_write_end()
        if not self._wait_exit(self.profile.close_timeout_s):
            notes.append(self._terminate("the host did not exit within its close bound",
                                         grace_s=min(self.profile.close_timeout_s, 30.0)))
        elif was == "ready" and self._exit_code not in (0, None):
            notes.append(f"the host exited with status {self._exit_code}")
        outcome = "settled" if not notes else "unsettled: " + "; ".join(notes)
        with self._cond:
            self._state, self._close_outcome = "closed", outcome[:600]
            self._cond.notify_all()
        _LIVE.discard(self)
        return self._close_outcome

    @property
    def close_outcome(self) -> str | None:
        return self._close_outcome

    def _close_write_end(self) -> None:
        # Under the send lock: a request being written never meets a closed (and possibly reused) descriptor number.
        acquired = self._send_lock.acquire(timeout=WRITE_BOUND_S * 2)
        try:
            with self._cond:
                fd, self._write_fd = self._write_fd, None
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        finally:
            if acquired:
                self._send_lock.release()

    def _wait_exit(self, timeout_s: float) -> bool:
        proc = self._proc
        if proc is None:
            return True
        try:
            proc.wait(timeout=max(0.0, float(timeout_s)))
        except subprocess.TimeoutExpired:
            return False
        with self._cond:
            self._exit_code = proc.returncode
        return True

    def _terminate(self, why: str, *, grace_s: float = KILL_GRACE_S) -> str:
        """SIGTERM, then SIGKILL of the child's process group; returns a note of what happened."""
        self._close_write_end()
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return why
        try:
            proc.terminate()
        except OSError:
            pass
        if self._wait_exit(grace_s):
            return f"{why}; it was terminated (SIGTERM)"
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        self._wait_exit(KILL_GRACE_S)
        return f"{why}; it was killed (SIGKILL to its process group); processes it launched may still run"


@atexit.register
def _close_live_hosts() -> None:
    """At interpreter exit, end every host this process still owns (bounded): its pipe closes, it stops and closes."""
    for host in list(_LIVE):
        try:
            host._close_write_end()
            if not host._wait_exit(KILL_GRACE_S):
                host._terminate("the endpoint exited while the host ran")
        except Exception:  # noqa: BLE001 - interpreter exit must not hang or fail here
            pass
