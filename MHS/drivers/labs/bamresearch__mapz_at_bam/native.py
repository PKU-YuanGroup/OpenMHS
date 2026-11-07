"""Hardware backend: opens an IKA RCT digital 5 hotplate through the upstream Minerva class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses the hardware backend of an unreviewed model-written package at R2 and R3
until a human signs ``reviewed_by`` in driver.lock.json.  The acceptance gate runs the fake backend and never imports
this module or the Minerva package.

The upstream constructor opens the serial line itself (IkaHotplate.py:88-116) and takes a COM port; it prepends
"COM" when the argument does not already start with it (IkaHotplate.py:109-110).  The plate is then identified with
IN_NAME, and the constructor expects a reply that starts with "RCT digital" (IkaHotplate.py:121-129).
"""


def connect(com_port, **options):
    from Minerva.Hardware.Hotplates.IkaHotplate import RCTDigital5

    if options:
        raise TypeError(f"RCTDigital5 takes only com_port; unsupported option(s): {sorted(options)}")
    return RCTDigital5(str(com_port))
