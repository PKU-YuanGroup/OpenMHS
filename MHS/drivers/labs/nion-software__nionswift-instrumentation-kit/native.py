"""Hardware backend: builds the upstream Instrument around the value and axis managers of a Nion installation.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed and it is R3: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json.  The acceptance gate runs the fake backend and never imports this module
or the upstream package.

The upstream class is not a transport: ``Instrument(instrument_id, value_manager, axis_manager)`` is the
device-facing adapter, and the value manager and axis manager are owned by the Nion Swift installation that
talks to the microscope (nion/device_kit/InstrumentDevice.py:28-43, 60-67).  This factory therefore takes those
two objects from the site instead of opening a connection of its own.  No hardware run of this package is
claimed.
"""


def connect(value_manager, axis_manager, instrument_id="instrument"):
    from nion.device_kit.InstrumentDevice import Instrument

    return Instrument(instrument_id, value_manager, axis_manager)
