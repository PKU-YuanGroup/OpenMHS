"""Fake backend of the DroneNavigation-v0 driver: a pure Python kinematic stand-in for the upstream environment.

Why a fake: the upstream class imports gym, pybullet, numpy and matplotlib (drone_envs/envs/drone_env_v0.py:1-11)
and package code never imports or runs the clone, so the gate cannot open the pybullet environment.  This module
mirrors the public surface the bridge uses (``reset``, ``step``, ``seed``, ``close``; gate G7) and the reward and
termination rules of ``DroneNavigationV0`` (drone_envs/envs/drone_env_v0.py:64-168).  The values below are test
data, not device facts; every numeric constant is marked ``# placeholder``.

What this is not: the upstream pybullet model.  The drone is a point mass without orientation, gravity, contacts or
drag, and the goal body, plane and collisions are ignored.  The integrator is a semi-implicit Euler step with the
base link mass, so trajectories differ from the upstream simulator and were never compared with it.  The driver's
fidelity ``gaps`` say this.
"""

import math
import random

# drone_envs/envs/drone_env_v0.py:24-27 and drone_envs/resources/drone.py:25-27
THRUST_LIMIT = 0.1                              # placeholder: per-axis thrust clip in newtons
# drone_envs/envs/drone_env_v0.py:51-53
TIMESTEP_S = 1.0 / 30.0                         # placeholder: pybullet time step in seconds
# drone_envs/resources/drone.urdf:11
MASS_KG = 0.027                                 # placeholder: base link mass in kilograms
# drone_envs/resources/drone.py:12
START_POSITION = [0.0, 0.0, 0.1]                # placeholder: base position at load in metres
# drone_envs/envs/drone_env_v0.py:137-141
GOAL_NEAR = 5.0                                 # placeholder: lower absolute goal coordinate
GOAL_FAR = 9.0                                  # placeholder: upper absolute goal coordinate
GOAL_Z_LOW = 5.0                                # placeholder: lower goal z
GOAL_Z_HIGH = 9.0                               # placeholder: upper goal z
# drone_envs/envs/drone_env_v0.py:155-157
BOUND_XY = 12.0                                 # placeholder: x and y episode bound
BOUND_Z_LOW = 0.0                               # placeholder: z lower episode bound
BOUND_Z_HIGH = 12.0                             # placeholder: z upper episode bound
# drone_envs/envs/drone_env_v0.py:158-166
BOUND_PENALTY = 1.0                             # placeholder: reward for leaving the box
REACH_DISTANCE = 2.0                            # placeholder: distance that counts as reaching the goal
REACH_REWARD = 50.0                             # placeholder: reward for reaching the goal
# drone_envs/config.py:14-33
OBSERVATION_LOW = [-12.0, -12.0, 0.0, -3.0, -3.0, -3.0, -9.0, -9.0, 0.0]    # placeholder
OBSERVATION_HIGH = [12.0, 12.0, 12.0, 3.0, 3.0, 3.0, 9.0, 9.0, 9.0]         # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeDroneNavigationV0:
    """DroneNavigation-v0 without pybullet: ``reset()``, ``step(action)`` and ``seed(seed)`` as upstream defines them."""

    def __init__(self):
        self.action_space = Box([-THRUST_LIMIT] * 3, [THRUST_LIMIT] * 3)    # placeholder
        self.observation_space = Box(OBSERVATION_LOW, OBSERVATION_HIGH)     # placeholder
        self._rng = random.Random(0)                                        # placeholder: deterministic start seed
        self._position = list(START_POSITION)                              # placeholder
        self._velocity = [0.0, 0.0, 0.0]                                   # placeholder
        self.goal = (GOAL_NEAR, GOAL_NEAR, GOAL_NEAR)                      # placeholder
        self.done = False
        self.reach_target = False
        self.prev_dist_to_goal = 0.0                                      # placeholder
        self.reset()                                                        # drone_env_v0.py:62 does the same

    def seed(self, seed=None):
        """Reseed the goal generator (drone_env_v0.py:78-80); the bridge calls this for a legacy gym environment."""
        self._rng = random.Random(seed) if seed is not None else random.Random()
        return [seed]

    def reset(self):
        """Start a new episode: reset state, draw a goal and return the 9-element observation (v0:82-97)."""
        self._position = list(START_POSITION)                              # placeholder
        self._velocity = [0.0, 0.0, 0.0]                                   # placeholder
        self.done = False
        self.reach_target = False
        self._draw_goal()
        self.prev_dist_to_goal = self._distance(self._position)
        return self._observation()

    def step(self, action):
        """Advance one 1/30 s kinematic step and return ``(observation, reward, done, reach_target)`` (v0:64-76)."""
        thrust = [max(-THRUST_LIMIT, min(THRUST_LIMIT, float(value))) for value in action]   # placeholder
        for axis in range(3):                                              # placeholder: x, y, z axes
            acceleration = thrust[axis] / MASS_KG                          # placeholder
            self._velocity[axis] += acceleration * TIMESTEP_S              # placeholder
            self._position[axis] += self._velocity[axis] * TIMESTEP_S      # placeholder
        observation = self._position + self._velocity
        reward = self._reward(observation)
        self.prev_dist_to_goal = self._distance(observation)
        return self._observation(), reward, self.done, self.reach_target

    def close(self):
        """Release the state; upstream disconnects the pybullet client (v0:121-122)."""
        self._position = None
        self._velocity = None

    def _draw_goal(self):
        """Draw the goal like drone_env_v0.py:135-142."""
        self.goal = (
            self._rng.uniform(GOAL_NEAR, GOAL_FAR) if self._rng.randrange(2)   # placeholder: two signs
            else self._rng.uniform(-GOAL_FAR, -GOAL_NEAR),
            self._rng.uniform(GOAL_NEAR, GOAL_FAR) if self._rng.randrange(2)   # placeholder: two signs
            else self._rng.uniform(-GOAL_FAR, -GOAL_NEAR),
            self._rng.uniform(GOAL_Z_LOW, GOAL_Z_HIGH),
        )

    def _distance(self, observation):
        """Euclidean distance from the first three values (the drone position) to the goal (v0:124-133)."""
        return math.sqrt(sum((observation[axis] - self.goal[axis]) ** 2 for axis in range(3)))  # placeholder: x, y, z

    def _reward(self, observation):
        """Distance improvement, the boundary penalty and the reach bonus (v0:148-168)."""
        distance = self._distance(observation)
        reward = self.prev_dist_to_goal - distance
        if (observation[0] >= BOUND_XY or observation[0] <= -BOUND_XY
                or observation[1] >= BOUND_XY or observation[1] <= -BOUND_XY
                or observation[2] <= BOUND_Z_LOW or observation[2] >= BOUND_Z_HIGH):
            reward -= BOUND_PENALTY
            self.done = True
        if distance < REACH_DISTANCE:
            self.done = True
            self.reach_target = True
            reward += REACH_REWARD
        return reward

    def _observation(self):
        """The environment observation: drone position, drone velocity and the goal (v0:75 and drone.py:38-49)."""
        return list(self._position) + list(self._velocity) + list(self.goal)
