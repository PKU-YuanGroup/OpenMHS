"""Hardware backend: the upstream x-axis class from lhrhost, attached to the caller's messaging stack.

The upstream ``Axis`` is a high-level object whose protocol node must be registered with the messaging stack that
sends commands to the robot's Arduino over its USB serial interface (README.rst:20; the robot class registers its
axis protocols the same way, lhrhost/robot/robot.py:25-30).  This package does not own that stack: the hardware
backend takes the integrator's stack as the ``messaging_stack`` option, and the integrator builds the stack and opens
the serial transport before calling this factory.

The loader refuses this backend of an unreviewed model-authored package at R2 and R3 until ``reviewed_by`` is set in
``driver.lock.json``; the acceptance gate never imports this module or the lhrhost package.
"""


def connect(messaging_stack=None, **options):
    """Return the upstream x-axis with its protocol registered on ``messaging_stack``."""
    if messaging_stack is None:
        raise ValueError(
            "the hardware backend needs the lhrhost messaging stack that reaches the robot's Arduino; pass it as "
            "the 'messaging_stack' option"
        )
    from lhrhost.robot.x_axis import Axis

    axis = Axis()
    messaging_stack.register_response_receivers(axis.protocol)
    messaging_stack.register_command_senders(axis.protocol)
    return axis
