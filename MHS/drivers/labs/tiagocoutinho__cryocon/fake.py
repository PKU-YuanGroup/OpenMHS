"""Fake backend of the CryoCon driver: an in-memory stand-in for cryocon.cryocon:CryoCon.

Gate G7: every public method defined on ``FakeCryoCon`` is a member of the upstream ``CryoCon`` class
(cryocon/cryocon.py:209-355), and the two other attributes the driver reaches, ``channels`` and ``loops``, are set
by the upstream ``__init__`` (cryocon/cryocon.py:252-253).  The helper classes mirror the upstream ``Channel`` and
``Loop`` descriptors (cryocon/cryocon.py:131-185), which is what the upstream dictionaries hold.  Nothing here
derives from the upstream class, imports it, or talks to a device.

The upstream ships a sinstruments TCP simulator (cryocon/simulator.py, README.md:98-155), but it is a standalone
device server with a ``handle_message`` surface, not the ``CryoCon`` object API the driver uses, and its optional
dependencies are not installed here.  This package therefore uses an in-memory fake and starts from values of the
same shape as the simulator's defaults.  Every value below is placeholder test data, not a fact about a device and
not a recording; it never moves by itself, so two reads return the same state.
"""

import datetime


class FakeChannel:
    """Stand-in for cryocon.cryocon:Channel: the same readable descriptors, with fixed placeholder values."""

    def __init__(self, name, temperature, unit, minimum, maximum, alarm):
        self._name = name
        self._temperature = temperature
        self._unit = unit
        self._minimum = minimum
        self._maximum = maximum
        self._alarm = alarm

    async def name(self):
        return self._name

    async def temperature(self):
        return self._temperature

    async def unit(self):
        return self._unit

    async def minimum(self):
        return self._minimum

    async def maximum(self):
        return self._maximum

    async def alarm(self):
        return self._alarm


class FakeLoop:
    """Stand-in for cryocon.cryocon:Loop: the readable descriptors the driver uses, with placeholder values."""

    def __init__(self, set_point, source, type, output_power, range):
        self._set_point = set_point
        self._source = source
        self._type = type
        self._output_power = output_power
        self._range = range

    async def set_point(self):
        return self._set_point

    async def source(self):
        return self._source

    async def type(self):
        return self._type

    async def output_power(self):
        return self._output_power

    async def range(self):
        return self._range


class FakeCryoCon:
    """The fake controller; each public method is a readable member of the upstream CryoCon class."""

    def __init__(self, **_options):
        self._idn = "Cryo-con,24C,000000,1.00A"          # placeholder
        self._name = "Cryocon fake"                       # placeholder
        self._hw_revision = "FAKE-HW"                     # placeholder
        self._fw_revision = "FAKE-FW"                     # placeholder
        self._lockout = False                             # placeholder
        self._led = False                                 # placeholder
        self._display_filter_time = 1.0                   # placeholder
        self._date = datetime.date(2026, 1, 2)            # placeholder
        self._time = datetime.time(3, 4, 5)               # placeholder
        self._control = False                             # placeholder
        self.channels = {
            "A": FakeChannel("A", 300.0, "K", 3.4, 304.12, "--"),        # placeholder
            "B": FakeChannel("B", 24.5, "C", -100.0, 200.0, "--"),       # placeholder
            "C": FakeChannel("C", 77.0, "F", -148.0, 392.0, "--"),       # placeholder
            "D": FakeChannel("D", 1234.5, "S", 0.0, 10000.0, "--"),      # placeholder
        }
        self.loops = {
            1: FakeLoop(25.0, "A", "MAN", 40.3, "MID"),                  # placeholder
        }

    async def idn(self):
        return self._idn

    async def name(self):
        return self._name

    async def hw_revision(self):
        return self._hw_revision

    async def fw_revision(self):
        return self._fw_revision

    async def lockout(self):
        return self._lockout

    async def led(self):
        return self._led

    async def display_filter_time(self):
        return self._display_filter_time

    async def date(self):
        return self._date

    async def time(self):
        return self._time

    async def control(self, value=None):
        return self._control
