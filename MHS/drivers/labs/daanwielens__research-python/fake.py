"""Fake SCPI transport for the Lake Shore 332 driver.

The upstream clone has no simulator, mock or recorded session: it is a set of Tkinter programs whose callbacks
open the instrument directly (``Lake.py:47-53, 84-87, 175-181``).  This fake is therefore a stateful stand-in for
the text transport, not a recording.  It answers the queries the driver declares and lets each write change the
answer of its own query, so the gate and the conformance suite can exercise the command map.

Every canned value and reply format below is test data for the fake, marked ``# placeholder``; none is a fact, a
limit or a citation.  The real temperatures, ranges and readings come from the instrument.  Gate G7 (transport
mode) checks the command words the driver sends against the clone, not this class.  Nothing here talks to a
temperature controller.
"""

import threading


class FakeLakeshore332:
    """A thread-safe line transport with the Lake Shore 332 command vocabulary used by the driver."""

    def __init__(self, **_options):
        self._lock = threading.Lock()
        self._pending = []
        self.written = []
        # All values below are placeholders for the fake's initial state, not device facts.
        self._temperature = 250.0  # placeholder
        self._temperature_celsius = -23.15  # placeholder
        self._setpoint = 250.0  # placeholder
        self._heater_range = 1  # placeholder
        self._heater_output = 5.0  # placeholder
        self._pid = "10,20,0"  # placeholder
        self._manual_output = 0.0  # placeholder

    def _reply(self, line):
        if line == "KRDG?":
            return format(self._temperature, "+.3f")  # placeholder reply format
        if line == "CRDG?":
            return format(self._temperature_celsius, "+.3f")  # placeholder reply format
        if line == "SETP? 1":
            return format(self._setpoint, "+.3f")  # placeholder reply format
        if line == "RANGE?":
            return str(self._heater_range)  # placeholder reply format
        if line == "HTR?":
            return format(self._heater_output, "+.1f")  # placeholder reply format
        if line == "PID? 1":
            return self._pid
        if line == "MOUT? 1":
            return format(self._manual_output, "+.1f")  # placeholder reply format
        return None

    def _apply(self, line):
        command, _, argument = line.partition(" ")
        if command == "SETP" and argument.startswith("1,"):
            self._setpoint = float(argument.split(",", 1)[1])
        elif command == "MOUT" and argument.startswith("1,"):
            self._manual_output = float(argument.split(",", 1)[1])
        elif command == "PID" and argument.startswith("1,"):
            self._pid = argument.split(",", 1)[1]
        elif command == "RANGE" and argument:
            self._heater_range = int(argument)
            if self._heater_range == 0:
                self._heater_output = 0.0  # placeholder: range 0 is off
            else:
                self._heater_output = 5.0  # placeholder

    def write(self, line, *, timeout_s=None):
        with self._lock:
            self.written.append(line)
            if "?" in line:
                self._pending.append(self._reply(line))
            else:
                self._apply(line)

    def read(self, *, timeout_s=None):
        with self._lock:
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
