"""Hardware backend: opens a Harvard PHD 2000 pump through the upstream Model 44 serial transport.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream package.

Options: ``port`` (required) is the serial device of the pump, for example ``COM3`` on Windows or ``/dev/ttyUSB0``
on Linux.  ``address`` is the Pump Chain address configured on the pump (0 to 99, default 0), and the remaining
options are the serial framing: 9600 baud, 8 data bits, no parity and 2 stop bits are the recommended PHD 2000
settings (README.md:33-39).  ``connect`` opens the line, then identifies the pump with the safe identity queries
(identified prompt, VER, identified prompt) before returning it.
"""


def connect(port, address=0, baudrate=9600, bytesize=8, parity="N", stopbits=2, timeout=1.0):
    from refactored_pump_control.harvard_phd2000_driver import HarvardPHD2000Driver
    from refactored_pump_control.serial_transport import SerialTransport

    transport = SerialTransport(
        port=port,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=timeout,
    )
    transport.connect()
    pump = HarvardPHD2000Driver(transport, address=address)
    pump.identify()
    return pump
