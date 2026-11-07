"""Fake backend of the VMAS driver: a pure Python stand-in for a VMAS balance environment behind its Gymnasium wrapper.

Why a fake: the gate refuses to import the read-only clone, and the upstream package needs torch, gym and, for the
wrapper, gymnasium and shimmy (setup.py:33-42 and vmas/simulator/environment/gym/gymnasium.py:14-23); none of them is
installed where the gate runs.  This module only re-states the *interface* the driver names as native
(``vmas.simulator.environment.gym.gymnasium:GymnasiumWrapper``): ``reset(seed=..., options=...)`` returns
``(observation, info)``, ``step(action)`` returns ``(observation, reward, terminated, truncated, info)``, and
``action_space``/``observation_space`` are Dicts of Boxes, one per agent, as the wrapper's converted spaces are for
``dict_spaces=True``.  It does not import or run the clone.

What this is not: the upstream simulator.  The balance scenario has three agents by default
(vmas/scenarios/balance.py:17), each with the default holonomic action size 2
(vmas/simulator/dynamics/holonomic.py:11-12 and vmas/simulator/core.py:929-937) and the default action range 1.0
(vmas/simulator/core.py:851); its observation concatenates nine blocks (vmas/scenarios/balance.py:245-256).  The
transitions here are deliberately simple placeholder dynamics, not VMAS's PyTorch rigid-body equations, and the
per-agent rewards of the wrapper are reduced to the single scalar that ``cap.world.step.v1`` carries.  Every number
below is test data and is marked ``# placeholder``; none of them is a fact, a limit or a reference.

The public surface is exactly what the fake class may implement (gate G7): ``reset`` and ``step``, the two methods the
wrapper also has.  The space classes duck-type ``gymnasium.spaces.Dict`` and ``Box`` (the bridge reads ``spaces``,
``low``, ``high`` and ``shape``); they are not the fake's native class and are not attributes of it.
"""

import math
import random

# balance.py:17 defaults to n_agents=3; these are the agent names the scenario builds (balance.py:36-38). # placeholder
AGENT_NAMES = ("agent_0", "agent_1", "agent_2")  # placeholder
ACTION_SIZE = 2                                 # holonomic.py:11-12
OBS_SIZE = 16                                   # balance.py:245-256 (2+2+2+2+2+2+2+1+1 values)
ACTION_BOUND = 1.0                              # core.py:851 default u_range; the fake's test bound # placeholder
U_MULTIPLIER = 0.7                              # balance.py:39 u_multiplier=0.7 # placeholder
DT_S = 0.1                                      # core.py:1095 default World dt # placeholder
PACKAGE_GOAL = (0.4, 0.6)                       # placeholder
INITIAL_PACKAGE = (0.0, 0.2)                    # placeholder
INITIAL_LINE = (0.0, 0.0)                       # placeholder
PACKAGE_VELOCITY = (0.01, 0.0)                  # placeholder
LINE_VELOCITY = (0.0, 0.0)                      # placeholder
LINE_ANGULAR_VELOCITY = 0.0                     # placeholder
START_SPAN = 0.5                                # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a named sub-space per agent."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = "object"


class FakeVMASBalance:
    """A balance environment of three agents: the interface of GymnasiumWrapper, not its physics."""

    def __init__(self, **_options):
        # Each Agent's action is a Box of u_range 1.0 on every axis (core.py:851); the wrapper converts the
        # Environment's Dict of Boxes (gymnasium.py:43-45), so the fake declares the same shape.  # placeholder
        action_box = Box([-ACTION_BOUND] * ACTION_SIZE, [ACTION_BOUND] * ACTION_SIZE)
        observation_box = Box([-math.inf] * OBS_SIZE, [math.inf] * OBS_SIZE)
        self.action_space = Dict({name: action_box for name in AGENT_NAMES})
        self.observation_space = Dict({name: observation_box for name in AGENT_NAMES})
        self._rng = random.Random(0)                          # placeholder seed
        self._seed = 0                                        # placeholder seed
        self._tick = 0
        self._agent_pos = [list(INITIAL_LINE) for _ in AGENT_NAMES]       # placeholder
        self._agent_vel = [[0.0, 0.0] for _ in AGENT_NAMES]               # placeholder
        self._package_pos = list(INITIAL_PACKAGE)                         # placeholder
        self._package_vel = list(PACKAGE_VELOCITY)                        # placeholder
        self._line_pos = list(INITIAL_LINE)                               # placeholder
        self._line_vel = list(LINE_VELOCITY)                              # placeholder
        self._line_ang_vel = LINE_ANGULAR_VELOCITY                        # placeholder
        self._line_rot = 0.0                                              # placeholder

    def reset(self, *, seed=None, options=None):
        """The wrapper's reset: seed the generator, then take a fresh start state (gymnasium.py:65-75)."""
        if seed is not None:
            self._seed = int(seed)
        self._rng = random.Random(self._seed)
        self._tick = 0
        self._agent_pos = [
            [self._rng.uniform(-START_SPAN, START_SPAN), self._rng.uniform(-START_SPAN, START_SPAN)]  # placeholder
            for _ in AGENT_NAMES
        ]
        self._agent_vel = [[0.0, 0.0] for _ in AGENT_NAMES]               # placeholder
        self._package_pos = list(INITIAL_PACKAGE)                         # placeholder
        self._package_vel = list(PACKAGE_VELOCITY)                        # placeholder
        self._line_pos = list(INITIAL_LINE)                               # placeholder
        self._line_vel = list(LINE_VELOCITY)                              # placeholder
        self._line_ang_vel = LINE_ANGULAR_VELOCITY                        # placeholder
        self._line_rot = 0.0                                              # placeholder
        # The wrapper's options argument is accepted and not used (gymnasium.py:65-73).
        del options
        return self._observation(), {}

    def step(self, action):
        """Apply one action per agent and return the wrapper's five-tuple (gymnasium.py:51-63)."""
        controls = self._controls(action)
        for index, (u_x, u_y) in enumerate(controls):
            # A placeholder Euler step of the holonomic model; not VMAS's PyTorch integration.  # placeholder
            self._agent_vel[index][0] += U_MULTIPLIER * u_x * DT_S
            self._agent_vel[index][1] += U_MULTIPLIER * u_y * DT_S
            self._agent_pos[index][0] += self._agent_vel[index][0] * DT_S
            self._agent_pos[index][1] += self._agent_vel[index][1] * DT_S
        self._package_pos[0] += self._package_vel[0] * DT_S              # placeholder
        self._package_pos[1] += self._package_vel[1] * DT_S              # placeholder
        self._line_pos[0] += self._line_vel[0] * DT_S                    # placeholder
        self._line_pos[1] += self._line_vel[1] * DT_S                    # placeholder
        self._line_rot += self._line_ang_vel * DT_S                      # placeholder
        self._tick += 1
        reward = -sum(                                                    # placeholder reward reduction
            abs(pos[0] - PACKAGE_GOAL[0]) + abs(pos[1] - PACKAGE_GOAL[1])  # placeholder
            for pos in self._agent_pos
        )
        # The wrapper returns one reward per agent; cap.world.step.v1 carries a single number, so the fake reduces
        # the placeholder per-agent rewards to their sum (a fidelity gap of the driver).
        return self._observation(), reward, False, False, {}

    def _controls(self, action):
        """Accept the bridge's agent-name mapping or the wrapper's list of per-agent actions."""
        if isinstance(action, dict):
            values = [action[name] for name in AGENT_NAMES]
        else:
            values = list(action)
        if len(values) != len(AGENT_NAMES):
            raise ValueError(f"expected {len(AGENT_NAMES)} agent actions, got {len(values)}")
        controls = []
        for value in values:
            if hasattr(value, "tolist"):
                value = value.tolist()
            flat = list(value)
            if len(flat) != ACTION_SIZE:
                raise ValueError(f"expected {ACTION_SIZE} action values, got {len(flat)}")
            controls.append((float(flat[0]), float(flat[1])))
        return controls

    def _observation(self):
        """The nine blocks of balance.py:245-256, in the wrapper's per-agent Dict form."""
        observations = {}
        for index, name in enumerate(AGENT_NAMES):
            pos_x, pos_y = self._agent_pos[index]
            vel_x, vel_y = self._agent_vel[index]
            observations[name] = [
                pos_x, pos_y,                                             # agent.state.pos
                vel_x, vel_y,                                             # agent.state.vel
                pos_x - self._package_pos[0], pos_y - self._package_pos[1],       # agent - package
                pos_x - self._line_pos[0], pos_y - self._line_pos[1],             # agent - line
                self._package_pos[0] - PACKAGE_GOAL[0],                   # package - package goal
                self._package_pos[1] - PACKAGE_GOAL[1],                   # placeholder
                self._package_vel[0], self._package_vel[1],               # package velocity
                self._line_vel[0], self._line_vel[1],                     # line velocity
                self._line_ang_vel,                                       # line angular velocity
                self._line_rot % math.pi,                                 # line rotation modulo pi
            ]
        return observations
