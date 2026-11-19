"""Fake backend of the Isaac Lab Extreme Parkour teacher driver.

Why a fake: the upstream environment needs Isaac Sim, Isaac Lab, ``isaaclab_assets`` and a GPU (README.md:13-25,
scripts/rsl_rl/demo.py:39-40), and package code never imports or runs the clone.  The acceptance gate therefore runs
this pure Python stand-in for one environment of the teacher task.  It keeps the members the upstream class has
(``reset``, ``step`` and ``close``; gate G7) and duck-types the Gymnasium spaces the bridge reads
(``action_space``, ``observation_space``, ``Box``, ``Dict``).

What this is not: the simulator.  The state values, the update law and the reward are test data, not facts, and the
real observation and action sizes are documented by their source lines below.  Differences are listed in the
driver's fidelity ``gaps``:

* upstream is vectorized (``is_vector_env = True``, 6144 environments); this fake presents one environment and keeps
  the batched space shapes of ``num_envs = 1``, but adapts rewards and flags to scalars and omits auto-reset;
* the action dimension 12 is a placeholder inferred from the 12 joint stiffness and 12 joint damping terms of the
  policy configuration (``parkour_rl_cfg.py:25``); the clone does not state the joint count;
* the fake's finite action Box deliberately restricts inputs to the upstream raw-action clip interval, unlike the
  native unbounded Gym Box; the generated bounds identify the fake rather than claiming an upstream space citation;
* there is no physics, terrain, contact sensor, height scanner or manager computation.

The episode truncation is the teacher task's 20.0 s episode length divided by the 20 ms environment step
(``parkour_teacher_cfg.py:48-52``: episode_length_s = 20.0, sim.dt = 0.005, decimation = 4).  The fake models no
termination condition; the upstream predicates are cited in driver.py facts.  Nothing here talks to a device.
"""

import random

# placeholder: the Unitree Go2 action dimension is not stated in the clone; 12 is inferred from the 12 joint
# stiffness and 12 joint damping terms counted in parkour_rl_cfg.py:25.
ACTION_DIM = 12
# placeholder: the observation vector is 53 + 132 + 9 + 29 + 10 * 53 = 753 values from parkour_rl_cfg.py:24-28 and
# the concatenation in observations.py:85-90; the values the fake fills are not the simulator's.
OBS_DIM = 753
# 20.0 s / (4 * 0.005 s) = 1000 environment steps (parkour_teacher_cfg.py:48-52); the step count is a placeholder
# because the fake does not integrate physics.
MAX_EPISODE_LENGTH = 1000
# Raw-action mapping from parkour_mdp_cfg.py:343,349 and parkour_actions/joint_actions.py:33-54.
ACTION_SCALE = 0.25
ACTION_CLIP = 4.8
# placeholder: the external asset's default pose is not reproduced; targets use this neutral offset.
DEFAULT_JOINT_OFFSET = 0.0


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: bounds, shape and dtype as the bridge reads them."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float64"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of names to sub-spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeParkourEnv:
    """One environment of the Extreme Parkour teacher task, without Isaac Sim or numpy."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        # The upstream constructor takes a ParkourManagerBasedRLEnvCfg; the fake ignores it (placeholder).
        self.cfg = cfg
        self.render_mode = render_mode
        self.num_envs = 1                                                        # placeholder: one env of 6144
        # Deliberately narrower fake contract: use the raw-action clip interval from parkour_mdp_cfg.py:349.
        # Upstream's Gym Box at RL_ENV:239-244 is unbounded and batched over 6144 environments; this fake's
        # dimensions are placeholders and its finite limits carry fake-backend provenance, not action_space_ref.
        unbounded = float("inf")
        self.action_space = Box([-ACTION_CLIP] * ACTION_DIM, [ACTION_CLIP] * ACTION_DIM, (1, ACTION_DIM))
        # RL_ENV:224-243: a Dict of unbounded Box spaces for the observation groups, batched over num_envs; the
        # teacher group is "policy" (parkour_mdp_cfg.py:44-61).
        self.observation_space = Dict({"policy": Box([-unbounded] * OBS_DIM, [unbounded] * OBS_DIM,
                                                     (1, OBS_DIM))})
        self._rng = random.Random()
        self._joints = [0.0] * ACTION_DIM                                       # placeholder start positions
        self._tick = 0
        self._closed = False

    def reset(self, seed=None, env_ids=None, options=None):
        """Reset one environment; same keyword names and ``(observation, info)`` pair as the upstream reset."""
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        self._joints = [self._rng.uniform(-0.01, 0.01) for _ in range(ACTION_DIM)]  # placeholder
        self._tick = 0
        return self._observation(), {"log": {}}

    def step(self, action):
        """Advance one environment step; same 5-tuple positions as the vectorized upstream step."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = self._action_values(action)
        # Placeholder instantaneous tracking of absolute targets, with the upstream raw-action affine mapping.
        self._joints = [max(-ACTION_CLIP, min(ACTION_CLIP, value)) * ACTION_SCALE + DEFAULT_JOINT_OFFSET
                        for value in values]
        self._tick += 1
        # placeholder: the reward and the termination flags are not the manager computations.  The truncation is
        # the teacher task's episode length in environment steps.
        truncated = self._tick >= MAX_EPISODE_LENGTH
        return self._observation(), 0.0, False, truncated, {"log": {}}

    def close(self):
        self._closed = True

    def _action_values(self, action):
        """Accept the bridge's flattened action list (and one batched row) and return the action values."""
        if isinstance(action, dict) and "values" in action:
            action = action["values"]
        values = list(action)
        if len(values) == 1 and isinstance(values[0], (list, tuple)):
            values = list(values[0])
        if len(values) != ACTION_DIM:
            raise ValueError(f"expected {ACTION_DIM} action values, got {len(values)}")
        return [float(value) for value in values]

    def _observation(self):
        """A placeholder observation with the teacher policy group's batched shape ``(1, 753)``."""
        policy = [0.0] * OBS_DIM
        policy[:ACTION_DIM] = self._joints
        policy[ACTION_DIM] = float(self._tick)
        return {"policy": [policy]}
