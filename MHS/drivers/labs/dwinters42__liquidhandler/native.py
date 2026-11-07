"""Hardware backend: a Python 3 port of the clone's framed-serial protocol for liquidhandler:Robot.

The clone's ``liquidhandler.py`` is Python 2 source (it uses ``print`` statements and ``raise ValueError, ...``), so
it cannot be imported under Python 3.  Gate G7 says in that case ``native.py`` must port it; this module ports the
subset of ``Robot`` the driver serves, using the frame, checksum, addresses and commands documented in
``Protocol.md:23-79`` and implemented in ``liquidhandler.py:130-209``.  It never imports the clone.

Used only with ``backend="hardware"``.  This package is model-authored and unreviewed and it is R2, so the loader
refuses this backend until a human signs ``reviewed_by`` in ``driver.lock.json``; the acceptance gate runs the fake
backend and never imports this module.  A serial line is opened at 9600 8N1 with no handshake as the protocol states
(``Protocol.md:23-26``); the transport wait ``timeout_s`` is a communication bound, not a device fact.

The port below follows ``liquidhandler.py``, copyright (c) 2010,2011 Daniel Winters <daniel@tydirium.org>.  The
upstream file grants permission to use, copy, modify, and distribute the software for any purpose with or without
fee, provided that the copyright notice and this permission notice appear in all copies:

Permission to use, copy, modify, and distribute this software for
any purpose with or without fee is hereby granted, provided that the
above copyright notice and this permission notice appear in all
copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA
OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

import time

#: The framed protocol's header and trailer bytes (Protocol.md:23-26).
FRAME_START = b"\xff\x02"
FRAME_END = b"\x03"
TERMINATOR = b"\r"


class Robot:
    """A Python 3 port of the driver-facing part of ``liquidhandler.Robot``."""

    def __init__(self, port="/dev/ttyUSB0", timeout_s=30.0, **_options):
        import serial  # pyserial, imported only when the hardware backend is actually opened

        self.armaddr = [18, 28]
        self.armlimits = [[2500, 1000, 1200, 10], [1600, 1000, 1200, 10]]
        self.pumpaddr = [11]
        self.syringecontents = [0]
        self.locations = {}
        self.curpos = [[0, 0, 0], [0, 0, 0]]
        self.s = serial.Serial(port, baudrate=9600, bytesize=8, parity="N", stopbits=1,
                               rtscts=0, xonxoff=0, timeout=0)
        self.timeout_s = float(timeout_s)
        for address in self.armaddr:
            self._sendcommand(address, "PI")
            self._sendcommand(address, "SP0")
            self._sendcommand(address, "SA %i %i %i %i" % (self.armlimits[self.armaddr.index(address)][0],
                                                           self.armlimits[self.armaddr.index(address)][2],
                                                           self.armlimits[self.armaddr.index(address)][2],
                                                           self.armlimits[self.armaddr.index(address)][3]))
        for address in self.pumpaddr:
            self._sendcommand(address, "Z1 0 R")

    # -- locations and arms (liquidhandler.py:77-103) ---------------------------------------------------------
    def AddPosition(self, name, coordinates):
        self.locations[name] = list(coordinates)

    def Goto(self, location, armnum=1):
        if location not in self.locations:
            raise ValueError("No such location!")
        self.Move(self.locations[location][:], armnum)

    def Move(self, pos=(0, 0, 0), armnum=1):
        command = "PA %i %i %i" % (int(pos[0]), int(pos[1]), int(pos[2]))
        self._sendcommand(self.armaddr[armnum - 1], command)
        self.curpos[armnum - 1] = list(pos)

    def MoveAxis(self, axis=0, pos=10, armnum=1):
        axes = ("X", "Y", "Z")
        self._sendcommand(self.armaddr[armnum - 1], "%sA %i" % (axes[axis], pos))
        self.curpos[armnum - 1][axis] = pos

    def ShowPosition(self, armnum=1):
        return self.curpos[armnum - 1]

    # -- syringe pumps (liquidhandler.py:107-147) -------------------------------------------------------------
    def Dispense(self, units, speed=10, pump=1):
        if int(units) > self.syringecontents[pump - 1]:
            raise ValueError("Not enough liquid in syringe!")
        self.Pump(pump, speed, self.syringecontents[pump - 1], "out")
        self.Pump(pump, speed, self.syringecontents[pump - 1] - int(units), "out")
        self.syringecontents[pump - 1] = self.syringecontents[pump - 1] - int(units)

    def Draw(self, units, source="bottle", speed=10, pump=1):
        if source == "bottle":
            direction = "in"
        elif source == "sample":
            direction = "out"
        else:
            raise ValueError("Source must be either 'bottle' or 'sample'!")
        if self.syringecontents[pump - 1] + units > 2000:
            raise ValueError("Syringe can only contain up to 2000 units!")
        self.Pump(pump, speed, self.syringecontents[pump - 1], direction)
        self.Pump(pump, speed, self.syringecontents[pump - 1] + int(units), direction)
        self.syringecontents[pump - 1] = self.syringecontents[pump - 1] + int(units)

    def Pump(self, pump, speed, position, direction):
        if int(speed) < 0 or int(speed) > 20:
            raise ValueError("Pump speed must be between 0 and 20!")
        if int(position) < 0 or int(position) > 2000:
            raise ValueError("Pump position must be between 0 and 2000!")
        if direction == "in":
            dircode = "I"
        elif direction == "out":
            dircode = "O"
        else:
            raise ValueError("Pump direction must be 'in' or 'out'!")
        command = "S%i A%i %s R" % (int(speed), int(position), dircode)
        return self._sendcommand(self.pumpaddr[pump - 1], command)

    # -- transport (liquidhandler.py:151-209, Protocol.md:23-37) ----------------------------------------------
    def _makecommandstring(self, command):
        message = FRAME_START + command.encode("latin-1") + FRAME_END
        checksum = message[1]
        for byte in message[2:]:
            checksum ^= byte
        return message + bytes([checksum]) + TERMINATOR

    def _sendcommand(self, address, command):
        cmd = "A%i%s" % (address, command)
        self.s.write(self._makecommandstring(cmd))
        time.sleep(0.3)
        deadline = time.monotonic() + self.timeout_s
        result = None
        while result is None:
            if time.monotonic() > deadline:
                raise TimeoutError("the liquid handler did not finish command %r within %.1f s"
                                   % (cmd, self.timeout_s))
            answer = self.s.readline()
            if not answer:
                time.sleep(0.1)
                continue
            words = answer.split(b"\x02")
            for word in words[1:]:
                if len(word) < 3:
                    result = -2
                else:
                    word = word[0:-2]
                    if b"Y" in word:
                        result = 0
                    elif b"A" in word:
                        result = -1
        self.s.write(self._makecommandstring("@%s" % address))
        if result != 0:
            raise IOError("Robot returns error!")


def connect(port="/dev/ttyUSB0", **options):
    """Open the serial line and return the Python 3 port of ``Robot``."""
    return Robot(port=port, **options)
