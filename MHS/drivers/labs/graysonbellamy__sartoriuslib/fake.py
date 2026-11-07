"""Fake backend of the Sartorius driver: an in-memory stand-in for sartoriuslib.devices.balance:Balance.

Gate G7: every public method and property defined here exists on the upstream Balance class
(src/sartoriuslib/devices/balance.py:300).  The driver reads ``info`` (the cached DeviceInfo property,
balance.py:326-330) and calls read_net, read_gross, read_tare_value, status, get_* and set_* (balance.py:408-973) and
close (balance.py:349-351).  Like the upstream facade every method is a coroutine function, and the setters take
``confirm=True`` like their upstream counterparts (balance.py:818-836).

The initial values are placeholder test data, not facts about any balance; each is marked ``# placeholder``.  The
display unit is placeholder ``g`` and the returned reading is converted to whatever unit is configured, so the
driver's milligram conversion is exercised.  Nothing here talks to a device.  ``close`` records the stop but keeps
answering reads: the runtime reads every state field for the e-stop receipt, while a real closed serial port would
refuse further I/O.
"""


class _Unit:
    def __init__(self, value):
        self.value = value


class _Mode:
    """An IntEnum-like value with the member name the driver reads (``.name``)."""

    def __init__(self, name):
        self.name = name


class _State:
    def __init__(self, value):
        self.value = value


class _Reading:
    def __init__(self, value, unit, stable=True):
        self.value = value
        self.unit = _Unit(unit)
        self.stable = stable


class _Status:
    def __init__(self, state, stable=True):
        self.state = _State(state)
        self.stable = stable


class _Info:
    model = "MSE1203S-100-DR"          # placeholder
    serial = "0000000000"              # placeholder
    software = "1.0.0"                 # placeholder


#: Placeholder factors from grams into the four display units this driver exposes.
_TO_UNIT = {"g": 1.0, "kg": 0.001, "mg": 1000.0, "µg": 1000000.0}


class FakeBalance:
    def __init__(self, **_options):
        self._info = _Info()
        self._net_g = 12.345           # placeholder
        self._tare_g = 0.5             # placeholder
        self._display_unit = "g"       # placeholder
        self._filter_mode = "stable"   # placeholder
        self._auto_zero = "on"         # placeholder
        self._isocal_mode = "off"      # placeholder
        self._tare_behavior = "with_stability"  # placeholder
        self._menu_access = "can_edit"           # placeholder
        self._closed = False

    @property
    def info(self):
        return self._info

    def _reading(self, grams):
        return _Reading(grams * _TO_UNIT[self._display_unit], self._display_unit)

    async def read_net(self, *, hires=0):
        return self._reading(self._net_g)

    async def read_gross(self, *, hires=0):
        return self._reading(self._net_g + self._tare_g)

    async def read_tare_value(self):
        return self._reading(self._tare_g)

    async def status(self):
        return _Status("stable")

    async def close(self):
        self._closed = True

    async def get_display_unit(self):
        return _Unit(self._display_unit)

    async def set_display_unit(self, unit, *, confirm=False):
        if confirm:
            self._display_unit = str(unit)

    async def get_filter_mode(self):
        return _Mode(self._filter_mode.upper())

    async def set_filter_mode(self, mode, *, confirm=False):
        if confirm:
            self._filter_mode = str(mode).strip().lower().replace(" ", "_").replace("-", "_")

    async def get_auto_zero(self):
        return _Mode(self._auto_zero.upper())

    async def set_auto_zero(self, mode, *, confirm=False):
        if confirm:
            self._auto_zero = str(mode).strip().lower().replace(" ", "_").replace("-", "_")

    async def get_isocal_mode(self):
        return _Mode(self._isocal_mode.upper())

    async def set_isocal_mode(self, mode, *, confirm=False):
        if confirm:
            self._isocal_mode = str(mode).strip().lower().replace(" ", "_").replace("-", "_")

    async def get_tare_behavior(self):
        return _Mode(self._tare_behavior.upper())

    async def set_tare_behavior(self, mode, *, confirm=False):
        if confirm:
            self._tare_behavior = str(mode).strip().lower().replace(" ", "_").replace("-", "_")

    async def get_menu_access(self):
        return _Mode(self._menu_access.upper())

    async def set_menu_access(self, mode, *, confirm=False):
        if confirm:
            self._menu_access = str(mode).strip().lower().replace(" ", "_").replace("-", "_")
