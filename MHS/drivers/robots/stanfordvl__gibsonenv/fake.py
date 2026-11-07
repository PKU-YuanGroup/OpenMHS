"""Fake backend of the Gibson driver: a pure Python stand-in for ``gibson.envs.ant_env:AntNavigateEnv``.

Why a fake: the upstream environment needs Python 3.6-era packages (``gym==0.9.4`` and
``pybullet==1.9.4``, setup.py:26-30), a downloaded scene database and an Nvidia GPU with CUDA
(README.md:67-69). The gate installs and imports nothing from the clone, so this module
re-implements the *interface* of ``AntNavigateEnv``: the 17-action ``Discrete`` space of the
``is_discrete: true`` configuration, the ``{"nonviz_sensor": [..28..]}`` observation selected
by ``output: [nonviz_sensor]``, the 300-frame termination rule and the
``(observation, reward, done, info)`` return shape of the clone.

The public members are the ones ``CameraRobotEnv`` exposes (``reset``, ``step``, ``close``;
this is what gate G7 checks against the clone's AST). The space classes duck-type
``gym.spaces.Discrete`` / ``Box`` / ``Dict`` (the bridge reads ``n``, ``start``, ``low``,
``high``, ``shape`` and ``spaces``).

What this is not: the upstream simulator. The fake has no PyBullet, no contacts, no actuator
or sensor model and no downloaded scenes, so its trajectories are not the upstream ones. All
such omissions are in the driver's fidelity ``gaps``. Numbers that model the upstream
interface (17, 28, 5, 300, the 0.01 s timestep and the reset jitter bound) are cited to the
clone; numbers of the placeholder dynamics are marked ``# placeholder`` and are test data,
not facts about Gibson.
"""

import math
import random

# The upstream interface, cited so the fake is not mistaken for a re-parameterisation.
SENSOR_SIZE = 28                    # robot_locomotors.py:259-260 (sensor_dim=28)
JOINT_COUNT = 8                     # robot_locomotors.py:259 (action_dim=8)
FOOT_COUNT = 4                      # robot_locomotors.py:251 (foot_list has four feet)
ACTION_COUNT = 17                   # robot_locomotors.py:266-267 (gym.spaces.Discrete(17))
SENSOR_LIMIT = 5.0                  # robot_locomotors.py:204 (np.clip(..., -5, +5))
MAX_STEPS = 300                     # ant_env.py:89 (done = self.nframe > 300)
TIMESTEP = 0.01                     # examples/configs/play/play_ant_nonviz.yaml:28 (timestep: 0.01)
RESET_JOINT_LOW = -0.1              # robot_locomotors.py:66 (uniform(low=-0.1, high=0.1))
RESET_JOINT_HIGH = 0.1              # robot_locomotors.py:66

# Placeholder dynamics of this fake, not measurements of the upstream model.
MOTOR_GAIN = 0.5                    # placeholder
DAMPING = 0.9                       # placeholder
FORWARD_GAIN = 0.02                 # placeholder
TARGET_X = 0.0                      # placeholder
TARGET_Y = 1.0                      # placeholder
START_X = 0.0                       # placeholder
START_Y = 0.0                       # placeholder


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        return len(value) == len(self.low) and all(lo <= item <= hi for lo, item in zip(self.low, value))


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces`` (a mapping)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.dtype = None


class FakeAntNavigateEnv:
    """``AntNavigateEnv`` without PyBullet: the same ``reset`` and ``step`` surface, a toy body."""

    def __init__(self, **_options):
        self.action_space = Discrete(ACTION_COUNT)                       # robot_locomotors.py:267
        self.observation_space = Dict({                                  # env_modalities.py:530-538
            "nonviz_sensor": Box([-SENSOR_LIMIT] * SENSOR_SIZE, [SENSOR_LIMIT] * SENSOR_SIZE),
        })                                                               # robot_locomotors.py:204
        self._rng = random.Random()
        self._reset_state()

    def _reset_state(self):
        self._x = START_X                                                # placeholder
        self._y = START_Y                                                # placeholder
        self._speed = 0.0                                                # placeholder
        # robot_locomotors.py:64-66: every joint angle is drawn uniformly from (-0.1, 0.1)
        self._joint_angles = [self._rng.uniform(RESET_JOINT_LOW, RESET_JOINT_HIGH) for _ in range(JOINT_COUNT)]
        self._joint_speeds = [0.0] * JOINT_COUNT                         # placeholder
        self._feet_contact = [1.0] * FOOT_COUNT                          # placeholder: feet on the ground
        self._tick = 0

    def _distance(self):
        return math.hypot(TARGET_X - self._x, TARGET_Y - self._y)        # placeholder target

    def _observation(self):
        """The ``nonviz_sensor`` array: 8 body features + 16 joint numbers + 4 feet contacts."""
        angle = math.atan2(TARGET_Y - self._y, TARGET_X - self._x)       # robot_locomotors.py:157-168
        more = [
            0.0,                                                         # placeholder: z - initial_z
            math.sin(angle),                                             # robot_locomotors.py:192
            math.cos(angle),                                             # robot_locomotors.py:192
            0.0,                                                         # placeholder: 0.3 * vx
            0.3 * self._speed,                                           # robot_locomotors.py:193
            0.0,                                                         # placeholder: 0.3 * vz
            0.0,                                                         # placeholder: roll
            0.0,                                                         # placeholder: pitch
        ]
        joints = []
        for angle_value, speed_value in zip(self._joint_angles, self._joint_speeds):
            joints.extend((angle_value, speed_value))                    # placeholder joint state
        values = more + joints + list(self._feet_contact)                # robot_locomotors.py:191-204
        return {"nonviz_sensor": [max(-SENSOR_LIMIT, min(SENSOR_LIMIT, float(value))) for value in values]}

    def reset(self, *, seed=None, options=None):
        """Reset the toy body; a seed fixes the joint-angle draw of robot_locomotors.py:64-66."""
        if options:
            raise ValueError("AntNavigateEnv.reset() takes no options")
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._reset_state()
        return self._observation(), {}

    def step(self, action):
        """Advance one 10 ms frame; the return shape is the clone's (env_modalities.py:182-228)."""
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        if self._tick is None:
            raise AssertionError("Call reset before using step method.")
        self._tick += 1                                                  # env_modalities.py:183
        # The discrete table has 8 positive and 8 negative joint torques plus a zero action
        # (robot_locomotors.py:270-286); this fake only uses the sign of that action.
        if 1 <= action <= JOINT_COUNT:
            self._joint_speeds[action - 1] += MOTOR_GAIN                 # placeholder
        elif JOINT_COUNT < action <= 2 * JOINT_COUNT:
            self._joint_speeds[action - JOINT_COUNT - 1] -= MOTOR_GAIN   # placeholder
        for index in range(JOINT_COUNT):
            self._joint_speeds[index] *= DAMPING                          # placeholder
            self._joint_angles[index] += self._joint_speeds[index] * TIMESTEP
        self._speed = DAMPING * self._speed + FORWARD_GAIN * sum(self._joint_speeds) / JOINT_COUNT  # placeholder
        before = self._distance()
        self._y += self._speed * TIMESTEP                                # placeholder
        after = self._distance()
        reward = (before - after) / TIMESTEP                             # potential change (ant_env.py:44-46)
        terminated = self._tick > MAX_STEPS                              # ant_env.py:89
        return self._observation(), reward, terminated, False, {}

    def close(self):
        self._tick = None
