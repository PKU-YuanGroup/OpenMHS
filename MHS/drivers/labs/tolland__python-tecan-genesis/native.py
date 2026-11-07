"""Hardware transport factory for the Tecan Genesis RSP 200 (the ``.native:connect`` backend).

The upstream clone is Python 2 and cannot be imported by the Python 3 runtime, so this module reimplements the
frame documented in ``bin/tecan_funcs.py:147-164``: STX (0x02), the rotating sequence letter A-G, the unit address,
the ASCII command, ETX (0x03), the XOR of those bytes and a trailing newline.  It exposes the attributes the
driver uses from ``tecan_funcs:Cmd_delayed``: ``cmdStack``, ``runningStack``, ``cmdCount``, ``add_cmd`` and
``start``.  ``start`` sends GFC, every stacked command and GSC to the M1 controller, exactly as
``Cmd_delayed.start`` does (``bin/tecan_funcs.py:70-80``).

The gate never imports this module; the loader refuses the hardware backend of this model-authored R2 package until
a human sets ``reviewed_by`` in driver.lock.json.  No hardware was attached and this code was never run.
"""

from __future__ import annotations

import time

STX = 0x02
ETX = 0x03
SEQUENCE = "ABCDEFG"


class CmdDelayedTransport:
    """A Python 3 transport with the command-stack surface of ``tecan_funcs:Cmd_delayed``."""

    def __init__(self, port=None, baudrate=9600, timeout_s=1.0, **_options):
        self.port = port or "/dev/ttyUSB0"
        self.baudrate = int(baudrate)
        self.timeout_s = float(timeout_s)
        self.cmdStack = []
        self.runningStack = []
        self.cmdCount = 0
        self.written = []
        self._serial = None
        self._seq = 0

    def _open(self):
        if self._serial is None:
            import serial

            self._serial = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout_s)
        return self._serial

    def add_cmd(self, cmd="RFV", dev="M1"):
        self.cmdStack.append((cmd, dev))
        self.cmdCount += 1

    def start(self):
        serial_port = self._open()
        frames = [self._frame("GFC", "M1")]
        for cmd, dev in list(self.cmdStack):
            frames.append(self._frame(cmd, dev))
            self.runningStack.append(dev)
        frames.append(self._frame("GSC", "M1"))
        for frame in frames:
            serial_port.write(frame)
            self.written.append(frame)
            time.sleep(0.1)
        replies = []
        for dev in self.runningStack:
            replies.append(self._read(dev))
        commands = [f"{dev}:{cmd}" for cmd, dev in self.cmdStack]
        return {"started": True, "commands": commands, "replies": replies}

    def _frame(self, cmd, dev):
        seq = SEQUENCE[self._seq % len(SEQUENCE)]
        self._seq += 1
        body = [ord(char) for char in seq + dev + cmd]
        checksum = 0
        for byte in [STX] + body + [ETX]:
            checksum ^= byte
        return bytes([STX] + body + [ETX, checksum, 0x0A])

    def _read(self, dev):
        serial_port = self._open()
        deadline = time.monotonic() + self.timeout_s
        buffer = bytearray()
        while time.monotonic() < deadline:
            chunk = serial_port.read(1)
            if not chunk:
                continue
            buffer.extend(chunk)
            if chunk == b"\n":
                break
        payload = _frame_payload(bytes(buffer))
        return payload if payload is not None else ""

    def close(self):
        if self._serial is not None:
            self._serial.close()
            self._serial = None


def _frame_payload(data):
    """The payload of the first STX...ETX frame in ``data`` (the XOR byte is not compared, as the clone's read)."""
    start = data.find(bytes([STX]))
    end = data.find(bytes([ETX]), start + 1)
    if start < 0 or end < 0:
        return None
    return data[start + 1:end].decode("ascii", "replace")


def connect(**options):
    return CmdDelayedTransport(**options)
