"""Fake backend of the Chilas laser driver: an in-memory stand-in for pychilaslasers.laser:Laser.

Gate G7: every public method and property defined on FakeLaser exists on ``pychilaslasers.laser:Laser`` -- the
``diode`` and ``tec`` attributes are created in ``Laser.__init__`` (laser.py:127-128), and ``system_state``,
``model``, ``calibrated``, ``turn_on``, ``turn_off`` and ``trigger_pulse`` are members of that class (laser.py:232,
483, 493, 159, 555, 562).  The component objects the driver reaches through those attributes implement only methods
and properties of ``pychilaslasers.laser_components.diode:Diode`` and
``pychilaslasers.laser_components.tec:TEC``.

The starting values are test data, not device facts: each one is marked ``# placeholder``.  The state never moves by
itself, so reading it twice gives the same value.  Nothing here talks to a device.
"""


class _FakeDiode:
    """The ``laser.diode`` component of the fake (upstream: pychilaslasers.laser_components.diode.Diode)."""

    def __init__(self):
        self._state = False            # placeholder
        self._current = 20.0           # placeholder
        self._min = 0.0                # placeholder
        self._max = 100.0              # placeholder

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = bool(value)

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, value):
        self._current = float(value)

    @property
    def value(self):
        return self._current

    @value.setter
    def value(self, value):
        self._current = float(value)

    @property
    def min_value(self):
        return self._min

    @property
    def max_value(self):
        return self._max

    def get_current(self):
        return self._current

    def set_current(self, current_ma):
        self._current = float(current_ma)

    def get_value(self):
        return self._current

    def set_value(self, value):
        self._current = float(value)

    def turn_on(self):
        self._state = True

    def turn_off(self):
        self._state = False


class _FakeTEC:
    """The ``laser.tec`` component of the fake (upstream: pychilaslasers.laser_components.tec.TEC)."""

    def __init__(self):
        self._target = 25.0            # placeholder
        self._temp = 24.5              # placeholder
        self._current = 10.0           # placeholder
        self._current_limit = 100.0    # placeholder
        self._min = 0.0                # placeholder
        self._max = 50.0               # placeholder

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._target = float(value)

    @property
    def temp(self):
        return self._temp

    @property
    def value(self):
        return self._temp

    @value.setter
    def value(self, value):
        self._target = float(value)

    @property
    def current(self):
        return self._current

    @property
    def current_limit(self):
        return self._current_limit

    @property
    def min_value(self):
        return self._min

    @property
    def max_value(self):
        return self._max

    def get_value(self):
        return self._temp

    def set_value(self, value):
        self._target = float(value)

    def get_temp(self):
        return self._temp

    def get_target_temp(self):
        return self._target

    def set_target(self, target):
        self._target = float(target)


class FakeLaser:
    """An in-memory pychilaslasers.laser:Laser: state in plain attributes, no serial port."""

    def __init__(self, **_options):
        self._diode = _FakeDiode()
        self._tec = _FakeTEC()
        self._system_state = False     # placeholder
        self._model = "Unknown"        # placeholder
        self._calibrated = False       # placeholder
        self._pulses = 0               # placeholder

    @property
    def diode(self):
        return self._diode

    @property
    def tec(self):
        return self._tec

    @property
    def system_state(self):
        return self._system_state

    @system_state.setter
    def system_state(self, state):
        self._system_state = bool(state)

    @property
    def model(self):
        return self._model

    @property
    def calibrated(self):
        return self._calibrated

    def turn_on(self):
        self._system_state = True

    def turn_off(self):
        self._system_state = False

    def trigger_pulse(self):
        self._pulses += 1
