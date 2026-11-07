"""Hardware backend: opens the serial line of the KDS Gemini 88 pump.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or pyserial.

The upstream clone does not provide a pump class; it writes a command with ``serial.Serial.write`` through its
``writeSerial`` helper (``realSerial.py:15-33``).  The object returned here has the same surface the driver uses:
``input`` holds the bytes of one command, ``Write`` appends CRLF and writes them, and ``ser`` is the open port.

Options: ``port`` (required) is the serial device, for example ``COM3`` on Windows or ``/dev/ttyUSB0`` on Linux.
The line defaults follow the upstream constructor (``realSerial.py:6``): 9600 baud, odd parity, two stop bits and
seven data bits.  ``timeout`` bounds one port read and ``read_timeout_s`` is the driver's status-read wait.
"""


class _Writer:
    """The upstream ``writeSerial`` surface used by the driver: ``input``, ``ser`` and ``Write``."""

    def __init__(self, ser):
        self.ser = ser
        self.input = b""

    def Write(self):
        self.ser.write(self.input + b"\r\n")
        return True


def connect(port, baudrate=9600, timeout=1.0, parity="O", stopbits=2, bytesize=7,
            read_timeout_s=None, **serial_options):
    import serial

    del read_timeout_s  # the driver reads this option itself; it is not a serial.Serial keyword
    ser = serial.Serial(port=port, baudrate=int(baudrate), timeout=float(timeout),
                        parity=str(parity), stopbits=float(stopbits), bytesize=int(bytesize), **serial_options)
    try:
        return _Writer(ser)
    except BaseException:
        ser.close()
        raise
