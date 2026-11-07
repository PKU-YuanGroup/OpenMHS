"""Fake backend of the MoDeSuite driver: a pure Python stand-in for ``SpotBendRodEnv``.

Why a fake: the upstream environment imports NVIDIA Isaac Sim and Isaac Lab (``task/Bend/spot_bend_env.py``
lines 3-15), needs a GPU, PhysX and USD assets (README.md:19 and :50-53), and the gate never imports the clone.
Nothing here imports or runs upstream code.  This module implements only the Gymnasium surface the bridge uses
(``reset``, ``step``, ``close``, ``action_space``, ``observation_space`` and ``dt``); the upstream class inherits
that surface from ``DirectRLEnv``, whose source is outside the clone.

Every number below is test data, not a device fact: the action bounds, the start jitter, the gains, the target
and the episode length are marked ``# placeholder`` and are not copied into a Fact, a Limit or the reference.
The observation length 58 and the 9-component action are the configuration values of
``task/Bend/spot_bend_env.py:21`` and ``:26``; the fake lays the observation out in the order of
``_get_observations`` (``:284-293``): sampled rod nodes, root position, root quaternion, target, joint positions,
joint velocities.  The fake does not reproduce the Isaac Lab dynamics; the driver's fidelity gaps say so.

What this is not: the upstream environment.  The fake is kinematic, its reward is a simplified distance, and it
was never compared with a real Isaac Lab run.
"""

import random

# placeholder: test data of this fake only
ACTION_DIM = 9
OBSERVATION_DIM = 58
JOINT_DIM = 18
ROD_NODES = 4
TIMESTEP_S = 0.01
EPISODE_STEPS = 2500
ACTION_SCALE = 6.0
BASE_GAIN = 0.05
JOINT_GAIN = 0.1
START_JITTER = 0.02
TARGET = (0.5, 0.5, 1.0)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeSpotBendEnv:
    """A kinematic stand-in for ``SpotBendRodEnv`` with its reset/step contract."""

    def __init__(self, **_options):
        # placeholder: the clone does not define the Box bounds (DirectRLEnv lives outside it); these are the
        # test bounds of the fake.  The random-agent script samples actions in the same range
        # (script/random_agent.py:58-59), but that script is not the space definition.
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)
        # placeholder: a bounded observation Box of the configured length.
        self.observation_space = Box([-1.0e9] * OBSERVATION_DIM, [1.0e9] * OBSERVATION_DIM)
        self.dt = TIMESTEP_S
        self._rng = random.Random()
        self._tick = 0
        self._episode = 0
        self._closed = False
        self._base = [0.0, 0.0, 0.0]
        self._quat = [1.0, 0.0, 0.0, 0.0]
        self._target = list(TARGET)
        self._joint_pos = [0.0] * JOINT_DIM
        self._joint_vel = [0.0] * JOINT_DIM
        self._rod = [0.0] * (ROD_NODES * 3)

    def reset(self, *, seed=None, options=None):
        """Return a fresh observation and an info dict, like ``DirectRLEnv.reset``."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._base = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(3)]
        self._quat = [1.0, 0.0, 0.0, 0.0]
        self._target = list(TARGET)
        self._joint_pos = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(JOINT_DIM)]
        self._joint_vel = [0.0] * JOINT_DIM
        self._rod = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(ROD_NODES * 3)]
        self._tick = 0
        self._episode += 1
        self._closed = False
        return self._observation(), {"episode": self._episode, "options": dict(options or {})}

    def step(self, action):
        """Apply one action and return ``(observation, reward, terminated, truncated, info)``."""
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"expected {ACTION_DIM} action values, got {len(values)}")
        # placeholder: the first three values nudge the base, the last six drive the arm.
        for axis in range(3):
            self._base[axis] += BASE_GAIN * values[axis]
        for joint in range(ACTION_DIM - 3):
            command = values[3 + joint]
            target = command + self.dt * command * ACTION_SCALE
            self._joint_vel[joint] = target - self._joint_pos[joint]
            self._joint_pos[joint] += JOINT_GAIN * self._joint_vel[joint]
        self._rod[0] += BASE_GAIN * values[0]
        self._rod[1] += BASE_GAIN * values[1]
        self._rod[2] += BASE_GAIN * values[2]
        self._tick += 1
        # placeholder: a simplified distance reward, not the four-term reward of compute_rewards.
        reward = -(abs(self._rod[-3] - self._target[0]) + abs(self._rod[-2] - self._target[1]))
        truncated = self._tick >= EPISODE_STEPS
        info = {"tick": self._tick, "episode": self._episode}
        return self._observation(), reward, False, truncated, info

    def close(self):
        """Release the fake state like ``DirectRLEnv.close``."""
        self._closed = True

    def _observation(self):
        values = (list(self._rod) + list(self._base) + list(self._quat) + list(self._target)
                  + list(self._joint_pos) + list(self._joint_vel))
        return values
