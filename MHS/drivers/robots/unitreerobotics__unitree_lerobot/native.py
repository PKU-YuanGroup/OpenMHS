"""Hardware backend: opens the upstream G1 29-DoF dual-arm controller.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream package;
nothing here ran on a robot.

The factory imports the installed ``unitree_lerobot`` package, not the read-only pinned clone.  The upstream class
imports ``unitree_sdk2py`` (robot_arm.py:6-13), which pyproject.toml:21 leaves commented out, so the deployment must
install it separately.  The constructor also joins a DDS domain (domain 0 unless ``simulation_mode=True``) and blocks
until it has received an ``rt/lowstate`` message (robot_arm.py:92-113); it has no timeout.  That wait and the DDS
transport are deployment concerns the loader cannot check here.

Options are the upstream constructor's ``motion_mode`` and ``simulation_mode``.  With ``motion_mode=True`` the
controller publishes on ``rt/arm_sdk`` instead of ``rt/lowcmd`` (robot_arm.py:97-100).  The driver never selects the
mode itself; the operator does.
"""


def connect(motion_mode=False, simulation_mode=False, **options):
    from unitree_lerobot.eval_robot.robot_control.robot_arm import G1_29_ArmController

    if options:
        raise TypeError(f"G1_29_ArmController takes motion_mode and simulation_mode, not {sorted(options)}")
    return G1_29_ArmController(motion_mode=motion_mode, simulation_mode=simulation_mode)
