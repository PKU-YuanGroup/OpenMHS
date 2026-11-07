"""Fake backend of the Assistive Gym driver: a pure Python stand-in for ``HumanTestingEnv``.

Why a fake: the upstream environment needs PyBullet, Keras/TensorFlow, SMPL-X and the bundled asset files
(setup.py:21, assistive_gym/envs/env.py:37-39), none of which is installed where the gate runs, and package code
never imports the clone.  This module mirrors the public surface of ``assistive_gym.envs:HumanTestingEnv`` that the
driver and the Gymnasium bridge use: ``reset``, ``step`` and ``seed`` (gate G7), plus the two spaces.  The space
classes duck-type ``gym.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

What this is not: the upstream environment.  It does not create a PyBullet client, a human model or a sphere, and it
does not run contacts; it keeps only the step counter and the 200-step TimeLimit that the Gym registration adds.  The
differences are listed in the fidelity ``gaps`` of the driver.  Nothing here talks to a device.
"""

#: assistive_gym/envs/human_testing.py:10 with assistive_gym/envs/agents/human.py:5-6:
#: right_arm_joints 0-9 plus left_arm_joints 10-19.
NUM_ARM_JOINTS = 20
#: assistive_gym/__init__.py:22-26: HumanTesting-v1 is registered with max_episode_steps=200.
MAX_EPISODE_STEPS = 200
#: assistive_gym/envs/env.py:21: AssistiveEnv defaults time_step=0.02 s and frame_skip=5.
TIME_STEP_S = 0.02
FRAME_SKIP = 5


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        try:
            return all(float(low) <= float(item) <= float(high)
                       for item, low, high in zip(value, self.low, self.high))
        except (TypeError, ValueError):
            return False


class FakeHumanTestingEnv:
    """``HumanTestingEnv`` without PyBullet: ``reset()``, ``step(action)`` and ``seed(seed)``.

    The real class returns the empty observation list and reward 0 from ``step`` (human_testing.py:15-17), and the
    Gym registration wraps it in a 200-step TimeLimit (assistive_gym/__init__.py:22-26).  This stand-in returns the
    five-tuple form the bridge accepts and reports the time limit as ``truncated``; the real ``step`` returns the
    four-tuple form and the Gym wrapper moves the time limit into ``info``.  The reward value is 0, as upstream
    human_testing.py:17.
    """

    def __init__(self):
        #: assistive_gym/envs/env.py:21 and :40-42 (the 20 arm joints and the -1..1 bounds).
        self.time_step = TIME_STEP_S
        self.frame_skip = FRAME_SKIP
        self.action_space = Box([-1.0] * NUM_ARM_JOINTS, [1.0] * NUM_ARM_JOINTS)
        #: human_testing.py:13 and env.py:43-45: both observation lengths are 0.
        self.observation_space = Box([], [])
        self._seed = None
        self._elapsed_steps = None

    def seed(self, seed=None):
        """assistive_gym/envs/env.py:78-80: set the generator and return the seed."""
        self._seed = seed
        return [seed]

    def reset(self):
        """human_testing.py:22-43 builds the world and returns ``self._get_obs()``."""
        self._elapsed_steps = 0                  # placeholder: a fresh episode starts at zero steps
        return self._get_obs()

    def step(self, action):
        """human_testing.py:15-17: advance the world, pay reward 0 and keep the empty observation."""
        if self._elapsed_steps is None:
            raise RuntimeError("Call reset before using step.")
        if len(action) != NUM_ARM_JOINTS:
            raise ValueError(f"expected {NUM_ARM_JOINTS} arm-joint values, got {len(action)}")
        self._elapsed_steps += 1
        # The 200-step TimeLimit of the registration; HumanTestingEnv.step itself never terminates.
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._get_obs(), 0, False, truncated, {}

    def _get_obs(self, agent=None):
        """human_testing.py:19-20: the environment exposes no observation."""
        return []
