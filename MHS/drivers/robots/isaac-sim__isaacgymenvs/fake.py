"""Fake backend of the Isaac Gym Ant driver: a pure Python, kinematic stand-in for the upstream Ant task.

Why a fake: the clone's environments need the external Isaac Gym Preview 4 simulator and a CUDA device (README.md:13-14),
and package code never imports or runs the clone.  This module therefore re-implements only the surface the Gymnasium
bridge uses, with the upstream task's 60-element observation layout and 8-element action Box.  It follows the two
environment classes the driver names:

* ``isaacgymenvs.tasks.ant:Ant`` (the class in ``native``) for the observation layout, the reset ranges, the episode
  length and the termination height;
* ``isaacgymenvs.tasks.base.vec_task:VecTask`` for the action and observation spaces and the action clipping.

The public members are ``reset`` and ``step``, which ``Ant`` inherits from ``VecTask``.  ``close`` is deliberately not
defined because the upstream class has none; the bridge checks for it and skips it.

Every number below is test data for the fake, not a measured fact: the dynamics constants are marked ``# placeholder``
and must never be cited as a Fact, a Limit or a reference.  The sizes and thresholds are the upstream task's declared
configuration and are restated in the driver's facts with their own citations.  Nothing here talks to a device or to
the upstream package.
"""

import math
import random

#: ant.py:67-68 sets numObservations=60 and numActions=8; ant.py:401-406 gives the observation layout.
OBSERVATION_SIZE = 60
ACTION_SIZE = 8
#: Ant.yaml:43 states dt=0.0166 s (1/60 s) and ant.py:112 copies it from the simulation configuration.
DT_SECONDS = 0.0166
#: Ant.yaml:10 sets episodeLength=1000 and ant.py:369 resets at max_episode_length - 1.
EPISODE_LENGTH = 1000
#: Ant.yaml:29 sets terminationHeight=0.31 and ant.py:368 resets below it.
TERMINATION_HEIGHT = 0.31

# test data (placeholders): the joint limits and the kinematic response of the fake
_JOINT_LIMIT = 1.0                              # placeholder
_VELOCITY_DECAY = 0.9                           # placeholder
_ACTION_GAIN = 0.1                              # placeholder
_START_HEIGHT = 0.44                            # placeholder
_HEIGHT_GAIN = 0.01                             # placeholder
_ALIVE_REWARD = 0.5                             # placeholder
_ACTION_REWARD = 0.001                          # placeholder
_ACTION_COST = 0.005                            # placeholder
_DEFAULT_SEED = 0                               # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _values(action):
    """The action as a list of floats, accepting a list, a tuple or an array-like."""
    if hasattr(action, "tolist"):
        action = action.tolist()
    if not isinstance(action, (list, tuple)):
        raise ValueError("the fake Ant needs one action value per joint")
    return [float(value) for value in action]


class FakeAnt:
    """One kinematic Ant: ``reset(seed, options)`` and ``step(action)`` with the upstream contract's shape."""

    def __init__(self, **_options):
        # VecTask lines 107 and 113: observation Box over num_obs values and action Box over num_actions values.
        self.action_space = Box([-1.0] * ACTION_SIZE, [1.0] * ACTION_SIZE)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self.dt = DT_SECONDS
        self._rng = random.Random(_DEFAULT_SEED)
        self._seed = _DEFAULT_SEED
        self._started = False
        self._tick = 0
        self._height = _START_HEIGHT
        self._dof_pos = [0.0] * ACTION_SIZE
        self._dof_vel = [0.0] * ACTION_SIZE
        self._actions = [0.0] * ACTION_SIZE
        self._forward = 0.0

    def reset(self, seed=None, options=None):
        """Start a new episode; ``seed`` fixes this fake's test data and ``options`` is accepted and ignored."""
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        elif not self._started:
            self._rng = random.Random(self._seed)
        # ant.py:257-258: upstream draws joints from +-0.2 and joint velocities from +-0.1; these test-data values are
        # placeholders for that draw.
        self._dof_pos = [self._rng.uniform(-0.2, 0.2) for _ in range(ACTION_SIZE)]      # placeholder
        self._dof_vel = [self._rng.uniform(-0.1, 0.1) for _ in range(ACTION_SIZE)]      # placeholder
        self._height = _START_HEIGHT
        self._actions = [0.0] * ACTION_SIZE
        self._forward = 0.0
        self._tick = 0
        self._started = True
        return self._observation(), {}

    def step(self, action):
        """Advance one 16.6 ms control step and return the Gymnasium five-tuple of this fake."""
        values = _values(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the fake Ant needs {ACTION_SIZE} action values, got {len(values)}")
        clipped = [max(-1.0, min(1.0, value)) for value in values]                     # VecTask.step:374
        for index, value in enumerate(clipped):
            velocity = _VELOCITY_DECAY * self._dof_vel[index] + _ACTION_GAIN * value   # placeholder
            self._dof_vel[index] = velocity
            position = self._dof_pos[index] + DT_SECONDS * velocity
            self._dof_pos[index] = max(-_JOINT_LIMIT, min(_JOINT_LIMIT, position))     # placeholder
        self._actions = clipped
        self._height = _START_HEIGHT + _HEIGHT_GAIN * (sum(self._dof_pos) / ACTION_SIZE)  # placeholder
        self._forward += 0.01 * sum(clipped)                                          # placeholder
        self._tick += 1
        reward = (_ALIVE_REWARD + _ACTION_REWARD * sum(clipped)
                  - _ACTION_COST * sum(value * value for value in clipped))           # placeholder
        terminated = self._height < TERMINATION_HEIGHT                                # Ant.yaml:29
        truncated = self._tick >= EPISODE_LENGTH                                      # Ant.yaml:10
        return self._observation(), reward, terminated, truncated, {}

    def _observation(self):
        """The 60-value vector in ant.py:401-406's order: height, velocity, angular velocity, yaw, roll, target,
        up, heading, 8 joint positions, 8 joint velocities, 24 contact forces, 8 actions."""
        velocity = [0.1 * self._forward, 0.0, 0.0]                                    # placeholder
        angular_velocity = [0.0, 0.0, 0.0]                                            # placeholder
        orientation = [0.0, 0.0, 0.0]                                                 # placeholder yaw, roll, target
        projections = [1.0, 1.0]                                                      # placeholder up, heading
        contacts = [0.0] * 24                                                         # placeholder contact forces
        observation = ([self._height] + velocity + angular_velocity + orientation + projections
                       + list(self._dof_pos) + list(self._dof_vel) + contacts + list(self._actions))
        if len(observation) != OBSERVATION_SIZE:
            raise AssertionError("the fake observation left the upstream 60-element layout")
        return observation
