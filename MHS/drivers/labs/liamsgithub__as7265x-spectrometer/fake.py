"""Fake backend of the AS7265x driver: an in-memory stand-in for the clone's module-level functions.

The upstream clone has no class: ``spectrometer.py`` exposes the functions ``readReg``, ``writeReg``, ``setDEVSEL``,
``init``, ``boardPresent``, ``hwVersion``, ``temperatures``, ``setBlueLED``, ``shutterLED``, ``setLEDDriveCurrent``,
``setIntegrationTime``, ``setGain``, ``readRAW`` and ``readCAL``.  This class defines only those public names (gate
G7 checks the fake against the upstream class named by ``native``); the driver resolves them on the backend object
that ``native.py`` returns.  The clone is Python 2.7, so the gate cannot parse it; see RESULT.json.

The register addresses and bit masks follow the clone (for example 0x05 for the integration time, 0x07 bit 0 for the
blue LED and bit 3 for a shutter LED); the starting register values and the array replies are test data of this
stand-in, marked ``# placeholder``, not device facts.  Nothing here talks to a device.
"""

import struct

#: Device names the clone selects (spectrometer.py:122, 195).
DEVICES = ("AS72651", "AS72652", "AS72653")

#: The clone's reorder mapping from read order to ascending frequency order (spectrometer.py:140).
REORDER = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (13, 9), (14, 11), (9, 10),
           (10, 12), (15, 13), (16, 14), (17, 15), (18, 16), (11, 17), (12, 18)]

#: Canned raw reply of this stand-in (18 values, ascending frequency order); placeholder test data.
RAW_VALUES = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117]  # placeholder

#: Canned calibrated reply of this stand-in (18 values, ascending frequency order); placeholder test data.
CAL_VALUES = [float(value) for value in range(1, 19)]  # placeholder


def _default_registers():
    """Placeholder register contents of the three devices: integration time 10, everything else at 0."""
    defaults = {}
    for index, device in enumerate(DEVICES):
        defaults[device] = {
            0x00: 0x40,              # placeholder: device type
            0x01: 0x01,              # placeholder: hardware version
            0x04: 0x00,              # placeholder: gain code 0
            0x05: 10,                # placeholder: integration time register
            0x06: 25 + index,        # placeholder: temperature register
            0x07: 0x00,              # placeholder: LEDs off, drive current code 0
        }
    return defaults


class FakeAs7265xSpectrometer:
    def __init__(self, **_options):
        self._registers = _default_registers()
        self._selected = DEVICES[0]

    # -- low level ------------------------------------------------------------------------------------------------
    def readReg(self, addr):
        return int(self._registers[self._selected].get(int(addr), 0))  # placeholder default for an unwritten register

    def writeReg(self, addr, data):
        self._registers[self._selected][int(addr)] = int(data) & 0xFF

    def setDEVSEL(self, device):
        if device not in self._registers:
            return False
        self._selected = device
        return True

    # -- spec functions -------------------------------------------------------------------------------------------
    def init(self):
        self._registers = _default_registers()
        self._selected = DEVICES[0]

    def boardPresent(self):
        return True  # placeholder reply of the stand-in

    def hwVersion(self):
        return (0x40, 0x01)  # placeholder reply of the stand-in

    def swVersion(self):
        return None

    def temperatures(self):
        values = []
        for device in DEVICES:
            self.setDEVSEL(device)
            values.append(self.readReg(0x06))
        return values

    def setBlueLED(self, state):
        self.setDEVSEL(DEVICES[0])
        current = self.readReg(0x07)
        self.writeReg(0x07, (current | 0x01) if state else (current & 0xFE))
        return True

    def shutterLED(self, device, state):
        if device not in self._registers:
            return False
        self.setDEVSEL(device)
        current = self.readReg(0x07)
        self.writeReg(0x07, (current | 0x08) if state else (current & 0xF7))
        return True

    def setLEDDriveCurrent(self, current):
        if current not in [0, 1, 2, 3]:
            return False
        for device in DEVICES:
            self.setDEVSEL(device)
            config = self.readReg(0x07)
            self.writeReg(0x07, (config & 0b11001111) | (int(current) << 4))
        return True

    def setIntegrationTime(self, time):
        if time not in range(0, 255):
            return False
        for device in DEVICES:
            self.setDEVSEL(device)
            self.writeReg(0x05, int(time))
        return True

    def setGain(self, gain):
        if gain not in [0, 1, 2, 3]:
            return False
        for device in DEVICES:
            self.setDEVSEL(device)
            config = self.readReg(0x04)
            self.writeReg(0x04, (config & 0b11001111) | (int(gain) << 4))
        return True

    def readRAW(self):
        return list(RAW_VALUES)

    def readCAL(self):
        return list(CAL_VALUES)

    def IEEE754toFloat(self, valArray):
        return struct.unpack(">f", bytes(int(item) & 0xFF for item in valArray))[0]

    def reorderData(self, unsortedData):
        sortedData = [0] * 18
        for source, target in REORDER:
            sortedData[target - 1] = unsortedData[source - 1]
        return sortedData
