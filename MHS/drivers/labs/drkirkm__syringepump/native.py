"""Hardware backend: opens the serial line of the Harvard Apparatus OEM syringe pump.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or pyserial.

The upstream clone has no transport class: each ``Pumps`` handler in ``pumpcontroller.py`` opens ``COM1``, writes
one CR-terminated ASCII line and closes the port.  The object this factory returns has the same button-handler
surface, so the driver reads and writes exactly the upstream line edits and calls exactly the upstream handler
names; only the port is injected (the clone hardcodes ``COM1`` at ``pumpcontroller.py:229``).  The line settings are
the upstream ones: 9600 baud, 8 data bits, no parity, a 0.5 s timeout and the pyserial default of one stop bit.

Options: ``port`` (required) is the serial device, for example ``COM3`` on Windows or ``/dev/ttyUSB0`` on Linux;
``baudrate``, ``bytesize``, ``parity``, ``stopbits`` and ``timeout`` override the line settings; ``address`` is
accepted because it is also a driver option and is not used here.
"""


class _Text:
    """The part of a Qt line edit the upstream handlers read: ``text`` and ``setText``."""

    def __init__(self):
        self._text = ""

    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)


class _PumpLink:
    """The upstream ``Pumps`` handler surface, writing through an injected serial port."""

    def __init__(self, serial_options):
        self._serial_options = dict(serial_options)
        self.lineEdit1 = _Text()
        self.lineEdit2 = _Text()
        self.lineEdit3 = _Text()
        self.lineEdit4 = _Text()
        self.lineEdit5 = _Text()
        self.lineEdit6 = _Text()

    def _write(self, *lines):
        import serial

        ser = serial.Serial(**self._serial_options)
        try:
            for line in lines:
                ser.write(line)
        finally:
            ser.close()

    # -- address 00 (unprefixed commands) -------------------------------------------------------------------------
    def diambuttonClicked(self):
        self._write(b"MMD " + self.lineEdit2.text().encode("ascii") + b"\r")

    def sfrbuttonClicked(self):
        self._write(b"MLH " + self.lineEdit1.text().encode("ascii") + b"\r")

    def runbuttonClicked(self):
        self._write(b"RUN\r")

    def stopbuttonClicked(self):
        self._write(b"STP\r")

    # -- address 01 (01-prefixed commands) ------------------------------------------------------------------------
    def diam2buttonClicked(self):
        self._write(b"01MMD " + self.lineEdit3.text().encode("ascii") + b"\r")

    def mlh2buttonClicked(self):
        self._write(b"01MLH " + self.lineEdit4.text().encode("ascii") + b"\r")

    def run2buttonClicked(self):
        self._write(b"01RUN\r")

    def stop2buttonClicked(self):
        self._write(b"01STP\r")

    # -- address 02 (02-prefixed commands) ------------------------------------------------------------------------
    def diam3buttonClicked(self):
        self._write(b"02MMD " + self.lineEdit6.text().encode("ascii") + b"\r")

    def mlh3buttonClicked(self):
        self._write(b"02MLH " + self.lineEdit5.text().encode("ascii") + b"\r")

    def run3buttonClicked(self):
        self._write(b"02RUN\r")

    def stop3buttonClicked(self):
        self._write(b"02STP\r")

    # -- stop all three addresses ---------------------------------------------------------------------------------
    def stopallbuttonClicked(self):
        self._write(b"STP\r", b"01STP\r", b"02STP\r")


def connect(port, address=None, baudrate=9600, bytesize=8, parity="N", stopbits=1, timeout=0.5,
            **serial_options):
    """Build the handler object for one pump; the port is opened per command, as the upstream does."""
    del address  # a driver option, not a serial.Serial keyword
    if not port:
        raise ValueError("the hardware backend needs a serial port (option 'port', for example 'COM3')")
    options = {
        "port": str(port),
        "baudrate": int(baudrate),
        "bytesize": int(bytesize),
        "parity": str(parity),
        "stopbits": float(stopbits),
        "timeout": float(timeout),
    }
    options.update(serial_options)
    return _PumpLink(options)
