"""Hardware backend of the New Era NE-500 driver: opens the pyserial handle the upstream GUI keeps as ``self.ser``.

The upstream GUI opens ``serial.Serial(serial_port, 19200, timeout=0.2)`` (pump_control3.py:23) and then passes that
handle to the protocol functions of new_era3.py.  This factory returns a small transport holder whose ``ser()`` method
returns a pyserial-like handle with the same line settings; the GUI, PyQt5 and the clone are never imported or run.
The pump address is a required option: the upstream GUI scans addresses 0-9 and the README requires a unique single
digit 0-9 for each pump (README.md:93), so the driver does not guess which pump of a chain it controls.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision); the acceptance gate runs
the fake backend and never imports this module.  The package is model-authored and unreviewed and the device is R2,
so the loader refuses this backend until a human sets ``reviewed_by`` in driver.lock.json.

Backend options: ``port`` (required, the pyserial device name, for example ``/dev/ttyUSB0`` or ``COM1``), ``address``
(required, 0-9), ``baudrate`` (default 19200) and ``timeout_s`` (default 0.2).
"""


class _SerialLink:
    def __init__(self, port, address, baudrate, timeout_s):
        self.address = address
        self._port = port
        self._baudrate = baudrate
        self._timeout_s = timeout_s
        self._serial = None

    def _open(self):
        if self._serial is None:
            from serial import Serial

            self._serial = Serial(self._port, self._baudrate, timeout=self._timeout_s)
        return self._serial

    def write(self, data):
        return self._open().write(data)

    def readline(self):
        return self._open().readline()

    def close(self):
        if self._serial is not None:
            self._serial.close()
            self._serial = None


class _Transport:
    """The backend object: the upstream ``PumpControl``'s serial handle as a method (``ser``)."""

    def __init__(self, link):
        self._link = link

    def ser(self):
        return self._link


def connect(**options):
    options = dict(options)
    port = options.pop("port", None)
    address = options.pop("address", None)
    baudrate = int(options.pop("baudrate", 19200))
    timeout_s = float(options.pop("timeout_s", 0.2))
    if options:
        raise TypeError(f"unknown backend option(s): {sorted(options)}")
    if not isinstance(port, str) or not port:
        raise ValueError("the hardware backend needs port (the pyserial device name)")
    if not isinstance(address, int) or isinstance(address, bool) or not 0 <= address <= 9:
        raise ValueError("the hardware backend needs address (the pump number 0-9)")
    return _Transport(_SerialLink(port, address, baudrate, timeout_s))
