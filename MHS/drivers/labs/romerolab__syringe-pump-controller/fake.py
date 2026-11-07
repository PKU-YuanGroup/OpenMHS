"""Fake serial link of the New Era pump: a stateful stand-in for the object the upstream GUI owns.

The upstream repository has no device class.  Its GUI (``pump_control.py:14``) opens the pyserial object
``self.ser`` (``pump_control.py:22``) and the protocol functions in ``new_era.py`` call ``ser.write`` and
``ser.readline``.  This fake implements those two transport methods and the CR-terminated commands of
``new_era.py``: ``<n>ADR``, ``<n>DIR``, ``<n>RAT``, ``<n>DIA``, ``<n>RUN``, ``<n>STP`` and the broadcast
``*RUN``/``*STP``.  A write changes the answer of its own query, so the gate and the conformance suite can
send any sequence on a fresh link.  The broadcast stop is answered with nothing because the driver's e-stop
and safe-state action write it without reading a reply.

Gate G7 checks these methods against ``pump_control:PumpControl``; ``write``, ``readline`` and ``close`` are
the transport attributes the GUI's ``self.ser`` has (``pump_control.py:22``, ``new_era.py:8``) and the AST
cannot see them through pyserial, so G7 reports them as MAYBE_ABSENT warnings.  Nothing here talks to a device.
"""

import threading

#: All numbers below are canned test data, not facts about an instrument.
_START_RATE_UH = 0.0          # placeholder
_START_DIAMETER_MM = 4.699    # placeholder
_START_DIRECTION = "INF"      # placeholder
_START_ADDRESS = 0            # placeholder


class FakePumpLink:
    """A pyserial-like link that parses the CR-terminated commands of ``new_era.py``."""

    def __init__(self, **_options):
        address = _options.get("address", _START_ADDRESS)
        self._address = int(address)
        self._flow_rate_uh = _START_RATE_UH
        self._diameter_mm = _START_DIAMETER_MM
        self._direction = _START_DIRECTION
        self._running = False
        self._buffer = b""
        self._lock = threading.Lock()

    # -- transport surface ---------------------------------------------------------------------------------------
    def write(self, data):
        if isinstance(data, str):
            data = data.encode("ascii")
        with self._lock:
            text = bytes(data).decode("ascii", "replace").strip("\r\n")
            if text:
                self._handle(text)
            return len(data)

    def readline(self):
        with self._lock:
            if not self._buffer:
                return b""
            end = self._buffer.find(b"\r")
            if end < 0:
                line, self._buffer = self._buffer, b""
                return line
            line, self._buffer = self._buffer[:end + 1], self._buffer[end + 1:]
            return line

    def close(self):
        with self._lock:
            self._buffer = b""

    # -- protocol ------------------------------------------------------------------------------------------------
    def _reply(self, text):
        self._buffer += (text + "\r").encode("ascii")

    def _ack(self, text):
        self._reply(f"{text}:  OK")

    def _handle(self, text):
        if text in ("*RUN", "*STP"):
            # The broadcast commands are written without a reply by the driver; no reply keeps the link in step.
            self._running = text == "*RUN"
            return
        if text.startswith("*"):
            # The upstream rate chain uses '*' as a separator; answer the last part once.
            for part in [item for item in text.split("*") if item]:
                self._handle(part)
            return
        head = text[:1]
        address = None
        if head.isdigit():
            split = 1
            while split < len(text) and text[split].isdigit():
                split += 1
            address, command = int(text[:split]), text[split:]
        else:
            command = text
        if command == "ADR":
            if address is None:
                self._reply("?:  ADR")
            else:
                self._ack(address)
            return
        if command in ("DIRINF", "DIRWDR"):
            self._direction = command[3:]
            self._ack(address if address is not None else "")
            return
        if command in ("DIR", "DIR?") or command.startswith("DIR"):
            if command == "DIR":
                self._reply(f"{address}:  {self._direction}")
            else:
                self._ack(address if address is not None else "")
            return
        if command == "RAT":
            unit = "UH" if self._flow_rate_uh < 5000 else "MH"
            value = self._flow_rate_uh if unit == "UH" else self._flow_rate_uh / 1000.0
            self._reply(f"{address}:  {value} {unit}")
            return
        if command.startswith("RAT"):
            argument = command[3:]
            unit = argument[-2:]
            value = argument[:-2]
            try:
                number = float(value)
            except ValueError:
                self._reply("?:  RAT")
                return
            self._flow_rate_uh = number * 1000.0 if unit == "MH" else number
            self._ack(address if address is not None else "")
            return
        if command == "DIA":
            self._reply(f"{address}:  {self._diameter_mm}")
            return
        if command.startswith("DIA"):
            try:
                self._diameter_mm = float(command[3:])
            except ValueError:
                self._reply("?:  DIA")
                return
            self._ack(address if address is not None else "")
            return
        if address is None:
            self._reply("?:  broadcast")
            return
        if command == "RUN":
            self._running = True
            self._ack(address)
            return
        if command == "STP":
            # The driver stops with a write-only command (the action's finally block and the e-stop), so no reply.
            self._running = False
            return
        self._reply("?:  unknown command")
