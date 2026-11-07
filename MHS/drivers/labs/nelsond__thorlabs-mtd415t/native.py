"""Hardware backend: opens a Thorlabs MTD415T through the upstream class.

Used only with backend="hardware" and allow_hardware=True, an operator decision, and never by the acceptance gate
(which runs the fake backend and never imports this module).  The upstream class opens its serial port in its own
constructor through pyserial's ``serial_for_url`` (thorlabs_mtd415t/serial_device.py:22-24) at the baudrate the
MTD415TDevice constructor fixes to 115200 (thorlabs_mtd415t/mtd415t_device.py:55); ``port`` is the serial URL pyserial
understands, for example ``/dev/ttyUSB0``.

This package is model-authored and unreviewed.  It is R0 (a read-only capability set: no setpoint, current-limit or
gain write is bound), so the loader's refusal of an unreviewed model-written hardware backend does not apply here:
that rule covers R2 and R3 only, and this module must not claim it.  The hardware backend was never opened by this
work; use it only with a person at the instrument.
"""


def connect(port, **options):
    from thorlabs_mtd415t import MTD415TDevice

    return MTD415TDevice(port, **options)
