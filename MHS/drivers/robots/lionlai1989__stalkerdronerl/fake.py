"""Analytic fake backend for the StalkerDroneRL QuadcopterTrackingEnv driver.

This is not a recording and not the upstream Gazebo simulator.  The upstream
environment imports rclpy, torch, stable_baselines3 and the clone's own ROS
modules (src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:14-39), and
package code never imports or runs the clone.  This module therefore mirrors the
public Gymnasium surface the bridge uses (``action_space``,
``observation_space``, ``reset(seed, options)``, ``step(action)`` and
``close``) with a pure Python kinematic stand-in: a point mass driven by a
normalized vertical force and three normalized torques, with the same
11-value observation layout and the same reward terms as the upstream code.
It models no Gazebo physics, no motor mixing, no ROS graph and no navigator
state machine.  All constants below are test data, marked ``# placeholder``;
they are not Facts, Limits or references to the device.

The action interpretation follows
``src/sdrl_rl_controller/sdrl_rl_controller/observation_state_action.py:133-162``
and the reward layout follows
``src/sdrl_rl_controller/sdrl_rl_controller/train_sac.py:107-115`` and
``:240-278``; observations follow
``src/sdrl_rl_controller/sdrl_rl_controller/observation_state_action.py:90-130``.
Those are upstream source facts in driver.py, not claims that this fake
reproduces the upstream dynamics.
"""

import math
import random

# train_sac.py:46-47: the upstream distance caps used in the reward.
MAX_POS_DIST = 9.0                       # placeholder: upstream observation cap in metres
MAX_VEL_DIST = 5.0                       # placeholder: upstream velocity cap in m/s

# observation_state_action.py:20-22: normalization constants of the upstream observation.
MAX_POS_ERR = 5.0                        # placeholder: position-error normalizer in metres
MAX_VEL_ERR = 3.0                        # placeholder: velocity-error normalizer in m/s
MAX_ANG_VEL = 6.28                       # placeholder: body-rate normalizer in rad/s

# train_sac.py:45, 55, 107-115, 266-276: upstream control period and reward terms.
GRAVITY = 9.81                           # placeholder: gravity in m/s^2
CONTROL_FREQ_HZ = 100.0                  # placeholder: upstream default control frequency
TIMESTEP_S = 1.0 / CONTROL_FREQ_HZ       # placeholder: one environment step period
BASE_REWARD = 0.2                        # placeholder: upstream base_reward
POS_DIST_PENALTY = -0.0388               # placeholder: upstream pos_dist_penalty
VEL_DIST_PENALTY = -0.007                # placeholder: upstream vel_dist_penalty
PROGRESS_REWARD = 1.0                    # placeholder: upstream progress_reward
DANGER_ZONE_TILT = math.pi / 6           # placeholder: upstream danger_zone_tilt
TILT_PENALTY = -0.5                      # placeholder: upstream tilt_penalty
SUCCESS_REWARD = 2.5                     # placeholder: upstream success_reward
CRASH_PENALTY = -10.0                    # placeholder: upstream crash_penalty
REWARD_LOW = -10.0                       # placeholder: upstream reward clip
REWARD_HIGH = 10.0                       # placeholder: upstream reward clip

# quadcopter_params.py:14-25, 86: mass, inertia, hover thrust and the printed
# maximum thrust.  These are copied as test data so the fake reacts in the
# same direction and scale as the upstream wrench mapping.
MASS_KG = 1.5                            # placeholder: upstream quadcopter mass
INERTIA = [0.0347563, 0.07, 0.0977]      # placeholder: upstream diagonal inertia
HOVER_FORCE_N = MASS_KG * GRAVITY * 1.1  # placeholder: upstream hover thrust
MAX_FORCE_N = 21.8843648                 # placeholder: upstream printed force_z_limit maximum
TORQUE_LIMIT_NM = 0.1                    # placeholder: upstream torque limits after clamping

# train_sac.py:56, 75-83: episode limit and curriculum start.
MAX_EPISODE_STEPS = 2000                 # placeholder: upstream default max_episode_steps
SUCCESS_RADIUS = 2.5                     # placeholder: upstream initial success radius
SUCCESS_TILT = math.radians(15.0)        # placeholder: upstream success_tilt_tol
MAX_TILT_ANGLE = math.pi / 4             # placeholder: upstream max_tilt_angle
MIN_ALTITUDE = 0.0                       # placeholder: local crash floor, not an upstream crash test
START_ALTITUDE = 0.05                    # placeholder: upstream teleport z
RESET_RANGE = 1.5                        # placeholder: upstream initial_random_range
TARGET_RANGE = 3.0                       # placeholder: local target range
TARGET_Z_LOW = 0.5                       # placeholder: local target altitude
TARGET_Z_HIGH = 2.0                      # placeholder: local target altitude
CRASH_STEPS = 4                          # placeholder: upstream consecutive CRASHED count


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads low, high, shape and dtype."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeQuadcopterTrackingEnv:
    """QuadcopterTrackingEnv without ROS or Gazebo: reset, step and close as the upstream class defines them."""

    def __init__(self, **_options):
        # train_sac.py:151-165: four normalized force/torque inputs and eleven normalized observations.
        self.action_space = Box([-1.0, -1.0, -1.0, -1.0], [1.0, 1.0, 1.0, 1.0])      # placeholder
        self.observation_space = Box([-1.0] * 11, [1.0] * 11)                         # placeholder
        self.max_steps = MAX_EPISODE_STEPS
        self._rng = random.Random(0)                                                   # placeholder: start seed
        self._closed = False
        self._reset_state()

    def reset(self, seed=None, options=None):
        """Start a new episode; upstream returns ``(observation, {})`` (train_sac.py:487-544)."""
        if seed is not None:
            self._rng = random.Random(int(seed))                                       # placeholder: seeded start
        self._closed = False
        self._reset_state()
        return self._observation(), {}

    def step(self, action):
        """Apply one normalized action for one 10 ms control step (train_sac.py:362-485)."""
        values = [float(value) for value in action]
        if len(values) != 4:
            raise ValueError(f"Invalid action shape: {tuple(values)}")                 # placeholder: upstream shape
        self._integrate(values)
        pos_dist = min(self._distance(), MAX_POS_DIST)
        vel_dist = min(math.sqrt(sum(value * value for value in self._velocity)), MAX_VEL_DIST)
        tilt = self._tilt()
        success = pos_dist < SUCCESS_RADIUS and tilt < SUCCESS_TILT
        crash_now = self._position[2] <= MIN_ALTITUDE or tilt > MAX_TILT_ANGLE
        self._crash_count = self._crash_count + 1 if crash_now else 0
        crash = crash_now and self._crash_count >= CRASH_STEPS
        reward = self._reward(pos_dist, vel_dist, tilt, success, crash_now)
        self._last_dist = pos_dist
        self._step_count += 1
        terminated = crash
        truncated = self._step_count >= self.max_steps
        info = {"success": bool(success), "crash": bool(crash)}
        return self._observation(), reward, terminated, truncated, info

    def close(self):
        """Release the state; upstream shuts down rclpy and destroys its node (train_sac.py:620-625)."""
        self._closed = True

    def _reset_state(self):
        """Draw a placeholder start and target; upstream teleports to random x, y and z=0.05."""
        self._position = [
            self._rng.uniform(-RESET_RANGE, RESET_RANGE),                              # placeholder: start x
            self._rng.uniform(-RESET_RANGE, RESET_RANGE),                              # placeholder: start y
            START_ALTITUDE,
        ]
        self._velocity = [0.0, 0.0, 0.0]                                               # placeholder: zero velocity
        self._attitude = [0.0, 0.0, 0.0]                                               # placeholder: roll, pitch, yaw
        self._rates = [0.0, 0.0, 0.0]                                                  # placeholder: p, q, r
        self._target = [
            self._rng.uniform(-TARGET_RANGE, TARGET_RANGE),                            # placeholder: target x
            self._rng.uniform(-TARGET_RANGE, TARGET_RANGE),                            # placeholder: target y
            self._rng.uniform(TARGET_Z_LOW, TARGET_Z_HIGH),                            # placeholder: target z
        ]
        self._step_count = 0
        self._crash_count = 0
        self._last_dist = None

    def _integrate(self, action):
        """A point-mass response to the normalized force and torque inputs, not upstream dynamics."""
        # action[0] maps to force_z like action_to_wrench (observation_state_action.py:144-152).
        force_z = (HOVER_FORCE_N + (MAX_FORCE_N - HOVER_FORCE_N) * action[0]
                   if action[0] >= 0 else HOVER_FORCE_N + HOVER_FORCE_N * action[0])
        accel_z = force_z / MASS_KG - GRAVITY                                          # placeholder
        torque = [TORQUE_LIMIT_NM * action[1], TORQUE_LIMIT_NM * action[2],
                  TORQUE_LIMIT_NM * action[3]]                                         # placeholder
        for axis in range(3):
            self._rates[axis] += torque[axis] / INERTIA[axis] * TIMESTEP_S             # placeholder
            self._rates[axis] *= 0.999                                                 # placeholder: damping
            self._attitude[axis] += self._rates[axis] * TIMESTEP_S                     # placeholder
        roll, pitch = self._attitude[0], self._attitude[1]
        pitch = max(-1.0, min(1.0, pitch))                                             # placeholder: tilt clamp
        roll = max(-1.0, min(1.0, roll))                                               # placeholder: tilt clamp
        accel_x = GRAVITY * math.tan(pitch)                                            # placeholder: forward tilt
        accel_y = -GRAVITY * math.tan(roll)                                            # placeholder: side tilt
        self._velocity[0] += accel_x * TIMESTEP_S                                      # placeholder
        self._velocity[1] += accel_y * TIMESTEP_S                                      # placeholder
        self._velocity[2] += accel_z * TIMESTEP_S                                      # placeholder
        for axis in range(3):
            self._position[axis] += self._velocity[axis] * TIMESTEP_S                  # placeholder

    def _distance(self):
        return math.sqrt(sum((self._target[axis] - self._position[axis]) ** 2 for axis in range(3)))

    def _tilt(self):
        return math.acos(max(-1.0, min(1.0, math.cos(self._attitude[0]) * math.cos(self._attitude[1]))))

    def _reward(self, pos_dist, vel_dist, tilt, success, crash_now):
        """The upstream reward terms (train_sac.py:240-278), applied to the fake state."""
        reward = BASE_REWARD
        reward += POS_DIST_PENALTY * pos_dist
        reward += VEL_DIST_PENALTY * vel_dist
        if self._last_dist is not None:
            reward += PROGRESS_REWARD * (self._last_dist - pos_dist)
        tilt_excess = abs(tilt) - DANGER_ZONE_TILT
        if tilt_excess > 0:
            reward += TILT_PENALTY * tilt_excess
        if success:
            reward += SUCCESS_REWARD
        if crash_now:
            reward += CRASH_PENALTY
        return max(REWARD_LOW, min(REWARD_HIGH, reward))

    def _observation(self):
        """The 11 normalized values of observation_state_action.py:90-130, in world-frame approximation."""
        dx = self._target[0] - self._position[0]
        dy = self._target[1] - self._position[1]
        dz = self._target[2] - self._position[2]
        values = [
            self._clip(dx / MAX_POS_ERR),
            self._clip(dy / MAX_POS_ERR),
            self._clip(dz / MAX_POS_ERR),
            self._clip(-self._velocity[0] / MAX_VEL_ERR),
            self._clip(-self._velocity[1] / MAX_VEL_ERR),
            self._clip(-self._velocity[2] / MAX_VEL_ERR),
            self._clip(self._attitude[0] / math.pi),
            self._clip(self._attitude[1] / (math.pi / 2.0)),
            self._clip(self._rates[0] / MAX_ANG_VEL),
            self._clip(self._rates[1] / MAX_ANG_VEL),
            self._clip(self._rates[2] / MAX_ANG_VEL),
        ]
        return [float(value) for value in values]

    @staticmethod
    def _clip(value):
        return max(-1.0, min(1.0, float(value)))
