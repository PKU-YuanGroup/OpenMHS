"""Fake backend of the AUVTracking_v0 driver: an analytic stand-in for ``TargetTrackingBase``.

Why a fake: the gate never imports the upstream clone, and the real environment needs HoloOcean 2.0.0, the
HoloOcean Ocean packages and the scenario files copied into the HoloOcean worlds directory (README.md:48-53), none
of which is installed here.  This module implements the public environment surface of
``auv_env.envs.base:TargetTrackingBase`` (``action_space``, ``observation_space``, ``reset``, ``step`` and
``seed``; gate G7) with the shipped ``AUVTracking_v0`` configuration: the PID 2-element action Box, the 6-element
state observation, the ``WorldAuvV0`` reward shape and its 100-step mean-reward termination rule.

Every constant copied from the clone cites its line at the pinned commit
8ff39512f796801aa461fa074f7972e3a4e3a81f.  Every number invented for the stand-in is marked ``# placeholder``.
What this is not: the upstream environment.  There is no HoloOcean physics, PID/LQR controller, KF belief, ocean
current, sonar, camera or obstacle; the target is static; the covariance value and the poses are analytic
stand-ins; and the upstream reset reseeds numpy from entropy, so a seed does not fix an upstream trajectory.  The
fake honors ``reset(seed)`` for its own repeatability only.  All of this is in the fidelity ``gaps`` of driver.py.
Nothing here talks to a device.
"""

import math
import random

#: The shipped ``configs/envs/v0_config.yml`` values (the file the card's AUVTracking_v0 selects, INIT:31).
NUM_TARGETS = 1                 # configs/envs/v0_config.yml:16
CONTROL_PERIOD_S = 0.2          # configs/envs/v0_config.yml:13
MARGIN = 1.0                    # configs/envs/v0_config.yml:14 (target clearance)
MARGIN2WALL = 1.0               # configs/envs/v0_config.yml:15
SENSOR_R = 4.0                  # configs/envs/v0_config.yml:46
FOV_DEG = 100.0                 # configs/envs/v0_config.yml:47
TARGET_INIT_COV = 50.0          # configs/envs/v0_config.yml:68 (scalar stand-in for the KF covariance)

#: WorldAuvV0's PID action space (world_auv_v0.py:43-48) from the shipped config: index [1] is the PID entry.
ACTION_LOW = [-1.0, -1.0]       # configs/envs/v0_config.yml:80
ACTION_HIGH = [1.0, 1.0]        # configs/envs/v0_config.yml:79
ACTION_SCALE = [1.5, 0.5]       # configs/envs/v0_config.yml:81

#: WorldAuvV0's observation space for one target (world_auv_v0.py:61-67); the obstacle upper bound is sensor_r.
OBS_LOW = [0.0, -math.pi, -50.0, 0.0, 0.0, -math.pi]
OBS_HIGH = [600.0, math.pi, 50.0, 2.0, SENSOR_R, math.pi]

#: WorldAuvV0's reward defaults (configs/envs/v0_config.yml:83-87) and termination rule (world_auv_v0.py:97-103).
REWARD_C_MEAN = 0.2             # configs/envs/v0_config.yml:84
REWARD_C_STD = 0.0              # configs/envs/v0_config.yml:85
REWARD_C_PENALTY = 5.0          # configs/envs/v0_config.yml:86
REWARD_C_SMOOTH = 1.0           # configs/envs/v0_config.yml:87
REWARD_WINDOW = 100             # world_auv_v0.py:26
DONE_AVG_REWARD = -3.5          # world_auv_v0.py:100

#: WorldBase's map setup (base.py:93-99) for the shipped scenario size and bottom corner.
MAP_SIZE = (40.0 - 2 * 0.25, 40.0 - 2 * 0.25)  # configs/envs/v0_config.yml:19 and base.py:93-96
MAP_BOTTOM = (-20.0 + 0.25, -20.0 + 0.25)      # configs/envs/v0_config.yml:20 and base.py:97-99
INIT_MARGIN = 0.25                             # base.py:93

#: placeholder: the analytic stand-in advances one step per tick and integrates with the PID control period.
#: The upstream integrates ticks_per_rl_step HoloOcean ticks at the scenario's sampling period (base.py:78,110-118).
STEP_S = CONTROL_PERIOD_S
#: placeholder: the fake's scalar covariance determinant starts at the configured initial covariance and moves by
#: these amounts; the upstream KF belief update (base.py:595-609) is not modelled.
COV_STEP_OBSERVED = 0.05
COV_STEP_UNOBSERVED = 0.01


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        self.low = list(low) if isinstance(low, (list, tuple)) else [low]
        self.high = list(high) if isinstance(high, (list, tuple)) else [high]
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype


def _wrap(angle):
    """``util.wrap_around``: put an angle in [-pi, pi] (auv_env/util.py:40-47)."""
    while angle >= math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


class FakeAuvTrackingV0:
    """The public environment surface of ``TargetTrackingBase`` for AUVTracking_v0, without HoloOcean or numpy."""

    def __init__(self, **_options):
        self.num_targets = NUM_TARGETS
        self.action_dim = len(ACTION_LOW)                                    # world_auv_v0.py:44
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, shape=(2,))         # world_auv_v0.py:43-48
        self.observation_space = Box(OBS_LOW, OBS_HIGH, shape=(6,))         # world_auv_v0.py:61-67
        self.action_range_scale = list(ACTION_SCALE)                         # world_auv_v0.py:48
        self.config = {"env": {"num_targets": NUM_TARGETS}}                  # the shape TargetTrackingBase reads
        self.state = None
        self.reset_num = 0
        self.has_discovered = [1] * self.num_targets
        self._seed = None
        self._rng = random.Random()
        self._tick = 0
        self._done = False
        self._reward_queue = []
        self._logdet = math.log(TARGET_INIT_COV)                             # placeholder: KF covariance stand-in
        #: placeholder: agent x, y, yaw; the real reset draws them through get_init_pose_random (base.py:454-533).
        self._agent = (0.0, 0.0, 0.0)
        self._target = (1.0, 0.0)                                            # placeholder
        self._observed = 0.0                                                 # placeholder

    # -- Gymnasium surface -------------------------------------------------
    def reset(self, seed=None, **kwargs):
        """Reset the analytic world; ``seed`` is a fake-only repeatability hook (upstream reseeds from entropy)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        else:
            self._rng = random.Random()                                      # base.py:47,463 reseed from entropy
        self.reset_num += 1
        self._tick = 0
        self._done = False
        self._reward_queue = []
        self._logdet = math.log(TARGET_INIT_COV)                             # base.py:420-423 (belief reset)
        # Agent pose: uniform over the map size and yaw in [-pi/2, pi/2] (base.py:465-466).  Placeholder: the
        # upstream rejection loop for obstacles, margins and insight (base.py:467-533) is not modelled.
        x = self._rng.random() * MAP_SIZE[0] + MAP_BOTTOM[0]
        y = self._rng.random() * MAP_SIZE[1] + MAP_BOTTOM[1]
        yaw = self._rng.uniform(-math.pi / 2, math.pi / 2)
        self._agent = (x, y, yaw)
        # Target at 1.0 .. 4.0 m and -pi/5 .. pi/5 around the agent yaw (configs/envs/v0_config.yml:69-70),
        # the insight branch of get_init_pose_random (base.py:477-487).  Placeholder: no obstacle rejection.
        distance = self._rng.uniform(1.0, 4.0)
        bearing = yaw + self._rng.uniform(-math.pi / 5, math.pi / 5)
        self._target = (x + distance * math.cos(bearing), y + distance * math.sin(bearing))
        self.has_discovered = [1] * self.num_targets
        self._observed = self._is_observed()
        self.state = self._observe(update_cov=False)
        return list(self.state), {"reset_info": "yes"}                       # base.py:432-444

    def step(self, action):
        """Apply one PID-scaled action, one analytic interval and the v0 reward/termination rule."""
        if self._done:
            raise RuntimeError("the episode has ended; reset before step")
        if len(action) != self.action_dim:
            raise ValueError("action must have %d elements" % self.action_dim)
        # PID path of WorldBase.step: CmdVel.linear.x and angular.z from the scaled action (base.py:174-179),
        # integrated here by a placeholder kinematic model for one control period.
        speed = float(action[0]) * self.action_range_scale[0]
        yaw_rate = float(action[1]) * self.action_range_scale[1]
        x, y, yaw = self._agent
        x += speed * math.cos(yaw) * STEP_S
        y += speed * math.sin(yaw) * STEP_S
        yaw = _wrap(yaw + yaw_rate * STEP_S)
        self._agent = (x, y, yaw)
        self._tick += 1

        self._observed = self._is_observed()
        observation = self._observe(update_cov=True)
        self.state = observation

        # Collision rule of WorldBase.step (base.py:255-257): in the wall margin, clear of the target, and no
        # obstacle; the fake has no obstacles, so only the wall box and the target clearance remain.
        is_col = not (self._in_bound(x, y)
                      and math.hypot(x - self._target[0], y - self._target[1]) > MARGIN)
        # WorldAuvV0.get_reward (world_auv_v0.py:78-95): r_detcov_mean is -log(det(covariance)) for one target,
        # r_detcov_std is 0 for one target and r_action_smooth is always 0 in the shipped code (world_auv_v0.py:85-88).
        r_detcov_mean = -self._logdet
        r_detcov_std = 0.0
        reward = (REWARD_C_MEAN * r_detcov_mean + REWARD_C_STD * r_detcov_std
                  + REWARD_C_SMOOTH * 0.0)
        if is_col:
            reward = min(0.0, reward) - REWARD_C_PENALTY
        self._reward_queue.append(reward)
        if len(self._reward_queue) > REWARD_WINDOW:
            self._reward_queue.pop(0)
        done = (len(self._reward_queue) == REWARD_WINDOW
                and (sum(self._reward_queue) / REWARD_WINDOW) < DONE_AVG_REWARD)
        self._done = bool(done)
        info = {"mean_nlogdetcov": r_detcov_mean, "std_nlogdetcov": r_detcov_std}   # base.py:271
        return list(observation), float(reward), bool(done), False, info

    def seed(self, seed=None):
        """Upstream forwards the seed to numpy's global generator (base.py:62-63); the reset above reseeds."""
        self._seed = seed
        if seed is not None:
            self._rng.seed(int(seed))

    # -- analytic internals ------------------------------------------------
    def _in_bound(self, x, y):
        """WorldBase.in_bound with the wall margin (base.py:535-543)."""
        return not (x < MAP_BOTTOM[0] + MARGIN2WALL
                    or x > MAP_SIZE[0] + MAP_BOTTOM[0] - MARGIN2WALL
                    or y < MAP_BOTTOM[1] + MARGIN2WALL
                    or y > MAP_SIZE[1] + MAP_BOTTOM[1] - MARGIN2WALL)

    def _is_observed(self):
        """The sight test of WorldBase.observation (base.py:577-593) with no blocking obstacle."""
        x, y, yaw = self._agent
        distance = math.hypot(self._target[0] - x, self._target[1] - y)
        bearing = _wrap(math.atan2(self._target[1] - y, self._target[0] - x) - yaw)
        return (distance <= SENSOR_R and abs(bearing) <= math.radians(FOV_DEG) / 2)

    def _observe(self, update_cov):
        """The six v0 state values (world_auv_v0.py:109-133) with a placeholder covariance update."""
        x, y, yaw = self._agent
        distance = math.hypot(self._target[0] - x, self._target[1] - y)
        bearing = _wrap(math.atan2(self._target[1] - y, self._target[0] - x) - yaw)
        if update_cov:
            if self._observed:
                self._logdet = max(-50.0, self._logdet - COV_STEP_OBSERVED)  # placeholder
            else:
                self._logdet = min(50.0, self._logdet + COV_STEP_UNOBSERVED)  # placeholder
        # No obstacles in the fake: the rangefinder reports sensor_r at angle 0 (world_auv_v0.py:114-118).
        return [distance, bearing, self._logdet, float(bool(self._observed)), SENSOR_R, 0.0]
