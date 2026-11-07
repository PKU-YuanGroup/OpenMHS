"""Hardware backend: a Python 3 port of the upstream ``pump`` serial protocol over pyserial.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only).  The acceptance gate runs the fake
backend and never imports this module.

The clone is Python 2 (``pump_controler.py:48``), so it cannot be imported by the Python 3 runtime.  This module
opens the same serial line the upstream constructor opens (``pump_controler.py:11-12``: port, baudrate,
timeout) and reproduces the wire commands of ``pump_controler.py``.  The upstream writes text followed by a
carriage return; this port reads back to a carriage return so the clone's reply slices keep their meaning.
Nothing here was run against hardware by the author of this package.
"""

import time


class Pump:
    """One serial link to the CHX syringe-pump controller, with the upstream method names."""

    def __init__(self, port, baudrate=19200, timeout=1.0):
        import serial

        self._timeout = float(timeout)                     # placeholder: the clone's default timeout (line 11)
        self._ser = serial.Serial(port=port, baudrate=int(baudrate), timeout=self._timeout,
                                  write_timeout=self._timeout)
        self._ser.reset_input_buffer()

    # -- transport -----------------------------------------------------------------------------------------------
    def _readline(self):
        """Read one carriage-return terminated line, keeping a single ``\\r`` as the clone's slices expect."""
        data = bytearray()
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            chunk = self._ser.read(1)
            if not chunk:
                continue
            data.extend(chunk)
            if chunk in (b"\r", b"\n"):
                break
        if not data:
            return ""
        text = bytes(data).decode("ascii", "replace")
        return text.rstrip("\r\n") + "\r"

    def _write(self, text):
        self._ser.write((text + "\r").encode("ascii"))

    def _exchange(self, text):
        self._write(text)
        reply = self._readline()
        if "?" in reply:
            raise RuntimeError(f"the controller rejected {text!r}: {reply!r}")
        return reply

    # -- the upstream method surface -----------------------------------------------------------------------------
    def cmd(self, cmds):
        self._write(cmds)

    def find_pumps(self, tot_range=10):
        pumps = []
        for i in range(tot_range):
            self._write(f"{i}ADR")
            if self._readline():
                pumps.append(i)
        return pumps

    def get_direction(self, pump=0):
        output = self._exchange(f"{pump}DIR")
        return "-" if output[4:7] == "WDR" else "+"

    def set_direction(self, direction="INF", pump=0):
        self._exchange(f"{pump}DIR{direction}")

    def set_rate(self, flowrate, unit="UM*", pump=0):
        direction = "INF"
        if flowrate < 0:
            direction = "WDR"
        self._exchange(f"{pump}DIR{direction}")
        rate = abs(flowrate)
        self._exchange(f"{pump}RAT{str(rate)[:5]}{unit}")

    def set_diameter(self, dia, pump=0):
        self._exchange(f"{pump}DIA{dia}")

    def get_diameter(self, pump=0):
        return self._exchange(f"{pump}DIA")[4:-1]

    def set_volume(self, vol, unit="UL", pump=0):
        self._exchange(f"{pump}VOL {vol}")

    def get_volume(self, pump=0):
        output = self._exchange(f"{pump}VOL")
        return float(output[4:-3]), output[-3:-1]

    def get_dispense(self, direction="INF", pump=0):
        output = self._exchange(f"{pump}DIS")
        unit = output[-3:-1]
        if direction == "INF":
            return float(output[5:10]), unit
        if direction == "WDR":
            return float(output[11:16]), unit
        raise ValueError(f"unknown dispense direction {direction!r}")

    def reset_dispense(self, direction="INF", pump=0):
        self._exchange(f"{pump}CLD {direction}")

    def get_rate(self, pump=0):
        direction = self._exchange(f"{pump}DIR")
        sign = "+"
        if direction[4:7] == "WDR":
            sign = "-"
        output = self._exchange(f"{pump}RAT")
        units = output[-3:-1]
        if units == "NH":
            rate = str(float(output[4:-3]) * 1000)
        elif units == "UH":
            rate = output[4:-3] + " ul/hour"
        elif units == "MH":
            rate = str(float(output[4:-3]) * 1000) + " ml/hour"
        elif units == "UM":
            rate = output[4:-3] + " ul/min"
        else:
            raise RuntimeError(f"the controller returned an unknown rate unit in {output!r}")
        return sign + rate

    def run(self, pump=None):
        self._write("RUN" if pump is None else f"{pump}RUN")

    def stop(self, pump=None):
        self._write("STP" if pump is None else f"{pump}STP")

    def get_version(self):
        self._write("ver")

    def set_(self):
        pass


def connect(port, baudrate=19200, timeout_s=1.0, **options):
    """Open the serial line of the clone; ``options`` may carry the driver's ``address`` and is ignored here."""
    del options
    return Pump(port, baudrate=baudrate, timeout=timeout_s)
