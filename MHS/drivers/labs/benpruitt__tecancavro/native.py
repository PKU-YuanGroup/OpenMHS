"""Hardware backend: opens a Tecan Cavro XCalibur D syringe pump over its serial port.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, so the loader refuses its hardware backend (R2) until driver.lock.json carries ``reviewed_by``.
The acceptance gate runs the fake backend and never imports this module or the tecancavro package.

Options of the backend: ``port`` (required) is the serial device ("/dev/ttyUSB0", "COM1"); ``address`` is the Tecan
OEM API address of the pump (the frame address byte is address + 0x31, tecanapi.py:26); ``baudrate`` defaults to
9600 as in the upstream example (example/webserver/webserver.py:39-40); ``timeout`` and ``max_attempts`` are the
serial retry settings (transport.py:109-110).  The other options go to ``XCaliburD``: ``num_ports`` (9),
``syringe_ul`` (1000), ``direction`` ("CW"), ``microstep`` (False), ``waste_port`` (9), ``slope`` (14) and
``init_force`` (0) (models.py:42-43).  The constructor reads the speeds, the plunger position and the port, so the
pump must be powered and on that serial line.
"""


def connect(port, address=0, baudrate=9600, timeout=0.2, max_attempts=5, **options):
    from tecancavro.models import XCaliburD
    from tecancavro.transport import TecanAPISerial

    link = TecanAPISerial(address, port, baudrate, timeout, max_attempts)
    return XCaliburD(link, **options)
