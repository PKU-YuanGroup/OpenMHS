"""Fake SCPI transport of the RIGOL DHO800/DHO900 driver: an in-memory instrument that answers the clone's commands.

The driver's ``native`` is ``scopebench_mcp.transports.tcp:TCPTransport``: a line-oriented SCPI transport with
``write``, ``read``, ``query`` and ``close``.  This class has the same surface and keeps the instrument state in
plain attributes, so a write changes the answer of its own query (``:CHANnel1:COUPling AC`` changes
``:CHANnel1:COUPling?``).  A query that is not implemented raises, like an instrument that does not answer.

Every numeric value below is test data of this fake, not a fact of the device; the ``# placeholder`` comments mark
them.  Nothing here talks to an instrument.
"""

from __future__ import annotations

import re

_IDENTITY = "RIGOL TECHNOLOGIES,DHO804D,FAKE0001,00.01.05"  # placeholder
_MEASURE = re.compile(r"^:MEASure:ITEM\? ([A-Za-z]+),CHANnel([1-4])$")
#: Canned instrument-side measurements, in the unit of the item: Hz, s, V or a ratio.
_MEASUREMENTS = {  # placeholder values
    "FREQuency": 1000.0,   # placeholder: 1 kHz
    "PERiod": 0.001,       # placeholder: 1 ms
    "VPP": 2.964,          # placeholder
    "VMAX": 1.482,         # placeholder
    "VMIN": -1.482,        # placeholder
    "VAVG": 0.0,           # placeholder
    "VRMS": 1.047,         # placeholder
    "PDUTy": 0.5,          # placeholder
    "NDUTy": 0.5,          # placeholder
    "RTIMe": 1e-6,         # placeholder
    "FTIMe": 1e-6,         # placeholder
}


class FakeDhoTransport:
    """A fake line-oriented SCPI transport for one RIGOL DHO oscilloscope."""

    def __init__(self, **_options):
        self.written: list[str] = []
        self._pending: list[str] = []
        self.identity = _IDENTITY
        self.trigger_status = "RUN"  # placeholder
        self.channel_coupling = "DC"  # placeholder
        self.channel_scale = 0.05  # placeholder
        self.channel_offset = 0.0  # placeholder
        self.trigger_level = 0.14  # placeholder
        self.timebase_scale = 0.001  # placeholder
        self.timebase_offset = 0.0  # placeholder

    # -- transport surface -----------------------------------------------------------------------------------------
    def write(self, line, *, timeout_s=None):
        text = line.decode("ascii") if isinstance(line, bytes) else str(line)
        text = text.strip()
        self.written.append(text)
        if "?" in text:
            self._pending.append(self._answer(text))
            return
        self._apply(text)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        self._pending.clear()

    # -- instrument model ------------------------------------------------------------------------------------------
    def _answer(self, text):
        if text == "*IDN?":
            return self.identity
        if text == ":SYSTem:ERRor?":
            return '0,"No error"'  # placeholder
        if text == ":TRIGger:STATus?":
            return self.trigger_status
        if text == ":TRIGger:EDGE:LEVel?":
            return f"{self.trigger_level:g}"
        if text == ":TIMebase:MAIN:SCALe?":
            return f"{self.timebase_scale:g}"
        if text == ":TIMebase:MAIN:OFFSet?":
            return f"{self.timebase_offset:g}"
        if text == ":CHANnel1:COUPling?":
            return self.channel_coupling
        if text == ":CHANnel1:SCALe?":
            return f"{self.channel_scale:g}"
        if text == ":CHANnel1:OFFSet?":
            return f"{self.channel_offset:g}"
        match = _MEASURE.match(text)
        if match is not None:
            item = match.group(1)
            if item not in _MEASUREMENTS:
                raise KeyError(f"FakeDhoTransport: no measurement item {item!r}")
            return f"{_MEASUREMENTS[item]:g}"
        raise KeyError(f"FakeDhoTransport: unexpected query {text!r}")

    def _apply(self, text):
        if text == ":STOP":
            self.trigger_status = "STOP"  # placeholder
            return
        command, _, argument = text.partition(" ")
        if not argument:
            raise KeyError(f"FakeDhoTransport: unexpected command {text!r}")
        value = argument.strip()
        if command == ":CHANnel1:COUPling":
            self.channel_coupling = value
        elif command == ":CHANnel1:SCALe":
            self.channel_scale = float(value)
        elif command == ":CHANnel1:OFFSet":
            self.channel_offset = float(value)
        elif command == ":TRIGger:EDGE:LEVel":
            self.trigger_level = float(value)
        elif command == ":TIMebase:MAIN:SCALe":
            self.timebase_scale = float(value)
        elif command == ":TIMebase:MAIN:OFFSet":
            self.timebase_offset = float(value)
        else:
            raise KeyError(f"FakeDhoTransport: unexpected command {text!r}")
