"""Fake backend of the NESP syringe pump driver: an in-memory stand-in for nesp_lib.pump:Pump.

Gate G7: every public member defined here exists on the upstream class nesp_lib.pump:Pump (properties and methods,
nesp_lib/pump.py:81-335), and the same names are the ones the driver reads and writes.  The starting values are test
data only, not facts: every one is marked ``# placeholder``.  The methods mirror the upstream signatures the driver
uses: ``run(wait_while_running=True)`` sends RUN and waits while the pump runs, ``run(False)`` only starts it,
``run_purge()`` starts a purge and ``stop(wait_while_running=True)`` sends STP.

The fake simulates only the pump's behaviour, not its serial protocol: the wire frames (STX, length, CCITT CRC and
ETX, nesp_lib/pump.py:527-576) are not produced or checked here, and nothing here opens a serial port or talks to a
device.  A dispense started with ``run(False)`` stays in the INFUSING or WITHDRAWING status until ``stop`` is called;
``run(True)`` finishes at once and adds the configured volume to the dispensation counter.
"""

import enum


class _FakeStatus(enum.Enum):
    """The Status members of nesp_lib/status.py:3-19 (a stand-in, not the upstream class)."""

    INFUSING = enum.auto()
    WITHDRAWING = enum.auto()
    PURGING = enum.auto()
    STOPPED = enum.auto()
    PAUSED = enum.auto()
    SLEEPING = enum.auto()
    WAITING = enum.auto()


class _FakePumpingDirection(enum.Enum):
    """The PumpingDirection members of nesp_lib/pumping_direction.py:3-8 (a stand-in)."""

    INFUSE = enum.auto()
    WITHDRAW = enum.auto()


class FakeNespPump:
    def __init__(self, **_options):
        self._model_number = 1000                              # placeholder
        self._firmware_version = (3, 928)                      # placeholder
        self._status = _FakeStatus.STOPPED                     # placeholder
        self._syringe_diameter_mm = 30.0                       # placeholder
        self._pumping_direction = _FakePumpingDirection.INFUSE  # placeholder
        self._pumping_volume_ml = 1.0                          # placeholder
        self._pumping_rate_ml_per_min = 10.0                   # placeholder
        self._volume_infused_ml = 0.0                          # placeholder
        self._volume_withdrawn_ml = 0.0                        # placeholder
        self._safe_mode_timeout_s = 0                          # placeholder

    @property
    def model_number(self):
        return self._model_number

    @property
    def firmware_version(self):
        return self._firmware_version

    @property
    def status(self):
        return self._status

    @property
    def running(self):
        return self._status in (_FakeStatus.INFUSING, _FakeStatus.WITHDRAWING, _FakeStatus.PURGING)

    @property
    def syringe_diameter_mm(self):
        return self._syringe_diameter_mm

    @syringe_diameter_mm.setter
    def syringe_diameter_mm(self, syringe_diameter_mm):
        self._syringe_diameter_mm = float(syringe_diameter_mm)

    @property
    def pumping_direction(self):
        return self._pumping_direction

    @pumping_direction.setter
    def pumping_direction(self, pumping_direction):
        self._pumping_direction = pumping_direction

    @property
    def pumping_volume_ml(self):
        return self._pumping_volume_ml

    @pumping_volume_ml.setter
    def pumping_volume_ml(self, pumping_volume_ml):
        self._pumping_volume_ml = float(pumping_volume_ml)

    @property
    def pumping_rate_ml_per_min(self):
        return self._pumping_rate_ml_per_min

    @pumping_rate_ml_per_min.setter
    def pumping_rate_ml_per_min(self, pumping_rate_ml_per_min):
        self._pumping_rate_ml_per_min = float(pumping_rate_ml_per_min)

    @property
    def volume_infused_ml(self):
        return self._volume_infused_ml

    @property
    def volume_withdrawn_ml(self):
        return self._volume_withdrawn_ml

    @property
    def safe_mode_timeout_s(self):
        return self._safe_mode_timeout_s

    @safe_mode_timeout_s.setter
    def safe_mode_timeout_s(self, safe_mode_timeout_s):
        self._safe_mode_timeout_s = int(safe_mode_timeout_s)

    def run(self, wait_while_running=True):
        infusing = self._pumping_direction is _FakePumpingDirection.INFUSE
        self._status = _FakeStatus.INFUSING if infusing else _FakeStatus.WITHDRAWING
        if not wait_while_running:
            return
        if infusing:
            self._volume_infused_ml += self._pumping_volume_ml
        else:
            self._volume_withdrawn_ml += self._pumping_volume_ml
        self._status = _FakeStatus.STOPPED

    def run_purge(self):
        self._status = _FakeStatus.PURGING

    def stop(self, wait_while_running=True):
        self._status = _FakeStatus.STOPPED
