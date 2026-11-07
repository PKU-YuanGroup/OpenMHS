"""``Recorder``: a recording proxy around a driver's backend object (gates G6 and G7).

::

    from mhs.testing import Recorder, log_of

    native = Recorder(FakeBath())          # or Recorder(methods={"get_temperature": 21.5}, attributes={...})
    driver = Bath(backend="fake", native=native)
    ...
    log = log_of(native)
    log.names                              # every attribute the driver asked for
    log.actuations(since=mark)             # calls and assignments outside a read

Unlike ``unittest.mock.Mock``, a :class:`Recorder` never invents an
attribute: asking for one the target does not have raises
:class:`AttributeError`, exactly as the real backend would, and the name is
listed in :attr:`RecordLog.missing`.  Every other attribute is forwarded to
the target.  Callables come back wrapped (same signature, ``__wrapped__``
set), so each call is recorded with its arguments before it runs. Ordinary
Python attribute objects come back as lazy child proxies sharing the same log:
``native.motor.stop()`` records ``motor.stop``, and ``native.motor.enabled =
False`` records ``motor.enabled``. Assignments and deletions are recorded and
forwarded; injected failures happen before the native mutation.

This is not a general transparent object wrapper. Scalars, enums, containers,
buffers, array/dataframe protocols, recognized space schemas and objects with
value/container operators remain unchanged. Their item mutations, method return values and calls made
internally by native code are not traced recursively. Child proxies do not
preserve ``is`` or concrete type checks. Aliases have the path actually used;
cycles are traversed lazily, with a bounded LRU cache. Evicted proxies still
record normally. Direct proxy arguments/assigned values are unwrapped before
entering native code; containers are never copied or rewritten. Attribute
property getters still run during lookup, before the resulting get is logged.

Each recorded event carries the *phase* it happened in, read from the call
stack: ``read`` while the runtime reads state (``Bridge.read``,
``interlocks``, ``safety_status`` and the driver's own ``@read`` /
``@interlock`` methods), ``estop`` inside ``Bridge.estop`` or the ``@estop``
method, ``reset`` inside ``Bridge.reset`` or ``@reset``, ``setup`` while the
backend is opened, and ``act`` otherwise.  A contract method counts only when
its code is the SDK's own (a file of the ``mhs`` package): a driver helper
that happens to be called ``make_bridge`` or ``read`` gets no phase from its
name (the gate registers the driver's decorated methods by code object).  "Zero native calls" in the gate
means zero events outside ``read`` and ``setup`` (the runtime reads the state
for every receipt, refused ones included).

The recorder's own interface is reached through :func:`log_of`, never
through attributes of the proxy, so it can never shadow a backend attribute
(an upstream class may well have a method called ``calls`` or ``reset``).
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import os
import sys
import threading
import time
from collections import OrderedDict
from collections.abc import Mapping as MappingABC, Sequence, Set
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Iterator, Mapping

__all__ = ["Call", "PHASES", "RecordLog", "Recorder", "log_of"]

#: Phases a recorded event can belong to.
PHASES = ("read", "act", "estop", "reset", "setup")
#: Bridge contract methods during which a native event is a read / an e-stop / a reset / an open.
_PHASE_METHODS: dict[str, str] = {
    "read": "read", "_read_param": "read", "interlocks": "read", "safety_status": "read", "describe": "read",
    "capabilities": "read", "resources": "read",
    "estop": "estop", "_estop_impl": "estop",
    "reset": "reset",
    "open": "setup", "open_native": "setup", "_get_native": "setup", "setup": "setup", "make_bridge": "setup",
    "teardown": "setup", "close": "setup",
}
_MAX_FRAMES = 80
#: Source directory of the ``mhs`` package: only contract methods defined here open a phase by name.
_SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep
_MISSING: Any = object()
_SLOTS = ("_mhs_target", "_mhs_log", "_mhs_methods", "_mhs_attributes", "_mhs_path")
_CHILD_CACHE_SIZE = 256
# Detect these statically: probing a property to decide whether to wrap it
# could itself execute native code. No scientific dependency is imported.
_VALUE_PROTOCOLS = (
    "__iter__", "__getitem__", "__len__", "__index__", "__int__", "__float__", "__complex__", "__bool__",
    "__add__", "__sub__", "__mul__", "__truediv__", "__matmul__", "__bytes__", "__buffer__", "__fspath__",
    "__array__", "__array_interface__", "__array_struct__", "__cuda_array_interface__", "__dlpack__",
    "__dataframe__",
)
_VALUE_COMPARISONS = ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__")
# The bridge dispatches on these schema families' concrete MRO. Their bounds,
# dimensions and member spaces are metadata, not nested device actuators. Use
# an explicit family plus its defining fields; neither a sample() method nor
# an attribute named action_space is enough to opt an actuator out of recording.
_SPACE_FIELDS = {
    "Discrete": ("n",), "MultiDiscrete": ("nvec",), "MultiBinary": ("n",),
    "Box": ("low", "high"), "Dict": ("spaces",), "Tuple": ("spaces",),
}
_SPACE_VALUE_METHODS = frozenset({"sample", "contains", "seed", "to_jsonable", "from_jsonable", "is_bounded"})


def _space_schema(value: Any) -> bool:
    """Recognize supported space metadata without importing Gym or calling descriptors."""
    # A familiar schema class name must not hide an object's own motor/control
    # methods. Inspect class dictionaries statically; properties are not run.
    if any(not name.startswith("_") and name not in _SPACE_VALUE_METHODS
           and (callable(member) or isinstance(member, (staticmethod, classmethod)))
           for cls in type(value).__mro__ for name, member in cls.__dict__.items()):
        return False
    for cls in type(value).__mro__:
        fields = _SPACE_FIELDS.get(cls.__name__)
        if fields is not None and all(inspect.getattr_static(value, name, _MISSING) is not _MISSING
                                      for name in fields):
            return True
    return False


def _attribute_object(value: Any) -> bool:
    """Conservatively select ordinary Python objects, not data/value protocols."""
    cls = type(value)
    if cls.__module__ == "builtins" or isinstance(value, (Enum, MappingABC, Sequence, Set, os.PathLike, type)):
        return False
    if _space_schema(value):
        return False
    if inspect.getattr_static(value, "__dict__", _MISSING) is _MISSING \
            and not any("__slots__" in base.__dict__ for base in cls.__mro__):
        return False
    if any(inspect.getattr_static(value, name, _MISSING) is not _MISSING for name in _VALUE_PROTOCOLS):
        return False
    # Value comparisons (including dataclasses, quantities and scientific
    # scalars) often require an exact concrete type. Preserve them unchanged.
    return not any(getattr(cls, name, getattr(object, name)) is not getattr(object, name)
                   for name in _VALUE_COMPARISONS)


def _unwrapped(value: Any) -> Any:
    """Do not store a child proxy in the native object or pass it as a direct argument."""
    if isinstance(value, Recorder):
        target = object.__getattribute__(value, "_mhs_target")
        if target is not _MISSING:
            return target
    return value


@functools.lru_cache(maxsize=2048)
def _sdk_file(filename: str) -> bool:
    """True when a code object's file belongs to the ``mhs`` package (not a driver package or upstream code)."""
    try:
        return os.path.abspath(filename).startswith(_SDK_DIR)
    except (TypeError, ValueError):  # pragma: no cover - odd code objects
        return False


@dataclass(frozen=True)
class Call:
    """One recorded event: ``kind`` is ``call``, ``get``, ``set`` or ``del``."""

    seq: int
    name: str
    kind: str
    phase: str
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    at: float = 0.0

    @property
    def actuating(self) -> bool:
        """True for a call, assignment or deletion outside a read or the backend's setup."""
        return self.kind != "get" and self.phase not in ("read", "setup")


class _Failure:
    def __init__(self, error: BaseException, phases: frozenset[str], names: frozenset[str] | None):
        self.error = error
        self.phases = phases
        self.names = names
        self.raised = 0


class RecordLog:
    """What a :class:`Recorder` saw (reach it with :func:`log_of`)."""

    def __init__(self, label: str):
        self.label = label
        self.calls: list[Call] = []
        #: every attribute name the driver asked for (found or not)
        self.names: set[str] = set()
        #: names the target does not have (the driver got an AttributeError)
        self.missing: set[str] = set()
        #: names the driver resolved or assigned on the backend (what it really relies on)
        self.found: set[str] = set()
        #: Full attribute paths, including descendants. The sets above remain
        #: root members for G7's root-class source comparison.
        self.paths: set[str] = set()
        self.missing_paths: set[str] = set()
        self.found_paths: set[str] = set()
        #: code objects of the driver's own read / e-stop / reset methods (set by the gate)
        self.phase_codes: dict[Any, str] = {}
        self._lock = threading.Lock()
        self._failures: list[_Failure] = []
        #: open phase windows (see :meth:`window`), counted across threads
        self._windows: dict[str, int] = {name: 0 for name in PHASES}
        self._children: OrderedDict[tuple[str, int], Recorder] = OrderedDict()

    def member(self, prefix: str, name: str, status: str | None = None) -> str:
        """Remember one attribute lookup without confusing nested paths with root members."""
        path = f"{prefix}.{name}" if prefix else name
        with self._lock:
            self.paths.add(path)
            if not prefix:
                self.names.add(name)
            if status == "found":
                self.found_paths.add(path)
                if not prefix:
                    self.found.add(name)
            elif status == "missing":
                self.missing_paths.add(path)
                if not prefix:
                    self.missing.add(name)
        return path

    def child(self, path: str, value: Any) -> Any:
        """Return a lazy attribute proxy, retaining at most a bounded set of paths."""
        if not _attribute_object(value) or isinstance(value, Recorder):
            return value
        key = (path, id(value))
        with self._lock:
            cached = self._children.get(key)
            if cached is not None:
                self._children.move_to_end(key)
                return cached
            proxy = object.__new__(Recorder)
            object.__setattr__(proxy, "_mhs_target", value)
            object.__setattr__(proxy, "_mhs_log", self)
            object.__setattr__(proxy, "_mhs_methods", {})
            object.__setattr__(proxy, "_mhs_attributes", {})
            object.__setattr__(proxy, "_mhs_path", path)
            self._children[key] = proxy
            if len(self._children) > _CHILD_CACHE_SIZE:
                self._children.popitem(last=False)
            return proxy

    # -- recording ------------------------------------------------------------
    @contextlib.contextmanager
    def window(self, phase: str) -> Iterator[None]:
        """Mark a bridge contract call of ``phase`` as running (on any thread) while the block runs.

        Bridges may run native calls on helper threads (bounded calls), where
        the call stack no longer shows the contract method; such an event takes
        the phase of the open windows: ``act`` when an actuating call is open,
        else ``estop``, ``reset``, ``setup`` or ``read``.
        """
        if phase not in PHASES:
            raise ValueError(f"unknown phase {phase!r}")
        with self._lock:
            self._windows[phase] += 1
        try:
            yield
        finally:
            with self._lock:
                self._windows[phase] -= 1

    def phase(self, depth: int = 2) -> str:
        """The phase of the running native event: from the call stack, else from the open windows."""
        from ..bridge.base import Bridge

        try:
            frame = sys._getframe(depth)
        except ValueError:  # pragma: no cover - shallow stack
            frame = None
        seen = 0
        codes = self.phase_codes
        while frame is not None and seen < _MAX_FRAMES:
            code = frame.f_code
            found = codes.get(code)
            if found is not None:
                return found
            name = _PHASE_METHODS.get(code.co_name)
            if name is not None and _sdk_file(code.co_filename):
                owner = frame.f_locals.get("self")
                if isinstance(owner, Bridge):
                    return name
            frame = frame.f_back
            seen += 1
        with self._lock:
            open_windows = [name for name, count in self._windows.items() if count > 0]
        for name in ("act", "estop", "reset", "setup", "read"):
            if name in open_windows:
                return name
        return "act"

    def record(self, name: str, kind: str, args: tuple[Any, ...] = (), kwargs: Mapping[str, Any] | None = None,
               *, phase: str | None = None) -> Call:
        event_phase = phase or self.phase(2)
        with self._lock:
            call = Call(len(self.calls), name, kind, event_phase, tuple(args), dict(kwargs or {}), time.monotonic())
            self.calls.append(call)
        return call

    def wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        log = self

        def recorded(*args: Any, **kwargs: Any) -> Any:
            args = tuple(_unwrapped(value) for value in args)
            kwargs = {key: _unwrapped(value) for key, value in kwargs.items()}
            call = log.record(name, "call", args, kwargs)
            log._maybe_fail(call)
            return fn(*args, **kwargs)

        try:
            functools.update_wrapper(recorded, fn)
        except (AttributeError, TypeError):  # pragma: no cover - exotic callables
            recorded.__wrapped__ = fn  # type: ignore[attr-defined]
        return recorded

    # -- failure injection ----------------------------------------------------
    def _maybe_fail(self, call: Call) -> None:
        if not call.actuating and call.phase not in ("estop", "reset"):
            return
        with self._lock:
            failures = list(self._failures)
        for failure in failures:
            if call.phase in failure.phases and (failure.names is None or call.name in failure.names):
                failure.raised += 1
                raise failure.error

    @contextlib.contextmanager
    def fail(self, error: BaseException | None = None, *, phases: Iterable[str] = ("act",),
             names: Iterable[str] | None = None) -> Iterator[_Failure]:
        """While active, every native call or assignment in ``phases`` (and ``names``, if given) raises ``error``.

        The default error is ``RuntimeError("injected native failure")``: a
        driver must report it as a ``failed`` receipt, never as success.
        """
        failure = _Failure(error or RuntimeError("injected native failure"), frozenset(phases),
                           frozenset(names) if names is not None else None)
        with self._lock:
            self._failures.append(failure)
        try:
            yield failure
        finally:
            with self._lock:
                self._failures.remove(failure)

    # -- queries --------------------------------------------------------------
    def mark(self) -> int:
        """A position in the log (pass it to :meth:`since`)."""
        with self._lock:
            return len(self.calls)

    def since(self, mark: int = 0) -> list[Call]:
        with self._lock:
            return list(self.calls[mark:])

    def actuations(self, since: int = 0) -> list[Call]:
        """Calls and assignments after ``since`` that are not reads or the backend's setup."""
        return [call for call in self.since(since) if call.actuating]

    def in_phase(self, phase: str, since: int = 0) -> list[Call]:
        return [call for call in self.since(since) if call.phase == phase and call.kind != "get"]


class Recorder:
    """An attribute recording proxy with explicit value exclusions (see the module docstring).

    ``Recorder(target)`` forwards to ``target``; ``Recorder(methods={...},
    attributes={...})`` is a stand-alone fake whose methods return the given
    values (a callable value is called with the arguments).  ``methods`` and
    ``attributes`` also override members of a target.
    """

    __slots__ = _SLOTS

    def __init__(self, target: Any = _MISSING, *, methods: Mapping[str, Any] | None = None,
                 attributes: Mapping[str, Any] | None = None, label: str | None = None):
        if target is _MISSING and methods is None and attributes is None:
            raise TypeError("Recorder needs a target object or methods={...} / attributes={...}")
        name = label or (type(target).__name__ if target is not _MISSING else "Recorder")
        object.__setattr__(self, "_mhs_target", target)
        object.__setattr__(self, "_mhs_log", RecordLog(name))
        object.__setattr__(self, "_mhs_methods", dict(methods or {}))
        object.__setattr__(self, "_mhs_attributes", dict(attributes or {}))
        object.__setattr__(self, "_mhs_path", "")

    def __getattribute__(self, name: str) -> Any:
        if name in _SLOTS or (name.startswith("__") and name.endswith("__")):
            return object.__getattribute__(self, name)
        log: RecordLog = object.__getattribute__(self, "_mhs_log")
        methods = object.__getattribute__(self, "_mhs_methods")
        attributes = object.__getattribute__(self, "_mhs_attributes")
        target = object.__getattribute__(self, "_mhs_target")
        prefix = object.__getattribute__(self, "_mhs_path")
        path = log.member(prefix, name)
        if name in methods:
            value = methods[name]
            log.member(prefix, name, "found")
            return log.wrap(path, value if callable(value) else (lambda *_args, **_kwargs: value))
        if name in attributes:
            log.member(prefix, name, "found")
            log.record(path, "get")
            return log.child(path, attributes[name])
        if target is _MISSING:
            log.member(prefix, name, "missing")
            raise AttributeError(f"{log.label} has no attribute {path!r} (mhs.testing.Recorder never invents one)")
        try:
            value = getattr(target, name)
        except AttributeError:
            log.member(prefix, name, "missing")
            raise
        log.member(prefix, name, "found")
        if callable(value):
            return log.wrap(path, value)
        log.record(path, "get")
        return log.child(path, value)

    def __setattr__(self, name: str, value: Any) -> None:
        log: RecordLog = object.__getattribute__(self, "_mhs_log")
        target = object.__getattribute__(self, "_mhs_target")
        attributes = object.__getattribute__(self, "_mhs_attributes")
        prefix = object.__getattribute__(self, "_mhs_path")
        path = log.member(prefix, name, "found")
        value = _unwrapped(value)
        call = log.record(path, "set", (value,))
        log._maybe_fail(call)
        if target is _MISSING or name in attributes:
            attributes[name] = value
        else:
            setattr(target, name, value)

    def __delattr__(self, name: str) -> None:
        log: RecordLog = object.__getattribute__(self, "_mhs_log")
        target = object.__getattribute__(self, "_mhs_target")
        attributes = object.__getattribute__(self, "_mhs_attributes")
        prefix = object.__getattribute__(self, "_mhs_path")
        path = log.member(prefix, name)
        call = log.record(path, "del")
        log._maybe_fail(call)
        if name in attributes:
            del attributes[name]
        elif target is _MISSING:
            raise AttributeError(name)
        else:
            delattr(target, name)

    def __repr__(self) -> str:
        target = object.__getattribute__(self, "_mhs_target")
        return f"Recorder({'<methods>' if target is _MISSING else repr(target)})"

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        target = object.__getattribute__(self, "_mhs_target")
        if target is _MISSING or not callable(target):
            raise TypeError("the recorded backend object is not callable")
        log: RecordLog = object.__getattribute__(self, "_mhs_log")
        prefix = object.__getattribute__(self, "_mhs_path")
        return log.wrap(log.member(prefix, "__call__", "found"), target)(*args, **kwargs)

    def __enter__(self) -> Any:
        return Recorder._forward(self, "__enter__")

    def __exit__(self, *exc: Any) -> Any:
        return Recorder._forward(self, "__exit__", *exc)

    async def __aenter__(self) -> Any:
        return await Recorder._forward(self, "__aenter__")

    async def __aexit__(self, *exc: Any) -> Any:
        return await Recorder._forward(self, "__aexit__", *exc)

    def _forward(self, name: str, *args: Any) -> Any:
        target = object.__getattribute__(self, "_mhs_target")
        log: RecordLog = object.__getattribute__(self, "_mhs_log")
        method = getattr(type(target), name, None) if target is not _MISSING else None
        prefix = object.__getattribute__(self, "_mhs_path")
        path = log.member(prefix, name)
        if method is None:
            log.member(prefix, name, "missing")
            raise AttributeError(f"{log.label} does not support {name}")
        log.member(prefix, name, "found")
        return log.wrap(path, getattr(target, name))(*args)


def log_of(recorder: Recorder) -> RecordLog:
    """The :class:`RecordLog` of ``recorder``."""
    if not isinstance(recorder, Recorder):
        raise TypeError(f"expected a mhs.testing.Recorder, got {type(recorder).__name__}")
    return object.__getattribute__(recorder, "_mhs_log")
