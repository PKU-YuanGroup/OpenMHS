"""In-process conformance harness: loopback transport, fresh endpoints, fault injection.

This is the public way to run the suite against a driver without sockets or
child processes (CONF-09), and the replacement for the reference-only
``x-cap.mhs-test.*`` hooks (CONF-08)::

    from mhs.conformance.inprocess import run_suite_inprocess

    report = run_suite_inprocess(lambda: build_my_server(), profile="MHS-Sim", level="CL3")

``factory`` is a zero-argument callable returning an ``MHSServer`` (anything
with ``handle(message)`` and a ``devices`` mapping of ``Device`` objects), or a
``(server, cleanup)`` pair.  The suite calls it once for the read-only
discovery checks and once more for every mutating group (``OP``, ``SAFE``,
``FID``), so no group sees another group's state and repeated runs give the
same verdicts.

:class:`Harness` instruments every device bridge of one server by shadowing
its contract-plane methods on the instance (``call``, ``write``, ``read``,
``estop``, ``reset``, ``interlocks``, ``safety_status``, ``snapshot``,
``restore``, ``safe_state``).  It records each call and can, per device:

* force interlocks ``open`` or ``unknown`` (SAFE-011, SAFE-012);
* delay a capability call, cooperatively honouring cancellation (PROTO-011,
  OP-011);
* drop the response of a call after its effect (OP-013, an unknown outcome);
* make a call raise.

It is also the actuation gate of an in-process run (CON-031): unless the run
has ``allow_actuation``, every ``call``/``write``/``restore``/``safe_state``
that reaches the bridge of a hardware or hybrid device is refused *before* the driver with
``MHS.AUTH.HARDWARE_DISABLED`` and recorded with ``faulted="blocked"`` and the
id of the test that sent it.  A negative test whose command the endpoint failed
to refuse therefore fails (and fails ``CON-031``) without moving anything.
Read-verb capabilities (``read_capabilities``) pass through.

Nothing here changes the server: faults are injected at the bridge boundary,
exactly where a misbehaving device would show them, and production endpoints
carry no test surface.

A method that cannot be shadowed (a read-only attribute, a property, a
``__setattr__`` guard that raises or silently drops the write) is listed in
:attr:`Harness.uninstrumented`: a wrapper counts as installed only when the
bridge then really resolves the name to it.  The suite treats the zero-call
evidence of such a device as unproven (CON-031, SAFE-011/012/014 fail closed
instead of passing vacuously), and, because such a bridge cannot be blocked,
sends no negative test to it on hardware.

One bridge object may serve several devices.  It is wrapped once and every
device sharing it is tracked; a call is attributed to the device its
``ctx.device_id`` names (when that device shares the bridge), and the gate
refuses an actuating call on a bridge shared with any hardware or hybrid
device whatever the call names (fail closed: the same object drives the
hardware).
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Mapping, Sequence

from mhs.errors import MHSError
from mhs.signals import OutcomeUnknown

__all__ = [
    "Harness",
    "Loopback",
    "Record",
    "client_for",
    "reference_factory",
    "run_suite_inprocess",
]

#: Bridge methods the harness instruments.
INSTRUMENTED = ("call", "write", "read", "estop", "reset", "interlocks", "safety_status", "snapshot", "restore",
                "safe_state")
#: Bridge methods that can change the device (a write/invoke reaching the driver, or the
#: driver's own safe-state routine, ``Bridge.safe_state``, which moves the device too).
ACTUATING = ("call", "write", "restore", "safe_state")
#: Device modes whose bridges the harness blocks without ``allow_actuation`` (CON-031).
HARDWARE_MODES = ("hardware", "hybrid")
#: Code of a call the harness refused before the driver (CON-031).
HARDWARE_GATE_CODE = "MHS.AUTH.HARDWARE_DISABLED"


class Loopback:
    """In-process JSON-RPC transport: every request is ``server.handle(message)``."""

    kind = "inprocess"
    timeout = 30.0

    def __init__(self, server: Any):
        self.server = server
        self.methods: list[str] = []
        self._lock = threading.Lock()

    def request(self, message: Mapping[str, Any], timeout: float | None = None) -> Any:
        with self._lock:
            self.methods.append(str(message.get("method")))
        response = self.server.handle(dict(message))
        return response.to_dict() if hasattr(response, "to_dict") else response

    def request_batch(self, messages: Sequence[Mapping[str, Any]], timeout: float | None = None) -> list[Any]:
        return [self.request(message, timeout=timeout) for message in messages]

    def notify(self, message: Mapping[str, Any]) -> None:
        self.server.handle(dict(message))

    def drain_notifications(self) -> list[dict[str, Any]]:
        take = getattr(self.server, "take_notifications", None)
        if callable(take):
            try:
                return list(take() or [])
            except Exception:  # noqa: BLE001 - notifications are best effort here
                return []
        return []

    def stderr_tail(self, limit: int = 20) -> list[str]:
        return []

    def close(self) -> None:
        pass


def client_for(server: Any) -> Any:
    """A connected ``mhs.client.MHSClient`` over a :class:`Loopback` (``hello`` already sent)."""

    from mhs.client import MHSClient

    client = MHSClient(Loopback(server))
    client.hello()
    return client


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------


@dataclass
class Record:
    """One bridge call seen by the harness."""

    device_id: str
    method: str
    capability_id: str | None = None
    ok: bool = True
    error: str | None = None
    empty_result: bool = False
    faulted: str | None = None
    #: The conformance test that was running when the call reached the bridge.
    test_id: str | None = None
    at: float = field(default_factory=time.monotonic)


class _LostResponse(MHSError, OutcomeUnknown):
    """The effect happened but its response was lost (recognised as an unknown outcome)."""

    def __init__(self, capability_id: str):
        MHSError.__init__(
            self,
            "MHS.OUTCOME.UNKNOWN",
            f"conformance harness dropped the response of {capability_id} after its effect",
            {"retryable": False, "details": {"injected": "drop_response"}},
        )
        self.native_code = None


class _HardwareGate(MHSError):
    """A write/invoke reached a hardware bridge in a run without ``allow_actuation`` (CON-031)."""

    def __init__(self, device_id: str, method: str, capability_id: str | None, test_id: str | None):
        target = f"{method}({capability_id})" if capability_id else f"{method}()"
        MHSError.__init__(
            self,
            HARDWARE_GATE_CODE,
            f"conformance harness blocked {target} on hardware device {device_id} before the driver: the run "
            f"has no --allow-actuation (CON-031); sent by {test_id or 'the suite'}",
            {"retryable": False, "details": {"injected": "hardware_gate", "device_id": device_id,
                                             "test_id": test_id}},
        )
        self.native_code = None


def _devices(server: Any) -> dict[str, Any]:
    devices = getattr(server, "devices", None)
    if isinstance(devices, Mapping):
        return {str(key): value for key, value in devices.items()}
    if isinstance(devices, (list, tuple)):
        return {str(getattr(item, "device_id", index)): item for index, item in enumerate(devices)}
    return {}


def _cancelled(ctx: Any) -> bool:
    if ctx is None:
        return False
    probe = getattr(ctx, "cancelled", None)
    if callable(probe):
        try:
            return bool(probe())
        except Exception:  # noqa: BLE001
            return False
    event = getattr(ctx, "cancel_event", None)
    is_set = getattr(event, "is_set", None)
    return bool(is_set()) if callable(is_set) else False


#: Position of ``ctx`` in each instrumented bridge method's arguments (``Bridge`` signatures).
_CTX_POSITION = {"read": 2, "write": 2, "estop": 1, "reset": 0, "snapshot": None, "restore": None,
                 "safety_status": None, "safe_state": 0}


def _positional_ctx(name: str, args: Sequence[Any]) -> Any:
    position = _CTX_POSITION.get(name)
    return args[position] if position is not None and len(args) > position else None


def _empty(result: Any) -> bool:
    return result is None or (isinstance(result, (Mapping, list, tuple)) and len(result) == 0)


class Harness:
    """Call recording, fault injection and the hardware gate for every device bridge of one in-process server.

    ``allow_actuation`` (default ``False``, fail closed) lets write/invoke calls
    reach hardware and hybrid bridges; the suite sets it from the run's options
    through :meth:`gate`.
    """

    def __init__(self, server: Any, *, allow_actuation: bool = False):
        self.server = server
        self.records: list[Record] = []
        self.uninstrumented: list[str] = []
        self.allow_actuation = bool(allow_actuation)
        #: Id of the conformance test currently running (set by the suite; stamped on every record).
        self.current_test: str | None = None
        self._lock = threading.Lock()
        self._faults: dict[str, dict[str, Any]] = {}
        self._inflight: dict[str, int] = {}
        self._installed: list[tuple[Any, str]] = []
        self._declared_interlocks: dict[str, list[str]] = {}
        self._hardware: set[str] = set()
        self._reads: dict[str, set[str]] = {}
        #: Devices whose bridge this harness instrumented (only those can be gated).
        self._bridged: set[str] = set()
        #: id(bridge) -> the device ids that share that bridge object (registry order).
        self._sharing: dict[int, list[str]] = {}
        for device_id, device in _devices(server).items():
            if str(getattr(device, "mode", "")) in HARDWARE_MODES:
                self._hardware.add(device_id)
            bridge = getattr(device, "bridge", None)
            safety = getattr(device, "safety", None)
            self._declared_interlocks[device_id] = [
                str(item.get("id")) for item in (getattr(safety, "interlocks", None) or [])
                if isinstance(item, Mapping) and item.get("id")
            ]
            if bridge is not None:
                self._instrument(device_id, bridge)
                self._bridged.add(device_id)

    # -- instrumentation ---------------------------------------------------
    def _instrument(self, device_id: str, bridge: Any) -> None:
        sharing = self._sharing.get(id(bridge))
        if sharing is not None:
            # Already wrapped for another device: the wrappers resolve the
            # target per call, so only the sharing set and the methods that
            # could not be shadowed are extended to this device.
            sharing.append(device_id)
            first = sharing[0]
            self.uninstrumented.extend(
                f"{device_id}:{entry.rpartition(':')[2]}" for entry in list(self.uninstrumented)
                if entry.rpartition(":")[0] == first
            )
            return
        sharing = self._sharing[id(bridge)] = [device_id]
        for name in INSTRUMENTED:
            original = getattr(bridge, name, None)
            if not callable(original) or getattr(original, "__mhs_harness__", None) is self:
                continue
            wrapper = self._wrap(sharing, name, original)
            wrapper.__mhs_harness__ = self  # type: ignore[attr-defined]
            try:
                setattr(bridge, name, wrapper)
            except (AttributeError, TypeError):
                self.uninstrumented.append(f"{device_id}:{name}")
                continue
            # A setattr that did not raise is not proof: a __setattr__ that
            # drops or forwards the write, or a class-level data descriptor,
            # leaves the bridge's own method in place.
            try:
                installed = getattr(bridge, name, None) is wrapper
            except Exception:  # noqa: BLE001 - an unreadable attribute is not shadowed
                installed = False
            if not installed:
                self.uninstrumented.append(f"{device_id}:{name}")
                continue
            self._installed.append((bridge, name))

    def _record(self, record: Record) -> None:
        with self._lock:
            self.records.append(record)

    # -- hardware gate (CON-031) -------------------------------------------
    def gate(self, hardware_ids: Sequence[str], *, allow_actuation: bool,
             read_capabilities: Mapping[str, Sequence[str]] | None = None) -> None:
        """Set the run's actuation policy: ``hardware_ids`` (from the manifests) join the devices the
        harness blocks unless ``allow_actuation``; ``read_capabilities`` maps a device to its read-verb
        capability ids, whose ``call`` is never blocked."""

        with self._lock:
            self._hardware.update(str(item) for item in hardware_ids)
            self.allow_actuation = bool(allow_actuation)
            for device_id, capability_ids in (read_capabilities or {}).items():
                self._reads.setdefault(str(device_id), set()).update(str(item) for item in capability_ids)

    def blocks(self, device_id: str) -> bool:
        """True when a write/invoke reaching ``device_id``'s bridge is refused before the driver.

        False for a device this harness does not instrument (another server's,
        or one without a bridge) and for a bridge whose actuating methods could
        not all be shadowed: such a device cannot be gated, so the suite does
        not send it negative tests.
        """

        device_id = str(device_id)
        return (not self.allow_actuation and device_id in self._hardware and device_id in self._bridged
                and not self.uninstrumented_for(device_id))

    def _refuses(self, device_ids: Sequence[str], method: str, capability_id: str | None) -> bool:
        """True when an actuating call on a bridge shared by ``device_ids`` is refused.

        Every hardware device sharing the bridge counts, whichever device the
        call names: a read-verb ``call`` passes only when it is a read of each
        of them.
        """
        if self.allow_actuation or method not in ACTUATING:
            return False
        hardware = [device_id for device_id in device_ids if device_id in self._hardware]
        if not hardware:
            return False
        return not (method == "call" and capability_id is not None
                    and all(capability_id in self._reads.get(device_id, ()) for device_id in hardware))

    def _target(self, sharing: Sequence[str], ctx: Any, named: Any = None) -> str:
        """The device a call is recorded under: ``ctx.device_id`` (or ``named``) when it shares the bridge.

        Without one, a bridge serving a single device records that device; a
        shared bridge records its first hardware device (fail closed: CON-031
        then sees the call), otherwise its first device.
        """
        if named is None:
            named = getattr(ctx, "device_id", None)
        if named is None and isinstance(ctx, Mapping):
            named = ctx.get("device_id")
        if named is not None and str(named) in sharing:
            return str(named)
        if len(sharing) == 1:
            return sharing[0]
        return next((device_id for device_id in sharing if device_id in self._hardware), sharing[0])

    def blocked(self, device_id: str | None = None, *, since: int = 0) -> list[Record]:
        """Calls the hardware gate refused before the driver."""
        return [record for record in self.actuations(device_id, since=since) if record.faulted == "blocked"]

    def _wrap(self, sharing: list[str], name: str, original: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap one bridge method; ``sharing`` is the (live) list of devices that share the bridge."""
        harness = self

        if name == "call":
            def call(capability_id: Any, *args: Any, **kwargs: Any) -> Any:
                ctx = args[1] if len(args) > 1 else kwargs.get("ctx")
                device_id = harness._target(sharing, ctx)
                faults = harness._faults.get(device_id, {})
                record = Record(device_id, "call", str(capability_id), test_id=harness.current_test)
                harness._enter(device_id)
                try:
                    if harness._refuses(sharing, "call", str(capability_id)):
                        record.faulted = "blocked"
                        raise _HardwareGate(device_id, "call", str(capability_id), record.test_id)
                    error = (faults.get("raise") or {}).get(str(capability_id))
                    if error is not None:
                        record.faulted = "raise"
                        raise error
                    seconds = (faults.get("delay") or {}).get(str(capability_id))
                    if seconds:
                        record.faulted = "delay"
                        deadline = time.monotonic() + float(seconds)
                        while time.monotonic() < deadline:
                            if _cancelled(ctx):
                                record.faulted = "delay-cancelled"
                                return {"status": "cancelled", "cancelled": True}
                            time.sleep(0.002)
                    result = original(capability_id, *args, **kwargs)
                    record.empty_result = _empty(result)
                    if str(capability_id) in (faults.get("drop") or set()):
                        record.faulted = "drop"
                        raise _LostResponse(str(capability_id))
                    return result
                except BaseException as exc:
                    record.ok = False
                    record.error = type(exc).__name__
                    raise
                finally:
                    harness._record(record)
                    harness._leave(device_id)

            return call

        if name == "interlocks":
            def interlocks(*args: Any, **kwargs: Any) -> Any:
                device_id = harness._target(sharing, kwargs.get("ctx"))
                record = Record(device_id, "interlocks", test_id=harness.current_test)
                try:
                    live = list(original(*args, **kwargs) or [])
                finally:
                    harness._record(record)
                forced = (harness._faults.get(device_id) or {}).get("interlocks")
                if not forced:
                    return live
                ids = list(dict.fromkeys(harness._declared_interlocks.get(device_id, [])
                                         + [str(item.get("id")) for item in live if isinstance(item, Mapping)]))
                states = {str(item.get("id")): dict(item) for item in live if isinstance(item, Mapping)}
                out = []
                for interlock_id in ids:
                    state = forced.get(interlock_id, forced.get("*"))
                    entry = dict(states.get(interlock_id) or {"id": interlock_id})
                    if state is not None:
                        entry["state"] = state
                        entry.setdefault("description", "forced by the conformance harness")
                    out.append(entry)
                return out

            return interlocks

        def generic(*args: Any, **kwargs: Any) -> Any:
            capability_id = None
            if name in ("read", "write") and args:
                capability_id = str(args[0])
            named = kwargs.get("device_id", args[0] if args else None) if name == "snapshot" else None
            device_id = harness._target(sharing, kwargs.get("ctx", _positional_ctx(name, args)),
                                        named if isinstance(named, str) else None)
            record = Record(device_id, name, capability_id, test_id=harness.current_test)
            mutating = name in ACTUATING or name == "estop"
            if mutating:
                harness._enter(device_id)
            try:
                if harness._refuses(sharing, name, capability_id):
                    record.faulted = "blocked"
                    raise _HardwareGate(device_id, name, capability_id, record.test_id)
                result = original(*args, **kwargs)
                record.empty_result = _empty(result)
                return result
            except BaseException as exc:
                record.ok = False
                record.error = type(exc).__name__
                raise
            finally:
                harness._record(record)
                if mutating:
                    harness._leave(device_id)

        return generic

    def _enter(self, device_id: str) -> None:
        with self._lock:
            self._inflight[device_id] = self._inflight.get(device_id, 0) + 1

    def _leave(self, device_id: str) -> None:
        with self._lock:
            self._inflight[device_id] = max(0, self._inflight.get(device_id, 0) - 1)

    def restore(self) -> None:
        """Remove the instance-level wrappers (the bridges' own methods apply again)."""

        for bridge, name in reversed(self._installed):
            try:
                delattr(bridge, name)
            except (AttributeError, TypeError):
                pass
        self._installed.clear()

    # -- observation -------------------------------------------------------
    def mark(self) -> int:
        with self._lock:
            return len(self.records)

    def since(self, mark: int = 0, *, device_id: str | None = None,
              methods: Sequence[str] | None = None) -> list[Record]:
        with self._lock:
            records = list(self.records[mark:])
        return [item for item in records
                if (device_id is None or item.device_id == device_id)
                and (methods is None or item.method in methods)]

    def uninstrumented_for(self, device_id: str, methods: Sequence[str] = ACTUATING) -> list[str]:
        """``methods`` of ``device_id``'s bridge the recorder could not shadow (registry order)."""

        missing = {entry.split(":")[-1] for entry in self.uninstrumented if entry.rpartition(":")[0] == device_id}
        return [name for name in INSTRUMENTED if name in methods and name in missing]

    def actuations(self, device_id: str | None = None, *, since: int = 0) -> list[Record]:
        """Bridge calls that could change the device (``call``, ``write``, ``restore``), blocked ones included."""
        return self.since(since, device_id=device_id, methods=ACTUATING)

    def estops(self, device_id: str | None = None, *, since: int = 0) -> list[Record]:
        return self.since(since, device_id=device_id, methods=("estop",))

    def busy(self, device_id: str) -> bool:
        with self._lock:
            return self._inflight.get(device_id, 0) > 0

    def wait_idle(self, device_id: str, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.busy(device_id):
                return True
            time.sleep(0.002)
        return not self.busy(device_id)

    # -- faults ------------------------------------------------------------
    @contextlib.contextmanager
    def _fault(self, device_id: str, key: str, value: Any) -> Iterator[None]:
        faults = self._faults.setdefault(device_id, {})
        previous = faults.get(key)
        faults[key] = value
        try:
            yield
        finally:
            if previous is None:
                faults.pop(key, None)
            else:
                faults[key] = previous

    def force_interlocks(self, device_id: str, state: str = "open", ids: Sequence[str] | None = None):
        """Report the given interlocks (default: all declared) in ``state`` (``open``/``unknown``)."""
        forced = {str(item): state for item in ids} if ids else {"*": state}
        return self._fault(device_id, "interlocks", forced)

    def delay_calls(self, device_id: str, capability_id: str, seconds: float):
        """Delay calls of ``capability_id``; a cancellation during the delay ends it as cancelled."""
        return self._fault(device_id, "delay", {str(capability_id): float(seconds)})

    def drop_responses(self, device_id: str, capability_id: str):
        """Let calls of ``capability_id`` act, then lose their response (unknown outcome)."""
        return self._fault(device_id, "drop", {str(capability_id)})

    def raise_in_calls(self, device_id: str, capability_id: str, error: BaseException):
        return self._fault(device_id, "raise", {str(capability_id): error})


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------


def _split(produced: Any) -> tuple[Any, Callable[[], None] | None]:
    if isinstance(produced, tuple) and len(produced) == 2 and callable(produced[1]):
        return produced[0], produced[1]
    return produced, None


def run_suite_inprocess(factory: Callable[[], Any], profile: str = "MHS-Sim", level: str = "CL3", *,
                        fresh_groups: bool = True, **options: Any) -> dict[str, Any]:
    """Run the suite against fresh in-process endpoints built by ``factory``.

    ``options`` are those of :func:`mhs.conformance.run_suite` (``allow_actuation``,
    ``read_only``, ``fixtures``, ``approvals``, ``source_commit``, ``save_path``,
    ``strict``, ``limitations``, ``include_optional``).  With ``fresh_groups``
    false every group shares the first endpoint, like a run against a remote
    endpoint.
    """

    from mhs.conformance.suite import execute

    instances: list[tuple[Any, Any, Harness, Callable[[], None] | None]] = []
    allow_actuation = bool(options.get("allow_actuation", False))

    def connect(group: str) -> tuple[Any, Harness]:
        server, cleanup = _split(factory())
        # Gate before the first request: hardware writes are refused at the bridge (CON-031).
        harness = Harness(server, allow_actuation=allow_actuation)
        client = client_for(server)
        instances.append((server, client, harness, cleanup))
        return client, harness

    try:
        return execute(connect, profile=profile, level=level, fresh_groups=fresh_groups, **options)
    finally:
        for _server, client, harness, cleanup in reversed(instances):
            for closer in (getattr(client, "close", None), harness.restore, cleanup):
                if callable(closer):
                    try:
                        closer()
                    except Exception:  # noqa: BLE001 - teardown must not mask the verdict
                        pass


def reference_factory(name: str, **options: Any) -> Callable[[], tuple[Any, Callable[[], None]]]:
    """A factory of fresh reference endpoints (``conveyor``, ``lab``, ``arm``, ``replay``).

    ``options`` go to :func:`mhs.reference.build_endpoint` (``test_profile``,
    ``noise``, ``seed``, ``bundle``, ``endpoint_id``).  The reference endpoints
    are protocol fixtures, not driver templates.
    """

    def factory() -> tuple[Any, Callable[[], None]]:
        from mhs.reference import build_endpoint, build_server

        spec = build_endpoint(name, **options)
        return build_server(spec, log_ready=False), spec.close

    factory.__name__ = f"reference_{name}"
    return factory
