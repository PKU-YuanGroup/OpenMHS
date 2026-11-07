"""Fake backend of the Flamingo driver: a pure Python interface stand-in for the Isaac Lab velocity-flat task.

Why a fake: the registered task needs Isaac Sim 4.5 and Isaac Lab 2.0.0 (README.md:3-5), a GPU and the manually
unzipped USD assets (README.md:74-78), and package code never imports the clone.  The gate therefore checks this
stand-in, which reproduces the parts of the Gymnasium contract the bridge reads: ``action_space`` and
``observation_space``, ``reset(seed, options)``, ``step(action)`` and ``close``.  The upstream class
``ManagerBasedConstraintRLEnv`` inherits the rest of that interface from ``ManagerBasedEnv`` and ``gym.Env``.

What this is not: the upstream environment.  It has no Isaac Sim, no rigid bodies, no contacts, no actuator, sensor
or noise model and no robot pose.  The 28-value observation follows the ``stack_policy`` term order of
``lab/flamingo/tasks/constraint_based/locomotion/velocity/velocity_env_cfg.py:240-250`` (six joint positions, eight
joint velocities, three base angular-velocity values, three base Euler values, eight last-action values); only the
last-action tail reflects the action, every other value is a fixed test placeholder, and the reward is a fixed test
placeholder.  The 8-value action and the 28-value observation are the sizes of the default ``FlamingoFlatEnvCfg``
(``.../flat_env_stand_drive_cfg.py:36-52`` and ``velocity_env_cfg.py:240-250``), not a claim that the physics is
modelled.  The upstream task serves a vector of 4096 environments by default (``velocity_env_cfg.py:419``); this
stand-in serves one environment and uses the single-environment spaces.

The timestep and the time limit are the task's: decimation 4 times sim.dt 0.005 s is 20 ms per step
(``velocity_env_cfg.py:433-436``), episode_length_s 20.0 s is 1000 steps (``flat_env_stand_drive_cfg.py:247-251`` and
``manager_based_constraint_rl_env.py:97-105``), and the time_out constraint truncates there
(``.../velocity/mdp/constraints.py:59-61``).  The base_contact constraint is not modelled.
"""

import math

# lab/flamingo/tasks/constraint_based/locomotion/velocity/flamingo_env/flat_env/stand_drive/
# flat_env_stand_drive_cfg.py:36-52: six joint-position terms and two wheel-velocity terms.
ACTION_SIZE = 8
# velocity_env_cfg.py:240-250 (stack_policy): 6 joint positions + 8 joint velocities + 3 base angular velocities
# + 3 base Euler angles + 8 last actions.
OBSERVATION_SIZE = 28
# flat_env_stand_drive_cfg.py:247-251 (episode_length_s = 20.0), velocity_env_cfg.py:433-436
# (decimation 4 and sim.dt 0.005), manager_based_constraint_rl_env.py:97-105 (ceil(20.0 / 0.02) = 1000).
MAX_EPISODE_STEPS = 1000
# The last-action term of velocity_env_cfg.py:240-250 is the action itself; the other 20 values are fixed test data.
ACTION_OBSERVATION_OFFSET = OBSERVATION_SIZE - ACTION_SIZE


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeFlamingoVelocityFlatEnv:
    """One Flamingo velocity-flat environment without Isaac Sim: the contract, not the physics."""

    def __init__(self, render_mode=None):
        if render_mode is not None:
            raise ValueError("the fake Flamingo environment cannot render; use render_mode=None")
        # manager_based_constraint_rl_env.py:327-348: an unbounded Box action space and an unbounded Box observation
        # space; the upstream task batches both over num_envs, this stand-in serves one environment.
        self.action_space = Box([-math.inf] * ACTION_SIZE, [math.inf] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self._seed = None
        self._tick = 0
        self._observation = [0.0] * OBSERVATION_SIZE  # placeholder
        self._terminated = False
        self._truncated = False

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``options`` is accepted for the Gymnasium reset contract and has no effect."""
        if seed is not None:
            self._seed = int(seed)
        self._tick = 0
        self._terminated = False
        self._truncated = False
        self._observation = [0.0] * OBSERVATION_SIZE  # placeholder
        return list(self._observation), {}

    def step(self, action):
        """Apply one 8-value action and advance one 20 ms control step."""
        values = list(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action must have {ACTION_SIZE} values, got {len(values)}")
        checked = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"the action values must be numbers, got {value!r}")
            checked.append(float(value))
        # Keep the last-action observation term observable: the tail of the observation is the raw action.
        self._observation = ([0.0] * ACTION_OBSERVATION_OFFSET  # placeholder
                             + checked)
        self._tick += 1
        self._terminated = False
        self._truncated = self._tick >= MAX_EPISODE_STEPS
        reward = 0.0  # placeholder
        return list(self._observation), reward, self._terminated, self._truncated, {}

    def close(self):
        self._observation = []
