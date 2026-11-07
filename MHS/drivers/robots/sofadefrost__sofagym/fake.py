"""Fake backend of the SofaGym driver: a pure Python stand-in for ``sofagym.envs.Trunk.TrunkEnv``.

Why a fake: the upstream environment needs a SOFA v23.06 installation with SofaPython3 and the SoftRobots plugins
(README.md:12-20), and package code never imports the clone, so the acceptance gate runs this module instead of
``gym.make("trunk-v0")``.  The public members are the ones ``TrunkEnv`` serves through its wrapped ``AbstractEnv``
(``reset`` at TrunkEnv.py:87-101, ``step`` and ``close`` delegated by the ``__getattr__`` at TrunkEnv.py:82-85), and the
two spaces match the upstream declaration: ``action_space`` is ``Discrete(nb_actions)`` with 16 actions
(TrunkEnv.py:54 and :72) and ``observation_space`` is a 66-element ``Box`` from -1 to 1 (TrunkEnv.py:32 and :75-77).

What this models, from the clone:

* the action/cable mapping of ``action_to_command`` (TrunkToolbox.py:331-378): actions 0-7 pull cables 0-7 by +1 and
  actions 8-15 by -1, anything else is an error;
* the geometry of the cable points (TrunkScene.py:72-95): four large cables of 21 points around the trunk axis, built
  with the same length 195 and pull points at distance 10;
* the observation of ``getState`` (TrunkToolbox.py:204-235): the four large cables' 21 points averaged over the four
  cables, every coordinate rounded to 3 decimals and divided by 4, then the goal position, 66 values in all;
* the reward and done rule of ``getReward`` (TrunkToolbox.py:77-82 and :238-257), with the tip being the mean of the
  last points of the first four cables (TrunkToolbox.py:103-121).

What this is not: the SOFA physics.  The cable deformation is a placeholder kinematic model (a lateral offset
proportional to the cable displacement, applied to a shared trunk centreline); the clone solves a TetrahedronFEM
deformation with CableConstraints (TrunkScene.py:66-67 and :98-100).  The goal is drawn with Python's
``random.Random``; upstream draws it with gym's ``np_random`` (AbstractEnv.py:228-234).  The fake returns the clone's
return shapes: ``reset`` returns the observation and ``step`` returns the four-tuple ``obs, reward, done, info``
(TrunkEnv.py:87-101, AbstractEnv.py:324-367); the bridge accepts both.

Nothing here talks to a device.
"""

import math
import random

# TrunkScene.py:72-74: the trunk is 195 long, with cables at distance 10 and 2 from the axis.
LENGTH1 = 10.0
LENGTH2 = 2.0
LENGTH_TRUNK = 195.0
_NORM = math.sqrt((LENGTH2 - LENGTH1) ** 2 + LENGTH_TRUNK ** 2)
DIRECTION_Y = (LENGTH2 - LENGTH1) / _NORM                  # TrunkScene.py:77-78
DIRECTION_Z = LENGTH_TRUNK / _NORM

# TrunkEnv.py:54 and :32: nb_actions 16 and dim_state 66.
NB_ACTIONS = 16
DIM_STATE = 66
# TrunkEnv.py:38: the two goals of goalList.
GOALS = ((40.0, 40.0, 100.0), (-10.0, 20.0, 80.0))

# TrunkScene.py:80-123: four large cables (21 points) and four small cables (10 points); the state reads the first four.
LARGE_CABLES = 4
CABLES = 8
POINTS = 21
# TrunkScene.py:76: the pull points of the four radial cable families.
PULL_POINT = ((0.0, LENGTH1, 0.0), (-LENGTH1, 0.0, 0.0), (0.0, -LENGTH1, 0.0), (LENGTH1, 0.0, 0.0))
PULL_DIRECTIONS = ((0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0))
# TrunkScene.py:98-100 and :119-121: maxPositiveDisp is 70 for the large cables and 40 for the small ones.
MAX_DISP = (70.0, 70.0, 70.0, 70.0, 40.0, 40.0, 40.0, 40.0)

# placeholder: lateral tip displacement, in clone coordinates, of one cable direction at full displacement.  The
# clone's deformation is computed by TetrahedronFEM and is not reproduced here.
BEND = 60.0


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n

    def sample(self):
        return self.start


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _action_to_command(action):
    """``TrunkToolbox.action_to_command`` (TrunkToolbox.py:331-378): cable and cable displacement of one action."""
    action = int(action)
    if 0 <= action < 8:
        return action, 1.0
    if 8 <= action < 16:
        return action - 8, -1.0
    raise NotImplementedError("Action must be in range 0 - 15")


class FakeTrunkEnv:
    """``TrunkEnv`` without SOFA: ``reset``, ``step`` and ``close`` answer the bridge."""

    def __init__(self, **_options):
        # TrunkEnv.py:72 and :75-77: Discrete(nb_actions) and Box(-1, 1, dim_state).
        self.action_space = Discrete(NB_ACTIONS)
        self.observation_space = Box([-1.0] * DIM_STATE, [1.0] * DIM_STATE)
        # TrunkEnv.py:53: the clone keeps the timestep in config["dt"], not as an attribute of the environment class,
        # so the driver's fidelity declares the per-step 50 ms instead of letting the bridge derive 0.
        self._rng = random.Random()
        self._z = self._point_z()
        self._base = self._base_centreline()
        self._displacement = [0.0] * CABLES
        self._prev_distance = None
        self._timer = 0
        self._closed = False
        self._goal = list(self._rng.choice(GOALS))          # TrunkEnv.py:69-70 draws one goal at construction

    @staticmethod
    def _point_z():
        """The 21 point heights of a cable: pull point at 0, then the 20 points of TrunkScene.py:87-92."""
        heights = [0.0]
        for k in range(0, 20, 2):
            heights.append(DIRECTION_Z * 17.5 * (k / 2) + 21.0)      # TrunkScene.py:89
            heights.append(DIRECTION_Z * 17.5 * (k / 2) + 27.0)      # TrunkScene.py:91
        return heights

    @staticmethod
    def _cable_point(index, point):
        """The ``point``-th position of large cable ``index`` from the scene's own construction (TrunkScene.py:83-95)."""
        if point == 0:
            return list(PULL_POINT[index])
        j = point - 1
        m = j // 2
        y = DIRECTION_Y * 17.5 * m + LENGTH1                        # TrunkScene.py:89/91
        z = DIRECTION_Z * 17.5 * m + (21.0 if j % 2 == 0 else 27.0)
        theta = 1.57 * index                                        # TrunkScene.py:84
        # rotation of (0, y, z) around z by theta: x' = -y sin(theta), y' = y cos(theta)
        return [-y * math.sin(theta), y * math.cos(theta), z]

    def _base_centreline(self):
        """The mean of the four large cables' points, before any cable displacement (TrunkToolbox.py:219-228)."""
        out = []
        for point in range(POINTS):
            x = y = z = 0.0
            for index in range(LARGE_CABLES):
                px, py, pz = self._cable_point(index, point)
                x += px / LARGE_CABLES
                y += py / LARGE_CABLES
                z += pz / LARGE_CABLES
            out.append((x, y, z))
        return out

    def _offset(self):
        """Placeholder kinematic bend: the sum of the cable pulls, one contribution per radial direction."""
        x = y = 0.0
        for index in range(CABLES):
            tension = self._displacement[index] / MAX_DISP[index]
            dx, dy = PULL_DIRECTIONS[index % len(PULL_DIRECTIONS)]
            x += dx * tension * BEND / len(PULL_DIRECTIONS)
            y += dy * tension * BEND / len(PULL_DIRECTIONS)
        return x, y

    def _tip(self):
        """The mean of the last points of the first four cables (TrunkToolbox.py:103-121)."""
        x, y = self._offset()
        base = self._base[-1]
        return [base[0] + x, base[1] + y, base[2]]

    def _state(self):
        """``getState`` (TrunkToolbox.py:204-235): 21 averaged points rounded and divided by 4, then the goal."""
        x, y = self._offset()
        last = self._z[-1]
        values = []
        for point in range(POINTS):
            profile = (self._z[point] / last) ** 2 if last else 0.0
            base = self._base[point]
            values.extend((round(base[0] + x * profile, 3) / 4.0,
                           round(base[1] + y * profile, 3) / 4.0,
                           round(base[2], 3) / 4.0))
        return values + list(self._goal)

    def _reward(self):
        """``getReward`` (TrunkToolbox.py:77-82): the improvement of the tip-to-goal distance, rooted and capped."""
        cost = math.dist(self._tip(), self._goal)
        if self._prev_distance is None or self._prev_distance <= 0.0:
            reward = 0.0
        else:
            reward = max((self._prev_distance - cost) / self._prev_distance, 0.0)
        self._prev_distance = cost
        return min(math.sqrt(reward), 1.0), cost

    def reset(self, seed=None, options=None):
        """A new episode: the cable displacements are zero and the goal is drawn again (TrunkEnv.py:87-101)."""
        if options:
            raise ValueError("TrunkEnv.reset takes no options")
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._closed = False
        self._displacement = [0.0] * CABLES
        self._timer = 0
        self._goal = list(self._rng.choice(GOALS))              # AbstractEnv.py:228-234
        self._prev_distance = math.dist(self._tip(), self._goal)
        return self._state()

    def step(self, action):
        """One environment step; the fake returns the clone's four-tuple (AbstractEnv.py:324-367)."""
        if self._goal is None:
            raise RuntimeError("reset() must be called before step()")
        cable, displacement = _action_to_command(action)        # TrunkToolbox.py:277-278
        value = self._displacement[cable] + displacement        # TrunkToolbox.py:296
        # placeholder: the CableConstraint's maxPositiveDisp bounds the pull; the clone reports it at TrunkScene.py:99.
        self._displacement[cable] = min(max(value, 0.0), MAX_DISP[cable])
        self._timer += 1                                        # AbstractEnv.py:360
        observation = self._state()
        reward, cost = self._reward()
        done = cost <= 1.0                                      # TrunkToolbox.py:254-255
        return observation, reward, done, {}

    def close(self):
        """``AbstractEnv.close`` closes the viewer; the fake drops its state."""
        self._goal = None
        self._closed = True
