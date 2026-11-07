"""Hardware backend: open a Keithley 2100 through the clone's VISA class.

Used only with ``backend="hardware"`` and an operator decision; the acceptance gate runs the fake backend and
never imports this module or the upstream package.  This package is model-authored and unreviewed, and it is R1:
the loader's refusal of a model-written hardware backend applies only at R2 and R3, so this package makes no such
claim.  A human must review the package before any hardware use.

The upstream ``Keithley2100VISADriver`` constructor takes one argument, the VISA resource name, and
``init_hardware()`` opens it with a newline write termination (keithley2100_VISADriver.py:13-31).  Other options
are not used by that class and are ignored here.
"""


def connect(rsrc_name, **_options):
    from pymodaq_plugins_keithley.hardware.keithley2100.keithley2100_VISADriver import (
        Keithley2100VISADriver,
    )

    device = Keithley2100VISADriver(rsrc_name)
    device.init_hardware()
    return device
