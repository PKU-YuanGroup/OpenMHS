"""Hardware backend: opens the Olin ModCon SMU through the upstream pyusb class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs reviewed_by in driver.lock.json (the
loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate runs the fake
backend and never imports this module or the upstream modconsmu package.

The upstream class is modconsmu.modconsmu:smu.  Its constructor finds one USB device by vendor id 0x6666 and product
id 0x0005 and reads four calibration words from it (modconsmu/modconsmu.py:38-56); it calls sys.exit when no device is
found (modconsmu/modconsmu.py:39-40), so the hardware backend is only usable with the SMU attached.  The upstream is
not installed by the gate: put the clone root (the directory that contains modconsmu/) on PYTHONPATH, or install the
clone, and install pyusb (README.mkd:7-11).  The constructor also registers set(amps=0) with atexit
(modconsmu/modconsmu.py:57-58).

The factory takes no options; there is no URL or port, because the upstream class itself searches the USB bus.
"""


def connect(**options):
    if options:
        raise TypeError(f"the Olin SMU backend takes no options, got {sorted(options)}")
    from modconsmu.modconsmu import smu

    return smu()
