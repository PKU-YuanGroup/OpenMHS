"""Hardware backend: opens a Thorlabs Elliptec rotation stage through the upstream ``Motor`` class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The gate never imports this
module or the upstream ``elliptec`` package; everything here was read from the clone, not run against a stage.
``Motor`` is a pyserial ``Serial`` subclass whose constructor opens the port and reads the motor information
(elliptec/rotation.py:8-24).  The upstream constructor takes the line settings but hard-codes its own; they are
passed through unchanged for an operator who reuses this factory.

This package is model-authored and unreviewed at R1.  The loader refuses a model-written hardware backend only at
R2 and R3, so at R1 nothing here prevents a hardware start: a human must review the package before using a stage.
"""


def connect(port, baudrate=9600, bytesize=8, parity="N", timeout=2):
    from elliptec.rotation import Motor

    return Motor(port, baudrate=baudrate, bytesize=bytesize, parity=parity, timeout=timeout)
