"""Hardware backend: opens a Science Jubilee through the upstream Machine class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human
signs ``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package
must not claim it).  The acceptance gate runs the fake backend and never imports this module or the
science_jubilee package.

Options of the backend: ``address`` (required) is the IP address loaded onto the Jubilee Duet's main
board; the upstream Machine() constructor expects it to match config.g (Machine.py:119-124, 201-206).
The other keyword options go to the Machine constructor: ``port``, ``baudrate``, ``deck_config``,
``crash_detection`` and ``crash_handler`` (Machine.py:109-118).  A simulated run belongs on the fake
backend, not here (Machine.py:486-488 short-circuits gcode() in simulated mode).
"""


def connect(address, **options):
    if options.get("simulated"):
        raise ValueError("the hardware backend cannot be simulated; use --backend fake")
    from science_jubilee.Machine import Machine

    return Machine(address=address, **options)
