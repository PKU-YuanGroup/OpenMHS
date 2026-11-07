"""Unavailable hardware backend for the blocked ALOHA package.

The reviewed RealEnv wrapper cannot interrupt in-flight step/reset command
publications, verify fresh stopped feedback, or constrain the reset trajectory
to the operator envelope. Importing/constructing RealEnv also initializes ROS
and can configure/reboot/enable torque on robots. Refuse before those effects,
regardless of backend options or any future human signature. Repair and review
of the control path are required before implementing this factory again.

The original factory is preserved with the original package in the private
reviewer-originals archive. No upstream module is imported by this file.
"""

from mhs.driver import DriverFailed


def connect(**options):
    """Refuse hardware construction while the control path remains blocked."""
    raise DriverFailed(
        "MHS.SAFETY.SAFE_STATE_UNREACHED",
        "ALOHA hardware backend is blocked: native interruption, fresh stopped-state confirmation, "
        "and reset-trajectory envelope enforcement are not implemented",
    )
