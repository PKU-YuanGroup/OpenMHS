"""Fake backend of the AM-Bench driver: a pure Python stand-in for ``ambench.tasks.press_button:PressButton``.

Why a fake: the acceptance gate runs without Isaac Sim 5.1, Isaac Lab, a CUDA GPU or the cloned packages
(README.md:42-43), and package code never imports the clone.  This module mirrors the public members the driver names
as ``native`` and that the Gymnasium bridge reads: ``action_space``, ``observation_space``, ``dt``, ``reset``,
``step`` and ``close`` (gate G7).  The free end-effector profile names ``ee_link`` as its control, base and
end-effector body (eef.py:63-65), so the fake reports the same pose and velocity for the base and the end effector.  ``action_space`` and ``observation_space`` are Gymnasium environment attributes
that ``DirectRLEnv`` builds outside the clone; the clone declares their members at base_env_cfg.py:28-39,
base_env_cfg.py:47 and press_button_env_cfg.py:175-180.

What this is: a small kinematic model with the upstream observation layout (ee_pos, ee_quat, ee_lin_vel,
ee_ang_vel, base_pos, base_quat, base_lin_vel, base_ang_vel, gripper_width, button_pressed, goal_pos;
press_button_env.py:81-97), the upstream success rule (plunger joint position >= 0.004; press_button_env.py:36-39,
press_button_env_cfg.py:170), the upstream reward (always zero; press_button_env.py:108-110) and the upstream 1/120 s
simulation step (base_env_cfg.py:46-52).  Every number that the clone states carries its line; every other number is
test data, marked ``# placeholder``.

What this is not: the upstream environment.  There are no rigid-body dynamics, contacts, collisions, actuators,
sensors or noise, so this is an F0 stand-in for an F1 Isaac Lab model.  The action-space bounds are not modelled
because the clone declares only the action dimension and Isaac Lab builds the Box outside the clone, so the action
space here is an unbounded eight-value Box.  The upstream ``_get_observations`` returns {"policy": [dict]}
(press_button_env.py:99-106); this fake returns the single environment's dict directly.  Nothing below talks to a
device.
"""

import math
import random

# base_env_cfg.py:46-52: decimation 1, sim dt 1/120; BaseEnv sets dt = sim.dt * decimation (base_env.py:39)
SIM_DT = 1.0 / 120.0
DECIMATION = 1
# press_button_env_cfg.py:104: episode_length_s = 20; Isaac Lab turns that into steps outside the clone
EPISODE_LENGTH_S = 20.0
MAX_EPISODE_STEPS = int(round(EPISODE_LENGTH_S / (SIM_DT * DECIMATION)))   # placeholder step count
# press_button_env_cfg.py:167-170: slider travel 0.0..0.01 and pressed threshold 0.004
PLUNGER_TRAVEL_MAX = 0.01
BUTTON_PRESSED_THRESHOLD = 0.004
# eef.py:29-35: the free end-effector starts at (0, 0, 1) with the identity quaternion and two fingers at 0.001
EE_START = (0.0, 0.0, 1.0)
EE_QUAT_START = (1.0, 0.0, 0.0, 0.0)
FINGER_START = 0.001
GRIPPER_WIDTH_START = 2.0 * FINGER_START
# press_button_env_cfg.py:109-127 with scenes/wall.py:18: the wall is at (2, 0, 1), 0.1 thick, and the button sits
# on its surface at half the thickness in front of it
WALL_POSITION = (2.0, 0.0, 1.0)
WALL_THICKNESS = 0.1
BUTTON_BASE = (WALL_POSITION[0] - 0.5 * WALL_THICKNESS, WALL_POSITION[1], WALL_POSITION[2])
# press_button_env_cfg.py:43-68: per-reset randomization of the wall pose and the button position
WALL_JITTER_X = 0.2
WALL_JITTER_Y = 0.2
BUTTON_JITTER_Y = 0.3
BUTTON_JITTER_Z = 0.3
# placeholder: how far the end effector moves toward the commanded pose per tick, the contact geometry that turns
# that pose into plunger travel, and the open width of the two-finger gripper
APPROACH_FRACTION = 0.5
CONTACT_RADIUS = 0.05
GRIPPER_OPEN_WIDTH = 0.04


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element (the bridge reads low/high)."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a name-to-space mapping (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _observation_space():
    """The eleven members of base_env_cfg.py:28-39 plus press_button_env_cfg.py:175-180, for a robot with no arms."""
    return Dict({
        "ee_pos": Box([-math.inf] * 3, [math.inf] * 3),
        "ee_quat": Box([-1.0] * 4, [1.0] * 4),
        "ee_lin_vel": Box([-math.inf] * 3, [math.inf] * 3),
        "ee_ang_vel": Box([-math.inf] * 3, [math.inf] * 3),
        "base_pos": Box([-math.inf] * 3, [math.inf] * 3),
        "base_quat": Box([-1.0] * 4, [1.0] * 4),
        "base_lin_vel": Box([-math.inf] * 3, [math.inf] * 3),
        "base_ang_vel": Box([-math.inf] * 3, [math.inf] * 3),
        "gripper_width": Box([0.0], [math.inf]),
        "button_pressed": Box([0.0], [1.0]),
        "goal_pos": Box([-math.inf] * 3, [math.inf] * 3),
    })


class FakePressButtonEnv:
    """PressButton without Isaac Lab: reset/step/close return what a Gymnasium direct environment returns."""

    def __init__(self, **options):
        # the driver factory passes its options; the fake has none
        del options
        self.dt = SIM_DT                                                    # base_env.py:39
        # base_env_cfg.py:47 declares only the 8-value dimension; the Box bounds come from Isaac Lab (not in clone)
        self.action_space = Box([-math.inf] * 8, [math.inf] * 8)
        self.observation_space = _observation_space()
        self._rng = random.Random()
        self._button = list(BUTTON_BASE)
        self._ee_pos = list(EE_START)
        self._ee_quat = list(EE_QUAT_START)
        self._ee_lin_vel = [0.0, 0.0, 0.0]
        self._gripper_width = GRIPPER_WIDTH_START
        self._plunger = 0.0
        self._tick = 0
        self._started = False
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Reset the fake scene; ``seed`` reseeds the per-episode button placement and ``options`` is accepted."""
        del options
        if self._closed:
            raise RuntimeError("the fake PressButton environment is closed")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        # placeholder draw: the wall x/y jitter and the button y/z jitter bounds are upstream (cfg:49-51,65-66)
        wall_dx = self._rng.uniform(-WALL_JITTER_X, WALL_JITTER_X)
        wall_dy = self._rng.uniform(-WALL_JITTER_Y, WALL_JITTER_Y)
        button_dy = self._rng.uniform(-BUTTON_JITTER_Y, BUTTON_JITTER_Y)
        button_dz = self._rng.uniform(-BUTTON_JITTER_Z, BUTTON_JITTER_Z)
        self._button = [BUTTON_BASE[0] + wall_dx, BUTTON_BASE[1] + wall_dy + button_dy,
                        BUTTON_BASE[2] + button_dz]
        self._ee_pos = list(EE_START)
        self._ee_quat = list(EE_QUAT_START)
        self._ee_lin_vel = [0.0, 0.0, 0.0]
        self._gripper_width = GRIPPER_WIDTH_START
        self._plunger = 0.0
        self._tick = 0
        self._started = True
        return self._observation(), {}

    def step(self, action):
        """Apply one absolute end-effector pose action and return (observation, reward, terminated, truncated, info)."""
        if self._closed:
            raise RuntimeError("the fake PressButton environment is closed")
        if not self._started:
            raise RuntimeError("call reset before step")
        if isinstance(action, (int, float)) or not hasattr(action, "__len__"):
            raise AssertionError(f"the PressButton action is an eight-value Box, got {action!r}")
        values = [float(value) for value in action]
        if len(values) != 8:
            raise AssertionError(f"the PressButton action has 8 values, got {len(values)}")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("the PressButton action values must be finite")

        target = values[0:3]
        old = self._ee_pos
        # placeholder: a proportional stand-in for the PID controller; the real one is not in the clone
        self._ee_pos = [old[axis] + APPROACH_FRACTION * (target[axis] - old[axis]) for axis in range(3)]
        self._ee_lin_vel = [(self._ee_pos[axis] - old[axis]) / SIM_DT for axis in range(3)]

        quat = values[3:7]
        norm = math.sqrt(sum(value * value for value in quat))
        self._ee_quat = [value / norm for value in quat] if norm > 0.0 else list(EE_QUAT_START)

        open_fraction = 0.5 * (min(max(values[7], -1.0), 1.0) + 1.0)         # robot_io.py:133-151
        self._gripper_width = GRIPPER_WIDTH_START + open_fraction * (GRIPPER_OPEN_WIDTH - GRIPPER_WIDTH_START)

        lateral = math.hypot(self._ee_pos[1] - self._button[1], self._ee_pos[2] - self._button[2])
        if lateral <= CONTACT_RADIUS:                                       # placeholder contact test
            depth = min(max(self._ee_pos[0] - (self._button[0] - CONTACT_RADIUS), 0.0), PLUNGER_TRAVEL_MAX)
            self._plunger = max(self._plunger, depth)

        self._tick += 1
        terminated = self._plunger >= BUTTON_PRESSED_THRESHOLD                # press_button_env.py:36-39
        truncated = self._tick >= MAX_EPISODE_STEPS                          # base_env.py:122
        return self._observation(), 0.0, terminated, truncated, {}            # press_button_env.py:108-110

    def close(self):
        self._closed = True

    def _observation(self):
        return {
            "ee_pos": list(self._ee_pos),
            "ee_quat": list(self._ee_quat),
            "ee_lin_vel": list(self._ee_lin_vel),
            "ee_ang_vel": [0.0, 0.0, 0.0],
            "base_pos": list(self._ee_pos),
            "base_quat": list(self._ee_quat),
            "base_lin_vel": list(self._ee_lin_vel),
            "base_ang_vel": [0.0, 0.0, 0.0],
            "gripper_width": [self._gripper_width],
            "button_pressed": [1.0 if self._plunger >= BUTTON_PRESSED_THRESHOLD else 0.0],
            "goal_pos": list(self._button),
        }
