"""Fake backend of the KitchenShift driver: a pure Python stand-in for ``Kitchen_v0``.

Why a fake: the upstream environment is built on ``dm_control``, MuJoCo and ``gym`` (``kitchen_v0.py:15-24``),
none of which the acceptance gate installs or imports, and package code never imports the read-only clone.  This
module mirrors the public surface of ``kitchen_shift.kitchen_v0:Kitchen_v0`` that the bridge uses: ``reset``,
``step`` and ``seed`` (all defined by the upstream class), plus the two spaces the bridge reads.

What is modelled: the four observation arrays with the upstream dimensions (9 robot and 21 object degrees of
freedom, ``kitchen_v0.py:63-64`` and ``:178-183``), the ``Box(-1, 1, shape=(9,))`` action space of the default
``absvel`` mode (``kitchen_v0.py:42`` and ``:107-108``, ``:129``), the action clipping and ``act_amp`` scaling
(``kitchen_v0.py:130-131`` and ``:222-231``), the always-zero reward and never-done step result of the class
(``kitchen_v0.py:215-220``), and the 280-step ``TimeLimit`` that the registration adds (``__init__.py:9``).

What is not modelled: MuJoCo, contacts, actuators, the robot controller and the observation noise.  The transition
below is a placeholder first-order motion, and the initial positions and their jitter are placeholders, not values
of the upstream model.  Nothing here talks to a device.
"""

import random

# kitchen_v0.py:63-64
ROBOT_DOF = 9
OBJECT_DOF = 21
# kitchen_v0.py:130-131: act_mid is zero and act_amp is 2.0 for every action element
ACTION_MID = 0.0
ACTION_AMP = 2.0
# kitchen_v0.py:44 and assets/kitchen.xml:16: the default frame_skip of 40 at the model's 0.002 s timestep
STEP_SECONDS = 40 * 0.002
# __init__.py:7-9: kitchen-v0 is registered with max_episode_steps=280
MAX_EPISODE_STEPS = 280
# placeholder: half-width of the fake's initial robot-position jitter (test data, not an upstream bound)
START_JITTER = 0.001
# placeholder: fraction of the command applied to the fake's robot velocity each step (test data)
VELOCITY_FRACTION = 1.0

_FLOAT_MAX = 1.7976931348623157e308


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None, dtype=None):
        if shape is None:
            self.low = [float(value) for value in low]
            self.high = [float(value) for value in high]
            self.shape = (len(self.low),)
        else:
            self.shape = tuple(int(item) for item in shape)
            self.low = _expand(low, self.shape)
            self.high = _expand(high, self.shape)
        self.dtype = dtype or "float32"

    def contains(self, value):
        values = list(value)
        return len(values) == len(self.low) and all(
            float(low) <= float(item) <= float(high) for low, high, item in zip(self.low, self.high, values))


def _expand(value, shape):
    """A scalar bound repeated over a one-dimensional shape, or the bound list as it is."""
    if isinstance(value, (list, tuple)):
        return [float(item) for item in value]
    count = 1
    for item in shape:
        count *= int(item)
    return [float(value)] * count


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = "float32"


def _observation_space():
    # kitchen_v0.py:133-137: a Dict of Box spaces with infinite bounds whose shapes come from _get_obs_dict()
    return Dict({
        "robot_qp": Box(-_FLOAT_MAX, _FLOAT_MAX, shape=(ROBOT_DOF,)),
        "robot_qv": Box(-_FLOAT_MAX, _FLOAT_MAX, shape=(ROBOT_DOF,)),
        "obj_qp": Box(-_FLOAT_MAX, _FLOAT_MAX, shape=(OBJECT_DOF,)),
        "obj_qv": Box(-_FLOAT_MAX, _FLOAT_MAX, shape=(OBJECT_DOF,)),
    })


class FakeKitchenV0:
    """``Kitchen_v0`` without MuJoCo: ``reset(objects_done_set=None)``, ``step(action)`` and ``seed(seed)``."""

    def __init__(self, **_options):
        # kitchen_v0.py:129: gym.spaces.Box(-1.0, 1.0, shape=(action_dim,)); action_dim is 9 in absvel mode
        self.action_space = Box(-1.0, 1.0, shape=(ROBOT_DOF,))
        self.observation_space = _observation_space()
        self._rng = random.Random(0)       # placeholder: default test-data generator, not an upstream seed
        self._seed = None
        self._elapsed_steps = 0
        # placeholder: the fake starts at zero, not at the upstream FRANKA_INIT_QPOS (constants.py:85)
        self._robot_qp = [0.0] * ROBOT_DOF
        self._robot_qv = [0.0] * ROBOT_DOF
        self._obj_qp = [0.0] * OBJECT_DOF
        self._obj_qv = [0.0] * OBJECT_DOF

    def _obs(self):
        # kitchen_v0.py:178-191: the four arrays, cast to float32 upstream
        return {
            "robot_qp": list(self._robot_qp),
            "robot_qv": list(self._robot_qv),
            "obj_qp": list(self._obj_qp),
            "obj_qv": list(self._obj_qv),
        }

    def reset(self, objects_done_set=None):
        # kitchen_v0.py:293-305: reset restores the simulator and returns the observation; objects_done_set names
        # the elements whose goal pose is restored.  The fake models the state but not the object goal poses.
        self._robot_qp = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(ROBOT_DOF)]
        # placeholder: zero velocities and object state, not the upstream reset state
        self._robot_qv = [0.0] * ROBOT_DOF
        self._obj_qp = [0.0] * OBJECT_DOF
        self._obj_qv = [0.0] * OBJECT_DOF
        self._elapsed_steps = 0
        return self._obs()

    def step(self, action):
        # kitchen_v0.py:222-231: clip the action to [-1, 1], then map it with act_mid + a * act_amp.
        values = [float(item) for item in action]
        if len(values) != ROBOT_DOF:
            raise ValueError(f"the action has {len(values)} elements; this environment takes {ROBOT_DOF}")
        clipped = [max(-1.0, min(1.0, value)) for value in values]
        command = [ACTION_MID + value * ACTION_AMP for value in clipped]
        # placeholder: a first-order motion, not the upstream robot controller or MuJoCo integration
        self._robot_qv = [value * VELOCITY_FRACTION for value in command]
        self._robot_qp = [position + velocity * STEP_SECONDS
                          for position, velocity in zip(self._robot_qp, self._robot_qv)]
        # kitchen_v0.py:215-220: reward 0.0, done False, empty info.  The registration's TimeLimit
        # (__init__.py:9) truncates at 280 steps; the bridge reads the gymnasium five-tuple.
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._obs(), 0.0, False, truncated, {}

    def seed(self, seed=None):
        # kitchen_v0.py:361-363: seed the environment's random generator and return [seed]
        self._seed = seed
        self._rng = random.Random(seed)
        return [seed]
