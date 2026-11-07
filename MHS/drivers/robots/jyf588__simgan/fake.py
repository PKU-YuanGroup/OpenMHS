"""Fake backend of the SimGAN hopper driver: a pure Python stand-in for ``my_pybullet_envs:HopperURDFEnvV3``.

Why a fake: the acceptance gate does not install or import the clone (pybullet, ``gym==0.14.0`` and the URDF assets
are needed, ``README.md:21-29``), and package code never imports the clone.  This module keeps the public interface of
the upstream environment class: ``reset()`` without a seed, ``step(a)`` returning a four-tuple, ``seed(seed)``
separately, and duck-typed ``Box`` spaces (the bridge reads ``low``, ``high``, ``shape`` and the class name).  Gate G7
checks every public method of this class against the upstream AST; the public members are therefore only ``reset``,
``step`` and ``seed``.

What this is not: the upstream PyBullet model.  It is a kinematic stand-in with a made-up mass-free update, no
contacts, no joint torques, no rendering, and no observation or action noise beyond the seeded reset perturbation.
Every number below is test data (marked ``# placeholder``) and is not a fact, a limit or a citation; the facts in
``driver.py`` cite the upstream lines instead.  The fidelity ``gaps`` of the driver list these differences.
"""

import math
import random

# hopper.py:53 (ctrl_dofs = [3, 4, 5]) and hopper_env_v3.py:100-103 (one action element per controlled joint)
ACTION_DIM = 3                              # placeholder: struct of the fake space, not a measured bound
OBS_DIM = 11                                # placeholder: five positions + six velocities (hopper.py:167-175)
TOTAL_DOFS = 6                              # placeholder: three root and three controlled joints (hopper.py:53-55)
Q_SCALED_HALF_SPAN = 2.0                    # placeholder: normalization of a joint position
JOINT_MIDPOINT_FRACTION = 0.5               # placeholder: midpoint of a joint's range
JOINT_LIMIT_FRACTION = 0.97                 # placeholder: upstream joint-limit test (hopper_env_v3.py:266)

# hopper.py:45-46 (base_init_pos [0, 0, 1.3]) and hopper.py:91-96 (init noise 0.02 / 0.1)
START_HEIGHT = 1.3                           # placeholder
INIT_Q_NOISE = 0.02                          # placeholder
INIT_DQ_NOISE = 0.1                          # placeholder

# hopper_env_v3.py:281 (termination thresholds) and hopper.py:19-21 (URDF joint limits quoted in the comment)
DONE_HEIGHT_LOW = 0.6                        # placeholder
DONE_HEIGHT_HIGH = 1.8                       # placeholder
DONE_DQ = 50.0                               # placeholder
JOINT_LOW = (-2.61799, -2.61799, -0.785398)  # placeholder
JOINT_HIGH = (0.5, 0.5, 0.785398)            # placeholder

# hopper_env_v3.py:257-271 (reward terms) and hopper.py:51 (obs_scaling [1.0]*5 + [1.0]*2 + [0.1]*4)
ALIVE_BONUS = 3.0                            # placeholder
ACTION_PENALTY = 0.5                         # placeholder
JOINT_LIMIT_PENALTY = 3.0                    # placeholder
ACCEL_PENALTY_WEIGHT = 0.05                  # placeholder
ACCEL_PENALTY_CAP = 5.0                      # placeholder
OBS_VELOCITY_SCALE = 0.1                     # placeholder: hopper.py:51 scales the last four velocities
CONTROL_PERIOD_S = 0.02                      # placeholder: the upstream default control_skip=10 at 1/500 s

# The kinematic update is invented for the fake: these gains have no upstream counterpart.
ACTION_GAIN = 2.0                            # placeholder
JOINT_DAMPING = 2.0                          # placeholder
HEIGHT_SPRING = 20.0                         # placeholder
HEIGHT_DAMPING = 4.0                         # placeholder
HEIGHT_ACTION_GAIN = 0.25                    # placeholder
FORWARD_ACTION_GAIN = 0.5                    # placeholder
FORWARD_DAMPING = 1.0                        # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeHopperURDFEnvV3:
    """The HopperURDFEnvV3 interface without PyBullet: ``reset``, ``step`` and ``seed`` (the upstream public methods)."""

    def __init__(self, **_options):
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)      # placeholder bounds
        self.observation_space = Box([-math.inf] * OBS_DIM, [math.inf] * OBS_DIM)  # placeholder dimension
        self._start_height = START_HEIGHT
        self._init_noise = True
        self._rng = random.Random(0)                                      # placeholder seed
        self._seed = 0                                                    # placeholder seed
        self._q = [0.0] * TOTAL_DOFS                                      # placeholder start positions
        self._dq = [0.0] * TOTAL_DOFS                                     # placeholder start velocities
        self._last_x = None
        self._steps = 0                                                   # placeholder counter
        self._done = False
        self._obs = [0.0] * OBS_DIM                                       # placeholder observation
        self.reset()

    # -- upstream surface -----------------------------------------------------
    def seed(self, seed=None):
        """``gym.utils.seeding.np_random(seed)`` stand-in (hopper_env_v3.py:312-315): set the RNG, return the seed."""
        seed = 0 if seed is None else int(seed)                           # placeholder default seed
        self._seed = seed
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        """``reset()`` of the upstream class (hopper_env_v3.py:108-191): no seed argument, returns the observation."""
        self._q = [0.0, self._start_height, 0.0, 0.0, 0.0, 0.0]          # placeholder start positions
        self._dq = [0.0] * TOTAL_DOFS                                     # placeholder start velocities
        if self._init_noise:
            self._q = [value + self._rng.uniform(-INIT_Q_NOISE, INIT_Q_NOISE) for value in self._q]
            self._dq = [value + self._rng.uniform(-INIT_DQ_NOISE, INIT_DQ_NOISE) for value in self._dq]
        self._last_x = None
        self._steps = 0
        self._done = False
        self._obs = self._observation()
        return list(self._obs)

    def step(self, a):
        """One fake transition: apply the bounded action, advance the kinematic state, return ``(obs, reward,
        done, info)`` in the upstream four-tuple shape (hopper_env_v3.py:283)."""
        if self._done:
            raise RuntimeError("the episode is done; reset before step")
        try:
            values = [float(value) for value in a]
        except (TypeError, ValueError) as exc:
            raise ValueError("the action must be a sequence of numbers") from exc
        if len(values) != ACTION_DIM:
            raise ValueError(f"the action must have {ACTION_DIM} elements")
        for value in values:
            if not math.isfinite(value):
                raise ValueError("the action values must be finite")
        act = [math.tanh(value) for value in values]

        old_ctrl_dq = [self._dq[3 + index] for index in range(ACTION_DIM)]
        for index in range(ACTION_DIM):
            joint = 3 + index
            acceleration = ACTION_GAIN * act[index] - JOINT_DAMPING * self._dq[joint]
            self._dq[joint] += CONTROL_PERIOD_S * acceleration
            self._q[joint] += CONTROL_PERIOD_S * self._dq[joint]
            if self._q[joint] < JOINT_LOW[index]:
                self._q[joint] = JOINT_LOW[index]
                self._dq[joint] = max(0.0, self._dq[joint])                # placeholder stop velocity
            elif self._q[joint] > JOINT_HIGH[index]:
                self._q[joint] = JOINT_HIGH[index]
                self._dq[joint] = min(0.0, self._dq[joint])                # placeholder stop velocity

        total = sum(act)
        self._dq[1] += CONTROL_PERIOD_S * (
            HEIGHT_SPRING * (self._start_height - self._q[1]) - HEIGHT_DAMPING * self._dq[1]
            + HEIGHT_ACTION_GAIN * total)
        self._q[1] += CONTROL_PERIOD_S * self._dq[1]
        self._dq[0] += CONTROL_PERIOD_S * (FORWARD_ACTION_GAIN * total - FORWARD_DAMPING * self._dq[0])
        self._q[0] += CONTROL_PERIOD_S * self._dq[0]

        self._steps += 1
        self._obs = self._observation()
        speed = 0.0 if self._last_x is None else (self._q[0] - self._last_x) / CONTROL_PERIOD_S  # placeholder
        self._last_x = self._q[0]
        q_scaled = [
            Q_SCALED_HALF_SPAN * (self._q[3 + index]
                                  - JOINT_MIDPOINT_FRACTION * (JOINT_LOW[index] + JOINT_HIGH[index]))
            / (JOINT_HIGH[index] - JOINT_LOW[index])
            for index in range(ACTION_DIM)
        ]
        joints_at_limit = sum(1 for value in q_scaled if abs(value) > JOINT_LIMIT_FRACTION)
        dq = [self._dq[3 + index] for index in range(ACTION_DIM)]
        acceleration_penalty = min(
            sum(abs(current - old) for current, old in zip(dq, old_ctrl_dq)) * ACCEL_PENALTY_WEIGHT,
            ACCEL_PENALTY_CAP)
        reward = (ALIVE_BONUS + speed - ACTION_PENALTY * sum(value * value for value in values)
                  - JOINT_LIMIT_PENALTY * joints_at_limit - acceleration_penalty)
        done = not self._not_done()
        self._done = done
        return list(self._obs), float(reward), bool(done), {"sas_window": [list(self._obs)]}

    # -- internals ------------------------------------------------------------
    def _observation(self):
        """The upstream layout (hopper.py:167-175): positions then velocities, last four velocities scaled."""
        return [
            self._q[1], self._q[2], self._q[3], self._q[4], self._q[5],
            self._dq[0], self._dq[1], self._dq[2],
            OBS_VELOCITY_SCALE * self._dq[3], OBS_VELOCITY_SCALE * self._dq[4],
            OBS_VELOCITY_SCALE * self._dq[5],
        ]

    def _not_done(self):
        """The upstream termination test (hopper_env_v3.py:281) against the fake's kinematic state."""
        return all(abs(self._dq[3 + index]) < DONE_DQ for index in range(ACTION_DIM)) \
            and DONE_HEIGHT_LOW < self._q[1] < DONE_HEIGHT_HIGH
