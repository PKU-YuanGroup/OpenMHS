"""Hardware backend: opens an OWON SP/SPE power supply through the upstream owon_ps:OwonPowerSupply class.

Used only with backend="hardware" and allow_hardware=True, which is an operator decision.  This package is
model-authored and unreviewed.  The loader refuses the hardware backend of an unreviewed model-written package only
at R2 and R3; this driver is R1, so the loader does not refuse it and no mechanical review gate protects a hardware
run.  A human must review this package before anyone passes --allow-hardware.  The acceptance gate runs the fake
backend and never imports this module or the upstream module.

The upstream driver is a single module, owon_ps.py, that is not a pip package (the card's install block lists no
commands).  Put the clone root on PYTHONPATH, or install the module yourself, before using this backend.

Backend options: ``port`` (required) is the serial device, for example "COM7" or "/dev/ttyUSB0".  Any other option
(``baudrate``, ``timeout``) is passed to OwonPowerSupply.__init__ (owon_ps.py:18-20); this factory does not choose
values for them and does not claim that the defaults of that constructor fit an installed unit.
"""


def connect(port, **options):
    from owon_ps import OwonPowerSupply

    device = OwonPowerSupply(port, **options)
    if getattr(device, "serial_port", None) is None:
        raise RuntimeError(f"owon_ps.OwonPowerSupply could not open the serial port {port!r}")
    return device
