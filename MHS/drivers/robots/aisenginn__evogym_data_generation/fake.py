"""Fake backend of the Evogym Walker-v0 driver: a pure Python analytic stand-in.

Why a fake: the acceptance gate runs on Python 3.14 without gymnasium or evogym installed, and the upstream package
needs Python >=3.7,<3.11 plus a compiled CMake extension (pyproject.toml:40-49, setup.py:61-65).  Package code never
imports the clone.  This module reproduces the public interface of ``evogym.envs.walk:WalkingFlat`` (the class the
driver names as ``native``): a Box action of actuator targets in [0.6, 1.6], a five-tuple ``step`` result, a
two-tuple ``reset`` result and a bounded observation.  It is an F0 analytic model, not the upstream soft-body
simulator: the centre of mass moves at a fixed gain from the mean actuator command, and there are no contacts,
deformation, collisions, rendering or self-collision detection.

Every constant copied from the upstream clone cites the line at commit
91c05ab7a793f86e099c21d377f183c95c9990cd.  Numbers that are test data of this model (the point count, the gain,
the initial centre, the relative point offsets) are marked ``# placeholder`` and are never used as Facts or Limits.
"""

# evogym/envs/walk.py:36: Box(low=0.6, high=1.6, shape=(num_actuators,), dtype=float)
ACTION_LOW = 0.6
ACTION_HIGH = 1.6
# evogym/envs/walk.py:37: Box(low=-100.0, high=100.0, shape=(2 + num_robot_points,), dtype=float)
OBSERVATION_BOUND = 100.0
# evogym/envs/base.py:384: VOXEL_SIZE = 0.1
VOXEL_SIZE = 0.1
# evogym/envs/walk.py:67: the goal is com_x > 99 * VOXEL_SIZE
GOAL_X = 99 * VOXEL_SIZE
# evogym/envs/__init__.py:16-20: Walker-v0 is registered with max_episode_steps=500
MAX_EPISODE_STEPS = 500
# evogym/simulator/SimulatorCPP/Sim.cpp:23: physics_updates_per_step = 30
PHYSICS_UPDATES_PER_STEP = 30
# evogym/simulator/SimulatorCPP/Environment.cpp:190: step_rk4(0.0001)
PHYSICS_DT_S = 0.0001
# The simulator advances 30 updates of 0.0001 s per environment step: 3 ms.
TIMESTEP_S = PHYSICS_UPDATES_PER_STEP * PHYSICS_DT_S
# evogym/envs/walk.py:69: reaching the goal adds 1.0 to the reward
GOAL_BONUS = 1.0

# Test data of this analytic model, not upstream Facts.  A 5x5 robot with one horizontal actuator is only the
# fake's placeholder configuration; the upstream body is an argument of WalkingFlat.__init__.
DEFAULT_BODY = [
    [2, 2, 2, 2, 2],
    [2, 2, 2, 2, 2],
    [2, 2, 3, 2, 2],
    [2, 2, 2, 2, 2],
    [2, 2, 2, 2, 2],
]  # placeholder
ACTUATOR_TYPES = (3, 4)  # evogym/utils.py:8-15: H_ACT is 3 and V_ACT is 4
# The simulated object's point count comes from the compiled simulator and the robot body.  The fake always uses
# four material points around the centre of mass.
POINT_COUNT = 4  # placeholder
POINT_OFFSETS = [(-0.10, -0.05), (0.10, -0.05), (-0.10, 0.05), (0.10, 0.05)]  # placeholder
# One unit of mean actuator command above 1.0 gives this speed in m/s in the fake.
SPEED_GAIN = 12.0  # placeholder


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``)."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float64"  # walk.py:36-37 uses dtype=float

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(self.low[i] <= float(value[i]) <= self.high[i] for i in range(len(self.low)))


def _clean_body(body):
    """Return the body as a list of rows; ``None`` uses the package's placeholder robot."""
    if body is None:
        return [list(row) for row in DEFAULT_BODY]
    rows = [list(row) for row in body]
    if not rows or not rows[0]:
        raise ValueError("body must be a non-empty two-dimensional voxel array")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("body rows must all have the same length")
    return rows


def _actuator_count(body):
    return sum(1 for row in body for cell in row if int(cell) in ACTUATOR_TYPES)


class FakeWalkerEnv:
    """An analytic Walker-v0 without the compiled simulator.

    Public members are the ones ``WalkingFlat`` has (``reset``, ``step``, ``close``; gate G7).  ``action_space`` and
    ``observation_space`` carry the upstream bounds; the actuator count is the number of actuator voxels in the body
    (walk.py:33), while the observation's point count is a placeholder because it comes from the compiled simulator.
    """

    def __init__(self, body=None, connections=None, render_mode=None, render_options=None):
        del connections, render_options
        if render_mode is not None:
            raise ValueError("the fake Walker cannot render; use render_mode=None")
        self._body = _clean_body(body)
        count = _actuator_count(self._body)
        if count == 0:
            raise ValueError("body must contain at least one actuator voxel")
        self.action_space = Box([ACTION_LOW] * count, [ACTION_HIGH] * count, (count,))
        size = 2 + 2 * POINT_COUNT
        self.observation_space = Box([-OBSERVATION_BOUND] * size, [OBSERVATION_BOUND] * size, (size,))
        self._center_x = 0.0  # placeholder
        self._velocity = [0.0, 0.0]  # placeholder
        self._tick = 0
        self._closed = False

    def _observation(self):
        # walk.py:51-54: get_vel_com_obs (2 values) concatenated with get_relative_pos_obs (2 per object point).
        values = [self._velocity[0], self._velocity[1]]
        # base.py:260-262 flattens the two coordinate rows, not a list of (x, y) pairs.
        values.extend(dx for dx, _dy in POINT_OFFSETS)
        values.extend(dy for _dx, dy in POINT_OFFSETS)
        return values

    def reset(self, seed=None, options=None):
        """``WalkingFlat.reset`` (walk.py:74-84): reset the world and return (observation, info).

        The upstream ``EvoGymBase.reset`` ignores both ``seed`` and ``options`` (base.py:65-69), so this fake does
        too; a seed accepted by the bridge does not change the initial state or the trajectory.
        """
        del seed, options
        self._center_x = 0.0  # placeholder
        self._velocity = [0.0, 0.0]  # placeholder
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        """One environment step: clip the action (base.py:54-57), move, reward the x displacement (walk.py:56-72)."""
        if self._closed:
            raise RuntimeError("the fake Walker environment is closed")
        values = list(action)
        if len(values) != len(self.action_space.low):
            raise ValueError("action must contain one value per actuator")
        # base.py:55: each actuator target is clipped to [0.6, 1.6] before it reaches the simulator.  The bridge
        # refuses an out-of-space action before this method; the clip preserves the upstream method's behavior for
        # a direct caller.
        clipped = [min(max(float(value), ACTION_LOW), ACTION_HIGH) for value in values]
        mean = sum(clipped) / len(clipped)
        old_center = self._center_x
        self._velocity = [SPEED_GAIN * (mean - 1.0), 0.0]  # placeholder model
        self._center_x = old_center + self._velocity[0] * TIMESTEP_S
        reward = self._center_x - old_center
        terminated = self._center_x > GOAL_X  # walk.py:67-69
        if terminated:
            reward += GOAL_BONUS
        self._tick += 1
        # gymnasium.make adds a TimeLimit of 500 steps (evogym/envs/__init__.py:19); the class itself returns
        # truncated False (walk.py:72), so the fake applies the wrapper limit here.
        truncated = (not terminated) and self._tick >= MAX_EPISODE_STEPS
        return self._observation(), reward, terminated, truncated, {}

    def close(self):
        self._closed = True
