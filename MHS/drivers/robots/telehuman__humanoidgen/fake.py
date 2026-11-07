"""Fake backend of the HumanoidGen driver: a pure Python stand-in for the ``blocks_stack_easy`` task.

Why a fake: the acceptance gate runs without SAPIEN, ManiSkill, torch, GPU or the repository's external assets, and
package code never imports the clone.  This module models only the Gymnasium surface the driver serves:
``action_space``, ``reset(seed, options)`` and ``step(action)``.  It reads no asset, builds no scene and talks to no
device.

The action dimension is 38 because the default ``pd_joint_pos`` controller combines the 14 arm joints and the 24
inspire-hand finger joints (h1_2_upper_body.py:106-195 and :245), and the repository's run loop passes the robot's
first 38 joint positions to ``env.step`` (run_scene.py:61-63).  The action space is left unbounded: the controller
configs pass ``lower=None`` and ``upper=None`` (h1_2_upper_body.py:213-230), so the actual envelope comes from the
robot model in the external assets, which this package does not have and does not invent.

The episode limit of 200 transitions is the ``max_episode_steps`` of the ``register_env`` decorator
(blocks_stack_easy.py:3).  The initial joint positions and their jitter are fake test data, marked ``# placeholder``;
they are not a fact about the robot.

What this is not (all listed in the fidelity ``gaps`` of the driver):

* no SAPIEN dynamics, contacts, friction, gravity, robot, table scene or cubes;
* the observation is a 38-float echo of the commanded joint positions, not the environment's state observation or
  its 512 by 512 camera image;
* no success test, reward model, rendering or snapshot/restore.
"""

import math
import random

# The default controller combines 14 arm joints and 24 inspire-hand joints (h1_2_upper_body.py:106-195 and :245).
ACTION_SIZE = 38
# Max episode length of the registered task (blocks_stack_easy.py:3).
MAX_EPISODE_STEPS = 200
# placeholder: neutral start and small jitter of the fake, test data only
INITIAL_QPOS = [0.0] * ACTION_SIZE
START_JITTER = 0.01


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeBlocksStackEasyEnv:
    """``blocks_stack_easy`` without ManiSkill: ``reset`` and ``step`` return what the Gymnasium environment does."""

    def __init__(self, **options):
        # The upstream constructor accepts the ManiSkill and run-config keyword arguments; the fake models none of
        # them beyond the two spaces.  No render_mode is accepted because the fake cannot render.
        if options.get("render_mode") is not None:
            raise ValueError("the fake blocks_stack_easy cannot render; use render_mode=None")
        self.action_space = Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE)
        self._rng = random.Random()
        self._qpos = list(INITIAL_QPOS)
        self._elapsed_steps = 0

    def reset(self, seed=None, options=None):
        """Return ``(observation, info)`` like ``TableSetting.reset`` (table_scene.py:249-251)."""
        if options is not None and not isinstance(options, dict):
            raise ValueError("options must be a mapping")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        # placeholder: a fresh fake joint state, not the upstream robot's initial configuration
        self._qpos = [value + self._rng.uniform(-START_JITTER, START_JITTER) for value in INITIAL_QPOS]
        self._elapsed_steps = 0
        return list(self._qpos), {}

    def step(self, action):
        """Store the commanded joint positions and return the five-tuple of ``BaseEnv.step``."""
        try:
            values = [float(item) for item in action]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"action must be an iterable of {ACTION_SIZE} numbers: {exc}") from exc
        if len(values) != ACTION_SIZE:
            raise ValueError(f"action must have {ACTION_SIZE} elements, got {len(values)}")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("action elements must be finite")
        self._qpos = values
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return list(self._qpos), 0.0, False, truncated, {"elapsed_steps": self._elapsed_steps}
