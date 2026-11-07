"""Hardware backend: opens the SPAMB Chemyx Fusion 4000-X through the upstream PumpController.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, and the pump driver is R2: the loader refuses its hardware backend until a human
signs ``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not
claim it).  The acceptance gate runs the fake backend and never imports this module or the upstream package.

The upstream import is local to :func:`connect` because ``hardware.pump`` is a top-level module of the clone's
``fluidics-control/`` directory: put that directory on ``PYTHONPATH`` (or run from it) when the operator uses the
hardware backend.  The driver itself needs nothing beyond the upstream class.

Options of the backend:
  * ``port`` (required) -- the serial device (``PumpController(port=...)``, pump.py:802-819);
  * ``pump_number`` -- 1 or 2 for the dual-channel Fusion 4000-X (pump.py:804-805, 831-845);
  * ``baudrate`` -- the RS232 baud rate, 9600 in the example (pump.py:806, fluidics-control/README.md:129).
"""


def connect(port, pump_number=1, baudrate=9600, **options):
    from hardware.pump import PumpController

    controller = PumpController(port=port, pump_number=pump_number, baudrate=baudrate, mock=False)
    controller.connect()
    return controller
