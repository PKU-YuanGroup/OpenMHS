"""In-memory fake of the Tecan Genesis RS-232 command stack for the fake backend.

The class implements only the attributes of the upstream ``tecan_funcs:Cmd_delayed`` class: ``cmdCount``,
``cmdStack``, ``runningStack``, ``add_cmd`` and ``start``.  ``start`` reproduces the three-phase group feed the
upstream method sends (GFC, each stacked command, GSC), builds the STX/ETX/XOR frame of ``do_cmd`` and records it
in ``written`` so a test can inspect the wire bytes.  It does not open a serial port.

Every value below is test data, not a fact: the fixed command text comes from the clone's examples and the frames
are computed by the protocol algorithm.  Nothing here talks to an instrument.
"""

STX = 0x02
ETX = 0x03
SEQUENCE = "ABCDEFG"


class FakeTecanGenesis:
    def __init__(self, **_options):
        self.cmdStack = []
        self.runningStack = []
        self.cmdCount = 0
        self.written = []
        self._seq = 0

    def add_cmd(self, cmd="RFV", dev="M1"):
        self.cmdStack.append((cmd, dev))
        self.cmdCount += 1

    def start(self):
        frames = []
        for cmd, dev in [("GFC", "M1")] + list(self.cmdStack) + [("GSC", "M1")]:
            frames.append(self._frame(cmd, dev))
        self.written.extend(frames)
        self.runningStack.extend(dev for _cmd, dev in self.cmdStack)
        commands = [f"{dev}:{cmd}" for cmd, dev in self.cmdStack]
        return {"started": True, "commands": commands, "frames": [frame.hex() for frame in frames]}

    def _frame(self, cmd, dev):
        seq = SEQUENCE[self._seq % len(SEQUENCE)]
        self._seq += 1
        body = [ord(char) for char in seq + dev + cmd]
        checksum = 0
        for byte in [STX] + body + [ETX]:
            checksum ^= byte
        return bytes([STX] + body + [ETX, checksum, 0x0A])
