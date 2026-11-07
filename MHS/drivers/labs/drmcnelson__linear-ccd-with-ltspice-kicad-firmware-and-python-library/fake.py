"""Fake backend of the TCD1304 controller: an in-memory stand-in for LCCDCONTROLLER.

Gate G7: every public method defined here exists on the upstream class (TCD1304Rev2_Python/TCD1304Rev2Controller.py):
``rawcommand`` (687), ``write`` (1302), ``clear`` (1315) and ``close`` (1323); the instance data members mirror the
attributes the upstream constructor assigns (``dataqueue`` 530, ``datalength`` 580, ``darklength`` 581,
``sensor`` 583, ``vperbit`` 545, ``bits`` 543, ``coefficients`` 551 and ``identifier`` 570).  The signatures mirror
the upstream ones.  The fake answers the two text queries the driver reads and turns ``clock 1 <shutter>`` into one
queued frame record shaped like the upstream reader's record (891-898); ``stop`` sets the stopped flag, so the
e-stop has an observable effect.

Every number below is test data of this stand-in, not a device fact, and each one is marked ``# placeholder``.  A
real device returns the configuration the firmware reports (the README names the TCD1304, 3648/3694 pixels,
README.md:12) and a frame of the full detector length; this stand-in returns 16 pixels so receipts stay small.  The
values never change by themselves, so reading the state twice gives the same state.  Nothing here talks to a device
or derives from the upstream class (G3 FAKE_IS_NATIVE).
"""

import queue

#: Frame length of this stand-in (placeholder test data).
PIXELS = 16
#: Leading dark pixels of this stand-in (placeholder test data).
DARK = 3
#: First wavelength and step of the stand-in's calibration (placeholder test data, nanometres).
FIRST_WAVELENGTH_NM = 400.0
WAVELENGTH_STEP_NM = 40.0
#: ADC counts of the stand-in frame (placeholder test data); no pixel reaches 4095.
COUNTS = [100.0, 250.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0,
          900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0, 1500.0, 1600.0]


class FakeLCCDController:
    def __init__(self, **_options):
        self.dataqueue = queue.Queue()
        self.identifier = "FAKE-TCD1304"                       # placeholder test data
        self.datalength = PIXELS                              # placeholder test data
        self.darklength = DARK                                # placeholder test data
        self.sensor = "TCD1304"                               # placeholder test data
        self.bits = 12                                        # placeholder test data
        self.vfs = 3.3                                        # placeholder test data, volts
        self.vperbit = self.vfs / (2 ** self.bits - 1)        # placeholder test data
        self.coefficients = [FIRST_WAVELENGTH_NM, WAVELENGTH_STEP_NM, 0.0, 0.0]  # placeholder test data
        self.stopped = False
        self.closed = False
        self._frames = 0
        self._last_shutter_us = None

    # -- text commands -----------------------------------------------------------------------------------------
    def rawcommand(self, command, key=None):
        """Answer a text command the way LCCDCONTROLLER.rawcommand returns a line for a key (687-718)."""
        lines = {
            "identifier": ["Identifier FAKE-TCD1304"],          # placeholder test data
            "configuration": ["PIXELS %d DARK %d INVERT -1.0 SENSOR TCD1304 BITS %d VFS %.1f"
                              % (PIXELS, DARK, self.bits, self.vfs)],  # placeholder test data
            "temperature": ["CHIPTEMPERATURE 25.0"],            # placeholder test data
            "stop": ["DONE"],
        }.get(str(command).strip(), [])
        if key is None:
            return list(lines)
        for line in lines:
            if line.startswith(str(key)):
                return line
        return None

    def write(self, buffer):
        """Record one command; clock queues a new frame and send queues the current buffer (upstream write 1302)."""
        text = str(buffer).strip()
        if text == "stop":
            self.stopped = True
            return
        parts = text.split()
        if len(parts) >= 3 and parts[0] == "clock":
            self._frames += 1
            self._last_shutter_us = int(parts[2])
            self._queue_frame(self._last_shutter_us)
        elif text == "send":
            self._queue_frame(self._last_shutter_us)           # placeholder: the last stand-in shutter
        elif len(parts) >= 3 and parts[0] == "set" and parts[1] == "holdoff":
            self.holdoff_us = int(parts[2])                    # placeholder test data

    def _queue_frame(self, shutter_us):
        scaled = [count * self.vperbit for count in COUNTS]    # placeholder test data
        record = [[scaled], shutter_us, shutter_us, shutter_us,
                  1, 0, 1, 1, 0, "CLOCKED", shutter_us, 0, None]  # placeholder record metadata
        self.dataqueue.put(record)

    def clear(self):
        """Drop queued frames, as LCCDCONTROLLER.clear does (1315-1321)."""
        while not self.dataqueue.empty():
            try:
                self.dataqueue.get_nowait()
            except queue.Empty:
                break

    def close(self, ignored=None):
        """Mark the controller closed (upstream close is 1323)."""
        self.closed = True
