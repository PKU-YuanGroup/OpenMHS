"""Shared raw environment adapter and bounded software idle acknowledgment."""
import threading
from mhs.driver import DriverFailed


class EnvironmentAdapter:
    def __init__(self, native, config, *, owns_world=False):
        self.native = native
        self.config = dict(config)
        self.owns_world = owns_world
        for key in ("sim_steps", "time_step"):
            if getattr(native, key, self.config[key]) != self.config[key]:
                raise ValueError(f"native {key} differs from the published construction configuration")
        self._lock = threading.Lock()
        self._active = False
        self._halted = False
        self._closing = False
        self._closed = False
        self._cleanup_started = False
        self._close_error = None

    def invoke(self, name, *args, check=None):
        with self._lock:
            if check is not None:
                check()
            if self._closing:
                raise DriverFailed("MHS.DEVICE.NOT_READY", "environment is closing or closed")
            if self._halted:
                raise DriverFailed("MHS.SAFETY.ESTOP_ENGAGED", "environment calls are fenced")
            if self._active:
                raise DriverFailed("MHS.DEVICE.NOT_READY", "a native environment call is still active")
            self._active = True
        try:
            return getattr(self.native, name)(*args)
        finally:
            with self._lock:
                self._active = False
                cleanup = self._claim_cleanup()
            if cleanup:
                self._cleanup()

    def fence(self):
        with self._lock:
            self._halted = True
            if self._closing:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED", "environment is closing or closed")
            if self._active:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                   "native call is still active; software latch remains engaged")
        return {"idle": True}

    def recover(self):
        with self._lock:
            if self._closing or self._active:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED", "cannot resume before native call is idle")
            self._halted = False

    def close(self):
        with self._lock:
            self._halted = True
            self._closing = True
            cleanup = self._claim_cleanup()
        if cleanup:
            self._cleanup()

    def _claim_cleanup(self):
        """Called under the lock; the final native return owns deferred cleanup."""
        if self._closing and not self._active and not self._cleanup_started:
            self._cleanup_started = True
            return True
        return False

    def _cleanup(self):
        # Teardown is irreversible. A failed cleanup cannot reopen the adapter
        # or replace the result of the native call that triggered deferred cleanup.
        errors = []
        try:
            try:
                self.native.close()
            except Exception as exc:
                errors.append(str(exc))
            if self.owns_world:
                try:
                    self.native.world.disconnect()
                except Exception as exc:
                    errors.append(str(exc))
        finally:
            with self._lock:
                self._closed = True
                self._close_error = "; ".join(errors) or None
