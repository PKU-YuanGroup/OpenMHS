"""Hardware backend: open a Tektronix TBS2000B through the upstream pyvisa class.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed; the acceptance gate runs the fake backend and never imports this module or the
upstream package.

``resource_name`` is required: it is the pyvisa resource string of the instrument, for example the USB resource the
upstream constructor is given (Tektronix_TBS2000B_control/oscilloscope_control.py:22-37).  ``options`` is accepted
so the loader can pass backend options, but the upstream constructor takes no other argument.
"""


def connect(resource_name, **_options):
    from Tektronix_TBS2000B_control.oscilloscope_control import Oscilloscope

    return Oscilloscope(resource_name=resource_name)
