"""Fake backend of the gym_fastsim driver: a pure Python kinematic stand-in for ``SimpleNavEnv``.

Why a fake: the acceptance gate runs without gym and pyfastsim, the upstream environment needs numpy and a compiled
libfastsim binding (``nav_env.py:5,14,75``), and package code never imports the clone.  This module implements the
members of ``gym_fastsim.simple_nav:SimpleNavEnv`` that the driver and the bridge touch -- ``reset``, ``step``,
``close``, ``get_robot_pos``, ``get_laserranges`` and ``get_all_sensors`` (gate G7) -- plus duck-typed
``gym.spaces.Box`` objects for the action and observation spaces (the bridge reads ``low``, ``high`` and ``shape``).

The constants that the clone states are cited; everything invented for the stand-in is marked ``# placeholder`` and is
test data, never a Fact or a Limit.  What this is not (also in the driver's fidelity ``gaps``):

* the upstream ``step`` calls ``libfastsim``'s ``robot.move`` (``nav_env.py:193-194``); the fake integrates a
  differential-drive placeholder and does not model walls, contacts, wheel slip or sensor geometry;
* the fake returns the same number of laser readings as kitchen-v1 (ten), but their values are placeholders;
* the observation space declares ``n_lasers + 2 + n_lightsensors`` bounds (``nav_env.py:118-119``) while the upstream
  ``get_all_sensors`` returns only the laser ranges (``nav_env.py:182-184``); the fake mirrors that mismatch;
* ``reset`` restores the fixed pose and ignores the seed, as the upstream reset does (``nav_env.py:217-223``).

Nothing here talks to a device.
"""

import math

# fastsim/gym_fastsim/simple_nav/nav_env.py:86 (SimpleNavEnv.__init__)
MAX_VEL = 4.0
# fastsim/gym_fastsim/assets/kitchen_lasers.xml:10-20: ten lasers, each with range="1"
N_LASERS = 10
MAX_SENSOR_RANGE = 1.0
# fastsim/gym_fastsim/assets/kitchen_lasers.xml:6-7
INIT_POS = [2.0, 4.0, 0.0]
GOAL_POS = [0.5, 0.5]
GOAL_DIAMETER = 0.2
# Placeholder integration constants of the stand-in (test data; the clone states no interval or wheelbase).
STEP_S = 0.1                                    # placeholder
WHEELBASE = 1.0                                 # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        if shape is None:
            low = [low] if not isinstance(low, (list, tuple)) else list(low)
            high = [high] if not isinstance(high, (list, tuple)) else list(high)
            shape = (len(low),)
        else:
            count = 1
            for size in shape:
                count *= int(size)
            low = [low] * count if not isinstance(low, (list, tuple)) else list(low)
            high = [high] * count if not isinstance(high, (list, tuple)) else list(high)
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(int(size) for size in shape)
        self.dtype = dtype

    def contains(self, value):
        return (isinstance(value, (list, tuple)) and len(value) == len(self.low)
                and all(self.low[i] <= value[i] <= self.high[i] for i in range(len(self.low))))


def _clip(value, low, high):
    return max(low, min(high, float(value)))


class FakeSimpleNavEnv:
    """The kitchen-v1 interface with placeholder lasers and a placeholder differential-drive integrator."""

    def __init__(self, xml_env=None, reward_func="binary_goalbased", render=False, light_sensor_range=200.,
                 light_sensor_mode="realistic"):
        self.xml_env = xml_env                                  # accepted for the upstream constructor shape
        self.reward_func_name = reward_func
        self.render_requested = render
        self.light_sensor_range = light_sensor_range
        self.light_sensor_mode = light_sensor_mode
        self.maxVel = MAX_VEL                                    # nav_env.py:86
        self.maxSensorRange = MAX_SENSOR_RANGE                   # nav_env.py:93 for the kitchen-v1 lasers
        self.maxLightSensorRange = 0.                             # no light sensor in kitchen_lasers.xml
        self.n_lasers = N_LASERS
        # nav_env.py:120-121: Box(low=-maxVel, high=maxVel, shape=(2,), dtype=np.float32)
        self.action_space = Box(-self.maxVel, self.maxVel, shape=(2,))
        # nav_env.py:118-119: n_lasers + 2 + n_lightsensors bounds (the fake mirrors the upstream mismatch)
        self.observation_space = Box(
            low=[0.0] * self.n_lasers + [0.0] * 2,
            high=[self.maxSensorRange] * self.n_lasers + [1.0] * 2,
        )
        self.initPos = list(INIT_POS)
        self.current_pos = list(INIT_POS)
        self.old_pos = list(INIT_POS)
        self.goalPos = list(GOAL_POS)
        self.goalRadius = GOAL_DIAMETER / 2.                     # nav_env.py:114-116
        self.v1_motor_order = 0.
        self.v2_motor_order = 0.
        self._closed = False

    def get_robot_pos(self):
        """nav_env.py:139-141: the robot pose as [x, y, theta]."""
        return list(self.current_pos)

    def get_laserranges(self):
        """Ten range-1 readings; the values are placeholders, not libfastsim raycasts."""
        x, y, theta = self.current_pos
        out = []
        for index in range(self.n_lasers):
            raw = MAX_SENSOR_RANGE * (0.5 + 0.5 * math.sin(x + y + theta + index))   # placeholder
            out.append(_clip(raw, 0.0, self.maxSensorRange))
        return out

    def get_all_sensors(self):
        """nav_env.py:182-184: only the laser ranges are returned."""
        return self.get_laserranges()

    def reset(self, seed=None, options=None):
        """nav_env.py:217-223: restore the fixed initial pose; upstream takes and consumes no seed."""
        del seed, options                                       # accepted for the Gymnasium bridge; ignored upstream
        self.current_pos = list(self.initPos)
        self.old_pos = list(self.initPos)
        self.v1_motor_order = 0.
        self.v2_motor_order = 0.
        return self.get_all_sensors()

    def step(self, action):
        """nav_env.py:186-212: clip the two wheel orders, move, and return the legacy 4-tuple."""
        [v1, v2] = action
        self.v1_motor_order = _clip(v1, -self.maxVel, self.maxVel)      # nav_env.py:190-191
        self.v2_motor_order = _clip(v2, -self.maxVel, self.maxVel)
        distance = (self.v1_motor_order + self.v2_motor_order) / 2.0
        turn = (self.v2_motor_order - self.v1_motor_order) / WHEELBASE  # placeholder
        x, y, theta = self.current_pos
        self.old_pos = list(self.current_pos)
        self.current_pos = [
            x + distance * math.cos(theta) * STEP_S,                    # placeholder
            y + distance * math.sin(theta) * STEP_S,                    # placeholder
            theta + turn * STEP_S,                                      # placeholder
        ]
        sensors = self.get_all_sensors()
        reward = self._get_reward()
        dist_obj = self._distance(self.current_pos, self.goalPos)
        terminated = dist_obj <= GOAL_DIAMETER                         # nav_env.py:209-210
        info = {"dist_obj": dist_obj, "robot_pos": list(self.current_pos)}   # nav_env.py:212
        return sensors, reward, terminated, info

    def _get_reward(self):
        """nav_env.py:33-39: binary goal reward with goalRadius = half the goal diameter."""
        return 1.0 if self._distance(self.current_pos, self.goalPos) <= self.goalRadius else 0.0

    @staticmethod
    def _distance(left, right):
        return math.sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2)

    def close(self):
        """nav_env.py:230-234: drop the robot and the map."""
        self._closed = True
