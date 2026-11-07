"""Fake backend of the LabJack U12 driver: an in-memory stand-in for the Lantz U12 wrapper.

Gate G7: every public method defined here exists on the upstream class
lantz.drivers.labjack._internal.u12:U12 (u12.py:395).  The methods mirror the high-level U12 calls the driver uses:
``getDriverVersion`` (2497), ``getFirmwareVersion`` (2510), ``eAnalogIn`` (1908), ``eCount`` (1977), ``aiBurst``
(2155), ``eAnalogOut`` (1942), ``pulseOutStart`` (2645), ``localID`` (2584), ``rawReadLocalId`` (568), ``reset``
(2729) and ``close`` (508).  The ``streaming`` flag is set by the upstream __init__ (u12.py:407) and by
``aiStreamStart`` (u12.py:2226).

Every number below is test data for this stand-in, never a Fact, a Limit or a reference: each one is marked
``# placeholder``.  The values never move by themselves, so reading the state twice gives the same state.  Nothing
here talks to a device.
"""


class FakeU12:
    def __init__(self, **_options):
        self.id = 0                         # placeholder: local ID of the stand-in
        self.streaming = False              # placeholder: no stream is running
        self._driver_version = 1.21         # placeholder: canned driver version
        self._firmware_version = 1.0        # placeholder: canned firmware version
        self._voltage = 1.25                # placeholder: canned AIN0 voltage
        self._counter = 17                  # placeholder: canned counter value
        self._local_id = 0                  # placeholder: canned stored local ID
        self._ao0 = 0.0                     # placeholder: analog output 0 start value
        self._ao1 = 0.0                     # placeholder: analog output 1 start value
        self._pulse = None                  # placeholder: no pulse train started
        self._resets = 0                    # placeholder: reset count of the stand-in
        self._closed = False

    def getDriverVersion(self):
        return self._driver_version

    def getFirmwareVersion(self, idNum=None):
        return {"idnum": self.id, "firmware": self._firmware_version}

    def eAnalogIn(self, channel, idNum=None, demo=0, gain=0):
        return {"idnum": self.id, "overVoltage": 0, "voltage": self._voltage}   # placeholder: no overvoltage

    def eCount(self, idNum=None, demo=0, resetCounter=0):
        return {"idnum": self.id, "count": self._counter, "ms": 0.0}   # placeholder: canned timestamp

    def aiBurst(self, numChannels, channels, scanRate, numScans, idNum=None, demo=0, stateIOin=0, updateIO=0,
                ledOn=0, gains=None, disableCal=0, triggerIO=0, triggerState=0, timeout=1, transferMode=0):
        samples = [self._voltage + index * 0.001 for index in range(int(numScans))]   # placeholder: canned ramp
        return {"idnum": self.id, "scanRate": float(scanRate), "voltages": [samples, samples, samples, samples],
                "stateIOout": [], "overVoltage": 0}   # placeholder: four channels, no overvoltage

    def eAnalogOut(self, analogOut0, analogOut1, idNum=None, demo=0):
        self._ao0, self._ao1 = float(analogOut0), float(analogOut1)
        return {"idnum": self.id}

    def pulseOutStart(self, bitSelect, numPulses, timeB1, timeC1, timeB2, timeC2, idNum=None, demo=0, lowFirst=0):
        self._pulse = (int(bitSelect), int(numPulses), int(timeB1), int(timeC1), int(timeB2), int(timeC2))
        return {"idnum": self.id}

    def localID(self, localID, idNum=None):
        self._local_id = int(localID)
        return {"idnum": self.id}

    def rawReadLocalId(self):
        return self._local_id

    def reset(self, idNum=None):
        self.streaming = False
        self._ao0 = 0.0                     # placeholder: reset returns outputs to zero
        self._ao1 = 0.0                     # placeholder: reset returns outputs to zero
        self._pulse = None
        self._resets += 1                   # placeholder: reset count of the stand-in
        return {"idnum": self.id}

    def close(self):
        self._closed = True
