"""Fake backend of the SoftGym PourWater driver: a pure-Python stand-in for ``PourWaterPosControlEnv``.

Why a fake: the upstream environment imports pyflex, the compiled Nvidia FleX binding
(``softgym/envs/flex_env.py:12-15``), numpy, gym and shapely (``softgym/envs/pour_water.py:1-8``), and package code
never imports the clone.  This module re-implements the observable state machine of the ``key_point`` observation
mode and the ``rotation_bottom`` action mode of ``PourWaterPosControlEnv`` (``softgym/envs/pour_water.py:359-372``
and ``:413-440``) plus the ``FlexEnv.step`` loop over ``action_repeat`` and the horizon test
(``softgym/envs/flex_env.py:177-197``).  Every rule and constant below cites the line of the clone at the pinned
commit (bb383f64cd488062587714abbae38f27ed9f2457).

The public members are the ones ``PourWaterPosControlEnv`` inherits from ``gym.Env`` and overrides (``reset``,
``step`` and ``close``; gate G7), and the space classes duck-type ``gym.spaces.Box`` (the bridge reads ``low``,
``high`` and ``shape``).

What this is not: the upstream environment.  There is no pyflex, no fluid particle simulation, no contact handling,
no cached start-state pickle and no rendering.  The observation carries the 13 key-point values of
``pour_water.py:368-370``, but the water fractions and the water height are an analytic placeholder and not a
particle count.  The driver's fidelity ``gaps`` list all of this.  Nothing here talks to a device.
"""

import math
import random

# softgym/envs/pour_water.py:52-53: the per-element bounds of the action space.
ACTION_LOW = (-0.01, -0.01, -0.015)
ACTION_HIGH = (0.01, 0.01, 0.015)
# softgym/envs/flex_env.py:26: the default action_repeat of FlexEnv.
ACTION_REPEAT = 8                                        # placeholder
# softgym/__init__.py:26: the horizon of the registered PourWaterPosControl-v0 environment.
HORIZON = 75                                             # placeholder
# softgym/envs/pour_water.py:59-60: reward_min and reward_max.
REWARD_MIN = 0.0                                         # placeholder
REWARD_MAX = 1.0                                         # placeholder
# softgym/envs/pour_water.py:35: the key_point observation has 13 elements.
KEY_POINT_DIM = 13                                       # placeholder
# softgym/envs/pour_water.py:368-370: the fixed shape values of the two glasses.  These are scene configuration
# stand-ins, not a device bound.
GLASS_DIS_X = 0.1                                        # placeholder
GLASS_DIS_Z = 0.1                                        # placeholder
GLASS_HEIGHT = 0.6                                       # placeholder
GLASS_DISTANCE = 1.0                                     # placeholder
POURED_HEIGHT = 0.6                                      # placeholder
POURED_GLASS_DIS_X = 0.1                                 # placeholder
POURED_GLASS_DIS_Z = 0.1                                 # placeholder
WATER_HEIGHT = 0.05                                      # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: one lower and one upper bound per flattened element."""

    def __init__(self, low, high, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype

    def contains(self, value):
        try:
            values = list(value)
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            float(lo) <= float(item) <= float(hi) for lo, hi, item in zip(self.low, self.high, values))


class FakePourWaterEnv:
    """``PourWaterPosControlEnv`` without pyflex, numpy, gym or shapely: ``reset``, ``step`` and ``close``.

    The observation is the 13-element ``key_point`` vector of ``pour_water.py:368-370``:
    ``[glass_x, glass_y, glass_rotation, glass_dis_x, glass_dis_z, height, glass_distance + glass_x,
    poured_height, poured_glass_dis_x, poured_glass_dis_z, water_height, in_poured_glass, in_control_glass]``.
    The action is the 3-element increment ``[dx, dy, dtheta]`` of ``pour_water.py:413-424``.
    """

    metadata = {"render.modes": ["human", "rgb_array"]}  # flex_env.py:36

    def __init__(self, observation_mode="key_point", action_mode="rotation_bottom", horizon=HORIZON,
                 action_repeat=ACTION_REPEAT, render_mode="fluid", **_options):
        if observation_mode not in ("cam_rgb", "point_cloud", "key_point"):
            raise ValueError(f"unsupported observation_mode {observation_mode!r}")
        if action_mode not in ("rotation_bottom", "rotation_top"):
            raise ValueError(f"unsupported action_mode {action_mode!r}")
        if render_mode not in ("particle", "fluid"):
            raise ValueError(f"unsupported render_mode {render_mode!r}")
        self.observation_mode = observation_mode
        self.action_mode = action_mode
        self.horizon = int(horizon)
        self.action_repeat = int(action_repeat)
        self.render_mode = 0 if render_mode == "particle" else 1   # fluid_env.py:12
        # pour_water.py:42: the key_point observation space is 13 floats bounded by +-inf.
        self.observation_space = Box([-math.inf] * KEY_POINT_DIM, [math.inf] * KEY_POINT_DIM)
        # pour_water.py:49-54: the action space is the 3-element Box of rotation_bottom/rotation_top.
        self.action_space = Box(ACTION_LOW, ACTION_HIGH)
        # flex_env.py:42-44: time_step, action_repeat and the configured horizon.
        self.time_step = 0
        self.inner_step = 0
        self.performance_init = None
        self._rng = random.Random()
        self._state = None
        self._closed = False

    # -- state -----------------------------------------------------------------------------------------------
    def _reset_state(self, seed):
        """Placeholder start state of one episode; the real environment loads a cached pyflex state."""
        if seed is not None:
            self._rng = random.Random(seed)
        self.glass_x = self._rng.uniform(-0.001, 0.001)        # placeholder
        self.glass_y = 0.0 if self.action_mode == "rotation_bottom" else 0.5 * 0.045 + 0.6  # placeholder
        self.glass_rotation = self._rng.uniform(-0.001, 0.001)  # placeholder
        self.in_poured = 0.0                                   # placeholder
        self.in_control = 1.0                                  # placeholder
        self.water_height = WATER_HEIGHT                       # placeholder
        self.time_step = 0
        self.inner_step = 0
        self.performance_init = None
        self._state = [self.glass_x, self.glass_y, self.glass_rotation]

    def _get_obs(self):
        """The key_point vector of ``pour_water.py:368-372`` (without the empty particle prefix)."""
        return [
            self.glass_x, self.glass_y, self.glass_rotation,
            GLASS_DIS_X, GLASS_DIS_Z, GLASS_HEIGHT,
            GLASS_DISTANCE + self.glass_x,
            POURED_HEIGHT, POURED_GLASS_DIS_X, POURED_GLASS_DIS_Z,
            self.water_height, self.in_poured, self.in_control,
        ]

    def _get_info(self):
        """The info dict of ``pour_water.py:394-411`` with the reward range of lines 59-60."""
        performance = float(self.in_poured)
        performance_init = performance if self.performance_init is None else self.performance_init
        if REWARD_MAX == performance_init:
            normalized = 0.0
        else:
            normalized = (performance - performance_init) / (REWARD_MAX - performance_init)
        return {"normalized_performance": normalized, "performance": performance}

    def _step_once(self, action):
        """One internal ``_step`` of ``pour_water.py:413-440``: the increment moves the pouring glass."""
        dx, dy, dtheta = (float(action[0]), float(action[1]), float(action[2]))
        self.glass_x += dx
        self.glass_y += dy
        self.glass_rotation += dtheta
        # Placeholder analytic stand-in for the fluid update of pyflex.step (pour_water.py:438): water leaves the
        # control glass in proportion to how far the glass has been tilted, never more than all of it.
        tilt = min(1.0, abs(self.glass_rotation) / (math.pi / 2.0))   # placeholder
        moved = min(self.in_control, 0.01 * tilt)                     # placeholder
        self.in_control = max(0.0, self.in_control - moved)
        self.in_poured = min(1.0, self.in_poured + moved)
        self.water_height = max(0.0, WATER_HEIGHT * self.in_control)  # placeholder
        self.inner_step += 1

    # -- gym.Env surface (flex_env.py:153-197) ---------------------------------------------------------------
    def reset(self, seed=None, options=None, **kwargs):
        """``FlexEnv.reset`` (``flex_env.py:153-175``): start an episode and return only the observation.

        The legacy ``gym`` API of the clone has no ``seed``/``options`` arguments; the bridge passes them, so this
        fake accepts them and uses the seed for its placeholder start state only.
        """
        self._reset_state(seed)
        return self._get_obs()

    def step(self, action, record_continuous_video=False, img_size=None):
        """``FlexEnv.step`` (``flex_env.py:177-197``): repeat the action, then return (obs, reward, done, info)."""
        for _ in range(self.action_repeat):
            self._step_once(action)
        obs = self._get_obs()
        reward = float(self.in_poured)                 # pour_water.py:377-392
        info = self._get_info()
        self.time_step += 1                            # flex_env.py:190
        done = bool(self.time_step >= self.horizon)    # flex_env.py:192-194
        return obs, reward, done, info

    def close(self):
        self._closed = True
        self._state = None
