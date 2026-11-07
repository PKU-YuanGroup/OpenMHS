"""Fake backend of the humanoid AMP driver: a pure Python stand-in for one ``HumanoidAmpEnv``.

Why a fake: the upstream environment needs Isaac Sim 5.0 and Isaac Lab 2.2, a GPU and the PhysX runtime
(README.md:6-7, :19), none of which exist where the acceptance gate runs, and package code never imports the
clone.  This module implements the Gymnasium surface the bridge calls -- ``action_space``,
``observation_space``, ``reset``, ``step`` and ``close`` -- with the spaces and dimensions the clone configures.

What is taken from the clone:

* the action has 28 values and the observation 81 (humanoid_amp_env_cfg.py:32-33);
* the physics step is 1/60 s and two physics steps make one environment step (humanoid_amp_env_cfg.py:29, :53);
* the episode lasts 10.0 s, so this kinematic fake truncates after 300 environment steps (humanoid_amp_env_cfg.py:28);
* early termination compares the reference-body height with 0.5 m (humanoid_amp_env_cfg.py:38-39,
  humanoid_amp_env.py:108-114);
* the observation layout is the concatenation ``compute_obs`` builds (humanoid_amp_env.py:221-240): joint
  positions (28), joint velocities (28), root height (1), two tangent/normal vectors (6), root linear velocity (3),
  root angular velocity (3) and four key-body positions relative to the root (12).

What is not the upstream environment (also listed in the driver's fidelity ``gaps``):

* the dynamics are kinematic: the action is a small joint-position increment and nothing models contacts,
  actuators, gravity or the soft joint-position limits that ``humanoid_amp_env.py:28-32`` and :80-82 use;
* the fake presents one unbatched environment, while the upstream scene config batches 4096 environments by default
  (humanoid_amp_env_cfg.py:62) and returns a ``{"policy": ...}`` observation;
* the fake never terminates on height because it has no balance model; it only truncates at the episode length;
* the initial joint values and the observation constants below are test data, not device facts, and every one is
  marked ``# placeholder``.

Nothing here talks to a device.
"""

import math
import random

# humanoid_amp_env_cfg.py:32-33
OBSERVATION_SIZE = 81
ACTION_SIZE = 28
# humanoid_amp_env_cfg.py:28-29, :53
EPISODE_LENGTH_S = 10.0
DECIMATION = 2
PHYSICS_DT_S = 1.0 / 60.0
STEP_DT_S = PHYSICS_DT_S * DECIMATION
# ceil(episode_length_s / (sim.dt * decimation)) = ceil(10.0 / (1/60 * 2)) = 300
MAX_EPISODE_STEPS = math.ceil(EPISODE_LENGTH_S / STEP_DT_S)
# humanoid_amp_env_cfg.py:38-39
TERMINATION_HEIGHT = 0.5
# humanoid_amp_env.py:38: four key bodies of the generic humanoid environment
KEY_BODY_COUNT = 4
# humanoid_amp_env.py:29-32 and :80-82: the real action is scaled into the soft joint limits.  The fake has no
# joint-limit table (HUMANOID_28_CFG comes from the external isaaclab_assets package), so it applies a small
# increment instead.
ACTION_INCREMENT = 0.01                                                     # placeholder
# humanoid_amp_env.py:105-106: the reward is one for every environment at every step
STEP_REWARD = 1.0                                                           # placeholder (constant of the fake)
# humanoid_amp_env.py:163: the upstream random reset lifts the root by 0.15 m; the fake uses a standing height
RESET_ROOT_HEIGHT = 1.0                                                     # placeholder
RESET_JOINT_SPREAD = 0.05                                                   # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakeHumanoidAmpEnv:
    """One ``HumanoidAmpEnv`` without Isaac Sim: the Gymnasium method surface and the configured dimensions."""

    def __init__(self, render_mode=None):
        if render_mode is not None:
            raise ValueError("the fake HumanoidAmpEnv cannot render; use render_mode=None")
        # humanoid_amp_env_cfg.py:32-33: one Box per space with the configured dimensions.  The bounds are not
        # stated in the clone (the DirectRLEnv base builds the spaces outside it), so the fake leaves them unbounded
        # instead of inventing a limit; the driver's fidelity gaps record that the base was not read as a source.
        self.action_space = Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE, (ACTION_SIZE,))
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE,
                                     (OBSERVATION_SIZE,))
        self._rng = random.Random()
        self._joint_positions = None
        self._joint_velocities = None
        self._height = None
        self._elapsed_steps = 0

    def reset(self, *, seed=None, options=None):
        """Reset one environment, echoing the gymnasium reset contract."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._joint_positions = [self._rng.uniform(-RESET_JOINT_SPREAD, RESET_JOINT_SPREAD)
                                 for _ in range(ACTION_SIZE)]                       # placeholder
        self._joint_velocities = [0.0] * ACTION_SIZE                                # placeholder
        self._height = RESET_ROOT_HEIGHT                                            # placeholder
        self._elapsed_steps = 0
        return self._observation(), {}

    def step(self, action):
        if self._joint_positions is None:
            raise RuntimeError("call reset before step")
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must hold {ACTION_SIZE} values, got {len(values)}")
        # A kinematic stand-in for humanoid_amp_env.py:80-82: move each joint by a small increment of its action.
        for index, value in enumerate(values):
            self._joint_positions[index] += ACTION_INCREMENT * float(value)
        self._joint_velocities = [ACTION_INCREMENT * float(value) for value in values]
        self._elapsed_steps += 1
        # humanoid_amp_env_cfg.py:38-39 with humanoid_amp_env.py:108-114: this height is a placeholder and the fake
        # has no balance model, so the height never crosses the termination threshold.
        terminated = bool(self._height < TERMINATION_HEIGHT)
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return self._observation(), STEP_REWARD, terminated, truncated, {}

    def close(self):
        self._joint_positions = None

    def _observation(self):
        """``compute_obs`` of humanoid_amp_env.py:221-240, in its configured layout."""
        tangent = [1.0, 0.0, 0.0]                                                   # placeholder
        normal = [0.0, 0.0, 1.0]                                                    # placeholder
        linear_velocity = [0.0, 0.0, 0.0]                                           # placeholder
        angular_velocity = [0.0, 0.0, 0.0]                                          # placeholder
        key_body_positions = [0.0] * (KEY_BODY_COUNT * 3)                           # placeholder
        observation = (
            list(self._joint_positions)
            + list(self._joint_velocities)
            + [self._height]
            + tangent
            + normal
            + linear_velocity
            + angular_velocity
            + key_body_positions
        )
        if len(observation) != OBSERVATION_SIZE:
            raise AssertionError(f"the fake observation has {len(observation)} values, expected {OBSERVATION_SIZE}")
        return observation
