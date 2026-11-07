"""Fake backend of the OmniIsaacGymEnvs driver: a single-environment stand-in for ``VecEnvRLGames``.

Why a fake: the upstream class needs Isaac Sim 4.0.0 (README.md:31-33) and the ``omni.isaac.gym``
framework (``omniisaacgymenvs/envs/vec_env_rlgames.py:34``), neither of which is installed where the gate runs, and
package code never imports the clone.  This module therefore implements the public entry points the Gymnasium bridge
uses on ``VecEnvRLGames`` -- ``reset(seed, options)`` and ``step(actions)`` -- plus the two spaces the bridge reads.
The space sizes, the reset ranges, the reward formula, the failure thresholds and the control period are taken from
the Cartpole task and its Hydra config; every one cites its line below.

What this is not: Isaac Sim or PhysX.  The update between steps is an analytic surrogate, clearly marked
``# placeholder``: it has no rigid-body dynamics, contacts, actuator or sensor model, so it is F0 (no dynamics
claim).  The real ``VecEnvRLGames`` step returns an observation dict and per-environment tensors; this fake serves
one environment and returns a plain four-vector with a scalar reward and a scalar done flag (the real sizes are named
in the driver's fidelity ``gaps`` and in RESULT.json).

Nothing here talks to a device.
"""

import math
import random

# rl_task.py:127-131: the default action space is Box(-1, 1) per action dimension; Cartpole does not override it.
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# cartpole.py:46-47: four observations (cart position, cart velocity, pole position, pole velocity), one action.
NUM_OBSERVATIONS, NUM_ACTIONS = 4, 1
# cartpole.py:44: the Cartpole episode length.
MAX_EPISODE_LENGTH = 500
# Cartpole.yaml:10 and :14: resetDist 3.0 and clipActions 1.0.
RESET_DIST = 3.0
CLIP_ACTIONS = 1.0
# Cartpole.yaml:13: clipObservations 5.0, applied in vec_env_rlgames.py:40.
CLIP_OBSERVATIONS = 5.0
# Cartpole.yaml:15-18: two physics steps of 0.0083 s per control step, about 60 Hz.
CONTROL_PERIOD_S = 2 * 0.0083
# cartpole.py:129-135: the reset draws positions and velocities from these half-ranges.
RESET_CART_POS = 1.0
RESET_POLE_POS = 0.125 * math.pi
RESET_CART_VEL = 0.5
RESET_POLE_VEL = 0.25 * math.pi
# cartpole.py:153-156: reward coefficients and the failure penalty.
REWARD_POLE_POS = 1.0
REWARD_CART_VEL = 0.01
REWARD_POLE_VEL = 0.005
FAILURE_REWARD = -2.0
# cartpole.py:162: the pole fails beyond pi/2.
POLE_LIMIT = math.pi / 2.0
# Placeholder gains of the analytic stand-in; they are test data, not properties of Isaac Sim.
CART_VELOCITY_GAIN = 2.0   # placeholder
POLE_VELOCITY_GAIN = 3.0   # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeVecEnvRLGames:
    """One Cartpole environment with ``VecEnvRLGames.reset``/``step`` names and Gymnasium spaces.

    ``reset(seed, options)`` reseeds the fake's own ``random.Random`` when a seed is given (the upstream reset
    accepts but ignores seed and options, vec_env_rlgames.py:106-115) and returns a four-vector observation.
    ``step(actions)`` returns ``(observation, reward, done, extras)``: the same four slots as the upstream's
    ``(obs_dict, rew, resets, extras)`` (vec_env_rlgames.py:104), but for one environment and with Python scalars
    instead of tensors.
    """

    def __init__(self, seed=None, options=None):
        # Cartpole task uses the RLTask default Box(-1, 1) for one action (rl_task.py:127-131, cartpole.py:47).
        self.action_space = Box([ACTION_LOW] * NUM_ACTIONS, [ACTION_HIGH] * NUM_ACTIONS)
        # Cartpole task uses the RLTask default Box(-inf, inf) for four observations (rl_task.py:132-136,
        # cartpole.py:46).
        self.observation_space = Box([-math.inf] * NUM_OBSERVATIONS, [math.inf] * NUM_OBSERVATIONS)
        self._rng = random.Random(seed)
        # placeholder: the state before the first reset; the bridge always resets before it steps
        self._cart_pos = 0.0
        self._cart_vel = 0.0
        self._pole_pos = 0.0
        self._pole_vel = 0.0
        self._progress = 0

    def _observation(self):
        values = [self._cart_pos, self._cart_vel, self._pole_pos, self._pole_vel]
        # vec_env_rlgames.py:40 clamps the observation to +-clipObservations (5.0 for Cartpole, Cartpole.yaml:13).
        return [max(-CLIP_OBSERVATIONS, min(CLIP_OBSERVATIONS, value)) for value in values]

    def reset(self, seed=None, options=None):
        """Draw the initial state from the ranges of ``CartpoleTask.reset_idx`` and return it as a four-vector."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        # cartpole.py:129-135: uniform positions and velocities in the reset half-ranges, sampled with 1 - 2 * u.
        self._cart_pos = RESET_CART_POS * (1.0 - 2.0 * self._rng.random())
        self._pole_pos = RESET_POLE_POS * (1.0 - 2.0 * self._rng.random())
        self._cart_vel = RESET_CART_VEL * (1.0 - 2.0 * self._rng.random())
        self._pole_vel = RESET_POLE_VEL * (1.0 - 2.0 * self._rng.random())
        self._progress = 0
        return self._observation()

    def step(self, actions):
        """Apply ``actions[0]`` once and return ``(observation, reward, done, extras)`` for the single environment."""
        values = list(actions)
        action = float(values[0])
        # vec_env_rlgames.py:77 clamps the action to +-clipActions (1.0 for Cartpole, Cartpole.yaml:14).
        action = max(-CLIP_ACTIONS, min(CLIP_ACTIONS, action))
        # Analytic stand-in, not Isaac Sim: the action sets the two velocities and the state integrates them.
        self._cart_vel = CART_VELOCITY_GAIN * action                 # placeholder
        self._pole_vel = POLE_VELOCITY_GAIN * action                 # placeholder
        self._cart_pos += self._cart_vel * CONTROL_PERIOD_S
        self._pole_pos += self._pole_vel * CONTROL_PERIOD_S
        self._progress += 1

        # cartpole.py:153-156: the upstream Cartpole reward and failure penalty.
        reward = (REWARD_POLE_POS
                  - self._pole_pos * self._pole_pos
                  - REWARD_CART_VEL * abs(self._cart_vel)
                  - REWARD_POLE_VEL * abs(self._pole_vel))
        if abs(self._cart_pos) > RESET_DIST or abs(self._pole_pos) > POLE_LIMIT:
            reward = FAILURE_REWARD
        # cartpole.py:160-163: a reset is flagged on the position thresholds or at the 500-step episode length.
        done = (abs(self._cart_pos) > RESET_DIST or abs(self._pole_pos) > POLE_LIMIT
                or self._progress >= MAX_EPISODE_LENGTH)
        return self._observation(), reward, done, {}
