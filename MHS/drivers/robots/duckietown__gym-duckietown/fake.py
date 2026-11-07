"""Fake backend of the Gym-Duckietown driver: a pure Python stand-in for ``gym_duckietown.envs:MultiMapEnv``.

Why a fake: the gate cannot import the clone (the upstream package needs gym, numpy<=1.20, pyglet, OpenGL and
Duckietown's world packages, setup.py:11-23), and package code never imports the clone.  This module mirrors the
public surface of ``MultiMapEnv`` (multimap_env.py:7-91): ``seed``, ``reset``, ``step``, ``close`` and the
``step_count`` property, plus the action space, observation space and reward range the wrapper copies from the
``DuckietownEnv`` it builds.  Gate G7 checks those members against the upstream class.

What this is not: the upstream OpenGL simulator.  Its ``step`` reads the action as ``DuckietownEnv.step`` does, a
velocity and a steering angle that it converts to the two wheel commands (envs/duckietown_env.py:36-63), but it
moves the robot along a straight placeholder lane with simple kinematic differential-drive integration of those
commands and returns one 3-value RGB pixel sample instead of the rendered 480 x 640 x 3 camera frame.  The
differences are the ``gaps`` in the driver's fidelity contract:

* no rendering, textures, distortion, map geometry, collision polygons or domain randomization;
* the initial pose and dynamics are simpler, and Python's random.Random replaces numpy's RandomState;
* the fake was never compared with an upstream run, so its trajectories and images are not upstream's.

Every numeric constant below is placeholder test data, not a fact about the device, except the action-space
bounds, which copy the upstream space, and the conversion constants, which copy DuckietownEnv's defaults; the
comments say which.  The real observation shape is the upstream one, but the fake still treats it as a placeholder
representation.  Nothing here talks to a device.
"""

import math
import random

# The deployed action space: MultiMapEnv copies the space of the DuckietownEnv it builds (multimap_env.py:22), and
# DuckietownEnv replaces the Simulator's Box(-1, 1, shape=(2,)) (simulator.py:309) with the same bounds,
# Box(low=[-1, -1], high=[1, 1], float32) (envs/duckietown_env.py:19).  These two lists copy them.  The two values are a
# velocity and a steering angle (envs/duckietown_env.py:11, :37), not the Simulator's wheel commands.
ACTION_LOW = [-1.0, -1.0]
ACTION_HIGH = [1.0, 1.0]
# The constants of DuckietownEnv's conversion: its defaults for gain, trim, wheel radius, motor constant and wheel
# velocity limit (envs/duckietown_env.py:15), which MultiMap-v0 keeps (it passes no kwargs, __init__.py:48, and
# MultiMapEnv passes only map_name and its own kwargs, multimap_env.py:20).  These copy them.
GAIN = 1.0
TRIM = 0.0
WHEEL_RADIUS = 0.0318
MOTOR_CONSTANT = 27.0
WHEEL_LIMIT = 1.0
# placeholder: the distance between the wheels.  Upstream's nominal WHEEL_DIST is 0.102 (simulator.py:134), and its
# default domain randomization perturbs it at every reset (simulator.py:213, :597); the fake keeps the nominal value.
WHEEL_DIST = 0.102
# placeholder: the deployed observation space is Box(0, 255, (480, 640, 3), uint8) (simulator.py:318-320); the fake
# returns one 3-value RGB sample but declares the real shape so the bridge derives the real observation kind.
CAMERA_SHAPE = (480, 640, 3)  # placeholder representation of the real camera frame
# placeholder: a bounded straight lane for the fake's pose update.
LANE_HALF_WIDTH = 0.40
TRACK_LENGTH = 8.0
MAX_SPEED = 1.0
TURN_RATE = 2.0
START_JITTER = 0.02
# placeholder: upstream Simulator default max_steps is 1500 (simulator.py:167); the fake uses the same horizon so a
# long episode ends at the same step count, but this is test data here.
MAX_STEPS = 1500
# placeholder: upstream default delta_time is 1/30 s (simulator.py:165, :300); one fake step is one tick.
DELTA_TIME = 1.0 / 30.0
# placeholder: upstream REWARD_INVALID_POSE is -1000 (simulator.py:175); used as the fake's terminal penalty.
INVALID_POSE_REWARD = -1000.0


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound and a shape (the bridge reads low/high/shape)."""

    def __init__(self, low, high, shape, dtype):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeMultiMapEnv:
    """MultiMapEnv without gym, numpy or OpenGL: two placeholder maps and a kinematic differential drive."""

    def __init__(self, **kwargs):
        # MultiMapEnv accepts **kwargs and passes them to DuckietownEnv (multimap_env.py:13, :20).  The fake cannot use
        # the upstream options, so it keeps them as data and does not pretend to apply them.
        self.options = dict(kwargs)
        self.window = None
        self.env_names = ["loop_only_duckies", "small_loop_only_duckies"]  # placeholder mirror of line 17
        self.env_list = []
        for map_id, name in enumerate(self.env_names):
            self.env_list.append(
                {
                    "name": name,
                    "map_id": map_id,
                    "rng": random.Random(),
                    "seed": None,
                    "x": 0.0,
                    "y": 0.0,
                    "angle": 0.0,
                    "step_count": 0,
                    "done": False,
                }
            )
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, (2,), "float32")
        self.observation_space = Box(0, 255, CAMERA_SHAPE, "uint8")
        self.reward_range = (-1000.0, 1000.0)
        self.cur_env_idx = 0
        self.cur_reward_sum = 0.0
        self.cur_num_steps = 0

    def seed(self, seed=None):
        """Seed every placeholder environment and the wrapper, and return ``[seed]`` (multimap_env.py:34-42)."""
        for env in self.env_list:
            env["rng"] = random.Random(seed)
            env["seed"] = seed
        self.np_random = random.Random(seed)
        self._seed = seed
        return [seed]

    def reset(self):
        """Advance to the next environment and reset it (multimap_env.py:44-49); legacy gym returns obs only."""
        self.cur_env_idx = (self.cur_env_idx + 1) % len(self.env_list)
        env = self.env_list[self.cur_env_idx]
        env["x"] = env["rng"].uniform(-START_JITTER, START_JITTER)
        env["y"] = env["rng"].uniform(-START_JITTER, START_JITTER)
        env["angle"] = env["rng"].uniform(-START_JITTER, START_JITTER)
        env["step_count"] = 0
        env["done"] = False
        return self._observation(env)

    def step(self, action):
        """Take a velocity and a steering angle for one tick; return the legacy ``(obs, reward, done, info)`` tuple.

        The two values become the left and right wheel commands as in ``DuckietownEnv.step``
        (envs/duckietown_env.py:36-63); only the pose update from those commands is the fake's own placeholder.
        """
        env = self.env_list[self.cur_env_idx]
        vel = float(action[0])
        angle = float(action[1])
        # DuckietownEnv.step (envs/duckietown_env.py:39-61): each wheel's rotation rate, converted to a duty cycle and
        # limited to WHEEL_LIMIT.  The Simulator's clip to [-1, 1] (simulator.py:1670) then changes nothing.
        omega_r = (vel + 0.5 * angle * WHEEL_DIST) / WHEEL_RADIUS
        omega_l = (vel - 0.5 * angle * WHEEL_DIST) / WHEEL_RADIUS
        right = max(min(omega_r * (GAIN + TRIM) / MOTOR_CONSTANT, WHEEL_LIMIT), -WHEEL_LIMIT)
        left = max(min(omega_l * (GAIN - TRIM) / MOTOR_CONSTANT, WHEEL_LIMIT), -WHEEL_LIMIT)
        # placeholder: kinematic update of a differential drive from the two wheel commands, not the upstream SE2
        # integration.
        speed = 0.5 * (left + right) * MAX_SPEED
        turn = 0.5 * (right - left) * TURN_RATE
        env["angle"] += turn * DELTA_TIME
        env["x"] += speed * math.cos(env["angle"]) * DELTA_TIME
        env["y"] += speed * math.sin(env["angle"]) * DELTA_TIME
        env["step_count"] += 1
        self.cur_reward_sum += 0.0
        self.cur_num_steps += 1

        if abs(env["y"]) > LANE_HALF_WIDTH:
            reward = INVALID_POSE_REWARD
            done = True
            msg = "Stopping the simulator because we are at an invalid pose."
        elif env["step_count"] >= MAX_STEPS:
            reward = 0.0
            done = True
            msg = "Stopping the simulator because we reached max_steps = %s" % MAX_STEPS
        else:
            # placeholder: a lane-centering reward with the sign of the upstream formula, not its coefficients.
            reward = speed - 10.0 * abs(env["y"])
            done = False
            msg = ""
        env["done"] = done
        self.cur_reward_sum += reward
        if done:
            self.cur_reward_sum = 0.0
            self.cur_num_steps = 0
        # the Simulator reports the wheel commands it applied (simulator.py:1592, :1626), and DuckietownEnv.step adds
        # its own entry with the upstream keys ("train" holds the trim) (envs/duckietown_env.py:64-71)
        info = {
            "Simulator": {"action": [left, right], "msg": msg},
            "DuckietownEnv": {"k": MOTOR_CONSTANT, "gain": GAIN, "train": TRIM, "radius": WHEEL_RADIUS,
                              "omega_r": omega_r, "omega_l": omega_l},
        }
        return self._observation(env), reward, done, info

    def close(self):
        """Release the placeholder environments (multimap_env.py:80-86)."""
        for env in self.env_list:
            env["done"] = True
        self.cur_env_idx = 0
        self.env_names = None
        self.env_list = None

    @property
    def step_count(self):
        """The step count of the current placeholder environment (multimap_env.py:88-90)."""
        return self.env_list[self.cur_env_idx]["step_count"]

    def _observation(self, env):
        """One placeholder RGB sample derived from the pose, map and step count (not a rendered camera image)."""
        red = int(255.0 * ((env["x"] / TRACK_LENGTH) % 1.0))
        green = int(127.5 * (1.0 + math.sin(env["angle"])))
        blue = 32 + 96 * env["map_id"] + min(31, env["step_count"] // 16)
        return [max(0, min(255, red)), max(0, min(255, green)), max(0, min(255, blue))]
