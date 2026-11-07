"""Fake backend of the SLS Mythen II driver: an in-memory stand-in for ``sls.client:Detector``.

Gate G7: every public method and property defined here exists on the upstream class ``sls.client:Detector``
(``sls/client.py:142-429``): the same properties (``energy_threshold``, ``exposure_time``, ``nb_frames``,
``nb_cycles``, ``frame_period``, ``delay_after_trigger``, ``run_status``, ``exposure_time_left``, ``detector_type``
and ``settings``) and the same methods (``get_nb_modules``, ``get_module_serial_number``, ``start_acquisition``,
``stop_acquisition`` and ``acquire``).  Like the upstream generator, ``acquire`` is a generator that yields frames.

This is an analytic in-memory stand-in, not a recording: it does not speak the binary wire protocol, it does not use
the upstream simulator, and it does not replay captured traffic.  Every starting value and every count below is test
data marked ``# placeholder``; none of it is a fact about a detector.  Acquisition pacing is shortened to a bounded
placeholder interval instead of honoring the configured exposure time, and the frame array is 16 counts instead of
the 7680 counts of a full Mythen II frame.  ``stop_acquisition`` sets a stop event, and ``acquire`` returns when the
event is set; the driver converts that into a cancellation.  Nothing here talks to a device.
"""

import threading
import time

#: Placeholder frame length (the real frame is 7680 counts, see driver.py).
_FRAME_LENGTH = 16
#: Placeholder cap on the per-frame pause; the fake does not wait for a configured exposure time.
_MAX_FRAME_PAUSE_S = 0.005


class _EnumName:
    """The ``.name`` member the driver reads from the upstream enum values."""

    def __init__(self, name):
        self.name = name


class FakeDetector:
    def __init__(self, **_options):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._remaining_frames = 0
        self._run_status = "IDLE"             # placeholder
        self._detector_type = "MYTHEN"        # placeholder name from DetectorType
        self._settings = "STANDARD"           # placeholder name from DetectorSettings
        self._energy_threshold = 9071         # placeholder eV
        self._exposure_time = 1.0             # placeholder s
        self._nb_frames = 1                   # placeholder
        self._nb_cycles = 1                   # placeholder
        self._frame_period = 0.0              # placeholder s
        self._delay_after_trigger = 0.0       # placeholder s

    # -- properties the upstream Detector exposes ---------------------------------------------------------------
    @property
    def detector_type(self):
        return _EnumName(self._detector_type)

    @property
    def settings(self):
        return _EnumName(self._settings)

    @property
    def run_status(self):
        with self._lock:
            return _EnumName(self._run_status)

    @property
    def energy_threshold(self):
        with self._lock:
            return self._energy_threshold

    @energy_threshold.setter
    def energy_threshold(self, value):
        with self._lock:
            self._energy_threshold = int(value)

    @property
    def exposure_time(self):
        with self._lock:
            return self._exposure_time

    @exposure_time.setter
    def exposure_time(self, value):
        with self._lock:
            self._exposure_time = float(value)

    @property
    def nb_frames(self):
        with self._lock:
            return self._nb_frames

    @nb_frames.setter
    def nb_frames(self, value):
        with self._lock:
            self._nb_frames = int(value)

    @property
    def nb_cycles(self):
        with self._lock:
            return self._nb_cycles

    @nb_cycles.setter
    def nb_cycles(self, value):
        with self._lock:
            self._nb_cycles = int(value)

    @property
    def frame_period(self):
        with self._lock:
            return self._frame_period

    @frame_period.setter
    def frame_period(self, value):
        with self._lock:
            self._frame_period = float(value)

    @property
    def delay_after_trigger(self):
        with self._lock:
            return self._delay_after_trigger

    @delay_after_trigger.setter
    def delay_after_trigger(self, value):
        with self._lock:
            self._delay_after_trigger = float(value)

    @property
    def exposure_time_left(self):
        with self._lock:
            if self._run_status not in ("RUNNING", "WAITING", "TRANSMITTING"):
                return 0.0
            return float(self._remaining_frames) * float(self._exposure_time)

    # -- methods the upstream Detector exposes --------------------------------------------------------------------
    def get_nb_modules(self, dimension=0):
        # Placeholder: the simulator's default X count and a single row along Y.
        return 6 if int(dimension) == 0 else 1

    def get_module_serial_number(self, mod_nb):
        # Placeholder serial number, deterministic per module index.
        return 0xEE0 + int(mod_nb)

    def start_acquisition(self):
        self._stop_event.clear()
        with self._lock:
            self._run_status = "RUNNING"

    def stop_acquisition(self):
        self._stop_event.set()
        with self._lock:
            self._run_status = "IDLE"
            self._remaining_frames = 0

    def acquire(self):
        self._stop_event.clear()
        with self._lock:
            self._run_status = "RUNNING"
            frames = max(1, self._nb_frames) * max(1, self._nb_cycles)
            pause = min(max(float(self._exposure_time), 0.0), _MAX_FRAME_PAUSE_S)
        try:
            for index in range(frames):
                with self._lock:
                    self._remaining_frames = frames - index
                deadline = time.monotonic() + pause
                while time.monotonic() < deadline:
                    if self._stop_event.is_set():
                        return
                    time.sleep(0.001)
                if self._stop_event.is_set():
                    return
                # Placeholder counts: a small deterministic frame shaped like a detector frame.
                yield [100 + index + channel for channel in range(_FRAME_LENGTH)]
        finally:
            with self._lock:
                self._run_status = "IDLE"
                self._remaining_frames = 0
