"""Hardware backend: opens the i3 Mega G-code serial port and builds the upstream GcodeGantry.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the pipettebot package.

Options of the backend: ``port`` (required) is the serial device, for example ``/dev/ttyUSB0``; ``baudrate`` defaults
to 250000, the stock Anycubic i3 Mega rate (docs/hardware.md:36); ``timeout`` is pyserial's read timeout in seconds;
``feedrate_mm_per_min`` is the default feedrate of the upstream ``GantryConfig`` (src/pipettebot/gantry.py:144).  The
serial link is opened by the upstream helper ``open_gcode_port`` (src/pipettebot/gantry.py:38-61), which also handles
the Linux termios2/BOTHER fallback for 250000 baud.
"""


def connect(port, baudrate=250000, timeout=2.0, feedrate_mm_per_min=3000, **options):
    from pipettebot.gantry import GantryConfig, GcodeGantry, open_gcode_port

    if options:
        raise TypeError(f"unknown options for the GcodeGantry backend: {sorted(options)}")
    link = open_gcode_port(port, baudrate=baudrate, timeout=timeout)
    if link is None:
        raise ConnectionError(f"cannot open the gantry serial port {port!r} at {baudrate} baud")
    return GcodeGantry(GantryConfig(port=port, baudrate=baudrate, feedrate_mm_per_min=feedrate_mm_per_min), link)
