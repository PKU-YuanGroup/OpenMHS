"""Hardware backend: opens the OT-2 through the upstream OT2MotionController.

Used only with backend="hardware" and allow_hardware=True (an operator decision).
This package is model-authored and unreviewed, and it is R2: the loader refuses
its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only).  The acceptance gate runs the fake
backend and never imports this module or the Opentrons stack.

``connect()`` calls ``OT2MotionController.build(port=..., simulate=False)``
(motion.py:228-278), as the upstream connector's own standalone mode does
(``create_app``, src/unitelabs/opentrons_ot2/__init__.py:116-120): it creates a
``GPIOCharDev`` for the OT-2 GPIO, configures it by board revision, awaits its
``setup()`` and builds a ``_RaisingSmoothieDriver`` on the requested serial
port.  Those steps run Opentrons code outside the clone when the backend opens.
There is no fallback to the simulator here; the simulator is selected only by
an explicit ``simulate=True`` in the upstream library.  The port must not be
held by another process: ``build()`` logs a failed connection as "check that no
other process holds the port (e.g. opentrons-robot-server)" (motion.py:270-276),
so the stock robot server must be stopped first.  ``lock_timeout_s=None`` (the
upstream default) makes the controller wait for its hardware lock without a
bound, the stop included.

The driver binds the upstream controller's own method signatures, so no
production adapter is needed and the package fake mirrors the same API.  The
real path needs the Opentrons stack the clone pins (opentrons 8.8.1 below
Python 3.12, 9.0.0 from Python 3.12; pyproject.toml:27-28).  The driver's
post-halt guard lives in the driver object of this process only: a new process
starts without it.  The hardware backend was not run and no hardware run is
claimed.
"""


async def connect(port="/dev/ttyAMA0", lock_timeout_s=None, **_options):
    """Build the real OT-2 controller on the Smoothie serial port."""
    from unitelabs.opentrons_ot2.io.motion import OT2MotionController

    return await OT2MotionController.build(port=port, simulate=False, lock_timeout_s=lock_timeout_s)
