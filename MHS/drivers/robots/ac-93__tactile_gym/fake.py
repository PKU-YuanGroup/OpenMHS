"""Fake backend of the tactile_gym driver: a pure Python stand-in for ``edge_follow-v0``.

Why a fake: the upstream environment imports ``pybullet``, ``pybullet_utils``, ``opencv``, ``numpy`` and
``opensimplex`` (``tactile_gym/rl_envs/base_tactile_env.py:1-7``), none of which the acceptance gate installs, and
package code never imports the clone.  This module implements the public surface the ``GymnasiumDriver`` bridge uses
(``reset``, ``seed``, ``step``, ``close`` and the two spaces; gate G7 checks these names against
``EdgeFollowEnv``) with a 2-D kinematic model of the task instead of PyBullet.

Every constant and rule below cites the line of the clone at commit 28417ebaf52ac325200c4fbd351cd13c6a466f7d.  The
space classes duck-type ``gym.spaces.Box`` and ``gym.spaces.Dict`` (the bridge reads ``low``, ``high``, ``shape``,
``dtype`` and ``spaces``); no gym or numpy is needed.

What this is not, all disclosed in the fidelity ``gaps`` of the driver:

* no PyBullet rigid-body dynamics, robot arm, IK, contacts or tactile sensor;
* the edge angle comes from Python's ``random.Random``, upstream uses numpy's generator (``:240``), so one seed does
  not give the same trajectory on both;
* only the oracle observation is returned; the tactile and visual image modes are not modelled.

Nothing here talks to a device.
"""

import math
import random

# tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:140
ACTION_MIN, ACTION_MAX = -0.25, 0.25
# edge_follow_env.py:25 (the constructor's default episode length)
MAX_STEPS = 250
# edge_follow_env.py:67
TERMINATION_DIST = 0.01
# edge_follow_env.py:33-37: one control step is 1/10 s of simulated time; each velocity action is repeated
# floor(0.1 / (1/240)) = 24 physics steps inside the upstream robot.
CONTROL_RATE = 1.0 / 10.0
# edge_follow_env.py:157: the velocity limit the normalised action is rescaled to
MAX_POS_VEL = 0.01
# edge_follow_env.py:208-216 (mg400 branch) and :90-95 (tactip)
EDGE_LEN = 0.105
EDGE_HEIGHT = 0.035
EMBED_DIST = 0.0035
# edge_follow_env.py:440-451
W_GOAL, W_EDGE, W_YAW = 1.0, 10.0, 1.0
# edge_follow_env.py:454-475: tcp position (3) + tcp linear velocity (3) + goal position (3) + edge angle (1)
OBS_DIM = 10


class Box:
    """Duck-typed ``gym.spaces.Box``: a flat lower and upper bound per element."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping from a key to a space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _flat(values):
    out = []
    for value in values:
        if isinstance(value, (list, tuple)):
            out.extend(_flat(value))
        else:
            out.append(float(value))
    return out


class FakeEdgeFollowEnv:
    """``edge_follow-v0`` without PyBullet: a 2-D edge, a goal at its end and a kinematic TCP."""

    def __init__(self, **options):
        # ``options`` are the endpoint's backend options; the fake needs none and keeps no device connection.
        self._max_steps = MAX_STEPS
        self.action_space = Box([ACTION_MIN] * 2, [ACTION_MAX] * 2, shape=(2,), dtype="float32")
        high = [math.inf] * OBS_DIM
        self.observation_space = Dict({"oracle": Box([-value for value in high], high, shape=(OBS_DIM,),
                                                       dtype="float32")})
        self._rng = random.Random()
        self._seed = None
        self._closed = False
        self._edge_ang = 0.0
        self._goal_pos = [0.0, 0.0, 0.0]
        self._tcp_pos = [0.0, 0.0, EMBED_DIST]
        self._tcp_vel = [0.0, 0.0, 0.0]  # placeholder: the arm is at rest at the reset pose
        self._env_step_counter = 0
        self.reset()

    # -- upstream surface ------------------------------------------------------
    def seed(self, seed=None):
        """Set the RNG (upstream delegates to ``gym.utils.seeding.np_random``, ``base_tactile_env.py:61-64``)."""
        self._seed = seed
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        """Start an episode: draw the edge angle and put the TCP at the reset pose (``:311-336``)."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._env_step_counter = 0
        self._edge_ang = self._rng.uniform(-math.pi, math.pi)  # :240
        self._goal_pos = [
            EDGE_LEN * math.cos(self._edge_ang),
            EDGE_LEN * math.sin(self._edge_ang),
            0.0,
        ]
        self._tcp_pos = [0.0, 0.0, EMBED_DIST]  # :305, in the work frame
        self._tcp_vel = [0.0, 0.0, 0.0]
        return {"oracle": self._observation()}

    def step(self, action):
        """Advance one control interval; return ``(observation, reward, done, info)`` (``:166-185``)."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = _flat(action)
        if len(values) != 2:
            raise ValueError(f"the xy action has 2 values, got {len(values)}")
        # ``scale_actions`` clips the normalised action and rescales it to the velocity limit (``:146-164``);
        # one control step applies that velocity for CONTROL_RATE seconds.
        values = [min(max(value, ACTION_MIN), ACTION_MAX) for value in values]
        self._tcp_vel = [values[0] / ACTION_MAX * MAX_POS_VEL,
                         values[1] / ACTION_MAX * MAX_POS_VEL,
                         0.0]
        self._tcp_pos[0] += self._tcp_vel[0] * CONTROL_RATE
        self._tcp_pos[1] += self._tcp_vel[1] * CONTROL_RATE
        self._env_step_counter += 1
        reward = self._dense_reward()
        done = self._termination()
        return {"oracle": self._observation()}, reward, done, {}

    def close(self):
        """Drop the modelled state (upstream disconnects PyBullet, ``base_tactile_env.py:69-74``)."""
        self._closed = True

    # -- task model ------------------------------------------------------------
    def _observation(self):
        return [*self._tcp_pos, *self._tcp_vel, *self._goal_pos, self._edge_ang]

    def _goal_distance(self):
        return math.hypot(self._tcp_pos[0] - self._goal_pos[0], self._tcp_pos[1] - self._goal_pos[1])

    def _edge_distance(self):
        # perpendicular distance from the TCP to the edge through the origin, in the xy plane (``:403-415``)
        dx, dy = math.cos(self._edge_ang), math.sin(self._edge_ang)
        return abs(dx * self._tcp_pos[1] - dy * self._tcp_pos[0])

    def _dense_reward(self):
        # ``yaw_dist`` is hard-coded to 0 upstream (``:447``), so the yaw term does not contribute.
        return -((W_GOAL * self._goal_distance()) + (W_EDGE * self._edge_distance())
                 + (W_YAW * 0.0))

    def _termination(self):
        # ``:418-428``: terminate at the goal or at the episode length.
        return self._goal_distance() < TERMINATION_DIST or self._env_step_counter >= self._max_steps
