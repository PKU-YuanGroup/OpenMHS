"""Fake backend of the gym-panda-reach driver: a pure Python kinematic stand-in for ``PandaEnv``.

Why a fake: ``PandaEnv.__init__`` connects to PyBullet in GUI mode (panda_env.py:26-29) and the package needs
pybullet, gym and a display, none of which the acceptance gate has; package code never imports the clone.  This
module re-implements the control law of ``gym_panda_reach.envs.panda_env:PandaEnv`` (the class the driver names as
``native``) in plain Python: the end effector moves by ``action[0..2] * 0.05``, the fingers take ``action[3]``, the
fixed goal object is the target, and the reward and the 24-value observation follow the upstream formulas.  Every
constant taken from the clone cites its line at commit 928d1e6b779b52d25bbef2a9f717bcf64991f6fb; the two numbers
that the fake invents (the end-effector start and the fixed object orientation) are marked ``# placeholder``.

What this is not: the upstream environment, and not PyBullet.  Differences, all listed in the fidelity ``gaps`` of
the driver:

* no rigid-body dynamics, contacts, inverse kinematics or joint limits: the commanded Cartesian displacement is
  applied exactly, and the object never moves (it is loaded with a fixed base upstream, panda_env.py:207-211);
* no simulated time: one ``step()`` call is one control event, so no timestep is claimed;
* no rendering;
* the seeded ``reset(seed=...)`` and the ``options`` argument are the fake's extension: the upstream ``reset`` takes
  no argument and draws the object start from the module-level random generator (panda_env.py:136,202-205).

The public members are the upstream class's (``compute_reward``, ``step``, ``reset``, ``close``; gate G7); the two
space classes only duck-type the ``gym.spaces.Box`` members the bridge reads (``low``, ``high``, ``shape``).  Nothing
here talks to a device.
"""

import random

# panda_env.py:36: spaces.Box(np.array([-1] * 4), np.array([1] * 4))
ACTION_LOW = [-1.0, -1.0, -1.0, -1.0]
ACTION_HIGH = [1.0, 1.0, 1.0, 1.0]
# panda_env.py:37: spaces.Box(np.array([-1] * 24), np.array([1] * 24))
OBSERVATION_LOW = [-1.0] * 24
OBSERVATION_HIGH = [1.0] * 24
# panda_env.py:51: dv = 0.05 (the Cartesian displacement for an action value of 1)
DV = 0.05
# panda_env.py:88: self.distance_threshold = 0.05
DISTANCE_THRESHOLD = 0.05
# panda_env.py:13: MAX_EPISODE_LEN = 20 * 100
MAX_EPISODE_LEN = 20 * 100
# panda_env.py:201-205: the object's uniform start bounds
OBJECT_X = (0.5, 0.8)
OBJECT_Y = (-0.2, 0.2)
OBJECT_Z = (0.65, 0.85)
# placeholder: the end-effector position the fake starts from; the upstream value comes from PyBullet forward
# kinematics of the rest pose (panda_env.py:153-162), which the fake does not run
START_POSITION = [0.3, 0.0, 0.75]
# placeholder: the world orientation of the fixed goal object, standing in for getBasePositionAndOrientation
OBJECT_ROTATION = [0.0, 0.0, 0.0, 1.0]


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _goal_distance(goal_a, goal_b):
    """Euclidean distance (panda_env.py:16-17)."""

    return sum((float(a) - float(b)) ** 2 for a, b in zip(goal_a, goal_b)) ** 0.5


class FakePandaEnv:
    """``panda-reach-v0`` without PyBullet: ``reset`` and ``step`` return the upstream shapes."""

    def __init__(self, **_options):
        self.step_counter = 0
        self.reward_type = "dense"
        self.distance_threshold = DISTANCE_THRESHOLD
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        self.observation_space = Box(OBSERVATION_LOW, OBSERVATION_HIGH)
        # The upstream keeps its PyBullet ids in pandaUid and objectUid; the fake keeps its small state there too.
        self.pandaUid = {"position": list(START_POSITION), "fingers": [0.0, 0.0], "rng": None}
        self.objectUid = [0.0, 0.0, 0.0]
        self.observation = self._observation([0.0, 0.0, 0.0], 0.0)

    def reset(self, seed=None, options=None):
        """Reset the episode; ``seed`` and ``options`` are accepted for the bridge (see the module docstring)."""

        self.step_counter = 0
        if seed is not None:
            self.pandaUid["rng"] = random.Random(seed)
        rng = self.pandaUid["rng"]
        uniform = rng.uniform if rng is not None else random.uniform
        self.pandaUid["position"] = list(START_POSITION)
        self.pandaUid["fingers"] = [0.0, 0.0]
        # panda_env.py:201-205: random.uniform on the three object coordinates
        self.objectUid = [uniform(*OBJECT_X), uniform(*OBJECT_Y), uniform(*OBJECT_Z)]
        self.observation = self._observation([0.0, 0.0, 0.0], 0.0)
        return list(self.observation)   # panda_env.py:247: the legacy API returns the observation alone

    def step(self, action):
        """Apply ``[dx, dy, dz, fingers]`` once and return ``(observation, reward, done, info)`` (panda_env.py:134)."""

        try:
            values = [float(value) for value in action]
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"action {action!r} is not a sequence of numbers") from exc
        if len(values) != 4:
            raise AssertionError(f"action {action!r} does not have four values")
        dx, dy, dz = values[0] * DV, values[1] * DV, values[2] * DV   # panda_env.py:52-54
        fingers = values[3]                                           # panda_env.py:55
        position = self.pandaUid["position"]
        new_position = [position[0] + dx, position[1] + dy, position[2] + dz]
        # panda_env.py:64-73: the upstream solves IK and lets PyBullet track it; the fake tracks the target exactly.
        self.pandaUid["position"] = new_position
        self.pandaUid["fingers"] = [fingers, fingers]
        self.step_counter += 1                                        # panda_env.py:97
        distance = _goal_distance(new_position, self.objectUid)
        done = distance < self.distance_threshold                     # panda_env.py:89-95
        reward = self.compute_reward(new_position, self.objectUid)    # panda_env.py:91,94
        if self.step_counter > MAX_EPISODE_LEN:                       # panda_env.py:99-101
            done = True
        self.observation = self._observation([dx, dy, dz], fingers)
        info = {"object_position": list(self.objectUid)}              # panda_env.py:103
        return list(self.observation), reward, done, info

    def compute_reward(self, achieved_goal, goal):
        """Dense reward ``-distance``, sparse reward ``-1`` above the threshold and ``0`` below (panda_env.py:39-45)."""

        distance = _goal_distance(achieved_goal, goal)
        if self.reward_type == "sparse":
            return -1.0 if distance > self.distance_threshold else 0.0
        return -distance

    def close(self):
        """Drop the fake state; the upstream disconnects PyBullet (panda_env.py:278-279)."""

        self.observation = None

    def _observation(self, grip_velocity, fingers):
        """The 24 values of panda_env.py:120-132, with a fixed object orientation and no object velocity."""

        position = self.pandaUid["position"]
        object_position = self.objectUid
        relative = [object_position[0] - position[0], object_position[1] - position[1],
                    object_position[2] - position[2]]
        finger_left, finger_right = self.pandaUid["fingers"]
        gripper_state = 0.5 * (finger_left + finger_right)             # panda_env.py:109-111
        return (
            list(position) + list(object_position) + relative + [gripper_state]
            + list(OBJECT_ROTATION)                                    # panda_env.py:112,228
            + [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]                          # object linear and angular velocity
            + list(grip_velocity)                                      # panda_env.py:115
            + [fingers * DV]                                           # panda_env.py:116-118
        )
