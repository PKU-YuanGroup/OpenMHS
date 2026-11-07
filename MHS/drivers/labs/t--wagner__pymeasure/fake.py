"""Fake backend of the Keithley 2000 driver: an in-memory stand-in for the upstream multimeter class.

Gate G7 checks the public members of ``FakeKeithley2000`` against
``instruments.keithley2000_multimeter:Keithley2000Multimeter``: ``identification`` is the upstream property
(``instruments/keithley2000_multimeter.py:677-679``) and ``channels`` is the pymeasure container accessor the
upstream class inherits (``case.py:447-453``); the channel helper mirrors the upstream ChannelRead query and
range properties the driver calls (``instruments/keithley2000_multimeter.py:74-90`` and ``228-249``).  Nothing
here derives from the upstream class, imports it, or talks to an instrument.

The clone ships no simulator, mock or test for this class, so the values below are fixed placeholder test data
(marked ``# placeholder``), not a recording and not a fact about an attached instrument.  The channel objects
are kept for the life of the fake, so a range written through the container stays visible to a later read.
"""


class FakeChannel:
    """Stand-in for the upstream ChannelRead object: one fixed sample per query, with placeholder values."""

    def __init__(self, name, value, range_value):
        self.name = name
        self._value = value
        self._range = range_value

    @property
    def range(self):
        return self._range

    @range.setter
    def range(self, value):
        self._range = float(value)

    def query(self, waiting_time=0, nr_of_samples=1):
        return [self._value for _ in range(nr_of_samples)]


class FakeKeithley2000:
    """The fake multimeter; its public members are the upstream members the driver uses."""

    def __init__(self, **_options):
        self._identification = "Keithley Instruments,2000,000000,FAKE"    # placeholder
        self._channels = [
            FakeChannel("voltage_dc", 1.25, 10.0),                         # placeholder
            FakeChannel("current_dc", 0.0025, 0.1),                         # placeholder
            FakeChannel("resistance", 1000.0, 1000.0),                     # placeholder
        ]
        self._reset_count = 0                                              # placeholder

    @property
    def identification(self):
        return self._identification

    def channels(self):
        """The upstream channel container accessor, in the order the upstream __init__ creates the channels."""
        return list(self._channels)

    def reset(self):
        """The upstream reset; the fake records that the recovery path ran."""
        self._reset_count += 1
