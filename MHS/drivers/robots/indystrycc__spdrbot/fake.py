"""Fake backend of the SPDR Bot Isaac Lab driver: a pure Python analytic stand-in.

Why a fake: the upstream environment needs Isaac Sim 4.5, Isaac Lab, ``isaaclab_assets`` and a GPU
(``spdrbot3_direct_project/README.md:15-26``, ``spdrbot3_direct_project/source/spdrbot3/setup.py:38-42``),
and package code never imports or runs the clone.  The acceptance gate therefore runs this one-environment
stand-in for ``spdrbot3.tasks.direct.spdrbot3.spdrbot3_env:Spdrbot3Env``.  It keeps the public members the bridge
uses (``reset``, ``step`` and ``close``; gate G7) and duck-types the Gymnasium spaces it reads
(``action_space``, ``observation_space``, ``Box``, ``Dict``).

Every constant that is not test data cites the clone at commit 70084cd435e9871b3db69280cce49a4fb2246664.  The
start positions, the root velocities, the projected gravity, the joint velocities, the reward velocities and the
joint update law are placeholders marked ``# placeholder``; they are never facts, limits or references.  The
fidelity gaps in ``driver.py`` disclose them.

What this is not: the simulator.  There is no PhysX, no contact sensor, no actuator or sensor model, no
rendering and no vectorization.  The action is accepted in the same twelve-value order and multiplied by the
upstream ``action_scale`` of 1; the twelve joints follow the requested position directly.  ``terminated`` is
always false because the death check needs contact forces the fake does not model.  Nothing here talks to a
device.
"""

import math
import random

# spdrbot3_env_cfg.py:53-55: action_scale = 1, action_space = 12, observation_space = 48.
ACTION_SCALE = 1
ACTION_DIM = 12
OBS_DIM = 48
# spdrbot3_env_cfg.py:51-52 and :59-60: episode_length_s = 20.0, decimation = 4, sim dt = 1/200 s.
EPISODE_LENGTH_S = 20.0
DECIMATION = 4
SIM_DT_S = 1.0 / 200.0
# placeholder: this fake chooses ceil(episode_length_s / (sim.dt * decimation)) = 1000 for max_episode_length.
# The external base's calculation is outside this clone and unverified.  spdrbot3_env.py:139 supplies only the
# comparison episode_length_buf >= max_episode_length - 1; 999 is this fake's chosen timeout.
MAX_EPISODE_LENGTH = math.ceil(EPISODE_LENGTH_S / (SIM_DT_S * DECIMATION))
MAX_EPISODE_STEPS = MAX_EPISODE_LENGTH - 1
# spdrbot3_env_cfg.py:101-108: the reward scales of the eight terms.
LIN_VEL_REWARD_SCALE = 5.0
YAW_RATE_REWARD_SCALE = 0.5
ACTION_RATE_REWARD_SCALE = -0.01


def _fill(value, shape):
    """A nested list of ``value`` with the given shape (spaces use nested low/high lists)."""

    if not shape:
        return value
    return [_fill(value, shape[1:]) for _ in range(int(shape[0]))]


def _flatten(value):
    """The flat list of numbers in an action array, in row-major order."""

    raw = value.tolist() if hasattr(value, "tolist") else value
    out = []

    def walk(item):
        if isinstance(item, (list, tuple)):
            for element in item:
                walk(element)
        else:
            out.append(float(item))

    walk(raw)
    return out


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the members ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape):
        self.shape = tuple(int(item) for item in shape)
        self.low = _fill(low, self.shape)
        self.high = _fill(high, self.shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = "dict"


class FakeSpdrbot3Env:
    """One environment of the SPDR Bot direct task, without Isaac Sim, Isaac Lab or numpy."""

    def __init__(self, cfg=None, render_mode=None, **kwargs):
        if render_mode is not None:
            raise ValueError("the fake SPDR Bot environment cannot render; use render_mode=None")
        del kwargs
        # The upstream constructor takes a Spdrbot3EnvCfg; the fake records it and does not use it.
        self.cfg = cfg
        # spdrbot3_env_cfg.py:54 and the external DirectRLEnv: a 12-value Box whose bounds are not in this clone.
        # placeholder: the unbounded values and leading 1 are this fake's one-environment batch choices;
        # the cfg defaults to 200 environments at :92, and the external base's bounds were not verified.
        self.action_space = Box(-math.inf, math.inf, (1, ACTION_DIM))
        # spdrbot3_env.py:79-98 returns a {"policy": ...} dict; the upstream observation_space is the external
        # base's batched policy Box.  The fake declares the structure it actually returns (see fidelity gaps).
        self.observation_space = Dict({"policy": Box(-math.inf, math.inf, (1, OBS_DIM))})
        self._rng = random.Random()
        self._commands = [0.0, 0.0, 0.0]           # placeholder until the first reset samples them
        self._joint_pos = [0.0] * ACTION_DIM       # placeholder: the upstream defaults come from SPDRBOT_CFG
        self._joint_vel = [0.0] * ACTION_DIM       # placeholder
        self._action = [0.0] * ACTION_DIM          # placeholder
        self._previous_action = [0.0] * ACTION_DIM  # placeholder
        self._episode_length_buf = 0               # placeholder: the upstream randomizes it on a full reset
        self._episode = 0
        self._started = False
        self._closed = False

    def reset(self, seed=None, options=None):
        """Bridge-facing reset of the fake episode; the external base implementation was not inspected."""
        del options   # spdrbot3_env.py:147-177 does not read the reset options
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        # spdrbot3_env.py:157-158: a full reset samples the three commands uniformly from -1.0 to 1.0.
        self._commands = [self._rng.uniform(-1.0, 1.0) for _ in range(3)]
        self._joint_pos = [0.0] * ACTION_DIM       # placeholder: the upstream resets to SPDRBOT_CFG defaults
        self._joint_vel = [0.0] * ACTION_DIM       # placeholder
        self._action = [0.0] * ACTION_DIM          # placeholder
        self._previous_action = [0.0] * ACTION_DIM  # placeholder
        # placeholder: the upstream randomizes episode_length_buf on a full reset (spdrbot3_env.py:152-154);
        # the fake starts every episode at 0 so its first timeout is exactly 999 steps.
        self._episode_length_buf = 0
        self._episode += 1
        self._started = True
        return self._observation(), {}

    def step(self, action):
        """The native vectorized ``step(action)`` with a five-tuple result, without physics."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if not self._started:
            raise AssertionError("Call reset before using step method.")
        values = _flatten(action)
        if len(values) != ACTION_DIM:
            raise AssertionError(f"{len(values)} action values; expected {ACTION_DIM}")
        # spdrbot3_env.py:72-77: the action is scaled and added to the default joint positions before the target
        # is written.  The fake's defaults are the placeholder zero vector, and the joint follows the target.
        self._previous_action = list(self._action)
        self._action = [value * ACTION_SCALE for value in values]
        self._joint_pos = list(self._action)       # placeholder: a direct position target, not actuator dynamics
        self._joint_vel = [0.0] * ACTION_DIM       # placeholder: no physics
        self._episode_length_buf += 1
        # spdrbot3_env.py:139: time_out = episode_length_buf >= max_episode_length - 1.
        truncated = self._episode_length_buf >= MAX_EPISODE_STEPS
        # placeholder: the root velocities, torques, joint accelerations and gravity vector are not simulated, so
        # the upstream reward terms are evaluated on zeros.  spdrbot3_env.py:100-136 and cfg:101-108.
        lin_vel_error = sum(value * value for value in self._commands[:2])
        yaw_rate_error = self._commands[2] * self._commands[2]
        action_rate = sum((now - before) ** 2 for now, before in zip(self._action, self._previous_action))
        reward = (
            math.exp(-lin_vel_error / 0.25) * LIN_VEL_REWARD_SCALE
            + math.exp(-yaw_rate_error / 0.25) * YAW_RATE_REWARD_SCALE
            + action_rate * ACTION_RATE_REWARD_SCALE
        ) * (SIM_DT_S * DECIMATION)
        # placeholder: no contact sensor is modelled, so the contact-force death check (spdrbot3_env.py:138-145)
        # never fires and terminated stays false.
        return self._observation(), reward, False, truncated, {}

    def close(self):
        """Release the fake state; the native close tears down the simulator."""
        self._closed = True
        self._started = False

    def _observation(self):
        """The native policy observation, a 48-value placeholder vector with the upstream layout."""
        # spdrbot3_env.py:81-96: root linear velocity (3), root angular velocity (3), projected gravity (3),
        # commands (3), joint positions minus defaults (12), joint velocities (12) and actions (12).
        policy = (
            [0.0, 0.0, 0.0]                       # placeholder: root linear velocity
            + [0.0, 0.0, 0.0]                     # placeholder: root angular velocity
            + [0.0, 0.0, -1.0]                    # placeholder: projected gravity of an upright base
            + list(self._commands)
            + list(self._joint_pos)               # placeholder: zero defaults
            + list(self._joint_vel)               # placeholder
            + list(self._action)
        )
        return {"policy": [policy]}
