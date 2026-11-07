"""Fake backend of the SQUAD Lab AD75019 crosspoint switch: ``Muxi`` with the clone's firmware behind its handle.

``FakeMuxi`` has the two members of ``qcdrivers.squad.mux.mux:Muxi`` the driver uses: ``visa_handle``, the pyVISA
resource the QCoDeS base class opens (used at mux.py:51-58, 86, 171 and 235), and ``close`` (mux.py:225-235).  It
does not import QCoDeS, pyVISA or ``qcdrivers`` and never opens a port.

``_FakeFirmware`` answers like the clone's Arduino sketch (src/qcdrivers/squad/mux/helpers/firmware.ino): the reply
lines are the sketch's literal strings, a line goes into the serial input buffer when the sketch prints it, and
``query`` writes a command and reads the oldest unread line, ``read`` reads the next one, as pyVISA does.  A command
the sketch does not register gets no line, so its query times out (the real pyVISA raises VisaIOError after the
2000 ms the upstream constructor sets, mux.py:55; the fake raises ``TimeoutError`` at once).  The route buffers are
sets of (x, y); nothing here models the analog switches, the chips or the shift-register timing.  STAT? also prints
the 16x16 buffer's bit, which the sketch reads past its 16-entry mappings for a pin above 15 (firmware.ino:95,
AD75019.cpp:79-82, AD75019.h:124-125): the fake prints 0 there, a placeholder for that undefined read.
"""

from __future__ import annotations

DISABLED = frozenset({12, 13, 14, 15, 28, 29, 30, 31})   # firmware.ino:77 (and mux.py:106)


class _FakeFirmware:
    """The serial line of the sketch: commands in, printed lines out."""

    def __init__(self):
        self._routes16 = set()
        self._routes32 = set()
        self._lines = []            # printed and not yet read, oldest first
        self._commands = []         # every command line received, for the tests
        self._closed = False

    # -- the sketch's handlers (firmware.ino) ----------------------------------------------------------------------
    def _receive(self, command):
        self._commands.append(command)
        header, _, rest = command.partition(" ")
        params = [part for part in rest.split(",") if part.strip()] if rest else []
        if header == "*IDN?":                                   # 47-49
            self._lines.append("SQUAD, Arduino AD75019 Switch, 1.0, 1.0")
        elif header == "*RST":                                  # 51-56
            self._clear()
            self._lines.append("Reset complete")
        elif header == "CLEAR":                                 # 108-112
            self._clear()
        elif header == "SWITCH32":                              # 71-88
            if len(params) != 2:
                self._lines.append("Usage: SWITCH32 x,y")
                return
            x, y = (int(item) for item in params)
            if x in DISABLED or y in DISABLED:
                self._lines.append("Route skipped: disabled range")
                return
            self._routes32.add((x, y))
            self._lines.append("Route added 32x32")
        elif header == "SWITCH16":                              # 58-69
            if len(params) != 2:
                self._lines.append("Usage: SWITCH16 x,y")
                return
            self._routes16.add(tuple(int(item) for item in params))
            self._lines.append("Route added 16x16")
        elif header == "STAT?":                                 # 90-106
            if len(params) != 2:
                self._lines.append("Usage: STAT? x,y")
                return
            x, y = (int(item) for item in params)
            bit16 = 1 if (x < 16 and y < 16 and (x, y) in self._routes16) else 0   # placeholder above pin 15
            bit32 = 1 if (x, y) in self._routes32 else 0
            self._lines.append(f"16x16: {bit16}")
            self._lines.append(f"32x32: {bit32}")
        # any other command: the parser has no handler and prints nothing

    def _clear(self):
        self._routes16.clear()
        self._routes32.clear()
        self._lines.append("Clear complete")

    # -- the pyVISA resource interface the upstream uses -----------------------------------------------------------
    def query(self, command):
        self._receive(str(command))
        return self.read()

    def read(self):
        if not self._lines:
            raise TimeoutError("placeholder: VISA read timed out (no line printed)")
        return self._lines.pop(0)

    def clear(self):
        self._lines.clear()

    def close(self):
        self._closed = True


class FakeMuxi:
    def __init__(self, **_options):
        self.visa_handle = _FakeFirmware()

    def close(self):
        self.visa_handle.close()   # mux.py:235
