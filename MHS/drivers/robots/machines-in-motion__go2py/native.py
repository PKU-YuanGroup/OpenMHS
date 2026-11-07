"""Hardware backend of the Go2 driver: opens Go2Py.robot.interface:GO2Real.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or Go2Py; nothing here ran on a robot.

Backend options: ``interface_name`` is the network interface connected to the robot, which the clone passes to
CycloneDDS (Go2Py/robot/interface.py:34-35, docs/setup.md:224); ``mode`` is ``lowlevel`` or ``highlevel``
(interface.py:28); ``vx_max``, ``vy_max`` and the yaw-rate maximum are the velocity envelope options of the deployment
(interface.py:29-31, 71-75).  The bridge must already be running, because GO2Real only creates DDS readers and
writers (interface.py:58-70).
"""


def connect(interface_name=None, mode="lowlevel", **options):
    from Go2Py.robot.interface import GO2Real

    if mode not in ("lowlevel", "highlevel"):
        raise ValueError("mode must be 'lowlevel' or 'highlevel'")
    return GO2Real(interface_name=interface_name, mode=mode, **options)
