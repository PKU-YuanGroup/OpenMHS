"""Fake backend of the gym-quadruped driver: a pure Python stand-in for ``QuadrupedEnv``.

Why a fake: the gate runs without the upstream package (it needs ``mujoco``, ``numpy``, ``gymnasium`` and ``scipy``,
pyproject.toml:1-20), and package code never imports the clone.  The fake has the public surface of
``gym_quadruped.quadruped_env:QuadrupedEnv`` that the Gymnasium bridge uses (``reset``, ``step``, ``close``,
``action_space``, ``observation_space``; gate G7) and returns the same shapes: a dict of the default observation names
and a five-tuple from ``step``.  Every number below is test data, not a device fact: the lines are marked
``# placeholder`` and are never copied into a Fact, a Limit or the reference.

What this is not: the upstream MuJoCo simulator.  It has no contacts, friction, actuator model, sensors or terrain;
joint velocities follow the commanded torques through one scalar integration step and the base does not move.  The
fake never terminates or truncates.  All differences are listed in the fidelity ``gaps`` of the driver.

Nothing here talks to a device.
"""

import math
from random import Random

# The go2 has twelve torque actuators and a nineteen-value qpos (seven base values plus twelve joints); these shapes
# are test data chosen to match the model family, not asserted as device facts.
NU = 12                                           # placeholder
NV = 18                                           # placeholder
NQ = 19                                           # placeholder
DT = 0.002                                        # placeholder: seconds per fake integration step
START_HIP_HEIGHT = 0.28                           # placeholder
POSITION_NOISE = 0.01                             # placeholder: radians of joint-position noise
VELOCITY_NOISE = 0.05                             # placeholder: joint-velocity noise
START_QPOS = [0.0, 0.0, START_HIP_HEIGHT, 1.0, 0.0, 0.0, 0.0] + [0.0] * NU   # placeholder
# The fake's observation keys are the upstream default observation names (quadruped_env.py:80).
OBSERVATION_SHAPES = {
    "qpos": NQ,
    "qvel": NV,
    "tau_ctrl_setpoint": NU,
    "feet_pos:base": 12,
    "feet_vel:base": 12,
}


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the member spaces by name."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _space(low, high):
    return Box(low, high)


class FakeQuadrupedEnv:
    """A deterministic stand-in for ``QuadrupedEnv``: ``reset(...)`` and ``step(action)`` like the environment."""

    def __init__(self, robot="go2", scene="flat", **options):
        self.robot_name = robot
        self.scene = scene
        # The upstream environment derives its torques from actuator_forcerange and actuator_forcelimited
        # (quadruped_env.py:224-235); the fake accepts any torque and integrates it, so its action space is unbounded.
        # placeholder: the bounds are test data of this fake.
        self.action_space = _space([-math.inf] * NU, [math.inf] * NU)
        self.observation_space = Dict({
            name: _space([-math.inf] * shape, [math.inf] * shape)
            for name, shape in OBSERVATION_SHAPES.items()
        })
        self._rng = Random()
        self._qpos = list(START_QPOS)
        self._qvel = [0.0] * NV
        self._ctrl = [0.0] * NU
        self._time = 0.0
        self._tick = 0

    def _observation(self):
        return {
            "qpos": list(self._qpos),
            "qvel": list(self._qvel),
            "tau_ctrl_setpoint": list(self._ctrl),
            "feet_pos:base": [0.0] * 12,          # placeholder: the fake does not model the feet
            "feet_vel:base": [0.0] * 12,          # placeholder
        }

    def reset(self, qpos=None, qvel=None, seed=None, random=True, options=None):
        """Reset like ``QuadrupedEnv.reset``: reseed, perturb the joints, return the observation dict (no info tuple)."""
        options = {} if options is None else dict(options)
        if seed is not None:
            self._rng = Random(seed)
        if qpos is None and qvel is None:
            self._qpos = list(START_QPOS)
            self._qvel = [0.0] * NV
            if random:
                amplitude = options.get("angle_sweep", POSITION_NOISE)   # placeholder amplitude
                self._qpos[7:] = [value + self._rng.uniform(-amplitude, amplitude) for value in self._qpos[7:]]
                self._qvel[6:] = [value + self._rng.uniform(-VELOCITY_NOISE, VELOCITY_NOISE)
                                  for value in self._qvel[6:]]
        else:
            self._qpos = list(self._qpos if qpos is None else qpos)
            self._qvel = list(self._qvel if qvel is None else qvel)
        self._ctrl = [0.0] * NU
        self._time = 0.0
        self._tick = 0
        return self._observation()

    def step(self, action):
        """Apply the torques, advance one fake integration step and return the environment's five-tuple."""
        self._ctrl = [float(value) for value in action]
        self._qvel[6:] = [velocity + torque * DT
                          for velocity, torque in zip(self._qvel[6:], self._ctrl)]
        self._qpos[7:] = [position + velocity * DT
                          for position, velocity in zip(self._qpos[7:], self._qvel[6:])]
        self._time += DT
        info = {"time": self._time, "step_num": self._tick, "invalid_contacts": {}}
        self._tick += 1
        return self._observation(), 0.0, False, False, info

    def close(self):
        """The upstream close() closes a viewer; the fake has none."""
