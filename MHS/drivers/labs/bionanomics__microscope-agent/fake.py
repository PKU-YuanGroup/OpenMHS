"""Fake backend of the Baumer camera: an in-memory stand-in for BaumerGenICam.

Gate G7: every public method below exists on ``acquisition.backends.baumer_genicam:BaumerGenICam``
(``acquisition/backends/baumer_genicam.py:105,142,183,260``), and the driver reaches only those methods.  Like the
upstream class, ``get_settings`` returns the current exposure/gain/pixel format plus the camera's ranges,
``set_settings`` accepts either setting independently and returns the new settings, ``capture`` writes one timestamped
PNG and returns its ``pathlib.Path``, and ``close`` stops the acquisition.  Nothing here imports ``harvesters``,
``cv2``, the upstream package or opens a camera.

Fidelity gap (model review, 2026-11-05): the upstream ``close`` stops and destroys the one acquirer the constructor
created and resets the harvester (``baumer_genicam.py:101-102, 260-263``), and no method re-creates it, so after an
e-stop the real object can no longer read settings or capture until the backend is loaded again.  By default this
fake keeps serving after ``close``: the gate's conformance suite reads the state after its e-stop, and a fake that
refuses then fails G8 TSAFE-001 and SAFE-014 (an SDK limitation recorded by the review).  The test switch
``destroy_on_close`` makes the fake refuse after ``close`` the way the upstream object does; the package tests use it.
A later ``close`` is accepted (the e-stop may run more than once); what a second ``close`` does on the real acquirer
is not shown in the clone.

Every number, string and image below is test data, not a fact or a bound of the device.  Each is marked
``# placeholder``; the real metadata, ranges and frame dimensions are read from the connected GenICam node map at run
time in the hardware backend.
"""

import os
import tempfile
from pathlib import Path

from mhs.pixels import encode_png_rows

_IMAGE_SIDE = 4  # placeholder: stand-in frame side in pixels

_EXPOSURE_MIN_US = 28.0  # placeholder: stand-in camera-reported minimum
_EXPOSURE_MAX_US = 60_000_000.0  # placeholder: stand-in camera-reported maximum
_GAIN_MIN = 1.0  # placeholder: stand-in camera-reported minimum
_GAIN_MAX = 251.1875  # placeholder: stand-in camera-reported maximum

_INITIAL_EXPOSURE_US = 10_000.0  # placeholder: stand-in start exposure
_INITIAL_GAIN = 1.0  # placeholder: stand-in start gain
_INITIAL_PIXEL_FORMAT = "RGB8"  # placeholder: stand-in pixel format
_INITIAL_BALANCE_WHITE_AUTO = "Off"  # placeholder: stand-in white-balance mode


def _png():
    """A complete 4 x 4 RGB PNG with placeholder pixels."""
    rows = []
    for row in range(_IMAGE_SIDE):
        samples = bytearray()
        for column in range(_IMAGE_SIDE):
            samples.extend(((row * 53 + column * 17) % 256,
                            (row * 29 + column * 71) % 256,
                            (row * 97 + column * 11) % 256))
        rows.append(bytes(samples))
    return encode_png_rows(_IMAGE_SIDE, _IMAGE_SIDE, 8, 2, rows, max_bytes=65536)


class FakeBaumerGenICam:
    """Source-shaped fake of ``BaumerGenICam`` for the fake backend."""

    def __init__(self, **_options):
        self._settings = {
            "exposure_time_us": _INITIAL_EXPOSURE_US,
            "exposure_time_range_us": [_EXPOSURE_MIN_US, _EXPOSURE_MAX_US],
            "gain": _INITIAL_GAIN,
            "gain_range": [_GAIN_MIN, _GAIN_MAX],
            "pixel_format": _INITIAL_PIXEL_FORMAT,
            "balance_white_auto": _INITIAL_BALANCE_WHITE_AUTO,
        }
        self._capture_count = 0
        self._capture_calls = 0
        self._close_calls = 0
        self._last_path = None
        self._closed = False
        self.destroy_on_close = False  # placeholder test switch: refuse after close, as the upstream object does

    def _require_open(self):
        if self._closed:
            raise RuntimeError("the acquirer was destroyed by close(); the upstream object is not reopened")

    def get_settings(self):
        """Return a copy of the current settings, as the upstream method does."""
        self._require_open()
        settings = dict(self._settings)
        settings["exposure_time_range_us"] = list(self._settings["exposure_time_range_us"])
        settings["gain_range"] = list(self._settings["gain_range"])
        return settings

    def set_settings(self, exposure_time_us=None, gain=None):
        """Apply either setting after the same range check as the upstream method; return the new settings."""
        self._require_open()
        if exposure_time_us is not None:
            value = float(exposure_time_us)
            if not (_EXPOSURE_MIN_US <= value <= _EXPOSURE_MAX_US):
                raise ValueError("requested exposure is outside the camera's reported range")
            self._settings["exposure_time_us"] = value
        if gain is not None:
            value = float(gain)
            if not (_GAIN_MIN <= value <= _GAIN_MAX):
                raise ValueError("requested gain is outside the camera's reported range")
            self._settings["gain"] = value
        return self.get_settings()

    def capture(self):
        """Write one placeholder PNG to the system temporary directory and return its path."""
        self._require_open()
        self._capture_calls += 1
        self._capture_count += 1
        handle, name = tempfile.mkstemp(prefix="baumer-camera-fake-", suffix=".png")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(_png())
        except BaseException:
            try:
                os.unlink(name)
            except OSError:
                pass
            raise
        if self._last_path is not None:
            try:
                os.unlink(self._last_path)
            except OSError:
                pass
        self._last_path = Path(name)
        return self._last_path

    def close(self):
        """Stop and destroy the fake acquisition and remove the last placeholder frame."""
        self._close_calls += 1
        if self.destroy_on_close:
            self._closed = True
        if self._last_path is not None:
            try:
                os.unlink(self._last_path)
            except OSError:
                pass
            self._last_path = None
