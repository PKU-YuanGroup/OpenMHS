"""Hardware backend: opens a Siglent SPD3303 series power supply through the upstream VISA class.

Used only with backend="hardware" and allow_hardware=True, which is an operator decision.  This package is
model-authored and unreviewed, and it is R1: the loader refuses the hardware backend of an unreviewed
model-written package only at R2 and R3, so at R1 the loader does not refuse it and nothing mechanical
protects a hardware run.  A human must review this package before anyone passes ``--allow-hardware``.  The
acceptance gate runs the fake backend and never imports this module or the upstream module.

The upstream class composes a pyvisa transport (``instro/psu/drivers/siglent_spd3303.py:11-18``), so
``visa_resource`` is any VISA resource string the installed VISA backend understands, for example
``USB0::0xF4EC::0x1430::SPD3XJGQ806726::INSTR`` as in the upstream guide (``docs/psu.md:18``).  This factory
passes the string unchanged and does not choose a VISA backend, terminator or timeout for the installed unit;
an operator who needs those settings passes a ``VisaConfig`` through a wrapper of their own rather than
editing this file.
"""


def connect(visa_resource):
    from instro.psu.drivers.siglent_spd3303 import SiglentSPD3303

    device = SiglentSPD3303(visa_resource)
    device.open()
    return device
