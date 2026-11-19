"""Hardware backend: opens the CubOS Gantry over the upstream GRBL serial driver.

Used only with backend="hardware" and allow_hardware=True (an operator
decision).  This package is model-authored and unreviewed, and it is R2: the
loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only).  The acceptance gate
runs the fake backend and never imports this module or the ``cubos`` package.

Options of the backend: ``config`` is the machine configuration mapping that
Gantry accepts (the same ``gantry`` YAML content: coordinates, working volume,
GRBL expectations, feed rates; docs/gantry-setup.md:1-10).  ``port`` is the
serial port to try first. Mill._locate_over_serial also probes other candidate
ports if that one does not verify (gantry_driver/driver.py:119-184); ``None``
starts the auto-scan without a preferred port. Connection reads settings and,
outside Alarm, sets status reporting to WPos ($10=0), absolute positioning
(G90) and the configured/default feed rate (driver.py:302-306,756-769).
It sends no axis target and never homes. These controller changes make
construction unsuitable for an MHS reset hook. The site must supply the calibrated ``config`` and the operator must
home the machine before a move (docs/operator-ui/gantry.md:49-54).

The stop queries Hold once after sending the feed hold; it neither polls until
stationary nor cancels the held planner path (driver.py:452-459). The serial
reader and in-flight commands may outlast the MHS stop budget; an unconfirmed
stop must remain failed and latched. No hardware import or controller call was
performed during model review.
"""


def connect(config=None, port=None):
    from cubos.gantry.gantry import Gantry

    device = Gantry(config=config or {})
    device.connect(port=port)
    return device
