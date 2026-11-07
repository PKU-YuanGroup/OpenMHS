"""Fake backend of the HAMEG HM1507 driver: an in-memory stand-in for HAMEG_HM1507.HAMEG_HM1507.

Gate G7: every public method defined here exists on the upstream class in HAMEG_HM1507.py.  The fake keeps the same
protocol arithmetic as the clone (HAMEG_HM1507.py:93-100 and 105-114): a time base command is ``TBA=`` or ``TBB=``
followed by one character, and a channel command is ``CH1=`` or ``CH2=`` followed by one character.  The command
list is test data, not a device fact; nothing here talks to an instrument.  The upstream class has no read method,
so the fake has none either.
"""

from .driver import TIME_DIVS, V_DIVS


class FakeHamegHm1507:
    def __init__(self, **_options):
        #: Placeholder connection state: the fake stands for an opened port.
        self.connected = True
        #: Every command string the fake received, in order; test data.
        self.commands = []

    def connect(self, port):
        self.connected = True
        self.commands.append(" ")

    def disconnect(self):
        if self.connected:
            self.commands.append("rm0")
        self.connected = False

    def autoset(self):
        self.commands.append("AUTOSET")

    def timeBase(self, base, single, timeDiv):
        if base not in ("A", "B"):
            raise IndexError("Only time base A and B exist")
        if timeDiv not in TIME_DIVS:
            raise IndexError("Unknown timeDiv!")
        settings = (32 if single else 0) + TIME_DIVS.index(timeDiv)
        self.commands.append("TB" + str(base) + "=" + chr(settings))

    def channel(self, channel, inv, modeDc, vDiv):
        if channel not in (1, 2):
            raise IndexError("Only channel 1 and 2 exist")
        if vDiv not in V_DIVS:
            raise IndexError("Unknown vDiv!")
        settings = 16
        if inv:
            settings += 32
        if not modeDc:
            settings += 64
        settings += V_DIVS.index(vDiv)
        self.commands.append("CH" + str(channel) + "=" + chr(settings))
