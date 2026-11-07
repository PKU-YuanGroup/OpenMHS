"""Hardware backend: open a BMG microplate reader through its 32-bit ActiveX COM interface.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate
runs the fake backend and never imports this module, the clone, comtypes or pywin32.

The upstream README says the connection needs 32-bit Python on Windows (README.md:15), and that the control name is
"CLARIOstar" even on a VANTAstar (README.md:50).  The clone's ``sidecar`` directory is a script bundle, not an
installed package (sidecar/pyproject.toml:24-27), so the operator points ``sidecar_path`` at that directory or puts it
on PYTHONPATH.  ``extended_temperature_range_model`` selects the 25.0-45.0 Cel or 10.0-60.0 Cel validator of the
installed model (sidecar/bmg_interface.py:18-25 and 72-84); it is a deployment option, not a driver limit.

One COM thread (model review, 2026-11-05).  BmgCom initializes COM on the thread that constructs it
(pythoncom.CoInitialize, sidecar/bmg_interface.py:27), and the upstream's own sidecar keeps the object on one worker
thread that initializes COM, constructs BmgCom and runs every call from a queue (sidecar/bmg_sidecar_server.py:31-87).
The OpenMHS runtime calls a driver from several threads (each operation, each state read and the e-stop), so this
factory does the same as the sidecar: ``connect`` starts one thread, which initializes COM, imports and constructs
BmgCom and then runs the calls of the returned object one at a time, in the order they arrive.  A call therefore waits
for the call before it, the e-stop's heater-off included; the package serves only short commands (GetVersion, GetInfo
and Temp).  ``close_connection`` ends the thread, which closes the COM connection and uninitializes COM, as the
sidecar's worker does.  The returned object offers only the calls this package serves: the plate tray, Init and the
assay run cannot be reached through it.  Never run: no Windows host, COM server or reader was available.
"""

import concurrent.futures
import queue
import sys
import threading
from pathlib import Path

_STOP = object()


class _ComThread:
    """The one thread that owns the BmgCom object (the upstream ComWorker pattern)."""

    def __init__(self, control_name, extended_temperature_range_model):
        self._calls = queue.Queue()
        self._ready = threading.Event()
        self._failure = None
        self._closed = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, args=(control_name, extended_temperature_range_model),
                                        name="bmg-com", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._failure is not None:
            self._closed = True
            raise self._failure

    def _run(self, control_name, extended_temperature_range_model):
        com_runtime = None
        device = None
        try:
            try:
                import pythoncom  # pywin32, as the upstream sidecar imports it (sidecar/bmg_sidecar_server.py:19)

                pythoncom.CoInitialize()
                com_runtime = pythoncom
                from bmg_interface import BmgCom

                device = BmgCom(control_name=control_name,
                                extended_temperature_range_model=extended_temperature_range_model)
            except BaseException as exc:  # noqa: BLE001 - handed to connect(), which raises it
                self._failure = exc
                return
            finally:
                self._ready.set()
            while True:
                work, result = self._calls.get()
                if work is _STOP:
                    break
                try:
                    result.set_result(work(device))
                except BaseException as exc:  # noqa: BLE001 - handed to the caller, which raises it
                    result.set_exception(exc)
        finally:
            if device is not None:
                try:
                    device.close_connection()
                except Exception:  # noqa: BLE001 - closing never fails (the sidecar only logs it)
                    pass
            if com_runtime is not None:
                com_runtime.CoUninitialize()

    def call(self, work):
        result = concurrent.futures.Future()
        with self._lock:
            if self._closed:
                raise RuntimeError("the BMG COM connection is closed")
            self._calls.put((work, result))
        return result.result()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._calls.put((_STOP, None))
        self._thread.join()


class BmgReader:
    """The BmgCom calls this package serves, each run on the COM thread."""

    def __init__(self, com_thread):
        self._com = com_thread

    def get_version(self):
        return self._com.call(lambda device: device.get_version())

    def get_status(self):
        return self._com.call(lambda device: device.get_status())

    def get_error(self):
        return self._com.call(lambda device: device.get_error())

    def read_temps(self):
        return self._com.call(lambda device: device.read_temps())

    def set_temp(self, temp):
        return self._com.call(lambda device: device.set_temp(temp))

    def close_connection(self):
        self._com.close()


def connect(control_name="CLARIOstar", extended_temperature_range_model=False, sidecar_path=None):
    """Start the COM thread, open the connection there through the clone's BmgCom and return the call proxy."""
    if sidecar_path is not None:
        location = str(Path(sidecar_path).resolve())
        if location not in sys.path:
            sys.path.insert(0, location)
    return BmgReader(_ComThread(control_name, bool(extended_temperature_range_model)))
