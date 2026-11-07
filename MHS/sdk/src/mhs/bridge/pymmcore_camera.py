"""Finite, retained single-camera operations for controlled native-shaped fixtures.

Native admission is deliberately closed. Python declaration evidence cannot
establish constructor ownership, the binary build or bounded adapter stopping.
No NumPy, ImSwitch, pymmcore or native library is imported at module import time.
"""
from __future__ import annotations

import inspect
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, fields
from typing import Any, Callable, Mapping

from .. import signals
from ..artifacts import publisher_from_context
from .base import Bridge, BridgeContext, busy, driver_failed, make_mhs_error, outcome_unknown, unsupported
from .python_execution import RetainedCall

CAPTURE = "cap.sensing.image.v1"
_ORDINARY = frozenset({"construction", "prepare", "acquisition", "configuration", "release", "observation"})
_CORE_METHODS = ("getLoadedDevices", "getCameraDevice", "getAutoShutter", "getShutterDevice",
                 "getImageWidth", "getImageHeight", "getExposure", "getBytesPerPixel",
                 "getNumberOfComponents", "isSequenceRunning", "getROI", "getProperty",
                 "clearCircularBuffer", "getRemainingImageCount", "stopSequenceAcquisition", "unloadDevice")
_OWNERS_LOCK = threading.Lock()
_OWNERS: dict[int, tuple[Any, "CameraLease"]] = {}


@dataclass(frozen=True)
class _StopProof:
    state: Mapping[str, Any]
    ordinary_epoch: int
    ordinary_pending: bool


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite and numeric")
    return float(value)


def _defaults(value):
    if value is None or type(value) in (str, int, float, bool):
        return (type(value), value)
    if type(value) is tuple:
        return (tuple, tuple(_defaults(x) for x in value))
    raise ValueError("mutable or executable camera method defaults are unsupported")


def _methods(receiver, names):
    cls = type(receiver)
    if (inspect.getattr_static(cls, "__getattribute__") is not object.__getattribute__
            or inspect.getattr_static(cls, "__getattr__", None) is not None):
        raise ValueError("dynamic camera receivers are unsupported")
    members = object.__getattribute__(receiver, "__dict__")
    result = {}
    for name in names:
        fn = inspect.getattr_static(cls, name, None)
        if (not inspect.isfunction(fn) or fn.__closure__ is not None or name in members
                or inspect.iscoroutinefunction(fn) or inspect.isgeneratorfunction(fn)):
            raise ValueError(f"{name} must be an unshadowed synchronous class method")
        result[name] = (fn, fn.__code__, _defaults(fn.__defaults__),
                        tuple((key, _defaults(value)) for key, value in (fn.__kwdefaults__ or {}).items()))
    return result


def _check_methods(receiver, proof):
    current = _methods(receiver, proof)
    if any(current[name][0] is not expected[0] or current[name][1] is not expected[1]
           or current[name][2:] != expected[2:] for name, expected in proof.items()):
        raise ValueError("camera method identity/code/defaults changed")


def _factory_proof(factory):
    if factory is None:
        return None
    create = factory.create
    receiver = create.__self__ if inspect.ismethod(create) else None
    fn = create.__func__ if receiver is not None else create
    if not inspect.isfunction(fn) or inspect.iscoroutinefunction(fn) or inspect.isgeneratorfunction(fn):
        raise ValueError("a controlled factory must be a synchronous Python function or bound method")
    # This fingerprints the fixture declaration, not arbitrary mutable objects
    # captured by a trusted fake. No native factory is admitted by this proof.
    cells = tuple((cell, cell.cell_contents) for cell in (fn.__closure__ or ()))
    return (create, receiver, fn, fn.__code__, _defaults(fn.__defaults__),
            tuple((key, _defaults(value)) for key, value in (fn.__kwdefaults__ or {}).items()),
            cells, factory.core_type, factory.manager_type)


def _check_factory(factory, expected):
    current = _factory_proof(factory)
    if expected is None:
        if current is not None:
            raise ValueError("camera factory changed")
        return
    if (any(current[i] is not expected[i] for i in (0, 1, 2, 3, 7, 8))
            or current[4:6] != expected[4:6] or len(current[6]) != len(expected[6])
            or any(a is not b or value is not old for (a, value), (b, old) in zip(current[6], expected[6]))):
        raise ValueError("camera factory identity/code/defaults/closure changed")


@dataclass(frozen=True)
class CameraFactory:
    """Explicit controlled-fixture types; never a native factory authorization."""
    create: Callable[["CameraLease"], Any]
    core_type: type
    manager_type: type

    def __post_init__(self):
        if not callable(self.create) or not isinstance(self.core_type, type) or not isinstance(self.manager_type, type):
            raise ValueError("a controlled lease factory and two exact receiver types are required")


@dataclass(frozen=True)
class CameraProfile:
    """Immutable software limits; supplied exposure bounds are operator limits."""
    camera: str
    pixel_format: str
    exposure_min_ms: float
    exposure_max_ms: float
    timeout_ms: int = 2000
    stop_timeout_ms: int = 500
    max_pixels: int = 4 * 1024 * 1024
    max_bytes: int = 2 * 1024 * 1024
    binning_values: tuple[int, ...] = ()
    sensor_width: int | None = None
    sensor_height: int | None = None

    def __post_init__(self):
        if type(self.camera) is not str or not self.camera or len(self.camera) > 64:
            raise ValueError("a fixed camera label of 1..64 characters is required")
        if self.pixel_format not in {"mono8", "mono16", "rgb8"}:
            raise ValueError("explicit mono8, mono16 or RGB8 profile is required")
        lo, hi = _number(self.exposure_min_ms, "exposure minimum"), _number(self.exposure_max_ms, "exposure maximum")
        if not 0 <= lo <= hi <= 600000:
            raise ValueError("finite nonnegative operator exposure limits are required")
        _integer(self.timeout_ms, 1, 30000, "timeout_ms")
        _integer(self.stop_timeout_ms, 1, 30000, "stop_timeout_ms")
        _integer(self.max_pixels, 1, 16 * 1024 * 1024, "max_pixels")
        _integer(self.max_bytes, 1, 16 * 1024 * 1024, "max_bytes")
        if type(self.binning_values) is not tuple or len(set(self.binning_values)) != len(self.binning_values):
            raise ValueError("binning choices must be an immutable unique tuple")
        for value in self.binning_values:
            _integer(value, 1, 16, "binning")
        if (self.sensor_width is None) != (self.sensor_height is None):
            raise ValueError("both fixed sensor dimensions are required for ROI")
        if self.sensor_width is not None:
            _integer(self.sensor_width, 1, 8192, "sensor width")
            _integer(self.sensor_height, 1, 8192, "sensor height")


class CameraLease:
    """Own a core before a factory initializes its camera or returns a manager.

    A controlled factory receives this ledger, registers the core immediately,
    then constructs its manager. Failed or late construction cannot erase it.
    The lease never calls global core reset or reloads a configuration.
    """
    def __init__(self, camera: str, factory: CameraFactory | None, record_log=None):
        self.camera = camera
        self.factory = factory
        self._record_log = record_log
        self._lock = threading.RLock()
        self.core = None
        self.manager = None
        self.released = False
        self._methods = {}
        self._core_methods = {}
        self.unresolved_values = []

    def register_core(self, core):
        with _OWNERS_LOCK, self._lock:
            if self.core is not None or self.released:
                raise ValueError("camera lease already has a core or was released")
            if id(core) in _OWNERS:
                raise ValueError("core already has an owner")
            # Transfer the handle before checking its declaration. A rejected
            # newly constructed receiver must not disappear from the ledger.
            _OWNERS[id(core)] = (core, self)
            self.core = core
            if self.factory is None or type(core) is not self.factory.core_type:
                raise ValueError("core differs from the exact declared fixture type")
            methods = _methods(core, _CORE_METHODS)
            self._core_methods = methods

    def bind_manager(self, manager):
        with self._lock:
            # A returned receiver may own native state even when its declaration
            # is invalid. Keep it before any property or method inspection.
            self.unresolved_values.append(manager)
            if self.core is None or self.manager is not None or self.released:
                raise ValueError("manager requires a previously registered owned core")
            if type(manager) is not self.factory.manager_type:
                raise ValueError("manager differs from the exact declared fixture type")
            members = object.__getattribute__(manager, "__dict__")
            if members.get("_core") is not self.core or members.get("_label") != self.camera:
                raise ValueError("manager does not belong to the declared camera/core lease")
            methods = _methods(manager, ("acquireSingleFrame", "acquireExclusive", "releaseExclusive",
                                         "setParameter", "crop", "setBinning"))
            self.manager, self._methods = manager, methods
            self.unresolved_values.pop()

    def check(self):
        with self._lock:
            if self.released or self.core is None or self.manager is None:
                raise ValueError("camera construction/ownership is incomplete")
            members = object.__getattribute__(self.manager, "__dict__")
            if members.get("_core") is not self.core or members.get("_label") != self.camera:
                raise ValueError("camera receiver identity changed")
            if type(self.manager) is not self.factory.manager_type or type(self.core) is not self.factory.core_type:
                raise ValueError("camera receiver class changed")
            _check_methods(self.manager, self._methods)
            _check_methods(self.core, self._core_methods)

    def method(self, name, *args, **kwargs):
        self.check()
        fn = self._methods[name][0].__get__(self.manager)
        if self._record_log is not None:
            self._record_log.member("", name, "found")
            fn = self._record_log.wrap(name, fn)
        return fn(*args, **kwargs)

    def core_call(self, name, *args):
        with self._lock:
            if self.released or self.core is None:
                raise ValueError("no owned camera core")
            _check_methods(self.core, self._core_methods)
            fn = self._core_methods[name][0].__get__(self.core)
        if self._record_log is not None:
            path = "_core." + name
            self._record_log.member("", path, "found")
            fn = self._record_log.wrap(path, fn)
        return fn(*args)

    def release_core(self):
        # Native unloading happens first, outside this short bookkeeping lock.
        with _OWNERS_LOCK, self._lock:
            if self.core is not None:
                owner = _OWNERS.get(id(self.core))
                if owner is None or owner[0] is not self.core or owner[1] is not self:
                    raise ValueError("core ownership changed during cleanup")
                del _OWNERS[id(self.core)]
            self.released = True


class _CameraCall(RetainedCall):
    """Do not authorize native entry until worker startup has returned.

    A fault injected after real Thread.start still leaves a tracked worker, but
    its dispatch gate is revoked. Failure before a worker exists can complete
    that revoked call without pretending a native operation stopped.
    """
    def __init__(self, label, execute, finished, *, deadline):
        self._startup_settled = threading.Event()
        self._startup_error = None
        def admitted(item):
            self._startup_settled.wait()
            if self._startup_error is not None:
                raise self._startup_error
            return execute(item)
        super().__init__(label, admitted, finished, deadline=deadline)

    def start(self):
        try:
            self.thread.start()
        except BaseException as exc:
            self._startup_error = outcome_unknown("camera worker startup failed; native dispatch was not authorized")
            self._startup_settled.set()
            if self.thread.ident is None:
                # Even a later injected start cannot pass the revoked gate.
                # No native function was admitted, so no native owner is live.
                self.error = self._startup_error
                self.done_at = time.monotonic()
                self.finished(self)
                self.done.set()
            raise self._startup_error from exc
        else:
            self._startup_settled.set()


class PymmcoreCameraBridge(Bridge):
    bridge_kind = "pymmcore-plus"
    bridge_id = "mhs.bridge.pymmcore-camera"

    def __init__(self, profile: CameraProfile, factory: CameraFactory | None,
                 *, backend: str = "fake", resource_id: str = "main", device_id=None, record_log=None):
        if backend != "fake":
            raise make_mhs_error("MHS.DEVICE.NOT_READY", "native camera admission is unresolved (B01-B10)",
                                 {"retryable": False})
        if type(profile) is not CameraProfile:
            raise ValueError("an immutable CameraProfile is required")
        if factory is not None and type(factory) is not CameraFactory:
            raise ValueError("controlled camera construction requires an exact CameraFactory")
        super().__init__(device_id=device_id)
        if record_log is not None:
            from ..testing.recorder import RecordLog
            if type(record_log) is not RecordLog:
                raise ValueError("camera recording requires the SDK's own RecordLog")
            record_log.phase_codes[PymmcoreCameraBridge._observe.__code__] = "read"
        self.profile, self.factory, self.resource_id = profile, factory, resource_id
        self._policy = (profile, factory, resource_id)
        self._profile_values = tuple((item.name, _defaults(getattr(profile, item.name))) for item in fields(profile))
        self._factory_values = _factory_proof(factory)
        self.lease = CameraLease(profile.camera, factory, record_log)
        self._activity = threading.RLock()
        self._jobs: dict[str, RetainedCall] = {}
        self._history = deque(maxlen=64)
        self._startup_failures = deque(maxlen=64)
        self._construction_entered = False
        self._counter = 0
        self._ordinary_epoch = 0
        self._claim = None
        self._request_owner = None
        self._request_waiter_done = True
        self._request_complete = threading.Event()
        self._request_complete.set()
        self._safety_requests = 0
        self._safety_sequence = 0
        self._cancel = threading.Event()
        self._latched = False
        self._uncertain = False
        self._fault = None
        self._closing = False
        self._cleanup_complete = False
        self._safe = False
        self._safe_proof: _StopProof | None = None
        self._cache = {"camera": profile.camera, "exposure_ms": None, "width": None, "height": None,
                       "acquiring": None, "binning": None, "roi": None, "state_stale": True}

    def _deadline(self, ctx, limit=None):
        context = BridgeContext.coerce(ctx)
        return context, time.monotonic() + min(context.remaining_ms(), limit or self.profile.timeout_ms) / 1000.

    def _reap(self):
        # Retired jobs cannot later publish a result: the thread and its callback
        # have already ended. Re-read error here, never trust a saved success flag.
        for kind, job in list(self._jobs.items()):
            if job.done.is_set():
                if job.error is not None:
                    if not isinstance(job.error, signals.OutcomeUnknown):
                        self._fault = self._fault or f"{kind}: {type(job.error).__name__}"
                    self._uncertain, self._safe = True, False
                self._history.append((kind, type(job.error).__name__ if job.error else None))
                del self._jobs[kind]
        if (self._request_owner is not None and self._request_waiter_done
                and not _ORDINARY.intersection(self._jobs)):
            self._request_owner = None
            self._request_complete.set()
            # A stop may have sampled idle before this owner performed a late
            # effect. Retirement invalidates that observation on every outcome.
            self._ordinary_epoch += 1
            self._safe = False

    def _finished(self, job):
        with self._activity:
            if job.error is not None:
                if not isinstance(job.error, signals.OutcomeUnknown):
                    self._fault = self._fault or f"{job.label}: {type(job.error).__name__}"
                self._uncertain, self._safe = True, False

    def _run(self, kind, fn, deadline, cancel=None):
        def execute(item):
            with self._activity:
                if self._closing and kind != "cleanup":
                    raise outcome_unknown("camera closed before this native phase entered")
            return fn()
        with self._activity:
            self._reap()
            if self._closing and kind != "cleanup":
                raise outcome_unknown("camera is closing; no new native phase may enter")
            if kind in self._jobs:
                raise busy(f"camera {kind} owner is still in flight")
            job = _CameraCall(kind, execute, self._finished, deadline=deadline)
            self._jobs[kind] = job
        # A delayed start must not hold the lock needed by stop or close. The
        # retained job already blocks any replacement ordinary owner.
        try:
            job.start()
        except BaseException:
            with self._activity:
                self._startup_failures.append(job)
                self._fault = self._fault or f"{kind}: worker startup failed"
                self._uncertain, self._safe = True, False
                self._cancel.set()
                self._reap()
            raise
        def abandon():
            with self._activity:
                self._uncertain, self._safe = True, False
                self._cancel.set()
        try:
            return job.wait(deadline=deadline, cancel_event=cancel, abandoned=abandon)
        except signals.Cancelled as exc:
            raise outcome_unknown("camera cancellation requested; native ownership remains retained") from exc
        finally:
            with self._activity:
                self._reap()

    def _guard(self, epoch, deadline, context):
        with self._activity:
            self._check_policy()
            if self._closing or self._latched or epoch != self.estop_epoch:
                raise outcome_unknown("camera request interrupted by stop or close")
            if context.cancelled() or self._cancel.is_set() or time.monotonic() >= deadline:
                self._uncertain, self._safe = True, False
                self._cancel.set()
                raise outcome_unknown("camera request expired or was cancelled; reconcile the native operation")
            if self._fault:
                raise outcome_unknown("camera has unreconciled native failure")

    def _check_policy(self):
        if (self.profile is not self._policy[0] or self.factory is not self._policy[1]
                or self.resource_id != self._policy[2] or self.lease.factory is not self.factory):
            raise ValueError("camera construction/profile authority changed")
        if tuple((item.name, _defaults(getattr(self.profile, item.name))) for item in fields(self.profile)) != self._profile_values:
            raise ValueError("camera profile values changed")
        _check_factory(self.factory, self._factory_values)

    def _construct(self):
        if self.factory is None:
            raise ValueError("no controlled construction factory")
        self._check_policy()
        with self._activity:
            self._construction_entered = True
        manager = self.factory.create(self.lease)
        self.lease.bind_manager(manager)

    def _identity(self):
        self._check_policy()
        self.lease.check()
        core, label = self.lease.core, self.profile.camera
        members = object.__getattribute__(self.lease.manager, "__dict__")
        if members.get("_triggerMode") != "software":
            raise ValueError("only the explicit software-triggered camera profile is supported")
        devices = self.lease.core_call("getLoadedDevices")
        if (type(devices) not in (tuple, list) or any(type(x) is not str for x in devices)
                or label not in devices or set(devices) - {"Core", label}
                or self.lease.core_call("getCameraDevice") != label):
            raise ValueError("camera identity or exclusive device ownership changed")
        if self.lease.core_call("getAutoShutter") is not False or self.lease.core_call("getShutterDevice") != "":
            raise ValueError("unmodelled illumination requires a separate profile")
        return core

    def _observe(self):
        core = self._identity()
        get = self.lease.core_call
        p = self.profile
        width = _integer(get("getImageWidth"), 1, 8192, "native width")
        height = _integer(get("getImageHeight"), 1, 8192, "native height")
        exposure = _number(get("getExposure"), "native exposure")
        if not p.exposure_min_ms <= exposure <= p.exposure_max_ms:
            raise ValueError("native exposure is outside the operator envelope")
        bpp, components = {"mono8": (1, 1), "mono16": (2, 1), "rgb8": (4, 4)}[p.pixel_format]
        actual_bpp, actual_components = get("getBytesPerPixel"), get("getNumberOfComponents")
        if type(actual_bpp) is not int or type(actual_components) is not int or (actual_bpp, actual_components) != (bpp, components):
            raise ValueError("native pixel layout differs from the declared backend profile")
        running = get("isSequenceRunning", p.camera)
        if type(running) is not bool:
            raise ValueError("native acquisition state is not a boolean")
        if width * height > p.max_pixels or width * height * (3 if p.pixel_format == "rgb8" else bpp) > p.max_bytes:
            raise ValueError("native frame exceeds the software pixel budget")
        roi = get("getROI", p.camera) if p.sensor_width is not None else None
        if roi is not None:
            if type(roi) not in (list, tuple) or len(roi) != 4:
                raise ValueError("native ROI is invalid")
            roi = dict(zip(("x", "y", "width", "height"), roi))
            self._check_roi(roi)
        binning = None
        if p.binning_values:
            raw = get("getProperty", p.camera, "Binning")
            if type(raw) is not str or raw not in tuple(str(n) for n in p.binning_values):
                raise ValueError("native binning is outside the declared choices")
            binning = int(raw)
        state = {"camera": p.camera, "width": width, "height": height, "exposure_ms": exposure,
                 "acquiring": running, "binning": binning, "roi": roi, "state_stale": False}
        with self._activity:
            self._cache = state
        return state

    def _admit(self, ctx):
        context, deadline = self._deadline(ctx)
        with self._activity:
            self._reap()
            self._check_policy()
            if self._closing or self._latched:
                raise make_mhs_error("MHS.SAFETY.ESTOP_ENGAGED", "camera is stopped or closing", {"retryable": False})
            if self._request_owner is not None or self._jobs or self._uncertain or self._fault or self._claim or self._safety_requests:
                raise busy("camera native ownership must settle and be reconciled before another request")
            if context.cancelled() or time.monotonic() >= deadline:
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "request cancelled or expired before native entry", {"retryable": False})
            self._counter += 1
            token = self._counter
            self._request_owner = token
            self._ordinary_epoch += 1
            self._request_waiter_done = False
            self._request_complete.clear()
            self._safe = False
            self._cancel = threading.Event()
            epoch = self.estop_epoch
        return context, deadline, epoch, token

    def _prepare(self, context, deadline, epoch, token):
        if self.lease.manager is None:
            self._run("construction", self._construct, deadline, context.cancel_event)
        self._guard(epoch, deadline, context)
        def prepare():
            self._guard(epoch, deadline, context)
            state = self._observe()
            members = object.__getattribute__(self.lease.manager, "__dict__")
            if state["acquiring"] or members.get("_exclusiveOwner") is not None or members.get("_running") is not False:
                raise ValueError("camera is already acquiring; no foreign sequence is preempted")
            name = f"mhs-{token}"
            if self.lease.method("acquireExclusive", name, timeout=0.0) is not True:
                raise ValueError("camera exclusive claim was refused")
            with self._activity:
                self._claim = name
            self._identity()
            self.lease.core_call("clearCircularBuffer")
            remaining = self.lease.core_call("getRemainingImageCount")
            if type(remaining) is not int or remaining != 0:
                raise ValueError("camera buffer could not be verified empty")
            return state
        return self._run("prepare", prepare, deadline, context.cancel_event)

    def _release_claim(self, deadline):
        with self._activity:
            name = self._claim
        if name is not None:
            def release():
                self.lease.method("releaseExclusive", name, restoreLive=False)
                if object.__getattribute__(self.lease.manager, "__dict__").get("_exclusiveOwner") is not None:
                    raise ValueError("exclusive camera claim did not release")
                with self._activity:
                    self._claim = None
            self._run("release", release, deadline)

    def _stop(self, deadline):
        def stop():
            # Capture in the worker before native stop dispatch, not when a
            # later caller joins this retained stop or receives its old result.
            with self._activity:
                self._reap()
                epoch = self._ordinary_epoch
                ordinary_pending = self._request_owner is not None or bool(_ORDINARY.intersection(self._jobs))
            self._identity()
            self.lease.core_call("stopSequenceAcquisition", self.profile.camera)
            state = self._observe()
            if state["acquiring"]:
                raise ValueError("camera still reports an active sequence after stop")
            return _StopProof(state, epoch, ordinary_pending)
        with self._activity:
            self._reap()
            pending = self._jobs.get("stop")
        if pending is not None:
            # Reuse the existing stop owner. Never overlap replacement stop jobs.
            return pending.wait(deadline=deadline, cancel_event=None,
                                abandoned=lambda: self._mark_uncertain())
        return self._run("stop", stop, deadline)

    def _current_stop(self, proof):
        # Called with _activity held, including at the final safety commit.
        return (type(proof) is _StopProof and not proof.ordinary_pending
                and proof.ordinary_epoch == self._ordinary_epoch
                and self._request_owner is None and not _ORDINARY.intersection(self._jobs))

    def _mark_uncertain(self):
        with self._activity:
            self._uncertain, self._safe = True, False
            self._cancel.set()

    def _check_roi(self, value):
        p = self.profile
        if p.sensor_width is None or type(value) is not dict or set(value) != {"x", "y", "width", "height"}:
            raise ValueError("ROI is not enabled or has unknown fields")
        x = _integer(value["x"], 0, p.sensor_width - 1, "ROI x")
        y = _integer(value["y"], 0, p.sensor_height - 1, "ROI y")
        width = _integer(value["width"], 1, p.sensor_width, "ROI width")
        height = _integer(value["height"], 1, p.sensor_height, "ROI height")
        if x + width > p.sensor_width or y + height > p.sensor_height:
            raise ValueError("ROI exceeds the operator sensor bounds")

    def call(self, capability_id, args=None, ctx=None):
        if capability_id != CAPTURE:
            raise unsupported(capability_id)
        args = dict(args or {})
        if set(args) - {"camera", "width", "height", "exposure_ms", "format"}:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "unknown capture input", {"retryable": False})
        if args.get("camera", self.profile.camera) != self.profile.camera or args.get("format", "png") != "png":
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "fixed camera and PNG output required", {"retryable": False})
        from .camera_pixels import detach_pixels, require_numpy
        require_numpy()  # missing optional numeric dependency refuses before construction/exposure
        publisher = publisher_from_context(BridgeContext.coerce(ctx))
        if publisher is None:
            raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", "camera capture requires an artifact store")
        publisher.preflight(1)
        context, deadline, epoch, token = self._admit(ctx)
        acquisition_admitted = False
        try:
            state = self._prepare(context, deadline, epoch, token)
            for name in ("width", "height", "exposure_ms"):
                if name in args and (type(args[name]) is bool or args[name] != state[name]):
                    raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"{name} must equal the current verified setting", {"retryable": False})
            size = state["width"] * state["height"] * {"mono8": 1, "mono16": 2, "rgb8": 3}[self.profile.pixel_format]
            raw_size = size + state["height"]
            # zlib compressBound plus fixed PNG framing, including block overhead.
            bound = raw_size + (raw_size >> 12) + (raw_size >> 14) + (raw_size >> 25) + 13 + 57
            if bound > min(publisher.max_bytes, self.profile.max_bytes):
                raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", "artifact budget cannot hold the complete bounded frame")
            publisher.preflight(bound)
            def acquire():
                self._guard(epoch, deadline, context)
                value = self.lease.method("acquireSingleFrame", cancelEvent=self._cancel,
                                          timeout=max(.001, deadline - time.monotonic()), pollInterval=.01)
                if type(value) is not tuple or len(value) != 2 or type(value[1]) is not str:
                    self.lease.unresolved_values.append(value)
                    raise ValueError("selected acquisition must return (pixels, exact status string)")
                if value[1] != "done":
                    if value[1] in {"cancelled", "timeout"}:
                        raise outcome_unknown("camera acquisition interrupted; final labelled stop is required")
                    raise ValueError("camera did not complete the acquisition")
                pixels = detach_pixels(value[0], pixel_format=self.profile.pixel_format,
                                       width=state["width"], height=state["height"],
                                       max_pixels=self.profile.max_pixels, max_bytes=self.profile.max_bytes)
                self.lease.check()
                return pixels
            acquisition_admitted = True
            pixels = self._run("acquisition", acquire, deadline, context.cancel_event)
            self._guard(epoch, deadline, context)
            after = self._stop(deadline).state
            if any(after[k] != state[k] for k in ("width", "height", "exposure_ms", "roi", "binning")):
                self._mark_uncertain()
                raise outcome_unknown("camera settings changed during acquisition")
            self._guard(epoch, deadline, context)
            encoded = pixels.png(min(self.profile.max_bytes, publisher.max_bytes))
            self._guard(epoch, deadline, context)
            descriptor = publisher.publish(encoded, "image/png")
            self._guard(epoch, deadline, context)
            return {"image_ref": descriptor["uri"], "width": pixels.width, "height": pixels.height,
                    "media_type": "image/png", "exposure_ms": state["exposure_ms"]}
        except BaseException:
            if acquisition_admitted:
                self._mark_uncertain()
                try:
                    # Cancellation alone cannot stop a blocked/late native
                    # start. This bounded protective lane retains its owner
                    # and never acknowledges safety while acquisition lives.
                    self._stop(time.monotonic() + self.profile.stop_timeout_ms / 1000.)
                except BaseException:
                    self._mark_uncertain()
            raise
        finally:
            self._finish_request(token, deadline)

    def _finish_request(self, token, deadline):
        with self._activity:
            self._reap()
            # A final capture stop can outlive the caller too. Keep the
            # exclusive claim until that native stop owner has settled; a
            # later safe-state reconciliation or close releases it explicitly.
            pending = bool((_ORDINARY | {"stop"}).intersection(self._jobs))
        try:
            if not pending and not self._closing:
                self._release_claim(deadline)
        finally:
            with self._activity:
                if self._request_owner == token:
                    self._request_waiter_done = True
                self._reap()

    def write(self, resource_id, patch, ctx=None):
        if resource_id != self.resource_id:
            raise unsupported(resource_id, "resource")
        patch = dict(patch)
        if len(patch) != 1:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", "configure exactly one camera field per command", {"retryable": False})
        name, value = next(iter(patch.items()))
        try:
            if name == "exposure_ms":
                value = _number(value, "exposure_ms")
                if not self.profile.exposure_min_ms <= value <= self.profile.exposure_max_ms:
                    raise ValueError("exposure is outside the operator envelope")
            elif name == "roi":
                self._check_roi(value)
            elif name == "binning":
                if type(value) is not int or value not in self.profile.binning_values:
                    raise ValueError("unsupported binning")
            else:
                raise ValueError("unknown camera configuration field")
        except ValueError as exc:
            raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", str(exc), {"retryable": False}) from exc
        context, deadline, epoch, token = self._admit(ctx)
        try:
            self._prepare(context, deadline, epoch, token)
            def configure():
                self._guard(epoch, deadline, context)
                if name == "exposure_ms":
                    self.lease.method("setParameter", "Exposure", value)
                elif name == "roi":
                    self.lease.method("crop", *(value[k] for k in ("x", "y", "width", "height")))
                else:
                    self.lease.method("setBinning", value)
                observed = self._observe()
                if observed[name] != value:
                    raise ValueError("native camera setting did not match the requested value")
                return observed
            result = self._run("configuration", configure, deadline, context.cancel_event)
            self._guard(epoch, deadline, context)
            return result
        finally:
            self._finish_request(token, deadline)

    def read(self, resource_id, fields=None, ctx=None):
        if resource_id != self.resource_id:
            raise unsupported(resource_id, "resource")
        with self._activity:
            self._reap()
            refresh = (self.lease.manager is not None and not self._jobs and self._request_owner is None
                       and not self._latched and not self._uncertain and not self._fault and not self._closing
                       and not self._safety_requests)
            token = None
            if refresh:
                context, deadline, epoch, token = self._admit(ctx)
        if refresh:
            try:
                self._run("observation", self._observe, deadline, context.cancel_event)
                self._guard(epoch, deadline, context)
            finally:
                self._finish_request(token, deadline)
        with self._activity:
            state = dict(self._cache)
            state["state_stale"] = not refresh
        return state if fields is None else {key: state[key] for key in fields if key in state}

    @property
    def estop_native(self):
        return "CMMCorePlus.stopSequenceAcquisition(camera_label)"

    def estop(self, reason="", ctx=None):
        with self._activity:
            self._engage_estop()
            self._latched, self._safe = True, False
            self._cancel.set()
        return self.safe_state(ctx)

    def safe_state(self, ctx=None):
        _, deadline = self._deadline(ctx, self.profile.stop_timeout_ms)
        with self._activity:
            self._reap()
            self._safe = False
            self._safety_sequence += 1
            generation = self._safety_sequence
            self._safety_requests += 1
            owner_at_stop = self._request_owner
            self._cancel.set()
            if self.lease.manager is None:
                self._safety_requests -= 1
                raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "native construction has not settled")
        try:
            proof = self._stop(deadline)
            with self._activity:
                self._reap()
                if self._jobs or owner_at_stop is not None or not self._current_stop(proof):
                    raise ValueError("stop observation predates retirement of native ownership")
            self._release_claim(deadline)
            with self._activity:
                self._reap()
                if (self._jobs or not self._current_stop(proof) or self._fault or self._closing
                        or generation != self._safety_sequence or self._safety_requests != 1):
                    raise ValueError("camera native failure or cleanup ownership remains")
                self._safe_proof = proof
                self._safe = True
            return {"achieved": True}
        except BaseException as exc:
            self._mark_uncertain()
            raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "camera stop could not be confirmed") from exc
        finally:
            with self._activity:
                self._safety_requests -= 1

    def reset(self, ctx=None):
        _, deadline = self._deadline(ctx)
        with self._activity:
            self._reap()
            epoch = self.estop_epoch
            generation = self._safety_sequence
            if (self._jobs or self._request_owner is not None or self._claim or self._fault
                    or self._closing or not self._safe or not self._current_stop(self._safe_proof)
                    or self._safety_requests):
                raise make_mhs_error("MHS.SAFETY.RESET_REFUSED", "camera reset requires settled owned work and fresh safe state", {"retryable": False})
            self._safety_requests += 1
        try:
            observed = self._run("reset_observation", self._observe, deadline)
            with self._activity:
                self._reap()
                if (observed["acquiring"] or self._jobs or self._request_owner is not None or self._claim
                        or self._fault or self._closing or not self._current_stop(self._safe_proof)
                        or epoch != self.estop_epoch
                        or self._safety_requests != 1 or generation != self._safety_sequence):
                    raise make_mhs_error("MHS.SAFETY.RESET_REFUSED", "camera safety changed during reset", {"retryable": False})
                self._latched, self._uncertain = False, False
                self._safe = False
                self._cancel = threading.Event()
            return {"reset": True, "resumed": False}
        finally:
            with self._activity:
                self._safety_requests -= 1

    def safety_status(self):
        with self._activity:
            self._reap()
            return {"safe_state": {"achieved": self._safe and self._current_stop(self._safe_proof)
                                  and not self._jobs and not self._fault
                                  and self._request_owner is None and not self._safety_requests and not self._closing},
                    "reconciliation_needed": bool(self._uncertain or self._fault or self._jobs),
                    "pending_native": sorted(self._jobs), "request_owner": self._request_owner,
                    "fault": self._fault, "closed": self._cleanup_complete,
                    "cleanup_pending": self._closing and not self._cleanup_complete}

    def close(self):
        with self._activity:
            self._reap()
            if self._cleanup_complete or "cleanup" in self._jobs:
                return
            self._closing, self._safe, self._closed = True, False, True
            self._cancel.set()
            owned = tuple(self._jobs.values())
            if (not owned and self._request_owner is None and self.lease.core is None
                    and not self._construction_entered and not self.lease.unresolved_values):
                self._cleanup_complete = True
                return
        def cleanup():
            for item in owned:
                item.done.wait()
            # An outer caller may be between retained phases. Closing forbids
            # its next phase; still wait for its dispatch authority to end.
            while not self._request_complete.is_set():
                with self._activity:
                    self._reap()
                self._request_complete.wait(.01)
            core = self.lease.core
            if core is not None:
                get = self.lease.core_call
                devices = get("getLoadedDevices")
                if type(devices) not in (list, tuple) or set(devices) - {"Core", self.profile.camera}:
                    raise ValueError("foreign devices cannot be cleaned up by this camera lease")
                if self.profile.camera in devices:
                    get("stopSequenceAcquisition", self.profile.camera)
                    if get("isSequenceRunning", self.profile.camera) is not False:
                        raise ValueError("owned camera is still acquiring during cleanup")
                if self.lease.unresolved_values:
                    raise ValueError("unexpected native return retains unresolved ownership")
                if self._claim is not None and self.lease.manager is not None:
                    self.lease.method("releaseExclusive", self._claim, restoreLive=False)
                    if object.__getattribute__(self.lease.manager, "__dict__").get("_exclusiveOwner") is not None:
                        raise ValueError("exclusive claim did not release during cleanup")
                    self._claim = None
                if self.profile.camera in devices:
                    get("unloadDevice", self.profile.camera)
                if self.profile.camera in get("getLoadedDevices"):
                    raise ValueError("camera label remains loaded after owned cleanup")
                self.lease.release_core()
            elif self._construction_entered or self.lease.unresolved_values:
                raise ValueError("failed construction did not establish a releasable core handle")
            with self._activity:
                self._cleanup_complete = True
        # Teardown remains strongly retained even after the caller's bound ends.
        try:
            self._run("cleanup", cleanup, time.monotonic() + self.profile.stop_timeout_ms / 1000.)
        except BaseException:
            self._mark_uncertain()
