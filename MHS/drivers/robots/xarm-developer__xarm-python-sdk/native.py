"""Hardware backend: opens an xArm through the SDK's own connection and checks that it is the arm the limits are for.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The
acceptance gate runs the fake backend and never imports this module or the xarm package; nothing here ran on an arm.

Options of the backend: ``port`` is the IP address of the controller (``XArmAPI(port=...)``, xarm_api.py:23-24); any
other option goes to the ``XArmAPI`` constructor (its keyword parameters are listed in xarm_api.py:70-83).  Every
driver call passes ``is_radian=True`` itself, and the constructor gets the same default.

The joint and tool ranges of the driver are the SDK's tables for the 7-axis robot type XARM7_X4 (device type 7,
xarm/core/config/x_config.py:41).  After connecting, the SDK knows the axis count and the robot type from the
controller's version string (xarm/x3/base.py:473-485), and a different arm is refused here.
"""


def connect(port=None, **options):
    from xarm.wrapper import XArmAPI

    arm = XArmAPI(port, is_radian=True, **options)
    if (arm.axis, arm.device_type) != (7, 7):
        found = (arm.axis, arm.device_type)
        arm.disconnect()
        raise RuntimeError(f"this driver's limits are those of the 7-axis robot type 7 (XARM7_X4); the arm reports "
                           f"axis {found[0]} and type {found[1]}")
    return arm
