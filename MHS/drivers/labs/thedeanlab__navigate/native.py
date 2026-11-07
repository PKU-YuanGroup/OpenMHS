"""Hardware backend: opens the ASI Tiger controller and builds an MS2000Stage.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed: the loader refuses the hardware backend of an unreviewed model-written package
at R2 and R3 only, so an operator can still open this R1 package with allow_hardware.  The acceptance gate runs
the fake backend and never imports this module or the navigate package.

Options: ``port`` (required) is the serial port of the Tiger controller (stage/asi.py:730-731); any other
option goes to ``MS2000Stage.connect`` -- ``baudrate`` (default 115200) and ``timeout`` (default 0.25 s),
stage/asi.py:723-725.  ``microscope_name`` and ``configuration`` are the two further arguments the MS2000Stage
constructor needs (stage/asi.py:632-654); ``configuration`` is the whole navigate configuration document, from
which the stage class reads its axes and the x_min/x_max bounds (stage/base.py:110-158).
"""


def connect(port, microscope_name, configuration, **options):
    from navigate.model.devices.stage.asi import MS2000Stage

    controller = MS2000Stage.connect(port, **options)
    return MS2000Stage(microscope_name, controller, configuration)
