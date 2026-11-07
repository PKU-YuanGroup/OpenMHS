"""Fake SCPI transport of the SR860 driver: a stateful register map, not a replay.

A strict transcript needs one fixed request sequence, but the gate and the conformance suite send many different
sequences, each on a fresh transport.  This transport therefore answers every query the driver can send from plain
attributes and lets a setting write change the answer of its own query (``FREQ x`` changes ``FREQ?``, ``SYNC 0``
changes ``SYNC?``, and so on).  An unknown query times out, like an instrument that does not answer.

Every value below is test data for the simulator, not a fact or a limit of the device: each start value is marked
``# placeholder``.  Gate G7 (transport mode) checks the command words the driver sends against the clone, not this
class.  Nothing here talks to an instrument.
"""

import math


class FakeSr860:
    #: Test identity in the *IDN? shape the upstream code parses (second comma field is the model).
    IDENTITY = "Stanford_Research_Systems,SR860,000000,v1.00"  # placeholder

    def __init__(self, **_options):
        self.frequency = 1000.0          # placeholder
        self.amplitude = 1.0             # placeholder
        self.phase = 0.0                 # placeholder
        self.dc_offset = 0.0             # placeholder
        self.harmonic = 1                # placeholder
        self.time_constant_index = 10    # placeholder: 0.1 s in the upstream tuple
        self.sync_filter_enable = True   # placeholder
        self.adv_filter_enable = False   # placeholder
        self.x_offset = 0.0              # placeholder
        self.y_offset = 0.0              # placeholder
        self.r_offset = 0.0              # placeholder
        self.x_offset_enable = False     # placeholder
        self.y_offset_enable = False     # placeholder
        self.r_offset_enable = False     # placeholder
        self.x = 1.5e-3                  # placeholder
        self.y = -2.5e-4                 # placeholder
        self.r = math.hypot(self.x, self.y)
        self.theta = math.degrees(math.atan2(self.y, self.x))
        self._pending = []
        self.written = []

    # -- transport ---------------------------------------------------------
    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        if "?" in line:
            self._pending.append(self._answer(line))
            return
        self._set(line)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        reply = self._pending.pop(0)
        if reply is None:
            raise TimeoutError("the instrument does not answer this query")
        return reply

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    # -- register map ------------------------------------------------------
    def _set(self, line):
        head, _, rest = line.partition(" ")
        value = rest.strip()
        if head == "FREQ":
            self.frequency = float(value)
        elif head == "SLVL":
            self.amplitude = float(value)
        elif head == "PHAS":
            self.phase = float(value)
        elif head == "SOFF":
            self.dc_offset = float(value)
        elif head == "HARM":
            self.harmonic = int(value)
        elif head == "OFLT":
            self.time_constant_index = int(value)
        elif head == "SYNC":
            self.sync_filter_enable = bool(int(value))
        elif head == "ADVFILT":
            self.adv_filter_enable = bool(int(value))
        elif head == "COFP":
            index, _, number = rest.partition(",")
            setattr(self, ("x_offset", "y_offset", "r_offset")[int(index)], float(number))
        elif head == "COFA":
            index, _, number = rest.partition(",")
            setattr(self, ("x_offset_enable", "y_offset_enable", "r_offset_enable")[int(index)],
                    bool(int(number)))

    def _answer(self, line):
        if line == "*IDN?":
            return self.IDENTITY
        if line == "FREQ?":
            return repr(self.frequency)
        if line == "SLVL?":
            return repr(self.amplitude)
        if line == "PHAS?":
            return repr(self.phase)
        if line == "SOFF?":
            return repr(self.dc_offset)
        if line == "HARM?":
            return str(self.harmonic)
        if line == "OFLT?":
            return str(self.time_constant_index)
        if line == "SYNC?":
            return "1" if self.sync_filter_enable else "0"
        if line == "ADVFILT?":
            return "1" if self.adv_filter_enable else "0"
        if line.startswith("COFP? "):
            index = int(line.split()[1])
            return repr((self.x_offset, self.y_offset, self.r_offset)[index])
        if line.startswith("COFA? "):
            index = int(line.split()[1])
            return "1" if (self.x_offset_enable, self.y_offset_enable, self.r_offset_enable)[index] else "0"
        if line.startswith("OUTP? "):
            index = int(line.split()[1])
            return repr((self.x, self.y, self.r, self.theta)[index])
        return None
