"""Fake backend of the FlyCraft driver: a pure Python stand-in for ``flycraft.env:FlyCraftEnv``.

Why a fake: upstream FlyCraft needs platform-specific compiled ``*.so``/``*.dll`` libraries and is documented as
Linux/Windows only (README.md:74); the gate never imports or runs the clone.  This module mirrors the class the
driver names as ``native`` (the methods ``reset``, ``step`` and ``close`` and the two spaces, gate G7) and keeps
the space bounds of the default ``guidance_law_mode`` configuration.  It does **not** model the F16 flight
dynamics: the observation update, reward and termination are simplified stand-ins, all listed in the fidelity
``gaps`` of ``driver.py``.

Numbers that are test data (the start state, the goal ranges, the kinematic increments, the reward scale and the
episode limit) are marked ``# placeholder``.  The space bounds are the upstream bounds and cite their lines.
Nothing here talks to a device.
"""

import math
import random

# Observation space bounds, in the order phi, theta, psi, v, mu, chi, p, h
# (flycraft/tasks/velocity_vector_control_task.py:454 and :464).
OBSERVATION_LOW = [-180.0, -90.0, -180.0, 0.0, -90.0, -180.0, -300.0, 0.0]
OBSERVATION_HIGH = [180.0, 90.0, 180.0, 1000.0, 90.0, 180.0, 300.0, 20000.0]
# Goal space bounds, in the order v, mu, chi (velocity_vector_control_task.py:469 and :474).
GOAL_LOW = [0.0, -90.0, -180.0]
GOAL_HIGH = [1000.0, 90.0, 180.0]
# Action space of the default guidance_law_mode: [p, nz, pla]
# (flycraft/planes/f16_plane.py:161 and :172).
ACTION_LOW = [-180.0, -4.0, 0.0]
ACTION_HIGH = [180.0, 9.0, 1.0]

# Test data below, not facts of the device.
STEP_S = 0.1                                    # placeholder
MAX_EPISODE_STEPS = 400                         # placeholder
START_STATE = [0.0, 0.0, 0.0, 200.0, 0.0, 0.0, 0.0, 5000.0]  # placeholder: phi, theta, psi, v, mu, chi, p, h
GOAL_V_RANGE = (100.0, 300.0)                   # placeholder
GOAL_MU_RANGE = (-90.0, 90.0)                   # placeholder
GOAL_CHI_RANGE = (-180.0, 180.0)                # placeholder
PHI_PER_P = 0.01                                # placeholder
THETA_PER_NZ = 0.05                             # placeholder
PSI_PER_P = 0.01                                # placeholder
V_PER_NZ = 0.5                                  # placeholder
MU_PER_P = 0.01                                 # placeholder
CHI_PER_P = 0.01                                # placeholder
REWARD_SCALES = (100.0, 180.0, 180.0)           # placeholder


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` as a mapping."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


def _clamp(value, low, high):
    return low if value < low else high if value > high else value


class FakeFlyCraftEnv:
    """``FlyCraftEnv`` without gymnasium, numpy or the compiled F16 model.

    The public members are the ones ``FlyCraftEnv`` has (``reset``, ``step``, ``close``; gate G7), and the two
    space objects duck-type the gymnasium spaces the bridge reads (``spaces``, ``low``, ``high``, ``shape``,
    ``dtype``).
    """

    def __init__(self, custom_config=None, config_file=None, **_options):
        # The fake serves the default NMR.json configuration (guidance_law_mode); custom_config and config_file
        # are accepted for signature compatibility and are not modelled (fidelity gaps).
        self.observation_space = Dict({
            "observation": Box(OBSERVATION_LOW, OBSERVATION_HIGH),
            "desired_goal": Box(GOAL_LOW, GOAL_HIGH),
            "achieved_goal": Box(GOAL_LOW, GOAL_HIGH),
        })
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        self._rng = random.Random()
        self._state = None
        self._goal = None
        self._steps = 0

    def reset(self, *, seed=None, options=None):
        """Reset the fake: reseed the goal draw when a seed is given and return ``(observation, info)``."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        # placeholder: a uniform goal, not the upstream goal sampler
        self._goal = [
            self._rng.uniform(*GOAL_V_RANGE),
            self._rng.uniform(*GOAL_MU_RANGE),
            self._rng.uniform(*GOAL_CHI_RANGE),
        ]
        self._state = list(START_STATE)  # placeholder: a fixed trimmed start, not the F16 trim result
        self._steps = 0
        return self._observation(), {"plane_state": self._plane_state()}

    def step(self, action):
        """Advance one placeholder kinematic step and return the Gymnasium five-tuple."""
        if self._state is None:
            raise RuntimeError("Call reset before using step method.")
        values = list(action)
        if len(values) != 3:
            raise ValueError("the default guidance_law_mode action has three values [p, nz, pla]")
        p, nz, pla = (float(item) for item in values)
        self._steps += 1
        phi, theta, psi, v, mu, chi, _p_rate, h = self._state
        # placeholder kinematics: no aerodynamics and no control law
        phi = _clamp(phi + PHI_PER_P * p * STEP_S, OBSERVATION_LOW[0], OBSERVATION_HIGH[0])
        theta = _clamp(theta + THETA_PER_NZ * nz * STEP_S, OBSERVATION_LOW[1], OBSERVATION_HIGH[1])
        psi = _clamp(psi + PSI_PER_P * p * STEP_S, OBSERVATION_LOW[2], OBSERVATION_HIGH[2])
        v = _clamp(v + V_PER_NZ * nz * STEP_S, OBSERVATION_LOW[3], OBSERVATION_HIGH[3])
        mu = _clamp(mu + MU_PER_P * p * STEP_S, OBSERVATION_LOW[4], OBSERVATION_HIGH[4])
        chi = _clamp(chi + CHI_PER_P * p * STEP_S, OBSERVATION_LOW[5], OBSERVATION_HIGH[5])
        h = _clamp(h + v * math.sin(math.radians(theta)) * STEP_S, OBSERVATION_LOW[7], OBSERVATION_HIGH[7])
        self._state = [phi, theta, psi, v, mu, chi, p, h]
        # placeholder: only the timeout truncation of the upstream task
        terminated = self._steps >= MAX_EPISODE_STEPS - 1
        truncated = terminated
        goal_v, goal_mu, goal_chi = self._goal
        reward = -((abs(v - goal_v) / REWARD_SCALES[0] + abs(mu - goal_mu) / REWARD_SCALES[1]
                    + abs(chi - goal_chi) / REWARD_SCALES[2]) / 3.0)  # placeholder dense reward
        info = {
            "step": self._steps,
            "is_success": False,
            "plane_state": self._plane_state(),
            "action": {"p": p, "nz": nz, "pla": pla, "rud": 0.0},
        }
        return self._observation(), float(reward), bool(terminated), bool(truncated), info

    def close(self):
        self._state = None

    def _observation(self):
        return {
            "observation": [float(item) for item in self._state],
            "achieved_goal": [self._state[3], self._state[4], self._state[5]],
            "desired_goal": list(self._goal),
        }

    def _plane_state(self):
        phi, theta, psi, v, mu, chi, p, h = self._state
        return {
            "phi": phi, "theta": theta, "psi": psi, "v": v, "mu": mu, "chi": chi, "p": p, "h": h,
        }
