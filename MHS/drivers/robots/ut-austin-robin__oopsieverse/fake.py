"""Fake backend for the OopsieVerse ``DamageableCloseDrawer`` environment.

The acceptance gate runs where RoboCasa, Robosuite, MuJoCo and gymnasium are not installed (the clone's own
``install.py:130-150`` clones Robosuite and RoboCasa), and package code never imports the clone.  This module is
therefore a pure Python stand-in for the environment named by ``native``: it exposes ``reset``, ``step`` and
``close`` (gate G7) and the two spaces the Gymnasium bridge reads (``action_space``, ``observation_space``).

It reproduces only the parts of the clone that are stated there:

* the drawer starts with a door state sampled from 0.95 to 1.0 (``oopsiebench/envs/robocasa/close_drawer.py:87-89``);
* the reward is ``10 * (1 - mean door state)`` (``close_drawer.py:123-129``);
* the success check needs a door state at most 0.05 (``close_drawer.py:131-136``);
* ``reset`` returns ``(observation, info)`` and ``step`` returns ``(observation, reward, done, info)``
  (``damagesim/robosuite/damageable_env.py:382-409``);
* the observation carries a float32 ``health`` vector (``damagesim/core/damageable_env.py:259-269``) and a
  ``robot0_proprio`` vector built from 7 joint sines, 7 joint cosines, 3 end-effector positions, 4 quaternions
  and 2 gripper positions (``damagesim/robosuite/damageable_env.py:289-301``).

Everything else is test data, marked ``# placeholder`` and never used as a Fact or a Limit: the seven-element
action vector, the end-effector step, the door travel per step, the start pose and the health damage rate.  The
real PandaOmron composite-controller action vector is assembled at run time
(``scripts/teleop_robocasa.py:838-845``) and its size and bounds are not stated in the clone, so the fake serves an
unbounded action space rather than inventing a bound.  The fake has no contacts, friction, actuators, cameras,
rendering or Robosuite/MuJoCo physics and was not compared with an upstream run.

Nothing here talks to hardware.
"""

import math
import random

# close_drawer.py:88: _setup_scene sets the drawer door state to between 0.95 and 1.0 (open at episode start).
DRAWER_OPEN_MIN = 0.95
DRAWER_OPEN_MAX = 1.0
# close_drawer.py:135: a drawer joint position above 0.05 fails the success check.
SUCCESS_DOOR_STATE = 0.05
# close_drawer.py:127: the reward is 10.0 * (1.0 - mean door state).
REWARD_SCALE = 10.0
# docs/damagesim.md:84: health is a per-link nonnegative scalar whose full value is 100.
HEALTH_FULL = 100.0

# The fake's own test data, not facts or limits.
N_ACTION = 7                                     # placeholder: the real composite-controller size is not in the clone
EEF_STEP = 0.01                                  # placeholder: metres of end-effector travel per unit action
DOOR_CLOSE_PER_STEP = 0.1                        # placeholder: door travel per unit closing action
HEALTH_DAMAGE_PER_UNIT = 0.01                    # placeholder: health lost per unit action magnitude
GRIPPER_OPEN = -1.0                               # placeholder
START_EEF = [0.0, 0.0, 0.0]                      # placeholder
START_QUAT = [1.0, 0.0, 0.0, 0.0]                # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a low and a high bound per flattened element."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named member spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _clamp(value, low=-1.0, high=1.0):
    """Clamp a normalized controller input; the teleoperation path clips every non-absolute part."""
    return max(low, min(high, float(value)))


class FakeCloseDrawerEnv:
    """A reduced, analytic stand-in for ``DamageableCloseDrawer``.

    ``reset(seed=None, options=None)`` re-samples the initial door state; ``step(action)`` advances a scalar door
    state and returns the legacy four-tuple the upstream damageable environment returns.  The bridge calls
    ``reset`` with a seed because this fake accepts one; the upstream ``reset`` takes no seed argument and the clone
    defines no seed setter, which the driver records as a fidelity gap.
    """

    def __init__(self):
        # The action vector is test data: an unbounded Box, so the bridge enforces no invented bound.
        infinite = [math.inf] * N_ACTION
        self.action_space = Box([-value for value in infinite], infinite, (N_ACTION,))
        self.observation_space = Dict(
            {
                "robot0_eef_pos": Box([-math.inf] * 3, [math.inf] * 3, (3,)),
                "robot0_gripper_qpos": Box([-math.inf] * 2, [math.inf] * 2, (2,)),
                "robot0_proprio": Box([-math.inf] * 23, [math.inf] * 23, (23,)),
                "health": Box([0.0], [HEALTH_FULL], (1,)),
            }
        )
        self._rng = random.Random()
        self._door_state = None
        self._phase = 0.0                                                        # placeholder
        self._eef_pos = list(START_EEF)
        self._gripper = GRIPPER_OPEN
        self._health = [HEALTH_FULL]
        self._steps = 0
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Start an episode and return ``(observation, info)``, as the upstream ``reset`` does."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._door_state = self._rng.uniform(DRAWER_OPEN_MIN, DRAWER_OPEN_MAX)   # close_drawer.py:88
        self._phase = self._rng.uniform(0.0, 2.0 * math.pi)                     # placeholder scene randomness
        self._eef_pos = list(START_EEF)                                          # placeholder
        self._gripper = GRIPPER_OPEN                                              # placeholder
        self._health = [HEALTH_FULL]                                             # docs/damagesim.md:84
        self._steps = 0
        return self._observation(), {"damage_info": {}, "obs_info": {}}

    def step(self, action):
        """Advance one control step and return ``(observation, reward, done, info)`` (damageable_env.py:400-409)."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if self._door_state is None:
            raise RuntimeError("reset() must be called before step()")
        values = [float(value) for value in action]
        if len(values) != N_ACTION:
            raise ValueError(f"the fake close_drawer action has {N_ACTION} values, got {len(values)}")
        # io_utils.py:154-156 clips every non-absolute controller part to [-1, 1].
        values = [_clamp(value) for value in values]
        self._eef_pos = [self._eef_pos[i] + EEF_STEP * values[i] for i in range(3)]   # placeholder gain
        self._gripper = values[6]                                                     # placeholder slot
        closing = max(0.0, -values[0])
        self._door_state = max(0.0, self._door_state - DOOR_CLOSE_PER_STEP * closing)  # placeholder gain
        self._health = [max(0.0, self._health[0] - HEALTH_DAMAGE_PER_UNIT * sum(abs(v) for v in values))]
        self._steps += 1

        reward = REWARD_SCALE * (1.0 - self._door_state)                             # close_drawer.py:127
        # close_drawer.py:135: the drawer is closed when every door joint is at most 0.05.  The gripper-distance
        # part of _check_success (close_drawer.py:138-142) is not modelled by this scalar fake.
        done = self._door_state <= SUCCESS_DOOR_STATE
        return self._observation(), float(reward), bool(done), {"damage_info": {}, "obs_info": {}}

    def close(self):
        self._closed = True

    def _observation(self):
        """The reduced observation dict: proprio values plus the damage health vector."""
        # damageable_env.py:291-296 lists the five parts in this order: 7 + 7 + 3 + 4 + 2 = 23 values.
        joint_sin = [math.sin(self._phase + 0.1 * self._steps + index) for index in range(7)]      # placeholder
        joint_cos = [math.cos(self._phase + 0.1 * self._steps + index) for index in range(7)]      # placeholder
        gripper = [self._gripper, -self._gripper]
        proprio = joint_sin + joint_cos + list(self._eef_pos) + list(START_QUAT) + gripper
        return {
            "robot0_eef_pos": list(self._eef_pos),
            "robot0_gripper_qpos": gripper,
            "robot0_proprio": proprio,
            "health": list(self._health),
        }
