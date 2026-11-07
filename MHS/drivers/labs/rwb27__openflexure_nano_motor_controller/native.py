"""Hardware backend: opens the OpenFlexure stage over its serial port.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate runs the fake
backend and never imports this module or the upstream package.  The upstream class opens the port in its constructor
and reads the firmware version, requiring v0.4 (openflexure_stage/stage.py:74-87); its default port settings are 115200
baud, 8 data bits, no parity and one stop bit (openflexure_stage/stage.py:41).

Options of the backend: ``port`` (the serial device, e.g. ``/dev/ttyUSB0`` or ``COM4``) may be given as the first
positional argument or not at all, in which case the upstream ``find_port`` autodetects it; any other keyword goes to
``pyserial.Serial`` through ``BasicSerialInstrument`` (openflexure_stage/stage.py:74, basic_serial_instrument.py:54-73).
"""


def connect(port=None, **options):
    from openflexure_stage.stage import OpenFlexureStage

    return OpenFlexureStage(port, **options)
