"""Fake backend of the Webots-drone driver: a pure-Python kinematic stand-in for ``DroneEnvContinuous``.

Why a fake: the acceptance gate runs without the upstream package (``gym==0.26.0``, numpy, opencv and the Webots
``controller`` binding, setup.py:25-27 and webots_simulation.py:20-21), and package code never imports the clone.  This
module re-implements the parts of ``webots_drone.envs.drone_continuous:DroneEnvContinuous`` the bridge needs: the
22-element vector observation, the four-channel action space, the seeded step length, the episode and no-action limits,
the terminal conditions and a simplified version of the reward.  Every constant and rule below cites the line of the
clone at the pinned commit (24eb199041403d108bc94fac0f522cb33a544c9c).  The public members are the ones the upstream
class has (``reset``, ``step``, ``close``; gate G7), and the two space classes duck-type ``gymnasium.spaces.Box``
(the bridge reads ``low``, ``high``, ``shape`` and ``dtype``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the Webots rigid-body world, contacts, collisions, aerodynamics and the drone controller are replaced by a
  kinematic integration of the commanded attitude with a placeholder attitude-to-speed gain;
* the initial pose, the nine distance-sensor readings and the target position are model data, marked
  ``# placeholder`` below; the target and the flight area use the constructor defaults of the clone;
* the pixel observation configuration (``is_pixels=True``) is not implemented: the fake serves the 22-element vector
  observation the driver declares through ``env_kwargs = {"is_pixels": False}``;
* the reward is the distance/orientation/velocity/elevation composition of ``webots_drone/reward.py`` with the
  distance-sensor penalties left out (the fake's sensors never report an obstacle).

Nothing here talks to a device or to Webots.
"""

import math
import random

# webots_simulation.py:78-87: the Mavic control ranges of WebotsSimulation.get_control_ranges
ACTION_LOW = (-math.pi / 12.0, -math.pi / 12.0, -math.pi, -5.0)
ACTION_HIGH = (math.pi / 12.0, math.pi / 12.0, math.pi, 5.0)

# worlds/forest_fire.wbt:14: basicTimeStep 8 (ms)
BASE_TIMESTEP_MS = 8
BASE_TIMESTEP_S = BASE_TIMESTEP_MS / 1000.0
# drone_continuous.py:43-45: time_limit_seconds=60, max_no_action_seconds=5, frame_skip=125 (1 s)
TIME_LIMIT_S = 60
NO_ACTION_LIMIT_S = 5
FRAME_SKIP = 125
# drone_continuous.py:119-120: the frame interval is frame_skip - 5 to frame_skip + 5
FRAME_MARGIN = 5
# drone_continuous.py:79-82 and preprocessor.py:21-23: seconds2steps(seconds, 1, sim.timestep)
MAX_EPISODE_FRAMES = int(TIME_LIMIT_S * 1000 / (1 * BASE_TIMESTEP_MS))
MAX_NO_ACTION_FRAMES = int(NO_ACTION_LIMIT_S * 1000 / (1 * BASE_TIMESTEP_MS))

# worlds/forest_fire.wbt:33-37: DEF FlightArea size 100 100; webots_simulation.py:89-95 halves it and appends the
# altitude limits of drone_continuous.py:48 ([11, 75]).
FLIGHT_AREA = ((-50.0, -50.0, 11.0), (50.0, 50.0, 75.0))
ALTITUDE_LIMITS = (11.0, 75.0)
# drone_continuous.py:47: the default initial altitude
INITIAL_ALTITUDE = 25.0
# drone_continuous.py:50: the default target dimensions (height, radius)
TARGET_DIMENSION = (7.0, 3.5)
# drone_continuous.py:46: the default goal threshold
GOAL_THRESHOLD = 5.0
# webots_drone/utils.py:21-30: risk distance = 4 * fire height + fire radius; drone_continuous.py:218-222 adds half
# the goal threshold.
RISK_DISTANCE = 4.0 * TARGET_DIMENSION[0] + TARGET_DIMENSION[1]
GOAL_DISTANCE = RISK_DISTANCE + GOAL_THRESHOLD / 2.0
# drone_continuous.py:93: max_distance is the distance between the two flight-area corners
MAX_DISTANCE = round(math.dist(FLIGHT_AREA[0], FLIGHT_AREA[1]), 4)
# reward.py:30-33 and drone_continuous.py:366-367: the reward normalisation and the movement threshold
VEL_FACTOR = 0.035
POS_THRESHOLD = 0.003
# drone_continuous.py:291-300: the near-object and collision thresholds of the penalty
NEAR_OBJECT_THRESHOLDS = (150 / 4000, 150 / 4000, 150 / 3200, 150 / 3200, 150 / 1000,
                          150 / 1000, 150 / 2200, 150 / 2200, 30 / 800)
COLLISION_THRESHOLDS = (50 / 4000, 50 / 4000, 50 / 3200, 50 / 3200, 50 / 1000, 50 / 1000, 10 / 800)

# The fake's own model data, not facts:
ATTITUDE_TO_SPEED = 5.0          # placeholder: metres per second per radian of attitude
THRUST_TO_SPEED = 0.5            # placeholder: metres per second per unit of the thrust channel
# A flight-area corner, chosen so the conformance probe has room to run: the world pose is a separate data point.
START_POSITION = (-40.0, 40.0, INITIAL_ALTITUDE)  # placeholder: the reset pose
START_ORIENTATION = (0.0, 0.0, 0.0)           # placeholder: level flight
DIST_SENSORS = [1.0] * 9         # placeholder: no obstacle in range
# drone_continuous.py:86,110-117,163-170: target_pos=2 of the default quadrants of the 100x100 area
TARGET_POSITION = (25.0, -25.0)  # placeholder: the default quadrant, not a measured target


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _check_target_distance(distance, distance_target, distance_margin):
    """webots_drone/utils.py:229-235."""
    low = distance_target - distance_margin / 2.0
    high = distance_target + distance_margin / 2.0
    return distance < low, low <= distance < high


def _check_flight_area(position):
    """webots_drone/utils.py:100-111: which flight-area faces the position is outside of."""
    return [position[1] > FLIGHT_AREA[1][1], position[1] < FLIGHT_AREA[0][1],
            position[0] > FLIGHT_AREA[1][0], position[0] < FLIGHT_AREA[0][0],
            position[2] > FLIGHT_AREA[1][2], position[2] < FLIGHT_AREA[0][2]]


def _same_position(first, second):
    """webots_drone/utils.py:238-241."""
    difference = round(math.dist(first, second), 4)
    if abs(difference) <= POS_THRESHOLD:
        difference = 0.0
    return difference == 0.0


def _distance2reward(distance, reference):
    """webots_drone/reward.py:22-23."""
    return -abs(1.0 - distance / reference)


def _orientation2reward(orientation_diff):
    """webots_drone/reward.py:18-19."""
    return (orientation_diff + 1.0) / 2.0


class FakeDroneEnv:
    """The vector-observation DroneEnvContinuous without Webots, numpy or opencv."""

    def __init__(self, **_options):
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        self.observation_space = Box([-math.inf] * 22, [math.inf] * 22)
        self.metadata = {"render.modes": ["human", "rgb_array"]}  # drone_continuous.py:38-41
        self._rng = random.Random()
        self._seed = None
        self._closed = False
        self._reset_state()

    def _reset_state(self):
        self._episode_frames = 0
        self._no_action_frames = 0
        self._risk_zone_steps = 0
        self._out_area_steps = 0
        self._time_s = 0.0
        self._position = list(START_POSITION)
        self._orientation = list(START_ORIENTATION)
        self._speed = [0.0, 0.0, 0.0]
        self._angular_velocity = [0.0, 0.0, 0.0]
        self._north_rad = 0.0
        self._dist_sensors = list(DIST_SENSORS)
        self._previous_position = list(self._position)
        self._previous_distance = self._distance_to_target(self._position)
        self._penalization = "no"
        self._final = "no"

    def reset(self, seed=None, options=None, **kwargs):
        """DroneEnvContinuous.reset (drone_continuous.py:442-454): restart and return (observation, info)."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        else:
            # drone_continuous.py:151-153: a seed of None asks numpy for a fresh random state
            self._seed = None
            self._rng = random.Random()
        self._reset_state()
        return self._observation(), self._info()

    def step(self, action):
        """DroneEnvContinuous.step (drone_continuous.py:456-498): one macro-step over 120-130 Webots steps."""
        if len(action) != len(ACTION_LOW):
            raise ValueError(f"the action needs {len(ACTION_LOW)} values, got {len(action)}")
        command = [min(max(float(value), low), high)
                   for value, low, high in zip(action, ACTION_LOW, ACTION_HIGH)]
        step_frames = self._rng.randint(FRAME_SKIP - FRAME_MARGIN, FRAME_SKIP + FRAME_MARGIN)  # 461-463
        dt = step_frames * BASE_TIMESTEP_S

        self._previous_position = list(self._position)
        self._previous_distance = self._distance_to_target(self._position)
        roll, pitch, yaw, altitude = command
        # The upstream controller receives the four values as disturbances; the fake integrates them kinematically.
        self._orientation = [roll, pitch, yaw]
        self._angular_velocity = [0.0, 0.0, 0.0]
        forward = pitch * ATTITUDE_TO_SPEED
        right = roll * ATTITUDE_TO_SPEED
        self._speed = [forward * math.cos(yaw) - right * math.sin(yaw),
                       forward * math.sin(yaw) + right * math.cos(yaw),
                       altitude * THRUST_TO_SPEED]
        self._position = [value + speed * dt for value, speed in zip(self._position, self._speed)]
        self._north_rad = self._wrap(yaw)
        self._time_s += dt

        distance = self._distance_to_target(self._position)
        in_risk, in_zone = _check_target_distance(distance, GOAL_DISTANCE, GOAL_THRESHOLD)
        self._risk_zone_steps = self._risk_zone_steps + 1 if in_risk else 0
        self._out_area_steps = self._out_area_steps + 1 if any(_check_flight_area(self._position)) else 0
        if _same_position(self._previous_position, self._position) and not in_zone:
            self._no_action_frames += step_frames
        else:
            self._no_action_frames = 0
        self._episode_frames += step_frames

        reward = self._compute_reward(distance, in_risk, in_zone)
        terminal = self._final_state(distance)
        final = terminal
        truncated = False
        if self._episode_frames >= MAX_EPISODE_FRAMES:                       # 477-481
            truncated = True
            final = "TimeLimit"
        if self._is_goal_state(distance, in_zone):                           # 482-487
            reward += 10.0
            truncated = True
            final = "GoalFound"
        terminated = terminal != "no"
        if terminated:                                                       # 489-491
            reward -= 2.0
        self._final = final
        return self._observation(), reward, terminated, truncated, self._info()

    def close(self):
        """DroneEnvContinuous.close (drone_continuous.py:514-519): release the viewer."""
        self._closed = True

    # -- helpers ---------------------------------------------------------
    def _distance_to_target(self, position):
        """VirtualTarget.get_distance (target.py:98-105): the target is 2-D, so its z follows the drone."""
        return round(math.hypot(position[0] - TARGET_POSITION[0], position[1] - TARGET_POSITION[1]), 4)

    def _target_orientation(self):
        """compute_target_orientation (utils.py:223-226)."""
        angle = math.atan2(TARGET_POSITION[1] - self._position[1], TARGET_POSITION[0] - self._position[0])
        angle -= math.pi / 2.0
        if angle < -math.pi:
            angle += 2.0 * math.pi
        return -angle

    def _orientation_diff(self):
        """VirtualTarget.get_orientation_diff(norm=True) (target.py:132-138)."""
        return math.cos(self._north_rad - self._target_orientation())

    def _is_goal_state(self, distance, in_zone):
        """DroneEnvContinuous.is_goal_state (drone_continuous.py:348-358)."""
        if not in_zone or self._out_area_steps != 0:
            return False
        d_goal = 1.0 + _distance2reward(distance, GOAL_DISTANCE)
        o_goal = _orientation2reward(self._orientation_diff())
        elevation = 0.0  # the target is 2-D: VirtualTarget.get_elevation_angle is 0 (target.py:120-130)
        e_goal = 1.0 - abs(elevation)
        return (d_goal * o_goal * e_goal) > 0.99

    def _final_state(self, distance):
        """DroneEnvContinuous.__is_final_state (drone_continuous.py:264-289)."""
        if self._no_action_frames >= MAX_NO_ACTION_FRAMES:
            return "NoAction"
        if (3.0 < self._orientation[0] or self._orientation[0] < -3.0) and self._dist_sensors[-1] < 0.01:
            return "Flipped"
        if distance > MAX_DISTANCE:
            return "MaxDistance"
        if self._risk_zone_steps > 1:
            return "InsideRiskZone"
        if self._out_area_steps > 1:
            return "OutFlightArea"
        return "no"

    def _compute_reward(self, distance, in_risk, in_zone):
        """compute_vector_reward (reward.py:37-66) plus the penalties of drone_continuous.py:291-330."""
        r_orientation = _orientation2reward(self._orientation_diff())
        r_distance = _distance2reward(distance, GOAL_DISTANCE)
        velocity = self._previous_distance - distance
        if abs(velocity) <= POS_THRESHOLD:                                  # reward.py:30-33
            velocity = 0.0
        r_velocity = max(-1.0, min(1.0, velocity / VEL_FACTOR))
        r_elevation = 1.0
        if in_risk:                                                         # reward.py:52-54
            r_velocity *= -1.0
        if in_zone:                                                         # reward.py:55-60
            r_velocity = ((1.0 + _distance2reward(self._previous_distance, GOAL_DISTANCE))
                          * (1.0 + _distance2reward(distance, GOAL_DISTANCE))
                          * (0.0 if _same_position(self._previous_position, self._position) else 1.0))
        penalty, self._penalization = self._penalization_value(in_risk)
        if penalty < 0:                                                     # drone_continuous.py:395-397
            return float(penalty)
        r_velocity = r_velocity * r_orientation * r_elevation               # reward.py:62-63
        r_pose = r_distance + (r_orientation - 1.0) + (r_elevation - 1.0)   # reward.py:64
        return r_velocity + r_pose * 0.1                                    # reward.py:65

    def _penalization_value(self, in_risk):
        """drone_continuous.py:291-330 with the fake's nine far-away sensors."""
        penalty = 0
        labels = []
        if any(value < threshold for value, threshold in zip(self._dist_sensors, NEAR_OBJECT_THRESHOLDS)):
            penalty -= 1
            labels.append("ObjectNear")
        if any(value < threshold for value, threshold in zip(self._dist_sensors, COLLISION_THRESHOLDS)):
            penalty -= 2
            labels.append("Near2Collision")
        if self._out_area_steps > 0:
            penalty -= 2
            labels.append("OutFlightArea")
        if self._no_action_frames > 0:
            penalty -= 2
            labels.append("SamePosition")
        if in_risk:
            penalty -= 2
            labels.append("InsideRiskZone")
        return penalty, "|".join(labels) if labels else "no"

    def _observation(self):
        """info2obs_1d (preprocessor.py:78-88): orientation, angular velocity, position, speed, north, sensors."""
        return (list(self._orientation) + list(self._angular_velocity)
                + list(self._position) + list(self._speed)
                + [self._north_rad] + list(self._dist_sensors))

    def _info(self):
        """The JSON-able part of DroneEnvContinuous.get_state (drone_continuous.py:205-216)."""
        return {
            "timestamp": round(self._time_s, 3),
            "orientation": list(self._orientation),
            "angular_velocity": list(self._angular_velocity),
            "position": list(self._position),
            "speed": list(self._speed),
            "north_rad": self._north_rad,
            "dist_sensors": list(self._dist_sensors),
            "motors_vel": [],
            "target_position": list(TARGET_POSITION),
            "target_dim": list(TARGET_DIMENSION),
            "final": self._final,
            "bonus": "no",
            "penalization": self._penalization,
        }

    @staticmethod
    def _wrap(angle):
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle
