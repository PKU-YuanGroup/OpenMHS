"""Fake backend of the LabJack U3 driver: an in-memory stand-in for u3:U3.

Gate G7: every public method defined here exists on the upstream class u3:U3 or its base Device
(src/u3.py:63, src/LabJackPython.py:189): ``configIO`` (src/u3.py:312), ``getAIN`` (src/u3.py:588),
``getTemperature`` (src/u3.py:570), ``getDIOState`` (src/u3.py:551), ``setDOState`` (src/u3.py:513),
``reset`` (src/u3.py:954) and ``close`` (src/LabJackPython.py:655).  The signatures mirror the upstream ones.

Every number below is test data for this stand-in, never a Fact, a Limit or a reference: each one is marked
``# placeholder``.  The values never move by themselves, so reading the state twice gives the same state.  The
stand-in starts with the FIO/EIO analog masks, digital line states and analog input voltage below; a reset returns
them to their starting values.  Nothing here talks to a device.
"""


class FakeU3:
    def __init__(self, **_options):
        self._fio_analog = 15            # placeholder test data: FIO0-FIO3 analog
        self._eio_analog = 0             # placeholder test data: no EIO line analog
        self._ain0 = 1.25                # placeholder test data: canned AIN0 voltage
        self._temperature = 295.15       # placeholder test data: canned internal temperature in Kelvin
        self._dio = [0] * 20             # placeholder test data: all 20 digital lines low
        self._timer_counter_config = 64  # placeholder test data: canned TimerCounterConfig
        self._timer_counter_pin_offset = 4   # placeholder test data: canned pin offset
        self._resets = 0                 # placeholder test data: reset count of the stand-in
        self._closed = False

    def configIO(self, TimerCounterPinOffset=None, EnableCounter1=None, EnableCounter0=None,
                 NumberOfTimersEnabled=None, FIOAnalog=None, EIOAnalog=None, EnableUART=None):
        """Read or write the IO configuration; returns the same keys as the upstream method (src/u3.py:420)."""
        if FIOAnalog is not None:
            self._fio_analog = int(FIOAnalog) & 0xFF    # placeholder test data: mask an 8-bit field
        if EIOAnalog is not None:
            self._eio_analog = int(EIOAnalog) & 0xFF    # placeholder test data: mask an 8-bit field
        if TimerCounterPinOffset is not None:
            self._timer_counter_pin_offset = int(TimerCounterPinOffset)
        return {
            "TimerCounterConfig": self._timer_counter_config,
            "DAC1Enable": 0,                          # placeholder test data: DAC1 disabled
            "FIOAnalog": self._fio_analog,
            "EIOAnalog": self._eio_analog,
            "NumberOfTimersEnabled": 0,               # placeholder test data: no timer
            "EnableCounter0": False,                  # placeholder test data: no counter
            "EnableCounter1": False,                  # placeholder test data: no counter
            "TimerCounterPinOffset": self._timer_counter_pin_offset,
        }

    def getAIN(self, posChannel, negChannel=31, longSettle=False, quickSample=False):
        """One calibrated analog input voltage (src/u3.py:588-631); only AIN0 is wired in this stand-in."""
        return self._ain0

    def getTemperature(self):
        """The internal temperature sensor in Kelvin (src/u3.py:570-586)."""
        return self._temperature

    def getDIOState(self, ioNum):
        """The state of one digital line without changing its direction (src/u3.py:551-568)."""
        return self._dio[int(ioNum)]

    def setDOState(self, ioNum, state=1):
        """Write one digital line; the line is also set to output (src/u3.py:513-530)."""
        self._dio[int(ioNum)] = int(state) & 1       # placeholder test data: one-bit line state

    def reset(self, hardReset=False):
        """Soft or hard reset (src/u3.py:954-977): the stand-in returns to its starting state."""
        self._fio_analog = 15            # placeholder test data: FIO0-FIO3 analog after reset
        self._eio_analog = 0             # placeholder test data: no EIO line analog after reset
        self._dio = [0] * 20             # placeholder test data: all lines low after reset
        self._timer_counter_config = 64  # placeholder test data: canned TimerCounterConfig after reset
        self._timer_counter_pin_offset = 4   # placeholder test data: canned pin offset after reset
        self._resets += 1                # placeholder test data: reset count of the stand-in

    def close(self):
        """Close the device handle (src/LabJackPython.py:655-681)."""
        self._closed = True
