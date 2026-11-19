"""Fake backend of the rotary-inverted-pendulum Gymnasium driver: a pure Python reduced model.

The gate runs without ``gymnasium`` or ``mujoco`` (the upstream policy project requires Python 3.12 and both
packages; ``pyproject.toml:11`` and ``:22-23``), and package code never imports the clone.  This module implements
the ``gymnasium.Env`` surface of ``policy/pendulum_env.py:RotaryInvertedPendulumEnv`` that the driver serves: the
same action space, the same observation frame and stacking, the same reset distribution, the same truncation and
hard-stop branches, and the same reward weights.  The public members are ``reset``, ``step``, ``render``, ``close``
and ``kick``, all of which the upstream class has (gate G7).

What this is not: the upstream MuJoCo environment.  The reduced model integrates the pendulum hinge under gravity
and a kinematic arm acceleration; it has no MuJoCo contacts, arm/pendulum inertia coupling, PD actuator, friction,
encoder quantisation, firmware measurement window or domain randomisation.  Those omissions are listed in the
driver's fidelity ``gaps``.  The fake was not compared with the upstream environment, which was not run.

The physics constants below are the upstream values that the model copies, each with its source line.  The initial
state draws are the upstream reset distribution, not invented test data.
"""

import collections
import math
import random

# policy/pendulum_env.py:66-67
MOTOR_LIMIT_RAD = math.radians(135.0)
MOTOR_SAFE_LIMIT_RAD = math.radians(125.0)
# policy/pendulum_env.py:79
GRAVITY = 9.81
# model/model.urdf:119-121
PENDULUM_COM_M = 0.051
# policy/pendulum_env.py:146,152,154,155
MAX_ACTION_DELTA_RAD = 0.10
CONTROL_FREQ_HZ = 50.0
MAX_VELOCITY_RAD_S = 3.5
MAX_ACCEL_RAD_S2 = 150.0
# policy/pendulum_env.py:343
PHYSICS_TIMESTEP_S = 0.001
# policy/pendulum_env.py:406
EPISODE_LENGTH_S = 8.0
# policy/pendulum_env.py:426
OBS_HISTORY_LEN = 4
# policy/reward.py:27-30
K_PEN_VEL = 0.001
K_MOTOR_POS = 0.5
K_MOTOR_VEL = 0.005
K_ACTION = 0.20


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != len(self.low):
            return False
        return all(self.low[index] <= float(item) <= self.high[index]
                   for index, item in enumerate(value))


class _Option:
    """The part of ``model.opt`` the physics-timing declaration reads (``model.opt.timestep``)."""

    def __init__(self):
        self.timestep = PHYSICS_TIMESTEP_S


class _Model:
    """The part of ``mujoco.MjModel`` the physics-timing declaration reads."""

    def __init__(self):
        self.opt = _Option()


class _Data:
    """The part of ``mujoco.MjData`` the physics-timing declaration reads (``data.time``)."""

    def __init__(self):
        self.time = 0.0


def _wrap_pi(value):
    """Wrap an angle into [-pi, pi] (``policy/pendulum_env.py:1299-1301``)."""
    return ((value + math.pi) % (2.0 * math.pi)) - math.pi


class FakeRotaryInvertedPendulumEnv:
    """A reduced model of ``policy/pendulum_env.py:RotaryInvertedPendulumEnv`` without numpy or MuJoCo."""

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 50}

    def __init__(
        self,
        *,
        params_path=None,
        control_freq_hz=CONTROL_FREQ_HZ,
        action_mode="accel",
        max_accel_rad_s2=MAX_ACCEL_RAD_S2,
        max_velocity_rad_s=MAX_VELOCITY_RAD_S,
        max_action_delta_rad=MAX_ACTION_DELTA_RAD,
        episode_length_s=EPISODE_LENGTH_S,
        upright_reset_frac=0.0,
        obs_history_len=OBS_HISTORY_LEN,
        obs_include_velocities=True,
        render_mode=None,
        terminate_on_hard_stop=True,
        hard_stop_penalty=5.0,
        action_smooth_window=4,
        **_unsupported_options,
    ):
        if action_mode not in ("accel", "velocity", "position_delta"):
            raise ValueError(
                f"action_mode must be 'accel', 'velocity', or 'position_delta', got {action_mode!r}"
            )
        if not 0.0 <= float(upright_reset_frac) <= 1.0:
            raise ValueError(f"upright_reset_frac must be in [0, 1], got {upright_reset_frac}")
        if int(obs_history_len) < 1:
            raise ValueError(f"obs_history_len must be >= 1, got {obs_history_len}")
        if not obs_include_velocities and int(obs_history_len) < 2:
            raise ValueError("obs_include_velocities=False needs obs_history_len >= 2")
        self.control_freq_hz = float(control_freq_hz)
        self.action_mode = action_mode
        self.max_accel_rad_s2 = float(max_accel_rad_s2)
        self.max_velocity_rad_s = float(max_velocity_rad_s)
        self.max_action_delta_rad = float(max_action_delta_rad)
        self.episode_length_s = float(episode_length_s)
        self.upright_reset_frac = float(upright_reset_frac)
        self.obs_history_len = int(obs_history_len)
        self.obs_include_velocities = bool(obs_include_velocities)
        self.render_mode = render_mode
        self.terminate_on_hard_stop = bool(terminate_on_hard_stop)
        self.hard_stop_penalty = float(hard_stop_penalty)
        # Accepted for signature compatibility; the reduced model does not implement the
        # firmware boxcar (action_smooth_window), transport lag, DR or the measurement model.
        self.action_smooth_window = int(action_smooth_window)

        # policy/pendulum_env.py:668-670: one control period is an integer number of physics steps.
        self.model = _Model()
        self.data = _Data()
        self._dt_control = 1.0 / self.control_freq_hz
        self._n_substeps = max(1, int(round(self._dt_control / self.model.opt.timestep)))
        self._max_steps = int(self.episode_length_s * self.control_freq_hz)

        self.action_space = Box([-1.0], [1.0])                          # policy/pendulum_env.py:731-733
        frame_high = (
            [MOTOR_LIMIT_RAD, 1.0, 1.0, 200.0, 200.0, 1.0]              # policy/pendulum_env.py:738-742
            if self.obs_include_velocities
            else [MOTOR_LIMIT_RAD, 1.0, 1.0, 1.0]
        )
        obs_high = frame_high * self.obs_history_len                    # policy/pendulum_env.py:743
        self.observation_space = Box([-value for value in obs_high], obs_high)

        self._rng = random.Random()
        self._motor_pos = 0.0
        self._motor_vel = 0.0
        self._motor_target = 0.0
        self._phi = 0.0
        self._pen_vel = 0.0
        self._step_count = 0
        self._prev_action = 0.0
        self._prev_motor_vel = 0.0
        self._obs_history = collections.deque(maxlen=self.obs_history_len)
        self._kick_value = 0.0
        self._kick_ticks_left = 0
        self._viewer = None

    # --- Gymnasium API -----------------------------------------------------

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self.data.time = 0.0
        if (self.upright_reset_frac > 0.0
                and self._rng.random() < self.upright_reset_frac):
            phi0 = math.pi + self._rng.uniform(-0.3, 0.3)               # policy/pendulum_env.py:808-811
            pen_vel0 = self._rng.uniform(-0.5, 0.5)
        else:
            phi0 = self._rng.uniform(-0.05, 0.05)                       # policy/pendulum_env.py:813-814
            pen_vel0 = 0.0
        self._motor_pos = self._rng.uniform(                            # policy/pendulum_env.py:815-817
            -0.7 * MOTOR_SAFE_LIMIT_RAD, 0.7 * MOTOR_SAFE_LIMIT_RAD
        )
        self._motor_target = self._motor_pos
        self._motor_vel = 0.0
        self._phi = _wrap_pi(phi0)
        self._pen_vel = pen_vel0
        self._step_count = 0
        self._prev_action = 0.0
        self._prev_motor_vel = 0.0
        self._kick_value = 0.0
        self._kick_ticks_left = 0
        self._obs_history.clear()
        return self._obs(), {}

    def step(self, action):
        if isinstance(action, (list, tuple)):
            action = action[0]
        action = float(action)
        action = max(-1.0, min(1.0, action))                            # policy/pendulum_env.py:944
        command = action
        if self._kick_ticks_left > 0:                                   # policy/pendulum_env.py:934-942
            command = self._kick_value
            self._kick_ticks_left -= 1

        previous_target = self._motor_target
        previous_motor_vel = self._motor_vel
        if self.action_mode in ("accel", "velocity"):
            if self.action_mode == "velocity":                          # policy/pendulum_env.py:1024-1054
                v_des = command * self.max_velocity_rad_s
                accel_cmd = (v_des - self._motor_vel) * self.control_freq_hz
                accel_cmd = max(-self.max_accel_rad_s2, min(self.max_accel_rad_s2, accel_cmd))
            else:
                accel_cmd = command * self.max_accel_rad_s2              # policy/pendulum_env.py:1051
            self._motor_vel = max(                                    # policy/pendulum_env.py:1055-1059
                -self.max_velocity_rad_s,
                min(self.max_velocity_rad_s, self._motor_vel + accel_cmd * self._dt_control),
            )
            if self._motor_target >= MOTOR_SAFE_LIMIT_RAD and self._motor_vel > 0.0:
                self._motor_vel = 0.0                                   # policy/pendulum_env.py:1069-1072
            elif self._motor_target <= -MOTOR_SAFE_LIMIT_RAD and self._motor_vel < 0.0:
                self._motor_vel = 0.0
            self._motor_target = max(                                  # policy/pendulum_env.py:1073-1077
                -MOTOR_SAFE_LIMIT_RAD,
                min(MOTOR_SAFE_LIMIT_RAD,
                    self._motor_target + self._motor_vel * self._dt_control),
            )
        else:
            self._motor_target = max(                                  # policy/pendulum_env.py:1086-1098
                -MOTOR_SAFE_LIMIT_RAD,
                min(MOTOR_SAFE_LIMIT_RAD,
                    self._motor_target + command * self.max_action_delta_rad),
            )
            self._motor_vel = (self._motor_target - previous_target) / self._dt_control
            accel_cmd = (self._motor_vel - previous_motor_vel) / self._dt_control

        arm_accel = accel_cmd
        for _index in range(self._n_substeps):                         # policy/pendulum_env.py:1120-1132
            # placeholder: an analytic test transition, not a sourced Furuta equation.  The copied angle
            # convention is phi = 0 hanging down (line 1180-1185); no rigid-body coupling or contacts are modelled.
            phi_acc = (
                -(GRAVITY / PENDULUM_COM_M) * math.sin(self._phi)
                + (arm_accel / PENDULUM_COM_M) * math.cos(self._phi)
            )
            self._pen_vel += phi_acc * self.model.opt.timestep
            self._phi = _wrap_pi(self._phi + self._pen_vel * self.model.opt.timestep)
            self.data.time += self.model.opt.timestep

        self._motor_pos = self._motor_target
        self._step_count += 1                                           # policy/pendulum_env.py:1135
        theta = _wrap_pi(self._phi - math.pi)
        reward = -(
            theta * theta
            + K_PEN_VEL * self._pen_vel * self._pen_vel
            + K_MOTOR_POS * self._motor_pos * self._motor_pos
            + K_MOTOR_VEL * self._motor_vel * self._motor_vel
            + K_ACTION * action * action
        )                                                               # policy/reward.py:94-102
        terminated = False
        if self.terminate_on_hard_stop and abs(self._motor_pos) >= MOTOR_LIMIT_RAD:
            terminated = True                                          # policy/pendulum_env.py:1144-1146
            reward -= self.hard_stop_penalty
        truncated = self._step_count >= self._max_steps                 # policy/pendulum_env.py:1148
        self._prev_action = action
        self._prev_motor_vel = self._motor_vel
        info = {
            "motor_pos": self._motor_pos,
            "phi": self._phi,
            "motor_target": self._motor_target,
            "motor_vel_cmd": self._motor_vel,
            "motor_max_accel_rad_s2": self.max_accel_rad_s2,
            "action_delay_steps": 0,
            "action_lag_tau_s": 0.0,
            "smoothed_action": command,
            "motor_tau_s": 0.0,
            "obs_staleness_s": 0.0,
            "motor_vel_meas": None,
        }
        return self._obs(), reward, terminated, truncated, info

    def render(self):
        if self.render_mode is None:
            return None
        return None

    def close(self):
        self._viewer = None

    def kick(self, value, ticks=2):
        self._kick_value = max(-1.0, min(1.0, float(value)))
        self._kick_ticks_left = max(0, int(ticks))

    # --- internal ----------------------------------------------------------

    def _obs(self):
        theta = _wrap_pi(self._phi - math.pi)                          # policy/pendulum_env.py:1248
        if self.obs_include_velocities:
            frame = [self._motor_pos, math.sin(theta), math.cos(theta), self._motor_vel,
                     self._pen_vel, self._prev_action]                  # policy/pendulum_env.py:1250-1254
        else:
            frame = [self._motor_pos, math.sin(theta), math.cos(theta),
                     self._prev_action]                                 # policy/pendulum_env.py:1256-1260
        if not self._obs_history:
            self._obs_history.extend([list(frame) for _index in range(self.obs_history_len)])
        else:
            self._obs_history.append(list(frame))                       # policy/pendulum_env.py:1263-1266
        values = []
        for item in self._obs_history:
            values.extend(item)
        return values
