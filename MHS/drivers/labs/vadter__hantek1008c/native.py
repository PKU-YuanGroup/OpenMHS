"""Hardware backend: opens a Hantek 1008C through the upstream USB class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream file
``pyhantek1008C.py`` sits at the clone root; the operator must put that root on ``PYTHONPATH`` (the upstream
README lists pyusb, overrides, matplotlib and pyqtgraph as its dependencies, README.md:1).  The upstream
constructor finds the USB device by vendor id 0783 and product id 5725, configures it and runs its init sequence
(pyhantek1008C.py:113-142, 325-333); every keyword option is passed to ``Hantek1008`` (ns_per_div,
vertical_scale_factor, active_channels, correction_data and the zero-offset compensation options,
pyhantek1008C.py:788-794).

This package is model-authored and unreviewed and is R1, so the loader's review gate for R2 and R3 does not apply
to it; an operator must still decide to enable the hardware backend.  The acceptance gate runs the fake backend
and never imports this module or the upstream package, so this hardware path was never run and no hardware
behavior is claimed.
"""


def connect(**options):
    from pyhantek1008C import Hantek1008

    return Hantek1008(**options)
