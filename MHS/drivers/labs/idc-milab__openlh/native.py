"""Hardware backend: opens the OpenLH's uArm Swift Pro through the upstream SwiftWithUltrasonic wrapper.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only).  The acceptance gate runs the fake
backend and never imports this module or the upstream package, so the hardware path below was never executed.

The upstream clone ships the Python package under ``pyuf/uf``; its own tests put ``pyuf`` on ``sys.path`` and import
``uf...`` (tests/test_position.py:3).  The driver package names the class by the repository path
``pyuf.uf.wrapper.swift_with_ultrasonic:SwiftWithUltrasonic`` (the card's entry symbol), which imports when the clone
root is on ``sys.path`` because ``pyuf`` is a namespace package.  A deployment can instead install the clone's
``pyuf/setup.py`` package and pass the ``uf...`` module through the normal Python path; the class is the same.

Options: ``dev_port`` (the serial port; the upstream default selects a port by USB VID:PID), ``baud`` (115200 by
default in the upstream constructor) and ``ultrasonic_port`` (D8 by default).  Every other option is passed to the
upstream constructor, which forwards it to the Swift module group.
"""


def connect(dev_port=None, baud=115200, ultrasonic_port="D8", **options):
    from pyuf.uf.wrapper.swift_with_ultrasonic import SwiftWithUltrasonic

    options.setdefault("dev_port", dev_port)
    options.setdefault("baud", baud)
    options.setdefault("ultrasonic_port", ultrasonic_port)
    return SwiftWithUltrasonic(**options)
