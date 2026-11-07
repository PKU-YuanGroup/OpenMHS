"""Explicit real-backend boundary, blocked before ROS import or construction."""
from mhs.bridge.base import make_mhs_error


def open_sim(*, launch_config=None, observer=None, rewarder=None, scenarios=None, **options):
    """The source constructor starts ROS, while close/seed are no-ops.

    A local fence does not prove an external graph is stopped. Until a sourced
    independent stop and ownership contract is available, this factory refuses
    before importing the native module. There is no fake fallback.
    """
    raise make_mhs_error("MHS.DEVICE.NOT_READY",
                         "SocialGym2 live deployment is blocked: no independently confirmed simulator stop "
                         "or owned lifecycle is implemented for the pinned ROS-launching constructor",
                         {"retryable": False})
