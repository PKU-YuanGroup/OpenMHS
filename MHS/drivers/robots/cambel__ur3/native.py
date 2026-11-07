"""Native construction is refused before any ROS import or side effect.

The pinned Arm cannot yet supply owned constructor unwind/ROS shutdown or a
bounded dashboard call that fences pending trajectory effects. A signature is
not a substitute for those missing lifetime guarantees. See NATIVE-BLOCKERS.md.
The original unvalidated factory is retained in the versioned repair evidence.
"""


def connect(**options):
    raise RuntimeError(
        "UR3 native admission is blocked: owned ROS lifecycle, bounded dashboard "
        "transport and retirement of pending trajectories are not established"
    )
