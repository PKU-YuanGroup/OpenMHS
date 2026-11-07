"""Fake backend of the Grip PickAndPlaceEnvironment driver: a pure-Python kinematic stand-in.

The upstream environment imports pybullet, NumPy, Open3D, OpenCV and the
repository's own modules (template_env.py:1-12, pick_and_place_env.py:1-18), and
package code never imports or runs the clone.  This module therefore implements
only the public surface of ``PickAndPlaceEnvironment`` that the driver calls:
``reset``, ``step`` and ``close`` (gate G7).  It is not the upstream simulator:
there is no pybullet, rigid-body dynamics, contact, gripper physics, camera
rendering or point-cloud pipeline.  Every number below is test data, not a
device fact or a source, and each is marked ``# placeholder``.
"""

import math
from collections.abc import Mapping

#: The seven joints of the Franka Panda arm (panda_robot.py:57-59).
JOINT_COUNT = 7                                                    # placeholder
#: Start joint angles of the stand-in, in radians.
START_JOINTS = [0.0] * JOINT_COUNT                                 # placeholder
#: Start gripper finger displacement, in metres.
START_GRIPPER = 0.04                                              # placeholder
#: Lower and upper finger displacement limits of the stand-in, in metres.
GRIPPER_LOW = 0.0                                                 # placeholder
GRIPPER_HIGH = 0.04                                               # placeholder
#: Tray and object positions of the upstream pick-and-place scene
#: (pick_and_place_env.py:39-43, :55-60), repeated here as test data.
START_TRAY = [0.3, -0.7, 0.0]                                      # placeholder
START_OBJECT = [0.3, -0.7, 0.1]                                    # placeholder
#: Fraction of the joint error removed by one tick.
JOINT_GAIN = 0.25                                                 # placeholder


def _values(value, count):
    """A finite list of ``count`` floats from a list, tuple or array-like."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(f"expected {count} values, got {value!r}")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError("action values must be finite numbers")
        out.append(float(item))
    return out


class FakePickAndPlaceEnvironment:
    """The public surface of ``PickAndPlaceEnvironment`` with a placeholder kinematic model."""

    def __init__(self, **options):
        from .sim import configuration
        config = configuration(options)
        self.seed = config["seed"]
        self.sim_steps = config["sim_steps"]
        self.time_step = config["time_step"]
        self._closed = False
        self._joints = list(START_JOINTS)                          # placeholder
        self._velocities = [0.0] * JOINT_COUNT                    # placeholder
        self._gripper = START_GRIPPER                             # placeholder
        self._tray = list(START_TRAY)                             # placeholder
        self._object = list(START_OBJECT)                         # placeholder
        self._tick = 0

    def reset(self):
        """Restore the placeholder start state and return the observation, as upstream reset does."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._joints = list(START_JOINTS)                          # placeholder
        self._velocities = [0.0] * JOINT_COUNT                    # placeholder
        self._gripper = START_GRIPPER                             # placeholder
        self._tray = list(START_TRAY)                             # placeholder
        self._object = list(START_OBJECT)                         # placeholder
        self._tick = 0
        return self._observation()

    def step(self, action):
        """Apply the placeholder joint and gripper commands and return ``(obs, reward, done, info)``."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if action is None:
            action = {}
        if not isinstance(action, Mapping):
            raise TypeError("action must be a mapping")
        joint = action.get("joint_position_cmd")
        if joint is not None:
            targets = _values(joint, JOINT_COUNT)
            for index, target in enumerate(targets):
                delta = target - self._joints[index]
                self._joints[index] += JOINT_GAIN * delta          # placeholder
                self._velocities[index] = JOINT_GAIN * delta       # placeholder
        gripper = action.get("gripper_cmd")
        if gripper is not None:
            if isinstance(gripper, str):
                if gripper not in ("open", "close"):
                    raise ValueError("gripper_cmd string must be 'open' or 'close'")
                self._gripper = GRIPPER_HIGH if gripper == "open" else GRIPPER_LOW  # placeholder
            else:
                if isinstance(gripper, bool) or not isinstance(gripper, (int, float)) \
                        or not math.isfinite(gripper):
                    raise ValueError("gripper_cmd must be a finite number or 'open'/'close'")
                self._gripper = min(GRIPPER_HIGH, max(GRIPPER_LOW, self._gripper + float(gripper)))  # placeholder
        self._tick += 1
        return self._observation(), 0.0, False, {}

    def close(self):
        """Mark the stand-in closed; upstream Env.close is a no-op cleanup hook."""
        self._closed = True

    def _observation(self):
        """A reduced JSON observation shaped like the upstream entity states."""
        return {
            "robot": {
                "joint_names": ["panda_joint{}".format(index) for index in range(1, JOINT_COUNT + 1)],
                "positions": list(self._joints),
                "velocities": list(self._velocities),
                "efforts": [0.0] * JOINT_COUNT,                   # placeholder
                "ee_pose": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]],  # placeholder
                "gripper_state": {"displacement": self._gripper},
            },
            "tray": {"pose": [list(self._tray), [0.0, 0.0, 0.0, 1.0]]},   # placeholder
            "object": {"pose": [list(self._object), [0.0, 0.0, 0.0, 1.0]]},  # placeholder
            "tick": self._tick,
        }
