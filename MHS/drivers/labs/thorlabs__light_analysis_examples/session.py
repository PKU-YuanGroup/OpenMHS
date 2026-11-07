"""Serialize one owned session and defer irreversible cleanup until native calls settle.

No thread is killed and no native close is issued underneath a DLL call. A stop
request immediately fences queued calls. It acknowledges only a successful
session close; a busy or failed close cannot be reported as a safe state.
"""
from functools import wraps
import threading

from mhs.driver import Cancelled, DriverFailed, current_context


def _native_call(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        context = current_context()
        # A queued method must not wait indefinitely or dispatch after its caller expires.
        while not self._io_lock.acquire(timeout=0.02):
            self._check_admission(context)
        try:
            with self._condition:
                self._check_admission(context)
                self._active = True
            try:
                return method(self, *args, **kwargs)
            finally:
                with self._condition:
                    self._active = False
                self._drain_cleanup()
        finally:
            self._io_lock.release()
    return guarded


class _Session:
    """Private lifecycle shared by the adapted fake and real native wrapper."""

    def __init__(self):
        self._condition = threading.RLock()
        self._io_lock = threading.Lock()
        self._active = False
        self._closing = False
        self._shutdown = False
        self._cleanup_running = False
        self._close_attempted = False
        self._sdk_attempted = False
        self._close_error = None
        self._sdk_error = None
        self.closed = False
        self._sdk_closed = False

    def _check_admission(self, context):
        with self._condition:
            if self._closing:
                raise DriverFailed("MHS.DEVICE.NOT_READY", "session is closing or closed; create a new endpoint")
        if context is not None:
            if context.cancelled() or context.remaining_ms() <= 0:
                raise Cancelled("native call was cancelled or expired before dispatch")

    def _drain_cleanup(self):
        with self._condition:
            if self._active or self._cleanup_running or not self._closing:
                return
            self._cleanup_running = True
        while True:
            with self._condition:
                if not self._close_attempted:
                    self._close_attempted = True
                    operation = "session"
                elif self._shutdown and not self._sdk_attempted:
                    self._sdk_attempted = True
                    operation = "sdk"
                else:
                    # Atomically relinquish ownership, so a concurrent teardown
                    # either joins this loop or becomes the next cleanup owner.
                    self._cleanup_running = False
                    return
            try:
                if operation == "session":
                    self._close_session()
                    with self._condition:
                        self.closed = True
                else:
                    self._close_sdk()
                    with self._condition:
                        self._sdk_closed = True
            except BaseException as exc:
                with self._condition:
                    if operation == "session":
                        self._close_error = exc
                    else:
                        self._sdk_error = exc

    def close(self):
        with self._condition:
            self._closing = True
        self._drain_cleanup()
        with self._condition:
            if not self.closed or self._close_error is not None:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                   "session close is pending or failed; native execution may still be active")
        return 0

    def closeSDK(self):
        with self._condition:
            self._closing = True
            self._shutdown = True
        self._drain_cleanup()
        with self._condition:
            if not self._sdk_closed or self._sdk_error is not None or self._close_error is not None:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                   "owned session/SDK cleanup is pending or failed")
        return 0
