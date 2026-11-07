"""Fake backend of the Multi-Tube-OD-Reader driver: an in-memory stand-in for my_app.classes.device:Device.

Gate G7: the fake device's public methods are the methods of the upstream Device class
(my_app/classes/device.py:34) -- ``connect`` (line 112), ``rename`` (line 122) and ``blink`` (line 134) -- and the
starting attributes ``name`` and ``sn`` are the ones the upstream constructor assigns (lines 54-55) and ``ports``
the list of 16 Port objects (line 58).  ``Device.connect`` returns the LabJack U3 handle (device.py:114-120);
``_FakeU3`` stands in for that external u3.U3 object, with the only methods this driver calls on it: ``configIO``
(timecourse.py:68), ``getAIN`` (the U3 convenience read of the analog input) and ``close`` (the handle close).

Every number and text below is placeholder test data, never a Fact, a Limit or a reference.  The values never
move by themselves, so reading the state twice gives the same state.  Nothing here talks to a device.
"""


class _FakePort:
    """One physical port position: the attributes the upstream Port assigns (my_app/classes/port.py:24-27)."""

    def __init__(self, device, position):
        self.users = []
        self.usage = 0                  # placeholder test data: port unused
        self.device = device
        self.position = position


class _FakeU3:
    """Stand-in for the u3.U3 handle returned by Device.connect (my_app/classes/device.py:119-120)."""

    def __init__(self, owner):
        self._owner = owner
        self._closed = False

    def configIO(self, FIOAnalog=None, EIOAnalog=None, **options):
        """Record the analog mask the driver selected; the upstream method returns the configuration."""
        self._owner.configurations.append(
            {"FIOAnalog": FIOAnalog, "EIOAnalog": EIOAnalog})       # placeholder test record
        return {"FIOAnalog": 0 if FIOAnalog is None else int(FIOAnalog),    # placeholder test reply
                "EIOAnalog": 0 if EIOAnalog is None else int(EIOAnalog)}   # placeholder test reply

    def getAIN(self, posChannel, negChannel=31, longSettle=False, quickSample=False):  # placeholder signature default
        """Return a canned calibrated voltage that depends on the AIN position (placeholder test data)."""
        if self._closed:
            raise RuntimeError("the fake U3 handle is closed")
        self._owner.ain_reads.append(int(posChannel))              # placeholder test record
        return 0.5 + 0.25 * int(posChannel)                        # placeholder test data

    def getTemperature(self):
        """A canned internal temperature in Kelvin (placeholder test data)."""
        return 295.15                                              # placeholder test data

    def close(self):
        """Close the handle; the upstream u3.U3 inherits close from its Device base."""
        self._closed = True
        self._owner.handle_closes += 1                             # placeholder test record


class FakeMultiTubeOdReader:
    """In-memory Device with 16 ports; it never opens a device or imports the clone."""

    def __init__(self, **_options):
        self.name = "fake-mtodr"            # placeholder test data
        self.sn = "470000001"               # placeholder test data
        self.ports = [_FakePort(self, position) for position in range(1, 17)]   # placeholder test data
        self.ain_reads = []                 # placeholder test record
        self.configurations = []            # placeholder test record
        self.handle_closes = 0              # placeholder test record
        self.blinks = 0                     # placeholder test record

    def connect(self):
        """The upstream Device.connect opens u3.U3 by serial number and returns the handle (device.py:112-120)."""
        return _FakeU3(self)

    def rename(self, new_name):
        """The upstream Device.rename writes the firmware name and updates the Device name (device.py:122-132)."""
        self.name = str(new_name)

    def blink(self):
        """The upstream Device.blink flashes the indicator LED and closes the connection (device.py:134-148)."""
        self.blinks += 1                    # placeholder test record
