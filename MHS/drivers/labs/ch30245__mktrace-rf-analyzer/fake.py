"""Fake backend of the MKTrace package: a source-shaped stand-in for the upstream ``pna.NaClient``.

It implements only the four public methods this package uses and that the pinned ``NaClient`` has: ``identify``,
``capture``, ``configure_measurements`` and ``abort_active_session`` (pna.py:236-334).  It reproduces the parts of
their behaviour the driver observes: the *IDN? identity, the 1/2/4-port validation, the stage order and bounded
cancellation of both sequences, the touchstone file written into the destination directory, and the transport close
that ``abort_active_session`` performs.  It does not open a socket, assemble SCPI lines, read a binary block, or
model vendor-specific analyzer state; those are the upstream transport's and analyzer's work, not the driver's.

Every string, number and byte below is placeholder test data, not an instrument fact.  The fake writes a small valid
Touchstone file (one frequency point) into the directory the driver passes, and the driver publishes it through the
SDK's native-file artifact helper.  The file name follows the upstream's timestamped MKTrace form
(pna.py:125-128), but the timestamp and the data are the fake's.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time

_IDN = "Keysight Technologies,N5247B,FAKE0001,A.00.00"   # placeholder: a supported Keysight identity
_PORT_COUNTS = (1, 2, 4)
_STAGE_DELAY_S = 0.02                                   # placeholder: a short observable step, not a device timing
_STARTING_PARAMETERS = ("S11",)                         # placeholder: the fake channel starts with S11


class _OperationCancelled(RuntimeError):
    """The upstream raises OperationCancelled when its cancel_event is set (pna.py:67-73)."""


class _CaptureResult:
    """The fields of pna.CaptureResult (pna.py:18-23) this package reads."""

    __slots__ = ("path", "idn", "correction_warning", "restoration_warnings")

    def __init__(self, path, idn, correction_warning, restoration_warnings=()):
        self.path = path
        self.idn = idn
        self.correction_warning = correction_warning
        self.restoration_warnings = tuple(restoration_warnings)


class _MeasurementSetupResult:
    """The fields of pna.MeasurementSetupResult (pna.py:34-41) this package reads."""

    __slots__ = ("idn", "channel", "required_parameters", "existing_parameters", "created_measurements",
                 "final_catalog")

    def __init__(self, idn, channel, required_parameters, existing_parameters, created_measurements, final_catalog):
        self.idn = idn
        self.channel = channel
        self.required_parameters = tuple(required_parameters)
        self.existing_parameters = tuple(existing_parameters)
        self.created_measurements = tuple(created_measurements)
        self.final_catalog = tuple(final_catalog)


class FakeNaClient:
    """A source-shaped NaClient over in-memory state and a temporary Touchstone file; every value is a placeholder."""

    def __init__(self, **_options):
        self.host = "127.0.0.1"                          # placeholder
        self.port = 5025                                 # placeholder
        self._idn = _IDN
        self._channel = 1                                # placeholder
        self._parameters = list(_STARTING_PARAMETERS)
        self._session_closed = False
        self._abort_calls = 0                            # placeholder: test counter

    # -- upstream members this package uses ---------------------------------------------------------------------
    def identify(self, cancel_event=None):
        # identify opens its own short-lived session upstream (pna.py:254-264), so a closed session does not block it.
        self._session_closed = False
        self._check_cancelled(cancel_event)
        return self._idn

    def abort_active_session(self):
        self._abort_calls += 1
        self._session_closed = True

    def capture(self, destination_folder, port_count, file_name=None, progress=None, cancel_event=None):
        if port_count not in _PORT_COUNTS:
            raise ValueError("Ports must be one of 1, 2, or 4.")   # upstream wording, pna.py:274-275
        self._session_closed = False
        self._check_cancelled(cancel_event)
        self._step(progress, "Preparing measurement", cancel_event)
        # The Keysight path refuses an incomplete S-parameter catalog before a sweep (pna.py:444-456).
        required = {f"S{output_port}{input_port}"
                    for input_port in range(1, port_count + 1)
                    for output_port in range(1, port_count + 1)}
        if not required.issubset(self._parameters):
            raise RuntimeError("Channel is missing required S-parameter measurements; no sweep was started.")
        self._step(progress, "Sweeping", cancel_event)
        self._step(progress, "Saving Touchstone", cancel_event)
        destination = Path(destination_folder)
        destination.mkdir(parents=True, exist_ok=True)
        name = self._file_name(file_name, port_count)
        path = destination / name
        temporary = path.with_suffix(path.suffix + ".part")
        try:
            temporary.write_bytes(self._touchstone(port_count))
            temporary.replace(path)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
        self._step(progress, "Loading trace", cancel_event)
        return _CaptureResult(path, self._idn, False, ())

    def configure_measurements(self, port_count, progress=None, cancel_event=None):
        if port_count not in _PORT_COUNTS:
            raise ValueError("Ports must be one of 1, 2, or 4.")   # upstream wording, pna.py:149-150
        self._session_closed = False
        self._check_cancelled(cancel_event)
        self._step(progress, "Reading NA measurements", cancel_event)
        required = tuple(f"S{output_port}{input_port}"
                         for input_port in range(1, port_count + 1)
                         for output_port in range(1, port_count + 1))
        existing = tuple(self._parameters)
        created = []
        for parameter in required:
            if parameter in self._parameters:
                continue
            self._step(progress, f"Adding {parameter}", cancel_event)
            name = f"MKTRACE_CH{self._channel}_{parameter}"   # placeholder: the upstream name form
            self._parameters.append(parameter)
            created.append((name, parameter))
        self._step(progress, "NA measurements ready", cancel_event)
        catalog = tuple((f"MKTRACE_CH{self._channel}_{parameter}", parameter) for parameter in self._parameters)
        return _MeasurementSetupResult(self._idn, self._channel, required, existing, created, catalog)

    # -- fake internals -----------------------------------------------------------------------------------------
    def _step(self, progress, stage, cancel_event):
        self._check_cancelled(cancel_event)
        if progress is not None:
            progress(stage)
        deadline = time.monotonic() + _STAGE_DELAY_S
        while time.monotonic() < deadline:
            self._check_cancelled(cancel_event)
            time.sleep(min(0.005, max(0.0, deadline - time.monotonic())))

    def _check_cancelled(self, cancel_event):
        if self._session_closed:
            raise _OperationCancelled("analyzer session closed")
        if cancel_event is not None and cancel_event.is_set():
            raise _OperationCancelled("analyzer operation cancelled")

    @staticmethod
    def _file_name(value, port_count):
        suffix = f".s{port_count}p"
        if value is None or not str(value).strip():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]   # placeholder timestamp
            return f"MKTrace_{timestamp}{suffix}"
        name = str(value).strip()
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
        return f"{name}{suffix}"

    @staticmethod
    def _touchstone(port_count):
        lines = ["! MKTrace fake capture: placeholder data, not an instrument measurement",
                 "# Hz S RI R 50",
                 # placeholder frequency and S-parameter values
                 "1e9 " + " ".join(
                     ("0.5 0" if output_port == input_port else "0 0")
                     for output_port in range(port_count) for input_port in range(port_count))]
        return ("\n".join(lines) + "\n").encode("ascii")
