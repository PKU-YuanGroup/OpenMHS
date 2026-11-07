"""Fake backend of the spot_mini_mini driver: a pure Python stand-in for ``spotmicro.spot_gym_env:spotGymEnv``.

Why a fake: the upstream clone needs gym, numpy and PyBullet, and package code never imports the clone, so the
acceptance gate serves this module instead of ``gym.make("SpotMicroEnv-v0")``.  The public methods are the ones the
upstream class has (``reset``, ``seed``, ``step`` and ``is_fallen``; gate G7), and the two space classes duck-type
``gym.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape`` and ``dtype``).

The space shapes and bounds follow the clone at commit c7e4905be176c63fa0e68a09c177b937e916fa60: twelve motor
actions in [-1, 1] (``spotmicro/spot_gym_env.py:31``, ``:240``, ``:280-282``) and the observation built by
``Spot.GetObservation`` (``spotmicro/spot.py:688-703``) with the bounds of ``GetObservationUpperBound``
(``spotmicro/spot.py:590-597``).  The step limit of 1000 is the registered ``max_episode_steps``
(``spotmicro/spot_gym_env.py:50``).

What this is not: the PyBullet simulation of the clone.  The fake integrates a small kinematic model with placeholder
tilt, gait-phase, acceleration and reward values; it does not model rigid bodies, contacts, the motor model, sensor
noise, latency or the environment randomizer.  Its initial tilt and gait phase come from Python's
``random.Random(seed)``; upstream starts from the stand pose and randomizes physical properties with numpy's global
generator.  The differences are listed in the fidelity ``gaps`` of the driver.

Nothing here talks to a device.
"""

import math
import random

# spotmicro/spot_gym_env.py:31 and :240, :280-282: one action per motor and _action_bound = 1.
NUM_MOTORS = 12
ACTION_BOUND = 1.0
# spotmicro/spot.py:590-597: the observation upper bound of roll/pitch, the rates, the leg phases and the contacts.
ROLL_PITCH_BOUND = 2.0 * math.pi
LEG_PHASE_BOUND = 2.0
CONTACT_BOUND = 1.0
# spotmicro/spot_gym_env.py:536-551: is_fallen compares the dot product of the base's local up with the world up.
FALLEN_UP_DOT = 0.55
# spotmicro/spot_gym_env.py:50: the registration wraps SpotMicroEnv-v0 with max_episode_steps=1000.
MAX_EPISODE_STEPS = 1000
# spotmicro/spot_gym_env.py:37: the observation bounds are widened by OBSERVATION_EPS.
OBSERVATION_EPS = 0.01
# spotmicro/spot_gym_env.py:198: the simulation time step is 0.01 s.
TIME_STEP = 0.01

# Placeholder test data of the fake's own kinematics.  These are not properties of the clone.
TILT_GAIN = 0.02                                # placeholder
GAIT_BIAS = 0.001                               # placeholder
ACC_GAIN = 0.1                                  # placeholder
PHASE_RATE = 0.1                                # placeholder
PHASE_ACTION_GAIN = 0.05                        # placeholder
INITIAL_TILT = 0.02                             # placeholder
REWARD = 1.0                                    # placeholder
PHASE_OFFSETS = (0.0, 0.5, 1.0, 1.5)            # placeholder


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeSpotGymEnv:
    """SpotMicroEnv-v0 without PyBullet: the four public methods of ``spotGymEnv`` the bridge uses."""

    def __init__(self, **options):
        self.contacts = bool(options.get("contacts", True))      # spotmicro/spot_gym_env.py:118
        self.action_space = Box([-ACTION_BOUND] * NUM_MOTORS, [ACTION_BOUND] * NUM_MOTORS)
        self.observation_space = Box(self._observation_low(), self._observation_high())
        self._rng = random.Random()
        self._tick = 0
        self._roll = 0.0
        self._pitch = 0.0
        self._gyro = [0.0, 0.0, 0.0]
        self._acc = [0.0, 0.0, 0.0]
        self._phase = 0.0
        self._leg_phases = [0.0, 0.0, 0.0, 0.0]
        self._contacts = [1, 1, 1, 1] if self.contacts else []

    def _observation_upper(self):
        """spotmicro/spot.py:588-597: roll, pitch, rates, accelerations, leg phases and contacts."""
        high = [ROLL_PITCH_BOUND, ROLL_PITCH_BOUND] + [math.inf] * 6 + [LEG_PHASE_BOUND] * 4
        if self.contacts:
            high += [CONTACT_BOUND] * 4
        return high

    def _observation_high(self):
        """spotmicro/spot_gym_env.py:276-279: the upper bound is widened by OBSERVATION_EPS."""
        return [value + OBSERVATION_EPS if math.isfinite(value) else value for value in self._observation_upper()]

    def _observation_low(self):
        """spotmicro/spot.py:600-602 and spotmicro/spot_gym_env.py:278-279."""
        return [-value - OBSERVATION_EPS if math.isfinite(value) else value for value in self._observation_upper()]

    def reset(self, seed=None, options=None):
        """Start an episode; the seed selects the fake's placeholder initial tilt and gait phase.

        ``options`` is accepted and ignored: the upstream reset takes initial_motor_angles, reset_duration,
        desired_velocity and desired_rate, so the bridge's options reach no upstream argument either.
        """
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._tick = 0
        self._roll = self._rng.uniform(-INITIAL_TILT, INITIAL_TILT)
        self._pitch = self._rng.uniform(-INITIAL_TILT, INITIAL_TILT)
        self._gyro = [0.0, 0.0, 0.0]
        self._acc = [0.0, 0.0, 0.0]
        self._phase = self._rng.uniform(0.0, LEG_PHASE_BOUND)
        self._update_legs()
        return self._observation(), {}

    def seed(self, seed=None):
        """spotmicro/spot_gym_env.py:382-384: upstream returns [seed] from gym.utils.seeding.np_random."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        return [seed]

    def step(self, action):
        """Advance the fake by one transition and return the five-tuple the bridge accepts."""
        values = list(action.tolist() if hasattr(action, "tolist") else action)
        if len(values) != NUM_MOTORS:
            raise ValueError(f"expected {NUM_MOTORS} action values, got {len(values)}")
        previous_roll, previous_pitch = self._roll, self._pitch
        # placeholder: a small tilt response to opposing motor commands, not PyBullet joint dynamics
        self._roll += TILT_GAIN * (values[0] - values[3]) + GAIT_BIAS * (values[6] - values[9])
        self._pitch += TILT_GAIN * (values[1] - values[4]) + GAIT_BIAS * (values[7] - values[10])
        limit = ROLL_PITCH_BOUND + OBSERVATION_EPS
        self._roll = max(-limit, min(limit, self._roll))
        self._pitch = max(-limit, min(limit, self._pitch))
        self._gyro = [(self._roll - previous_roll) / TIME_STEP,
                      (self._pitch - previous_pitch) / TIME_STEP, 0.0]
        self._acc = [ACC_GAIN * (values[6] - values[9]),
                     ACC_GAIN * (values[7] - values[10]),
                     ACC_GAIN * (values[8] - values[11])]
        # placeholder: the gait phase advances with time and the mean absolute motor command
        self._phase = (self._phase + PHASE_RATE
                       + PHASE_ACTION_GAIN * sum(abs(value) for value in values) / NUM_MOTORS) % LEG_PHASE_BOUND
        self._update_legs()
        self._tick += 1
        terminated = self.is_fallen()
        truncated = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), REWARD, terminated, truncated, {}

    def is_fallen(self):
        """spotmicro/spot_gym_env.py:536-551: true when the base's up vector tilts below the 0.55 dot product."""
        return math.cos(self._roll) * math.cos(self._pitch) < FALLEN_UP_DOT

    def _update_legs(self):
        self._leg_phases = [(self._phase + offset) % LEG_PHASE_BOUND for offset in PHASE_OFFSETS]
        self._contacts = [1 if phase < 1.0 else 0 for phase in self._leg_phases] if self.contacts else []

    def _observation(self):
        """spotmicro/spot.py:688-703: roll, pitch, gyro xyz, acceleration xyz, leg phases, contacts."""
        return ([self._roll, self._pitch] + list(self._gyro) + list(self._acc)
                + list(self._leg_phases) + list(self._contacts))
