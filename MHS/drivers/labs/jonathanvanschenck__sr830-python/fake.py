"""Fake SCPI transport of the SR830 driver: a lookup replay with the effect of writes.

The upstream class queries ``OFLT ?``, ``SENS ?``, ``SYNC ?``, ``FREQ ?`` and ``OUTP? <n>`` and writes
``OFLT <index>``, ``SENS <index>`` and ``SYNC <index>`` (sr830.py).  This transport answers those exact lines and
lets a write change the answer of its own query, so a fresh transport can serve any order of reads and writes.
It is a lookup fake, not a recording of an instrument run; every canned reply below is test data and is marked as a
placeholder.  Nothing here talks to an instrument.
"""

import math


class FakeSr830:
    def __init__(self, **_options):
        # Everything below is canned test data, not a fact about an instrument: # placeholder
        self.frequency = 1000.0  # placeholder
        self.time_constant_index = 10  # placeholder
        self.sensitivity_index = 17  # placeholder
        self.sync_filter = 1  # placeholder
        self.r = 1.0e-3  # placeholder
        self.theta = 30.0  # placeholder
        self.x = self.r * math.cos(math.radians(self.theta))  # placeholder
        self.y = self.r * math.sin(math.radians(self.theta))  # placeholder
        self.identity = "Stanford_Research_Systems,SR830,000000,0.0"  # placeholder
        self.written = []
        self._pending = []

    def _reply(self, line):
        if line == "*IDN?":
            return self.identity
        if line == "FREQ ?":
            return f"{self.frequency:.10g}"
        if line == "OFLT ?":
            return str(self.time_constant_index)
        if line == "SENS ?":
            return str(self.sensitivity_index)
        if line == "SYNC ?":
            return str(self.sync_filter)
        if line == "OUTP? 1":
            return f"{self.x:.10g}"
        if line == "OUTP? 2":
            return f"{self.y:.10g}"
        if line == "OUTP? 3":
            return f"{self.r:.10g}"
        if line == "OUTP? 4":
            return f"{self.theta:.10g}"
        return None

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        text = line.strip()
        if "?" in text:
            self._pending.append(self._reply(text))
            return
        command, _, argument = text.partition(" ")
        if command == "OFLT" and argument:
            self.time_constant_index = int(argument)
            return
        if command == "SENS" and argument:
            self.sensitivity_index = int(argument)
            return
        if command == "SYNC" and argument:
            self.sync_filter = int(argument)
            return
        raise ValueError(f"the fake SR830 does not implement {text!r}")

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        reply = self._pending.pop(0)
        if reply is None:
            raise TimeoutError("the fake SR830 does not answer this query")
        return reply

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass
