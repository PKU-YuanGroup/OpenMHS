"""Hardware backend: opens a Reglo ICC pump through the upstream pyserial driver.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream package.

Options of this backend: ``port`` (required) is the serial port of the pump, for example ``/dev/ttyACM0`` or
``COM42`` (the upstream README says the USB interface is the intended one, README.md:2).  ``channel`` selects the
channel the driver drives (default 1); the upstream object still exposes every channel the pump reports.
``pump_addr``, ``dispense_dirs``, ``tubing_ids`` and ``serial_no`` are passed to the upstream constructor; other
keyword options go to ``serial.Serial`` (for example ``exclusive`` on POSIX).  The upstream sets the baud rate and
timeout itself (reglo_icc_pump/_driver.py:84-87), so do not pass ``baudrate`` or ``timeout`` here.
"""


def connect(port, channel=1, pump_addr=1, dispense_dirs=None, tubing_ids=None, serial_no=None, **serial_options):
    import serial

    from reglo_icc_pump import RegloIccPump

    del channel  # the driver reads this option itself; the upstream object is not channel-scoped
    directions = {int(key): value for key, value in (dispense_dirs or {}).items()} or None
    tubings = {int(key): float(value) for key, value in (tubing_ids or {}).items()} or None
    ser_port = serial.Serial(port, RegloIccPump.BAUDRATE, timeout=RegloIccPump.CMD_TIMEOUT_S, **serial_options)
    try:
        return RegloIccPump(ser_port, pump_addr=pump_addr, dispense_dirs=directions, tubing_ids=tubings,
                            serial_no=serial_no)
    except BaseException:
        ser_port.close()
        raise
