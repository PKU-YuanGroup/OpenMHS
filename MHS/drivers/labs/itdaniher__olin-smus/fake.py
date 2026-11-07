"""Fake backend of the Olin SMU driver: an in-memory stand-in for modconsmu.modconsmu:smu.

Gate G7: the public methods defined here, set() and update(), are the two public methods of the upstream class
(modconsmu/modconsmu.py:60-101), and the attributes the driver reaches, v, i and driving, are set by the upstream
__init__ (modconsmu/modconsmu.py:33-36).  set() copies the upstream branch structure: it stores one target, switches
the driving mode and calls update(); update() returns the measured voltage and current, and the third value when mod
is true.  The numbers below are test data, not device facts: every one is marked placeholder.  The fake models an
ideal source (the measured quantity equals the active target and the other quantity is zero) and nothing moves by
itself, so two reads of the same state agree.  Nothing here talks to a device.
"""


class FakeOlinSmus:
    def __init__(self, **_options):
        self.v = 0.0                    # placeholder: voltage target
        self.i = 0.0                    # placeholder: current target
        self.driving = "i"
        self.updateNeeded = 0
        self._measured_voltage = 0.0    # placeholder
        self._measured_current = 0.0    # placeholder
        self._mod_voltage = 0.0         # placeholder

    def set(self, volts=None, amps=None):
        if volts and amps != None:
            raise NotImplementedError
        if volts != None:
            self.v = volts
            self.driving = "v"
            self.updateNeeded = 1
        elif amps != None:
            self.i = amps
            self.driving = "i"
            self.updateNeeded = 1
        self.update()

    def update(self, mod=1):
        if self.driving == "v":
            self._measured_voltage = float(self.v)      # placeholder: ideal voltage-source model
            self._measured_current = 0.0                # placeholder
        elif self.driving == "i":
            self._measured_voltage = 0.0                # placeholder
            self._measured_current = float(self.i)      # placeholder: ideal current-source model
        self.updateNeeded = 0
        if mod:
            return (self._measured_voltage, self._measured_current, self._mod_voltage)
        return (self._measured_voltage, self._measured_current)
