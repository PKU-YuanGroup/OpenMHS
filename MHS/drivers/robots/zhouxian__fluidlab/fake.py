"""Fake backend of the FluidLab Circulation driver: a pure Python stand-in for ``FluidEnv``/``CirculationEnv``.

Why a fake: the upstream package needs Taichi, torch, yacs, numpy and a GPU stack (``environment.yml``), the gate does
not install or import the clone, and package code never imports upstream code.  This module re-implements the public
surface of ``fluidlab.envs.circulation_env:CirculationEnv`` that the bridge uses (``reset``, ``step``, ``seed``) on a
small agent-only state.  The public members are the ones the upstream class and its base ``FluidEnv`` have (gate G7);
the two space classes duck-type ``gym.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape`` and ``dtype``).

Upstream references are to the clone at 7295eb6ed7ee92b2be471fd30b432238577f28ce:
``fluidlab/envs/circulation_env.py`` (action range, horizon), ``fluidlab/envs/fluid_env.py`` (reset, step, obs, spaces),
``fluidlab/envs/configs/agent_circulation.yaml`` (agent initial pose, 8 action dimensions and velocity scales),
``fluidlab/fluidengine/effectors/aircon.py`` (the 9-element AirCon state) and
``fluidlab/fluidengine/simulators/mpm_simulator.py`` (the physics timestep).

What this is not: the upstream environment.  The fake integrates no particles, smoke, contacts or fluid forces, and
every number not cited below is test data marked ``# placeholder``.  The driver's fidelity gaps and RESULT.json name
the real observation size (5487 floats) and what the fake omits.  Nothing here talks to a device.
"""

import math

# fluidlab/envs/configs/agent_circulation.yaml:6: action_dim: 8
ACTION_DIM = 8
# fluidlab/envs/circulation_env.py:27: self.action_range = np.array([-0.1, 0.1])
ACTION_LOW, ACTION_HIGH = -0.1, 0.1
# fluidlab/envs/configs/agent_circulation.yaml:5: init_pos: (0.8, 0.8, 0.5)
INIT_POS = (0.8, 0.8, 0.5)
# fluidlab/fluidengine/effectors/effector.py:25-26,45: the default init_euler (0, 0, 0) gives the identity
# quaternion in wxyz order. The AirCon starts at strength s = 0 and radius r = 0 (aircon.py:18-25).
INIT_QUAT = (1.0, 0.0, 0.0, 0.0)
# fluidlab/envs/circulation_env.py:21-22: horizon = horizon_action = 1000 (the registration passes loss_type
# 'default', so fluid_env.py:86-87 keeps the horizon equal to horizon_action).
HORIZON = 1000
# fluidlab/envs/configs/agent_circulation.yaml:8: action_scale_v = (1, 1, 1, 1, 1, 1, 100000, 50)
SCALE_STRENGTH = 100000.0
SCALE_RADIUS = 50.0
# Upstream reports one environment step as int(2e-3 / self.dt) substeps (mpm_simulator.py:24-30). The fake does not
# integrate them; the driver's fidelity declares the 2e-3 s control period as timestep_ms 2.0.
CONTROL_PERIOD_S = 2e-3


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element of a one-dimensional array."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeCirculationEnv:
    """The ``FluidEnv`` interface of Circulation-v0 over a 9-value agent state, without numpy."""

    def __init__(self):
        # placeholder for the initial strength and radius: the AirCon fields start at zero (aircon.py:18-25)
        self._init_state = list(INIT_POS) + list(INIT_QUAT) + [0.0, 0.0]
        self._state = None
        self._t = 0
        self._seed = None
        # fluidlab/envs/fluid_env.py:89-91: the observation space is Box(-inf, inf, obs.shape) and the action space
        # is Box(action_range[0], action_range[1], (agent.action_dim,)).  The fake observation is the 9-element
        # agent state (see the module docstring), not the full 5487-element upstream observation.
        self.observation_space = Box([-math.inf] * 9, [math.inf] * 9)
        self.action_space = Box([ACTION_LOW] * ACTION_DIM, [ACTION_HIGH] * ACTION_DIM)

    def reset(self):
        """``FluidEnv.reset`` (fluid_env.py:95-97): restore the stored initial state and return the observation."""
        self._state = list(self._init_state)
        self._t = 0
        return self._obs()

    def seed(self, seed):
        """``FluidEnv.seed`` (fluid_env.py:31-33) records the seed; reset restores a fixed initial state."""
        self._seed = int(seed)

    def step(self, action):
        """``FluidEnv.step`` (fluid_env.py:131-150) over the simplified agent state."""
        if self._state is None:
            raise AssertionError("Call reset before using step method.")
        values = [float(value) for value in action]
        if len(values) != ACTION_DIM:
            raise ValueError(f"the action must have {ACTION_DIM} values")
        # fluid_env.py:132: the action is clipped to action_range, not rejected
        values = [min(max(value, ACTION_LOW), ACTION_HIGH) for value in values]

        pos = self._state[0:3]
        for index in range(3):
            pos[index] += values[index]
        quat = self._state[3:7]
        # placeholder: a small angular-velocity integration for dimensions 4 to 6, then normalise the quaternion
        for index in range(3):
            quat[index + 1] += 0.1 * values[index + 3]  # placeholder
        norm = math.sqrt(sum(component * component for component in quat)) or 1.0  # placeholder
        quat = [component / norm for component in quat]
        strength = values[6] * SCALE_STRENGTH           # agent_circulation.yaml:8
        radius = values[7] * SCALE_RADIUS               # agent_circulation.yaml:8
        self._state = [float(value) for value in pos] + quat + [strength, radius]
        self._t += 1

        # placeholder: a stand-in for circulation_loss.py:134-136 (reward = 11 - cur_step_loss); the fake has no
        # temperature field, so this bounded penalty only makes the action observable.
        reward = 11.0 - 0.001 * abs(strength) - abs(radius)
        done = self._t == HORIZON                      # fluid_env.py:139-143
        if math.isnan(reward):                         # fluid_env.py:145-147
            reward = -1000
            done = True
        return self._obs(), reward, done, {}

    def _obs(self):
        """The 9-element agent state: position (3), quaternion (4), strength s, radius r (aircon.py:192-195)."""
        return list(self._state)
