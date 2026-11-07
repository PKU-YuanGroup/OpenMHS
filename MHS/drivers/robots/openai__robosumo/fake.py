"""Fake backend of the RoboSumo driver: a pure Python stand-in for ``robosumo.envs:SumoEnv`` (Ant-vs-Ant).

Why a fake: the upstream package imports ``gym``, ``mujoco_py`` and MuJoCo (``requirements.txt:1-5``) and the gate
never imports the clone.  This module is a reduced planar kinematic model of the two-ant sumo task, not MuJoCo.  The
members the gymnasium bridge uses (``reset``, ``step``, ``dt``, ``action_space``, ``observation_space``) are the names
the upstream class has (gate G7): ``reset``/``step`` come from the external ``gym.Env`` base that ``SumoEnv`` extends,
and ``dt``, ``action_space`` and ``observation_space`` are defined by ``robosumo/envs/mujoco_env.py:122-123`` and
``robosumo/envs/sumo.py:109-114``.

Every constant below cites the line of the clone at the pinned commit
(3a317e27d2342dd47a869950e93315b23a74921a).  The fake's own motion scale is a placeholder and is marked so.

What this is not (all listed in the fidelity ``gaps`` of driver.py):

* no MuJoCo: no contact, friction, actuator, sensor or noise model; the agents move on a plane with a fixed step;
* the observation is three position values per agent, not the real 120-value per-agent vector
  (``agents.py:190-212``);
* the action space is a ``Dict`` with the named members ``ant0`` and ``ant1``, each the same eight-motor ``Box`` as
  the upstream ``Tuple`` element, so the gymnasium bridge can derive the real ctrlrange limits per member (it derives
  no limits from the elements of a ``Tuple``); a ``Dict`` is not the upstream shape (``sumo.py:112-114``);
* the reward is the sum of the two agents' reduced rewards, not the upstream per-agent tuple
  (``sumo.py:188-192``); the per-agent values are carried in ``info["rewards"]``;
* the move_to_opp and push_opp shaping terms (``sumo.py:168-184``) are not modelled.

Nothing here talks to a device.
"""

import math
import random

# robosumo/__init__.py:12-15 (RoboSumo-Ant-vs-Ant-v0 registration)
AGENT_NAMES = ("ant", "ant")
TATAMI_SIZE = 2.0
TIMESTEP_LIMIT = 500
# robosumo/envs/sumo.py:55 (the environment adds 0.1 to the tatami size)
TATAMI_MARGIN = 0.1
# robosumo/envs/sumo.py:149-150 (lose test)
LOSE_HEIGHT = 0.29
# robosumo/envs/sumo.py:235 (respawn circle)
RESET_RADIUS = 1.15
RESET_HEIGHT = 1.25
# robosumo/envs/sumo.py:49-50 (reset noise defaults; no registration overrides the position noise)
INIT_POS_NOISE = 0.1
# robosumo/envs/agents.py:15-19 and :217-221 (control cost)
CTRL_COST = 0.1
# robosumo/envs/sumo.py:38-39
WIN_REWARD = 2000.0
DRAW_PENALTY = -1000.0
# robosumo/envs/assets/ant.xml:58-65 (eight motors, ctrlrange -1.0 1.0)
ANT_ACTUATORS = 8
CTRL_LOW, CTRL_HIGH = -1.0, 1.0
# robosumo/envs/mujoco_env.py:122-123 and robosumo/envs/assets/tatami.xml:3 (0.01 s * 5)
DT = 0.01 * 5
# placeholder: metres of planar travel per unit of mean motor command in this reduced model (not a device fact)
MOVE_SCALE = 0.2


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Tuple:
    """Duck-typed ``gym.spaces.Tuple``: the bridge reads ``spaces`` and its length."""

    def __init__(self, spaces):
        self.spaces = list(spaces)


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads the member spaces by name."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeSumoEnv:
    """A reduced Ant-vs-Ant sumo world with the bridge's reset/step contract."""

    def __init__(self):
        controls = Box([CTRL_LOW] * ANT_ACTUATORS, [CTRL_HIGH] * ANT_ACTUATORS)
        # robosumo/envs/sumo.py:109-114: the upstream action space is a Tuple of the two per-agent spaces; the fake
        # names the same two Boxes so the bridge derives their ctrlrange limits (see the module docstring).
        self.action_space = Dict({"ant0": controls, "ant1": Box([CTRL_LOW] * ANT_ACTUATORS, [CTRL_HIGH] * ANT_ACTUATORS)})
        self.observation_space = Tuple([
            Box([-math.inf] * 3, [math.inf] * 3),
            Box([-math.inf] * 3, [math.inf] * 3),
        ])
        self._rng = random.Random()
        self._positions = None
        self._steps = 0

    @property
    def dt(self):
        """``MujocoEnv.dt``: model timestep times frame_skip (``mujoco_env.py:122-123``)."""
        return DT

    def reset(self, *, seed=None, options=None):
        """Start a new episode: two agents on the respawn circle (``sumo.py:232-252``)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        phi = self._rng.uniform(0.0, 2.0 * math.pi)
        delta = (2.0 * math.pi) / len(AGENT_NAMES)
        positions = []
        for index in range(len(AGENT_NAMES)):
            angle = phi + index * delta
            x = RESET_RADIUS * math.cos(angle) + self._rng.uniform(-INIT_POS_NOISE, INIT_POS_NOISE)
            y = RESET_RADIUS * math.sin(angle) + self._rng.uniform(-INIT_POS_NOISE, INIT_POS_NOISE)
            z = RESET_HEIGHT + self._rng.uniform(-INIT_POS_NOISE, INIT_POS_NOISE)
            positions.append([x, y, z])
        self._positions = positions
        self._steps = 0
        return self._observation(), {}

    def step(self, action):
        """Advance the reduced model one fixed step and return the bridge's five-tuple."""
        if self._positions is None:
            raise AssertionError("Call reset before using step method.")
        controls = self._controls(action)
        positions = []
        for index, values in enumerate(controls):
            x, y, z = self._positions[index]
            push = sum(values) / len(values)
            positions.append([x + push * MOVE_SCALE, y, z])  # placeholder: planar push, no contact physics
        self._positions = positions
        self._steps += 1

        out = [self._is_out(position) for position in positions]
        rewards = []
        for index, values in enumerate(controls):
            main = 0.0
            if out[index]:
                main -= WIN_REWARD
            if any(out[other] for other in range(len(positions)) if other != index):
                main += WIN_REWARD
            if self._steps > TIMESTEP_LIMIT:
                main += DRAW_PENALTY
            control = -CTRL_COST * sum(value * value for value in values)  # agents.py:217-221
            rewards.append(main + control)
        terminated = any(out)
        truncated = self._steps > TIMESTEP_LIMIT and not terminated
        info = {"rewards": [float(value) for value in rewards], "steps": self._steps}
        return self._observation(), float(sum(rewards)), terminated, truncated, info

    def _observation(self):
        return tuple([float(value) for value in position] for position in self._positions)

    @staticmethod
    def _is_out(position):
        """``sumo.py:149-150``: z below 0.29 or |x| or |y| at least tatami_size + 0.1."""
        return position[2] < LOSE_HEIGHT or max(abs(position[0]), abs(position[1])) >= TATAMI_SIZE + TATAMI_MARGIN

    @staticmethod
    def _controls(action):
        """Unpack the bridge's named action and check the per-agent Box bounds (``ant.xml:58-65``)."""
        if isinstance(action, dict):
            if sorted(action) != ["ant0", "ant1"]:
                raise ValueError("the action must name the two agents ant0 and ant1")
            action = [action["ant0"], action["ant1"]]
        if not isinstance(action, (list, tuple)) or len(action) != len(AGENT_NAMES):
            raise ValueError("the action must carry one control vector per agent")
        out = []
        for values in action:
            if isinstance(values, dict):
                values = values.get("values")
            if not isinstance(values, (list, tuple)) or len(values) != ANT_ACTUATORS:
                raise ValueError("each agent action must have %d controls" % ANT_ACTUATORS)
            vector = [float(value) for value in values]
            if any(not math.isfinite(value) or value < CTRL_LOW or value > CTRL_HIGH for value in vector):
                raise ValueError("each control must be inside the actuator ctrlrange -1.0 .. 1.0")
            out.append(vector)
        return out
