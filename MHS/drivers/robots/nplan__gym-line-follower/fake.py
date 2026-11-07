"""Fake backend of the gym-line-follower driver: a pure Python kinematic stand-in for ``LineFollowerEnv``.

Why a fake: the gate does not have ``gym``, ``pybullet``, ``opencv-python`` or ``shapely``, the upstream
package is not installed (``setup.py:5-7``), and package code never imports the clone.  This fake is pure
Python and does not use numpy.  This module models the upstream interface
(``reset``, ``step``, ``close``, ``seed``, ``action_space``, ``observation_space``) and the parts of
``gym_line_follower/envs/line_follower_env.py`` that define the contract: the action is two motor powers in
[-1, 1] (line 80), the default observation is 8 line points as x, y pairs (lines 89-92), a step scales the
action by the power limit (lines 171-172) and advances sub_steps simulation steps (lines 179-181), and the
episode ends on the track, on a track error above ``max_track_err`` or on the step limit (lines 220-234).

What this is not: the upstream pybullet environment.  The fake is a kinematic unicycle on a fixed circular
track; it has no rigid-body dynamics, contacts, wheel slip, motor torque or camera rendering.  Its RNG is
Python's ``random.Random``, while upstream uses ``gym.utils.seeding`` and a randomised Bezier track.  All
fidelity gaps are listed in the driver's ``fidelity`` block, and no number here is a device bound: the
numbers are test data (marked ``# placeholder``) unless they are a cited upstream constructor default.
"""

import math
import random

# The observation window of gym_line_follower/envs/line_follower_env.py:89-92 (x in [0.0, 0.3], y in [-0.2, 0.2]).
OBS_X_MIN, OBS_X_MAX = 0.0, 0.3
OBS_Y_MIN, OBS_Y_MAX = -0.2, 0.2

# Test-data geometry of the fake track and its lookahead points; none of these is a device bound.
TRACK_RADIUS = 1.0                              # placeholder
START_LATERAL_RANGE = 0.02                      # placeholder
START_YAW_RANGE = 0.2                           # placeholder (the upstream default of line 147)
LOOKAHEAD = (0.06, 0.10, 0.14, 0.18, 0.22, 0.25, 0.28, 0.30)  # placeholder
MAX_SPEED = 0.5                                 # placeholder, m/s at full power
MAX_TURN_RATE = 1.5                             # placeholder, rad/s at full differential power
CHECKPOINTS = 500                               # placeholder; upstream default on line 143
MAX_TRACK_ERROR = 0.3                           # placeholder; upstream default on line 32
POWER_LIMIT = 0.4                               # placeholder; upstream default on line 32
SUB_STEPS = 10                                  # placeholder; upstream default on line 31
SIM_TIME_STEP = 1.0 / 250.0                     # placeholder; upstream default on line 31
TIME_PENALTY = 0.2                              # placeholder; upstream value on line 218
FAILURE_REWARD = -100.0                         # placeholder; upstream value on line 225/229
CHECKPOINT_REWARD = 1000.0 / CHECKPOINTS        # placeholder; upstream formula on line 212


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


def _wrap_angle(angle):
    """Map an angle to (-pi, pi] (a real angle difference, not a wire format)."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle <= -math.pi:
        angle += 2.0 * math.pi
    return angle


def _interpolate(points, count):
    """Pick ``count`` points at equal arc length along a polyline (the upstream interpolate_points role)."""
    if count <= 0:
        return []
    if len(points) == 1:
        return [points[0]] * count
    lengths = [0.0]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
    total = lengths[-1]
    if total <= 0.0:
        return [points[0]] * count
    out = []
    for index in range(count):
        target = total * index / (count - 1) if count > 1 else 0.0
        segment = 1
        while segment < len(lengths) and lengths[segment] < target:
            segment += 1
        if segment >= len(lengths):
            out.append(points[-1])
            continue
        run = lengths[segment] - lengths[segment - 1]
        fraction = 0.0 if run <= 0.0 else (target - lengths[segment - 1]) / run
        left, right = points[segment - 1], points[segment]
        out.append((left[0] + fraction * (right[0] - left[0]),
                    left[1] + fraction * (right[1] - left[1])))
    return out


class FakeLineFollowerEnv:
    """A kinematic line follower with the public members of ``LineFollowerEnv`` (gate G7).

    ``reset(seed, options)`` and ``step(action)`` follow the gymnasium call shapes so the family bridge can
    drive it; upstream's ``reset`` takes no seed and its ``step`` returns a four-tuple, which this fake also
    does.  Nothing here opens a file, a socket or a device.
    """

    def __init__(self, gui=False, nb_cam_pts=8, sub_steps=SUB_STEPS, sim_time_step=SIM_TIME_STEP,
                 max_track_err=MAX_TRACK_ERROR, power_limit=POWER_LIMIT, max_time=60, config=None,
                 randomize=True, obsv_type="points_latch", track=None, track_render_params=None):
        self.gui = gui
        self.nb_cam_pts = int(nb_cam_pts)
        self.sub_steps = int(sub_steps)
        self.sim_time_step = float(sim_time_step)
        self.speed_limit = float(power_limit)
        self.max_track_err = float(max_track_err)
        self.max_time = float(max_time)
        self.max_steps = self.max_time / (self.sim_time_step * self.sub_steps)
        self.randomize = bool(randomize)
        self.obsv_type = str(obsv_type).lower()
        if self.obsv_type not in ("points_visible", "points_latch", "points_latch_bool", "camera"):
            raise ValueError("Observation type '{}' not supported.".format(self.obsv_type))
        if self.obsv_type == "camera":
            raise ValueError("the fake does not render the upstream 240 x 320 x 3 camera image")
        self.config = config
        self.preset_track = track
        self.track_render_params = track_render_params
        self.action_space = Box([-1.0, -1.0], [1.0, 1.0], shape=(2,))
        if self.obsv_type == "points_visible":
            self.observation_space = Box([OBS_X_MIN, OBS_Y_MIN, 0.0] * self.nb_cam_pts,
                                         [OBS_X_MAX, OBS_Y_MAX, 1.0] * self.nb_cam_pts,
                                         shape=(3 * self.nb_cam_pts,))
        elif self.obsv_type == "points_latch_bool":
            self.observation_space = Box([OBS_X_MIN, OBS_Y_MIN] * self.nb_cam_pts + [0.0],
                                         [OBS_X_MAX, OBS_Y_MAX] * self.nb_cam_pts + [1.0],
                                         shape=(2 * self.nb_cam_pts + 1,))
        else:
            self.observation_space = Box([OBS_X_MIN, OBS_Y_MIN] * self.nb_cam_pts,
                                         [OBS_X_MAX, OBS_Y_MAX] * self.nb_cam_pts,
                                         shape=(2 * self.nb_cam_pts,))
        self.np_random = random.Random()
        self.step_counter = 0
        self.observation = [0.0] * len(self.observation_space.low)
        self.position_on_track = 0.0
        self.progress = 0.0
        self.done = False
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self._prev_phi = 0.0
        self._next_checkpoint = 1.0 / CHECKPOINTS
        self._start()

    # -- upstream public surface (LineFollowerEnv) ---------------------------------
    def seed(self, seed=None):
        self.np_random = random.Random(seed)
        return [seed]

    def reset(self, seed=None, options=None):
        if seed is not None:
            self.np_random = random.Random(int(seed))
        if options is not None and not isinstance(options, dict):
            raise ValueError("options must be a mapping")
        self.step_counter = 0
        self.progress = 0.0
        self.position_on_track = 0.0
        self.done = False
        self.observation = [0.0] * len(self.observation_space.low)
        self._start()
        observation = self._observe()
        return observation, {"x": self.x, "y": self.y, "yaw": self.yaw}

    def step(self, action):
        values = [float(item) for item in action]
        if len(values) != 2:
            raise ValueError("the action is two motor powers, got {!r}".format(action))
        left = self.speed_limit * max(-1.0, min(1.0, values[0]))
        right = self.speed_limit * max(-1.0, min(1.0, values[1]))
        speed = 0.5 * (left + right) * MAX_SPEED
        turn = (right - left) * MAX_TURN_RATE
        dt = self.sim_time_step * self.sub_steps
        self.x += speed * math.cos(self.yaw) * dt
        self.y += speed * math.sin(self.yaw) * dt
        self.yaw = _wrap_angle(self.yaw + turn * dt)
        self.step_counter += 1

        phi = math.atan2(self.y, self.x)
        self.position_on_track += TRACK_RADIUS * _wrap_angle(phi - self._prev_phi)
        self._prev_phi = phi
        progress = self.position_on_track / (2.0 * math.pi * TRACK_RADIUS)
        if progress > self.progress:
            self.progress = min(1.0, progress)

        error = abs(math.hypot(self.x, self.y) - TRACK_RADIUS)
        normalized = min(1.0, error / self.max_track_err) if self.max_track_err > 0 else 1.0
        reward = -TIME_PENALTY
        while self._next_checkpoint <= self.progress:
            reward += CHECKPOINT_REWARD * (1.0 - normalized) ** 2
            self._next_checkpoint += 1.0 / CHECKPOINTS

        done = False
        if self.progress >= 1.0:
            done = True
        elif abs(self.position_on_track - self.progress * 2.0 * math.pi * TRACK_RADIUS) > 0.5:
            reward = FAILURE_REWARD
            done = True
        elif error > self.max_track_err:
            reward = FAILURE_REWARD
            done = True
        elif self.step_counter > self.max_steps:
            done = True
        self.done = done
        observation = self._observe()
        info = {"x": self.x, "y": self.y, "yaw": self.yaw}
        return observation, reward, done, info

    def close(self):
        self.done = True
        self.observation = []

    # -- fake internals (not part of the upstream surface) -------------------------
    def _start(self):
        angle = -math.pi / 2.0
        lateral = self.np_random.uniform(-START_LATERAL_RANGE, START_LATERAL_RANGE) if self.randomize else 0.0
        offset = self.np_random.uniform(-START_YAW_RANGE, START_YAW_RANGE) if self.randomize else 0.0
        radius = TRACK_RADIUS + lateral
        self.x = radius * math.cos(angle)
        self.y = radius * math.sin(angle)
        self.yaw = _wrap_angle(angle + math.pi / 2.0 + offset)
        self._prev_phi = angle
        self._next_checkpoint = 1.0 / CHECKPOINTS

    def _observe(self):
        """Eight line points in the robot frame, interpolated like the upstream points_latch observation."""
        visible = []
        phi = math.atan2(self.y, self.x)
        cos_yaw, sin_yaw = math.cos(self.yaw), math.sin(self.yaw)
        for distance in LOOKAHEAD:
            angle = phi + distance / TRACK_RADIUS
            px = TRACK_RADIUS * math.cos(angle)
            py = TRACK_RADIUS * math.sin(angle)
            dx, dy = px - self.x, py - self.y
            local_x = cos_yaw * dx + sin_yaw * dy
            local_y = -sin_yaw * dx + cos_yaw * dy
            if OBS_X_MIN <= local_x <= OBS_X_MAX and OBS_Y_MIN <= local_y <= OBS_Y_MAX:
                visible.append((local_x, local_y))
        if len(visible) < 2:
            return list(self.observation)
        points = _interpolate(visible, self.nb_cam_pts)
        values = []
        for x, y in points:
            values.extend([x, y])
        if self.obsv_type == "points_visible":
            values = []
            for x, y in points:
                values.extend([x, y, 1.0])
        elif self.obsv_type == "points_latch_bool":
            values.append(1.0)
        self.observation = values
        return list(values)
