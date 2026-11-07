"""Fake backend of the PDM driver: an in-memory stand-in for pypdm.pdm:PDM.

Gate G7: every public method and property defined here exists on pypdm.pdm:PDM (the class at pypdm/pdm.py:250).  The
interface follows the upstream class: read_address() and read_protocol_version() are the two query methods, the other
public members are the properties the upstream class defines (frequency, pulse_width, delay, offset_current,
current_percentage, current, temperature, maximum_current, maximum_mean_current, current_source, interlock_status,
activation, mode, sync_source, delay_line_type) and apply(), which sends the "apply all instructions" command.  The
enum values the upstream returns are Enum members; here they are small objects with the same ``name`` and ``value``
members.  Every starting value is test data of this fake, marked # placeholder, not a fact of any PDM; nothing here
talks to a device.
"""


class _EnumValue:
    """A stand-in for an upstream Enum member: the name and the numeric value of the enum (pypdm/pdm.py:78-167)."""

    def __init__(self, name, value):
        self.name = name
        self.value = value


class FakePdm:
    def __init__(self, **_options):
        self._address = 1                       # placeholder: the address byte, test data only
        self._version = "3.7"                   # placeholder: the protocol version reply, test data only
        self._frequency = 1000                  # placeholder: Hz
        self._pulse_width = 100000              # placeholder: ps
        self._delay = 0                         # placeholder: ps
        self._current_percentage = 20.0         # placeholder: percent
        self._offset_current = 0.0              # placeholder: mA
        self._maximum_current = 500.0           # placeholder: mA
        self._maximum_mean_current = 100.0      # placeholder: mA
        self._temperature = 25.0                # placeholder: degC
        self._activation = False                # placeholder: the laser activation instruction
        self._applied = 0                       # placeholder: how many apply() commands this fake received
        self._interlock = _EnumValue("CLOSED", 0)
        self._mode = _EnumValue("PULSED", 0)
        self._current_source = _EnumValue("NUMERIC", 1)
        self._sync_source = _EnumValue("INTERNAL", 2)
        self._delay_line_type = _EnumValue("NONE", 0)

    # -- the two query methods of the upstream class -----------------------------------------------------------
    def read_address(self):
        return self._address

    def read_protocol_version(self):
        return self._version

    # -- the properties the driver reads and (some) writes -------------------------------------------------------
    @property
    def activation(self):
        return self._activation

    @activation.setter
    def activation(self, value):
        self._activation = bool(value)

    @property
    def interlock_status(self):
        return self._interlock

    @property
    def temperature(self):
        return self._temperature

    @property
    def current(self):
        return self._current_percentage * self._maximum_current / 100

    @property
    def current_percentage(self):
        return self._current_percentage

    @current_percentage.setter
    def current_percentage(self, value):
        self._current_percentage = float(value)

    @property
    def maximum_current(self):
        return self._maximum_current

    @property
    def maximum_mean_current(self):
        return self._maximum_mean_current

    @property
    def offset_current(self):
        return self._offset_current

    @offset_current.setter
    def offset_current(self, value):
        self._offset_current = float(value)

    @property
    def frequency(self):
        return self._frequency

    @frequency.setter
    def frequency(self, value):
        self._frequency = int(value)

    @property
    def pulse_width(self):
        return self._pulse_width

    @pulse_width.setter
    def pulse_width(self, value):
        self._pulse_width = int(value)

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, value):
        self._delay = int(value)

    @property
    def mode(self):
        return self._mode

    @property
    def current_source(self):
        return self._current_source

    @property
    def sync_source(self):
        return self._sync_source

    @property
    def delay_line_type(self):
        return self._delay_line_type

    # -- the actuation ---------------------------------------------------------------------------------------------
    def apply(self):
        # the upstream method sends APPLY_ALL_INSTRUCTIONS and returns nothing; the fake only counts the command
        self._applied += 1
