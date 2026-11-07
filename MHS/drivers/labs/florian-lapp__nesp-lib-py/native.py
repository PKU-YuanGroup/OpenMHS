"""Hardware backend: opens a New Era syringe pump through pyserial and the upstream nesp_lib Pump class.

Used only with backend="hardware" and allow_hardware=True, an operator decision.  This package is model-authored and
unreviewed, and its risk is R2 (a model review raised it: a pump that dispenses liquid), so the loader refuses its
hardware backend until a human signs ``reviewed_by`` in driver.lock.json.  The acceptance gate runs the fake backend and never imports this module, pyserial or nesp_lib.

``connect`` mirrors the README: a Port is opened and the Pump is constructed from it (README.md:35-65).  Port opens
``serial.Serial(port=name, baudrate=baud_rate)`` (nesp_lib/port.py:30-35) and its default baud rate is 9_600
(nesp_lib/port.py:9-10).  Constructing the Pump sets the safe mode timeout and reads the model number and firmware
version of the pump (nesp_lib/pump.py:71-79), so a device that does not answer raises during connect.

Options of the backend: ``port`` (required) is the serial device name (for example ``COM1`` or ``/dev/ttyUSB0``);
``baud_rate`` goes to Port; ``address``, ``model_number`` and ``safe_mode_timeout_s`` go to the Pump constructor
(the upstream defaults are ADDRESS_DEFAULT 0, MODEL_NUMBER_IGNORE 0 and SAFE_MODE_TIMEOUT_DISABLED 0,
nesp_lib/pump.py:17-28).
"""


def connect(port, baud_rate=9600, **options):
    from nesp_lib import Port, Pump

    return Pump(Port(port, baud_rate), **options)
