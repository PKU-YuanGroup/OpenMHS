"""Fake backend of the CompactERAS driver: an in-memory stand-in for compacteras:CompactERAS.

Gate G7: the only public methods defined here are ``verifyVersion`` and ``getSupportedDevices``, which
exist on ``sophys.common.devices.compacteras:CompactERAS``
(src/sophys/common/devices/compacteras.py:71-76, 144-146).  The device members the driver reaches are
the ``CH1`` to ``CH4`` Channel components and the ``version`` and ``supported_devices`` signals that
the upstream class declares as Components (compacteras.py:56-69); each Channel here holds the
``voltage`` and ``current`` read-only signals of compacteras.py:20-21.  The values are frozen test
data of this stand-in, not device facts: every one is marked ``# placeholder`` and none is copied into
a Fact, a Limit or the reference.  The values never move by themselves, so reading the state twice
gives the same state.  Nothing here talks to an electrometer.
"""

import logging


class _FakeSignal:
    """The read-only part of an ophyd Signal that the driver uses: ``get()``."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class _FakeChannel:
    """A Channel Device with its two read-only EpicsSignalRO Components."""

    def __init__(self, voltage, current):
        self.voltage = _FakeSignal(voltage)
        self.current = _FakeSignal(current)


class FakeCompactERAS:
    def __init__(self, **_options):
        self.CH1 = _FakeChannel(voltage=1.0, current=1.0e-9)    # placeholder test data
        self.CH2 = _FakeChannel(voltage=2.0, current=2.0e-9)    # placeholder test data
        self.CH3 = _FakeChannel(voltage=3.0, current=3.0e-9)    # placeholder test data
        self.CH4 = _FakeChannel(voltage=4.0, current=4.0e-9)    # placeholder test data
        self.version = _FakeSignal("1.0.0")                     # placeholder test data
        self.supported_devices = _FakeSignal("ERAS1 ERAS2")     # placeholder test data
        self.sampling_rate = _FakeSignal(1000.0)                # placeholder test data
        self.acquisition_bandwidth = _FakeSignal(100.0)         # placeholder test data

    def verifyVersion(self, minimum_version, maximum_version=None, logger=None):
        """As upstream, a version mismatch warns but a successful read still returns True."""
        if logger is None:
            logger = logging.getLogger()
        current = str(self.version.get())
        major, minor, *_ = (int(part) for part in current.split("."))
        minimum_major, minimum_minor, *_ = (int(part) for part in minimum_version.split("."))
        if maximum_version is None:
            maximum_major = minimum_major + 1
            maximum_minor = 0
        else:
            maximum_major, maximum_minor, *_ = (int(part) for part in maximum_version.split("."))
        if (
            (major, minor) < (minimum_major, minimum_minor)
            or (major, minor) > (maximum_major, maximum_minor)
        ):
            logger.warning("SoftIOC has an incompatible major version, so things might be broken! "
                           "(Expected: %s.%s - %s.%s, Got: %s)",
                           minimum_major, minimum_minor, maximum_major, maximum_minor, current)
        return True

    def getSupportedDevices(self):
        return str(self.supported_devices.get()).split(" ")
