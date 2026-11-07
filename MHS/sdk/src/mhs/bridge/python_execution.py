"""Retain a Python native execution beyond its caller's observation deadline.

The worker owns synchronous dispatch and terminal resolution. Cancelling an
asyncio task requests cooperative cancellation; the worker remains live until
the coroutine (including cancellation cleanup) really returns. Arbitrary native
threads, Status objects and remote futures are never treated as killed.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
import time
from typing import Any, Callable

from mhs import signals
from mhs.bridge.base import outcome_unknown, is_status_like


class RetainedCall:
    def __init__(self, label: str, execute: Callable[["RetainedCall"], Any],
                 finished: Callable[["RetainedCall"], None], *, deadline: float | None = None,
                 resolve_cancel: Callable[[Any], Any] | None = None):
        self.label, self.execute, self.finished = label, execute, finished
        self.deadline = deadline
        self.uncertainty_recorded = False
        self.resolve_cancel = resolve_cancel
        self.done = threading.Event()
        self.value: Any = None
        self.error: BaseException | None = None
        self.done_at: float | None = None
        self._lock = threading.Lock()
        self._task: asyncio.Task | None = None
        self._cancel_requested = False
        self._raw: Any = None
        self._cancel_thread: threading.Thread | None = None
        self._terminal = False
        self.thread = threading.Thread(target=self._run, name=f"mhs-native-{label}"[:60], daemon=True)

    def _run(self) -> None:
        try:
            self.value = self.execute(self)
        except BaseException as exc:
            self.error = exc
        finally:
            with self._lock:
                self._terminal = True
                cancel_thread = self._cancel_thread
            if cancel_thread is not None:
                cancel_thread.join()
            self.done_at = time.monotonic()
            self.finished(self)
            self.done.set()

    def track_awaitable(self, value: Any) -> Any:
        if not inspect.isawaitable(value):
            with self._lock:
                self._raw = value
                self._start_native_cancel()
            return value

        async def terminal():
            task = asyncio.current_task()
            with self._lock:
                self._task = task
                cancelled = self._cancel_requested
            if cancelled:
                # Schedule cancellation after entering the native coroutine so
                # its finally block gets its normal opportunity to run.
                asyncio.get_running_loop().call_soon(task.cancel)
            return await value

        return terminal()

    def request_cancel(self) -> None:
        with self._lock:
            if self._terminal:
                return
            self._cancel_requested = True
            task = self._task
            self._start_native_cancel()
        if task is not None and not task.done():
            try:
                task.get_loop().call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass

    def _start_native_cancel(self) -> None:
        """Called under the lock; cancellation completion is also retained."""
        if not self._cancel_requested or self._cancel_thread is not None or self._raw is None:
            return
        raw = self._raw
        def cancel():
            try:
                if not is_status_like(raw) and not isinstance(raw, concurrent.futures.Future):
                    return
                stop = getattr(raw, "cancel", None)
                if stop is None and is_status_like(raw):
                    stop = getattr(raw, "stop", None)
                if callable(stop):
                    value = stop()
                    if self.resolve_cancel is not None:
                        self.resolve_cancel(value)
            except BaseException:
                # Failed cancellation is never completion or a stop acknowledgment.
                pass
        self._cancel_thread = threading.Thread(target=cancel, name="mhs-native-cancel", daemon=True)
        self._cancel_thread.start()

    def wait(self, *, deadline: float | None, cancel_event: Any,
             abandoned: Callable[[], None]) -> Any:
        while True:
            now = time.monotonic()
            if self.done.is_set() and (deadline is None or self.done_at <= deadline):
                if self.error is not None:
                    raise self.error
                return self.value
            if cancel_event is not None and cancel_event.is_set():
                abandoned()
                self.request_cancel()
                raise signals.Cancelled(f"{self.label}: caller cancelled; native completion remains tracked")
            if deadline is not None and now >= deadline:
                abandoned()
                self.request_cancel()
                raise outcome_unknown(
                    f"{self.label} exceeded its time bound; native completion remains tracked",
                    details={"native_completion_confirmed": self.done.is_set()},
                )
            self.done.wait(.01 if deadline is None else max(0., min(.01, deadline - now)))
