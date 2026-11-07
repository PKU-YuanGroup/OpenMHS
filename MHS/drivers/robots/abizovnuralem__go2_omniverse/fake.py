"""Fake backend of the go2_omniverse driver: a pure Python kinematic stand-in for the Isaac Lab Go2 task.

Why a fake: the acceptance gate runs without Isaac Sim, Isaac Lab, ``gymnasium``, ``torch`` or a GPU (JAZZY.md:68-69
installs Isaac Sim 5.0 and Isaac Lab 0.54.3), and package code never imports the clone.  The upstream script creates
the environment with ``gym.make("Isaac-Velocity-Rough-Unitree-Go2-v0", cfg=UnitreeGo2CustomEnvCfg())``
(omniverse_sim.py:19 and :384) and the environment class lives in Isaac Lab, outside the clone.  This module therefore
models the *contract* the clone configures: a policy observation group named ``policy`` (omniverse_sim.py:407), the
observation-term order of custom_rl_env.py:167-183, the joint-position action scale (custom_rl_env.py:330), the
20 s time-out (custom_rl_env.py:298) and the 20 ms policy step (custom_rl_env.py:296 and :300).

What this is not: the upstream task.  There is no rigid-body dynamics, no contact sensor, no actuator model and no
height ray caster.  The base is moved by a placeholder kinematic mapping of the joint targets, the reward is a constant
placeholder, and only the time-out truncates an episode; the illegal-contact termination of custom_rl_env.py:255-257 is
not modelled.  Every number that is not cited above is marked ``# placeholder`` (test data, never a fact or a limit).
The fake was never compared with an Isaac Sim run.

The public members are the Gymnasium environment interface the bridge uses (``reset``, ``step``, ``close``; gate G7),
and the two space classes duck-type ``gymnasium.spaces.Box`` and ``gymnasium.spaces.Dict`` (the bridge reads ``low``,
``high``, ``shape`` and ``spaces``).

Nothing here talks to a device.
"""

import math
import random

# custom_rl_env.py:296 and :300: decimation 4 with sim.dt 0.005 s, so one policy step is 0.02 s.
DECIMATION = 4
SIM_DT_S = 0.005
STEP_DT_S = DECIMATION * SIM_DT_S
# custom_rl_env.py:298: episode_length_s 20.0.
EPISODE_LENGTH_S = 20.0
MAX_EPISODE_STEPS = int(round(EPISODE_LENGTH_S / STEP_DT_S))  # 1000 policy steps
# custom_rl_env.py:330: UnitreeGo2CustomEnvCfg reduces the joint-position action scale to 0.25.
ACTION_SCALE = 0.25
# custom_rl_env.py:118-119: GridPatternCfg(resolution=0.1, size=[1.6, 1.0]).
SCAN_RESOLUTION_M = 0.1
SCAN_SIZE_M = (1.6, 1.0)
SCAN_COLUMNS = int(round(SCAN_SIZE_M[0] / SCAN_RESOLUTION_M)) + 1  # 17
SCAN_ROWS = int(round(SCAN_SIZE_M[1] / SCAN_RESOLUTION_M)) + 1  # 11
SCAN_POINTS = SCAN_COLUMNS * SCAN_ROWS  # 187
# custom_rl_env.py:181: the height scan is clipped to (-1.0, 1.0).
SCAN_CLIP = 1.0
# custom_rl_env.py:172: projected_gravity is corrupted with uniform noise in (-0.05, 0.05).
GRAVITY_NOISE = 0.05
# placeholder: the Go2 leg joint count comes from the external UNITREE_GO2_CFG (custom_rl_env.py:326), not the clone.
N_JOINTS = 12  # placeholder
#: concatenated observation terms of custom_rl_env.py:167-183, in their preserved order
OBSERVATION_TERMS = (
    ("base_lin_vel", 3),
    ("base_ang_vel", 3),
    ("projected_gravity", 3),
    ("velocity_commands", 3),
    ("joint_pos", N_JOINTS),
    ("joint_vel", N_JOINTS),
    ("actions", N_JOINTS),
    ("height_scan", SCAN_POINTS),
)
OBSERVATION_SIZE = sum(size for _name, size in OBSERVATION_TERMS)  # 235
# placeholder: the default base height of the kinematic stand-in.
BASE_HEIGHT_M = 0.4  # placeholder
# placeholder: reset spreads of the kinematic stand-in.
RESET_JOINT_SPREAD = 0.05  # placeholder
RESET_YAW_SPREAD = 0.05  # placeholder
# placeholder: the height scan of the kinematic stand-in is a static sine ridge.
SCAN_AMPLITUDE_M = 0.05  # placeholder
SCAN_WAVELENGTH_POINTS = 7.0  # placeholder
# placeholder: the constant reward of the kinematic stand-in (the real reward is the sum of the configured terms).
REWARD = 0.0  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named member spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeGo2Env:
    """The Isaac Lab Go2 velocity task without Isaac Sim: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, **_options):
        unbounded = float("inf")
        # The manager-based Isaac Lab environment exposes one unbounded Box action for the joint-position targets;
        # the clone states the action term and its scale, not a numeric action bound.
        self.action_space = Box([-unbounded] * N_JOINTS, [unbounded] * N_JOINTS, (N_JOINTS,))
        # omniverse_sim.py:407 reads the observation group "policy"; the fake uses the concatenated terms.
        self.observation_space = Dict(
            {"policy": Box([-unbounded] * OBSERVATION_SIZE, [unbounded] * OBSERVATION_SIZE, (OBSERVATION_SIZE,))}
        )
        self._rng = random.Random()
        self._initialise(seed=None, draw=False)
        self._closed = False

    def _initialise(self, *, seed, draw):
        """Put the stand-in at its start state; draw the seeded values when the reset asks for them."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._steps = 0
        self._x = 0.0  # placeholder
        self._y = 0.0  # placeholder
        self._yaw = self._rng.uniform(-RESET_YAW_SPREAD, RESET_YAW_SPREAD) if draw else 0.0  # placeholder
        self._vx = 0.0  # placeholder
        self._vy = 0.0  # placeholder
        self._yaw_rate = 0.0  # placeholder
        self._base_height = BASE_HEIGHT_M  # placeholder
        self._joint_pos = [self._rng.uniform(-RESET_JOINT_SPREAD, RESET_JOINT_SPREAD)
                           for _ in range(N_JOINTS)] if draw else [0.0] * N_JOINTS  # placeholder
        self._joint_vel = [0.0] * N_JOINTS  # placeholder
        self._last_action = [0.0] * N_JOINTS  # placeholder
        self._gravity = self._draw_gravity()

    def _draw_gravity(self):
        """Projected gravity of an upright base, with the uniform noise of custom_rl_env.py:172."""
        return [
            self._rng.uniform(-GRAVITY_NOISE, GRAVITY_NOISE),
            self._rng.uniform(-GRAVITY_NOISE, GRAVITY_NOISE),
            -1.0 + self._rng.uniform(-GRAVITY_NOISE, GRAVITY_NOISE),
        ]

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``seed`` fixes the stand-in's random stream, ``options`` are accepted and unused."""
        self._initialise(seed=seed, draw=True)
        return self._observation(), {}

    def step(self, action):
        """Advance one 20 ms policy step with the joint-position action and return the five-tuple."""
        values = [float(value) for value in action]
        if len(values) != N_JOINTS:
            raise ValueError(f"the action has {N_JOINTS} values, got {len(values)}")
        # custom_rl_env.py:330: target = default + 0.25 * action; the stand-in stores the offset from the default.
        targets = [ACTION_SCALE * value for value in values]
        # placeholder: the joint velocities and the base motion are a kinematic mapping, not dynamics.
        self._joint_vel = [0.5 * value for value in values]  # placeholder
        self._joint_pos = targets
        self._last_action = values
        drive = sum(value / N_JOINTS for value in targets)  # placeholder
        turn = (sum(value / N_JOINTS for value in targets[: N_JOINTS // 2])
                - sum(value / N_JOINTS for value in targets[N_JOINTS // 2:])) / 2.0  # placeholder
        self._vx = drive  # placeholder
        self._vy = 0.0  # placeholder
        self._yaw_rate = turn  # placeholder
        self._x += self._vx * STEP_DT_S  # placeholder
        self._y += self._vy * STEP_DT_S  # placeholder
        self._yaw += self._yaw_rate * STEP_DT_S  # placeholder
        self._gravity = self._draw_gravity()
        self._steps += 1
        # custom_rl_env.py:298: the 20 s time-out; the fake never terminates on illegal contact
        # (custom_rl_env.py:255-257, which needs the contact sensor).
        truncated = self._steps >= MAX_EPISODE_STEPS
        return self._observation(), REWARD, False, truncated, {}

    def close(self):
        """Close the stand-in; it holds no external resource."""
        self._closed = True

    def _observation(self):
        """The concatenated policy observation of custom_rl_env.py:167-183."""
        commands = [0.0, 0.0, 0.0]  # placeholder: the start command of specify_cmd_for_robots (omniverse_sim.py:355)
        values = (
            [self._vx, self._vy, 0.0]  # base_lin_vel
            + [0.0, 0.0, self._yaw_rate]  # base_ang_vel
            + list(self._gravity)  # projected_gravity
            + commands  # velocity_commands
            + list(self._joint_pos)  # joint_pos
            + list(self._joint_vel)  # joint_vel
            + list(self._last_action)  # actions
            + self._height_scan()  # height_scan
        )
        return {"policy": values}

    def _height_scan(self):
        """A static placeholder terrain sampled on the grid of custom_rl_env.py:118-119, clipped at line 181."""
        scan = []
        for index in range(SCAN_POINTS):
            height = SCAN_AMPLITUDE_M * math.sin(2.0 * math.pi * index / SCAN_WAVELENGTH_POINTS)  # placeholder
            scan.append(max(-SCAN_CLIP, min(SCAN_CLIP, height)))
        return scan
