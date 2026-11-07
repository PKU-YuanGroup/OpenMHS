"""ROS-free analytic fake for the cheetah_sim joint publisher.

The fake mirrors the pinned Python 2/rospy surface the driver relies on:
``Cheetah.controllers`` (a dict of four leg objects keyed by leg name, as in
stand_demo.py:18), ``Cheetah.stand`` and ``LegController._writeJointPosInRad``.
It runs no Gazebo, ROS, IK or physics.  Every number below is placeholder
test data, not a device fact.
"""

#: Placeholder end-effector pose used only by the fake's stand method.  It is
#: deliberately not the upstream stand pose; the fake does not compute IK.
_FAKE_STAND_END_POS = (0.0, 0.0, 0.0)  # placeholder
_FAKE_JOINT_OFFSET = [0.0, 0.0, 0.0]  # placeholder


class _FakeLeg:
    """Placeholder stand-in for LegController; the method names mirror upstream."""

    def __init__(self, name):
        self.name = name  # placeholder state
        self.joint_name = ["hip", "thigh", "calf"]  # upstream API names, no numeric fact
        self.offset = list(_FAKE_JOINT_OFFSET)  # placeholder
        self.pos_puber = [None, None, None]  # placeholder stand-ins for ROS publishers
        self.commands = []  # placeholder record of (index, published_rad)

    def _instancePuber(self, index):
        # The fake has no ROS publisher; keep the upstream method name.
        return None  # placeholder

    def _writeJointPosInRad(self, index, rad):
        # The upstream adds the leg offset before publishing; the fake records
        # the converted value without sending anything.
        self.commands.append((index, rad + self.offset[index]))  # placeholder
        return None

    def _writeJointPosInDeg(self, index, deg):
        import math

        self._writeJointPosInRad(index, math.radians(deg))
        return None

    def writeEndPos(self, EndPos):
        self._last_end_pos = tuple(EndPos)  # placeholder
        return None


class FakeCheetahSim:
    def __init__(self, **_options):
        self.leg_names = ["LF", "LB", "RF", "RB"]  # placeholder state
        # The upstream Cheetah keeps a dict keyed by leg name (stand_demo.py:18).
        self.controllers = {name: _FakeLeg(name) for name in self.leg_names}
        self.stand_calls = 0  # placeholder state

    def stand(self):
        self.stand_calls += 1  # placeholder
        for leg in self.controllers:
            self.controllers[leg].writeEndPos(_FAKE_STAND_END_POS)
        return None

    def run(self):
        # The upstream run() loops until ROS shutdown; the fake performs one
        # placeholder stand call and returns.
        self.stand()
        return None
