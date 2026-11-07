"""Owned event loop for asynchronous Gymnasium environments (``asyncio_owned_loop_v1``).

A source-reviewed backend declares which native entry points are coroutines,
which keyword arguments its ``reset`` accepts, the local bounds of each native
call and, optionally, an explicit remote stop and a stop probe.  The
declaration is a contract about the backend; flags and citation strings are
not proof of native behaviour.

One daemon thread runs one asyncio event loop and is the only thread that
calls the environment's ``step``, ``reset``, ``close``, remote stop and stop
probe (the single-owner rule: a client library bound to the loop, or one that
is not thread-safe, is never entered from two threads).  A caller waits at most
the declared bound.  A native call that does not settle within its bound is
never cancelled locally: cancelling the local coroutine would not end the
remote work it started.  The call stays *owned*: new native work, safety reset
and native cleanup are refused or deferred until it settles, and its late
outcome is recorded.  Cancellation of an operation is observed between native
calls, never inside one.

No native code, network, simulator or pacing is provided by this module.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import math
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

__all__ = ["ASYNC_MODE", "AsyncProfile", "OwnedLoop", "OwnedTimeout", "ProfileViolation", "OwnedBusy"]

ASYNC_MODE = "asyncio_owned_loop_v1"
_PATH = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*\Z")
_KINDS = ("coroutine", "sync")
_RESET_KWARGS = ("seed", "options")
#: Settlement records of abandoned calls kept for diagnostics (oldest dropped first).
_MAX_LATE = 16


class AsyncProfileError(ValueError):
    """An asynchronous-environment declaration violates the profile."""


class OwnedTimeout(Exception):
    """A native call did not settle within its bound; it stays owned (never cancelled locally)."""

    def __init__(self, kind: str, timeout_s: float):
        super().__init__(f"native {kind} did not settle within {timeout_s:g} s; it remains owned")
        self.kind = kind
        self.timeout_s = timeout_s


class OwnedBusy(Exception):
    """Earlier native work is still owned; nothing was dispatched."""

    def __init__(self, owned: Mapping[str, Any]):
        super().__init__(f"earlier native {owned.get('kind')} is still owned "
                         f"({'abandoned after its bound' if owned.get('abandoned') else 'in progress'})")
        self.owned = dict(owned)


class ProfileViolation(Exception):
    """A native entry point returned a value its declared kind does not allow."""


def _bound(config: Mapping[str, Any], name: str, low: float, high: float, *, required: bool = True,
           default: float | None = None) -> float | None:
    if name not in config:
        if required:
            raise AsyncProfileError(f"{name} is required")
        return default
    value = config[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AsyncProfileError(f"{name} must be a number of seconds")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise AsyncProfileError(f"{name} must be within {low:g}..{high:g} s")
    return value


@dataclass(frozen=True)
class AsyncProfile:
    """A resolved ``asyncio_owned_loop_v1`` declaration (see the module docstring)."""

    step: str
    reset: str
    reset_kwargs: tuple[str, ...]
    step_timeout_s: float
    reset_timeout_s: float
    close_timeout_s: float
    remote_stop: str | None = None
    stop_probe: str | None = None
    stop_timeout_s: float | None = None
    settle_timeout_s: float | None = None
    source_refs: tuple[str, ...] = ()

    @classmethod
    def resolve(cls, config: Mapping[str, Any]) -> "AsyncProfile":
        if not isinstance(config, Mapping):
            raise AsyncProfileError("the asynchronous profile must be a mapping")
        allowed = {"mode", "step", "reset", "reset_kwargs", "step_timeout_s", "reset_timeout_s",
                   "close_timeout_s", "remote_stop", "stop_probe", "stop_timeout_s", "settle_timeout_s",
                   "source_refs"}
        unknown = set(config) - allowed
        if unknown:
            raise AsyncProfileError(f"unknown asynchronous profile keys {sorted(map(str, unknown))}")
        if config.get("mode") != ASYNC_MODE:
            raise AsyncProfileError(f"mode must be {ASYNC_MODE!r}")
        step, reset = config.get("step"), config.get("reset")
        if step not in _KINDS or reset not in _KINDS:
            raise AsyncProfileError("step and reset must each be 'coroutine' or 'sync'")
        kwargs = config.get("reset_kwargs")
        if (not isinstance(kwargs, (list, tuple)) or len(set(kwargs)) != len(kwargs)
                or any(name not in _RESET_KWARGS for name in kwargs)):
            raise AsyncProfileError("reset_kwargs must list the distinct native reset keywords "
                                    "(a subset of ['seed', 'options'])")
        stop, probe = config.get("remote_stop"), config.get("stop_probe")
        for name, value in (("remote_stop", stop), ("stop_probe", probe)):
            if value is not None and (not isinstance(value, str) or len(value) > 200 or not _PATH.fullmatch(value)):
                raise AsyncProfileError(f"{name} must be an explicit public attribute path such as 'world.pause'")
        if probe is not None and stop is None:
            raise AsyncProfileError("stop_probe requires remote_stop")
        if stop is None and ("stop_timeout_s" in config or "settle_timeout_s" in config):
            raise AsyncProfileError("stop_timeout_s/settle_timeout_s require remote_stop")
        refs = config.get("source_refs", ())
        if not isinstance(refs, (list, tuple)) or len(refs) > 20 or any(
                not isinstance(ref, str) or not ref or len(ref) > 500 for ref in refs):
            raise AsyncProfileError("source_refs must be bounded strings; citations do not validate the backend")
        return cls(
            step=step, reset=reset, reset_kwargs=tuple(kwargs),
            step_timeout_s=_bound(config, "step_timeout_s", 0.001, 600.0),
            reset_timeout_s=_bound(config, "reset_timeout_s", 0.001, 600.0),
            close_timeout_s=_bound(config, "close_timeout_s", 0.001, 600.0),
            remote_stop=stop, stop_probe=probe,
            stop_timeout_s=_bound(config, "stop_timeout_s", 0.001, 60.0, required=stop is not None),
            settle_timeout_s=_bound(config, "settle_timeout_s", 0.0, 60.0, required=stop is not None),
            source_refs=tuple(refs),
        )

    def descriptor(self) -> dict[str, Any]:
        return {"mode": ASYNC_MODE, "step": self.step, "reset": self.reset,
                "reset_kwargs": list(self.reset_kwargs), "step_timeout_s": self.step_timeout_s,
                "reset_timeout_s": self.reset_timeout_s, "close_timeout_s": self.close_timeout_s,
                "remote_stop": self.remote_stop, "stop_probe": self.stop_probe,
                "stop_timeout_s": self.stop_timeout_s, "settle_timeout_s": self.settle_timeout_s,
                "source_refs": list(self.source_refs)}

    def notes(self) -> list[str]:
        """Operating notes for the manifest profile (plain sentences, no bound claims beyond the declaration)."""
        kinds = f"step is {'awaited' if self.step == 'coroutine' else 'called'} and reset is " \
                f"{'awaited' if self.reset == 'coroutine' else 'called'} on one owned event-loop thread"
        out = [f"Asynchronous environment ({ASYNC_MODE}): {kinds}; local bounds step "
               f"{self.step_timeout_s:g} s, reset {self.reset_timeout_s:g} s, close {self.close_timeout_s:g} s. "
               "A native call that exceeds its bound is not cancelled locally: its outcome is unknown, it stays "
               "owned, new native work and safety reset are refused until it settles, and an explicit world "
               "reset is required afterwards."]
        if self.remote_stop is None:
            out.append("No remote stop is declared: the e-stop is the software latch; while native work is "
                       "owned the safe state is reported unachieved.")
        else:
            probe = (f" and confirmed by {self.stop_probe} returning True" if self.stop_probe else
                     " without a stop probe (no read-back confirmation)")
            out.append(f"The e-stop calls the declared remote stop {self.remote_stop} on the owned loop "
                       f"(bound {self.stop_timeout_s:g} s){probe}; owned native work must then settle within "
                       f"{self.settle_timeout_s:g} s, otherwise the stop outcome is unknown.")
        if "seed" not in self.reset_kwargs:
            out.append("The native reset accepts no seed: no seed capability is served and no seeded "
                       "determinism is claimed.")
        return out


@dataclass
class _Work:
    kind: str
    future: concurrent.futures.Future | None
    started: float = field(default_factory=time.monotonic)
    abandoned: bool = False
    stop: bool = False
    #: Set (under the loop's lock) by the coroutine itself as it ends, before its result is delivered.
    released: bool = False
    result: Any = None
    error: BaseException | None = None

    def describe(self) -> dict[str, Any]:
        return {"kind": self.kind, "abandoned": self.abandoned,
                "age_s": round(max(0.0, time.monotonic() - self.started), 3)}


class OwnedLoop:
    """One asyncio loop on one daemon thread; the only caller of the environment's native methods.

    Ordinary work (step, reset, close) is single-flight.  Stop work (the
    remote stop and its probe) may be submitted while ordinary work is owned:
    it is scheduled on the same loop, so it runs when the loop is free (at an
    ``await`` of the owned coroutine, or after a blocking call returns), never
    concurrently on another thread.  Listeners are told (on the loop thread;
    they must not block) whenever owned work settles.
    """

    def __init__(self, name: str = "mhs-gym-owned-loop"):
        self.name = name
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._work: _Work | None = None
        self._stop_work: _Work | None = None
        self._shutdown = False
        self._listeners: list[Callable[[], None]] = []
        self.late: list[dict[str, Any]] = []

    # -- state ---------------------------------------------------------------
    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def owned(self) -> dict[str, Any] | None:
        """The owned ordinary work (``None`` when the environment is idle)."""
        with self._lock:
            return self._work.describe() if self._work is not None else None

    def owned_stop(self) -> dict[str, Any] | None:
        with self._lock:
            return self._stop_work.describe() if self._stop_work is not None else None

    def owns_any(self) -> bool:
        with self._lock:
            return self._work is not None or self._stop_work is not None

    @property
    def started(self) -> bool:
        return self._thread is not None

    @property
    def thread_alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def describe(self) -> dict[str, Any]:
        with self._lock:
            return {"owned": self._work.describe() if self._work is not None else None,
                    "owned_stop": self._stop_work.describe() if self._stop_work is not None else None,
                    "late": [dict(item) for item in self.late],
                    "loop": ("shut down" if self._shutdown else "running" if self._thread is not None
                             else "not started")}

    # -- execution -----------------------------------------------------------
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        # Called with self._lock held.
        if self._loop is not None:
            return self._loop
        loop = asyncio.new_event_loop()
        ready = threading.Event()

        def serve() -> None:
            asyncio.set_event_loop(loop)
            loop.call_soon(ready.set)
            try:
                loop.run_forever()
            finally:
                try:
                    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:  # noqa: BLE001 - best-effort teardown after the owner released the env
                    pass
                finally:
                    loop.close()

        thread = threading.Thread(target=serve, name=self.name, daemon=True)
        thread.start()
        if not ready.wait(5.0):  # pragma: no cover - defensive
            raise RuntimeError("the owned event loop did not start")
        self._loop, self._thread = loop, thread
        return loop

    def submit(self, kind: str, fn: Callable[[], Any], *, expect: str, stop: bool = False,
               guard: Callable[[], None] | None = None) -> _Work:
        """Schedule ``fn()`` on the owned loop (``expect``: 'coroutine', 'sync' or 'any').

        ``guard`` runs under the loop's lock immediately before scheduling and
        may raise to refuse: a stop submitted (or completed) before it is then
        always ordered before any admitted ordinary call.
        """
        if self._thread is not None and threading.current_thread() is self._thread:
            raise RuntimeError("native work cannot be submitted from the owned loop thread")
        work = _Work(kind, None, stop=stop)

        async def invoke() -> Any:
            outcome = "returned"
            try:
                value = fn()
                if inspect.isawaitable(value):
                    if expect == "sync":
                        if asyncio.iscoroutine(value):
                            value.close()
                        raise ProfileViolation(f"declared synchronous native {kind} returned an awaitable")
                    value = await value
                elif expect == "coroutine":
                    raise ProfileViolation(f"declared coroutine native {kind} returned a non-awaitable "
                                           f"{type(value).__name__}")
                work.result = value
                return value
            except BaseException as exc:
                outcome = "cancelled" if isinstance(exc, asyncio.CancelledError) else f"raised {type(exc).__name__}"
                work.error = exc
                raise
            finally:
                # Ownership ends here, on the loop, before the caller can see the result: a caller that
                # returns from wait() never observes its own settled call as still owned.
                self._release(work, outcome)

        with self._lock:
            if self._shutdown:
                raise RuntimeError("the owned event loop is shut down")
            current = self._stop_work if stop else self._work
            if current is not None:
                raise OwnedBusy(current.describe())
            if not stop and self._stop_work is not None:
                raise OwnedBusy(self._stop_work.describe())
            if guard is not None:
                guard()
            loop = self._ensure_loop()
            coroutine = invoke()
            try:
                future = asyncio.run_coroutine_threadsafe(coroutine, loop)
            except BaseException:
                coroutine.close()
                raise
            work.future = future
            if stop:
                self._stop_work = work
            else:
                self._work = work
        # Fallback only: a coroutine cancelled before it ever ran releases nothing itself.
        future.add_done_callback(lambda _future, _work=work: self._settled(_work))
        return work

    def wait(self, work: _Work, timeout_s: float) -> Any:
        """The work's result within ``timeout_s``; otherwise :class:`OwnedTimeout` (the work stays owned)."""
        try:
            return work.future.result(timeout=max(0.0, float(timeout_s)))
        except concurrent.futures.TimeoutError:
            with self._lock:
                if not work.released:
                    work.abandoned = True
                    raise OwnedTimeout(work.kind, timeout_s) from None
            # It settled at the bound: its outcome is known even if the loop has not delivered it yet.
            if work.error is not None:
                raise work.error from None
            return work.result

    def run(self, kind: str, fn: Callable[[], Any], *, expect: str, timeout_s: float, stop: bool = False,
            guard: Callable[[], None] | None = None) -> Any:
        return self.wait(self.submit(kind, fn, expect=expect, stop=stop, guard=guard), timeout_s)

    def current_stop(self) -> _Work | None:
        with self._lock:
            return self._stop_work

    def current_work(self) -> _Work | None:
        with self._lock:
            return self._work

    def wait_idle(self, timeout_s: float) -> bool:
        """Wait (bounded) until no ordinary work is owned; True when idle."""
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while True:
            with self._lock:
                work = self._work
            if work is None:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            try:
                work.future.result(timeout=remaining)
            except concurrent.futures.TimeoutError:
                return self.owned() is None
            except BaseException:  # noqa: BLE001 - a settled failure is settled
                pass
            # The done callback may run just after result() returns; give it a turn.
            for _ in range(50):
                with self._lock:
                    if self._work is not work:
                        break
                time.sleep(0.001)

    def _settled(self, work: _Work) -> None:
        future = work.future
        if future.cancelled():
            outcome = "cancelled"
        elif future.exception() is not None:
            outcome = f"raised {type(future.exception()).__name__}"
        else:
            outcome = "returned"
        self._release(work, outcome)

    def _release(self, work: _Work, outcome: str) -> None:
        with self._lock:
            if work.released:
                return
            work.released = True
            if self._work is work:
                self._work = None
            if self._stop_work is work:
                self._stop_work = None
            if work.abandoned:
                self.late.append({"kind": work.kind, "outcome": outcome,
                                  "after_s": round(max(0.0, time.monotonic() - work.started), 3)})
                del self.late[:-_MAX_LATE]
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback()
            except Exception:  # noqa: BLE001 - a listener never breaks settlement
                pass

    # -- shutdown ------------------------------------------------------------
    def shutdown(self, timeout_s: float) -> str:
        """Stop the loop when nothing is owned: 'settled', 'not_started', 'owned' or 'timed_out'."""
        with self._lock:
            if self._work is not None or self._stop_work is not None:
                return "owned"
            self._shutdown = True
            loop, thread = self._loop, self._thread
        if loop is None or thread is None:
            return "not_started"
        if thread is threading.current_thread():  # pragma: no cover - cleanup never runs on the loop
            return "owned"
        try:
            loop.call_soon_threadsafe(loop.stop)
        except RuntimeError:  # pragma: no cover - already stopped
            return "settled"
        thread.join(max(0.0, float(timeout_s)))
        return "timed_out" if thread.is_alive() else "settled"


def resolve_path(target: Any, path: str) -> Callable[..., Any]:
    """``target.a.b`` for a declared dotted path; it must be callable."""
    value = target
    for part in path.split("."):
        value = getattr(value, part)
    if not callable(value):
        raise AsyncProfileError(f"declared native {path!r} is not callable")
    return value
