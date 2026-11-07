"""Fake backend of the Zolix stage driver: an in-memory stand-in for talos.hal.devices.zolix:ZolixXYRStage.

Gate G7: every public method defined here exists on the upstream ZolixXYRStage class in
talos/hal/devices/zolix.py:99-466 -- ``move_abs_um`` (238), ``stop`` (347), ``get_position`` (417), ``get_status``
(390) and ``disconnect`` (disconnect method of the upstream class).  The fake keeps the same engineering units as
the upstream driver: micrometres for X and Y and degrees for R, already converted with the configured scale.  It is
an analytic stand-in, **not** a recording of traffic and not the upstream simulator twin
(``talos.hal.sim.sim_zolix:SimZolixXYRStage``, which this package does not use).  The move takes a short,
fixed placeholder time so that a status poll sees motion; that timing is test data, not the firmware's motion
timing.  Every start value and duration below is marked ``# placeholder`` and is never copied into a Fact or a
Limit.  Nothing here opens a port or talks to hardware.

Known gaps against the upstream: targets are not rounded to whole pulses (talos/hal/devices/zolix.py:264-268); a
stop leaves the fake at its pre-move position, while a real stage stops part-way; a refused move raises
``RuntimeError`` where the upstream raises ``DeviceBusyError`` or ``EStopError`` (talos/hal/devices/zolix.py:304-309);
and the fake has no limit switches, alarm sources or serial faults.
"""

from __future__ import annotations

import time

#: How long the fake keeps reporting motion after a move (test data, not a device value).
_MOVE_S = 0.08  # placeholder


class _Position:
    """The fields of talos.models.StagePosition that the driver reads."""

    __slots__ = ("x_um", "y_um", "r_deg")

    def __init__(self, x_um: float, y_um: float, r_deg: float):
        self.x_um = x_um
        self.y_um = y_um
        self.r_deg = r_deg


class _Status:
    """The fields of talos.models.StageStatus that the driver reads."""

    __slots__ = ("any_moving", "estop", "alarm")

    def __init__(self, any_moving: bool, estop: bool = False, alarm: bool = False):
        self.any_moving = any_moving
        self.estop = estop
        self.alarm = alarm


class FakeZolixXYRStage:
    def __init__(self, **_options):
        self._x_um = 0.0          # placeholder
        self._y_um = 0.0          # placeholder
        self._r_deg = 0.0         # placeholder
        self._target = None
        self._move_end = None
        self._estop = False       # placeholder: the fake starts with no emergency-stop bit
        self._alarm = False       # placeholder: the fake starts with no axis alarm
        self._stop_calls = 0
        self._closed = False

    def _settle(self) -> None:
        if self._target is not None and time.monotonic() >= self._move_end:
            self._x_um, self._y_um, self._r_deg = self._target
            self._target = None
            self._move_end = None

    def move_abs_um(self, x_um, y_um, r_deg=None, speed=None, speed_pps=None):
        self._settle()
        if self._target is not None:
            raise RuntimeError("Zolix fake: an axis is already moving")
        if self._estop:
            raise RuntimeError("Zolix fake: the emergency-stop bit is set")
        target = (float(x_um), float(y_um), self._r_deg if r_deg is None else float(r_deg))
        if target == (self._x_um, self._y_um, self._r_deg):
            return
        self._target = target
        self._move_end = time.monotonic() + _MOVE_S

    def get_position(self):
        self._settle()
        return _Position(self._x_um, self._y_um, self._r_deg)

    def get_status(self):
        self._settle()
        return _Status(self._target is not None, self._estop, self._alarm)

    def stop(self):
        self._settle()
        self._target = None
        self._move_end = None
        self._stop_calls += 1

    def disconnect(self):
        self._target = None
        self._move_end = None
        self._closed = True
