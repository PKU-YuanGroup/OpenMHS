"""Fake backend of the JSBGym driver: a pure-Python kinematic stand-in for ``jsbgym.environment:NoFGJsbSimEnv``.

Why a fake: the acceptance gate runs without gymnasium, jsbsim or numpy, and package code never imports the clone.
This module mirrors the public surface of the class the driver names as ``native`` (``reset``, ``step`` and
``close``; gate G7) and the two ``gymnasium.spaces.Box`` objects the environment derives from its task (the bridge
reads ``low``, ``high`` and ``shape``).  The JSBSim flight dynamics are replaced by a small deterministic model;
the driver's fidelity contract is F0 and its ``gaps`` state every difference from the upstream environment.

Every numeric literal below except the action bounds is test data of this stand-in, not a claim about the upstream
environment: each such constant is marked ``# placeholder``.  The action bounds copy the upstream action space,
and the driver's ``action_space_ref`` cites the lines that write them; the other numbers that the upstream
environment does state are cited from the clone in driver.py and facts.md, never here.  Nothing here talks to a
device, imports the clone or renders.
"""

import math


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, dtype="float64"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype

    def contains(self, value):
        if len(value) != len(self.low):
            return False
        return all(self.low[index] <= float(value[index]) <= self.high[index]
                   for index in range(len(self.low)))


class FakeNoFGJsbSimEnv:
    """The FlightGear-disabled JSBGym interface without JSBSim, numpy or gymnasium.

    ``reset(seed, options)`` returns ``(observation, info)`` and ``step(action)`` returns
    ``(observation, reward, terminated, False, info)`` as the upstream class does.  The observation has the upstream
    shape (11 numbers, the task's state variables) and the action is the three normalised control-surface commands.
    The transition is the stand-in's own kinematic model (see the driver fidelity ``gaps``), not JSBSim.
    """

    # placeholder: mirrors the upstream integration frequency (environment.py:25)
    JSBSIM_DT_HZ = 60
    # placeholder: mirrors the upstream NoFGJsbSimEnv metadata (environment.py:235-238)
    metadata = {"render_modes": ["human", "graph"], "render_fps": 60}

    # placeholder: the upstream observation Box bounds (properties.py:19-66 and tasks.py:270-278)
    _OBSERVATION_LOW = [
        -1400.0, -0.5 * math.pi, -math.pi, -2200.0, -2200.0, -2200.0,
        -2.0 * math.pi, -2.0 * math.pi, -2.0 * math.pi, -1400.0, -180.0,
    ]
    _OBSERVATION_HIGH = [
        85000.0, 0.5 * math.pi, math.pi, 2200.0, 2200.0, 2200.0,
        2.0 * math.pi, 2.0 * math.pi, 2.0 * math.pi, 85000.0, 180.0,
    ]
    # The upstream action Box (tasks.py:236-239) of HeadingControlTask's three action variables (tasks.py:279),
    # each in -1..1 (properties.py:93-101).  These two lists copy it.
    _ACTION_LOW = [-1.0, -1.0, -1.0]
    _ACTION_HIGH = [1.0, 1.0, 1.0]

    # placeholder: initial state and episode constants of the stand-in
    _INITIAL_ALTITUDE_FT = 5000.0
    _INITIAL_HEADING_DEG = 270.0
    _CRUISE_SPEED_FPS = 200.0
    _EPISODE_TIME_S = 60.0
    _MAX_ALTITUDE_DEVIATION_FT = 1000.0
    _TRACK_SCALE_DEG = 180.0

    # placeholder: control response and reward scales of the stand-in
    _AILERON_ROLL_RAD = 0.4
    _ELEVATOR_PITCH_RAD = 0.2
    _RESPONSE = 0.25
    _YAW_RATE_DEG_S = 15.0
    _SIDESLIP_FPS = 10.0
    _VERTICAL_SPEED_FPS = 10.0

    def __init__(self, aircraft=None, task_type=None, agent_interaction_freq=5, shaping=None,
                 render_mode=None, **options):
        del aircraft, task_type, shaping, render_mode, options
        if not isinstance(agent_interaction_freq, int) or isinstance(agent_interaction_freq, bool) \
                or agent_interaction_freq <= 0:
            raise ValueError("agent_interaction_freq must be a positive integer")
        if agent_interaction_freq > self.JSBSIM_DT_HZ:
            raise ValueError("agent interaction frequency must be less than or equal to JSBSim integration "
                             f"frequency of {self.JSBSIM_DT_HZ} Hz")
        self.sim_steps_per_agent_step = self.JSBSIM_DT_HZ // agent_interaction_freq
        self.observation_space = Box(self._OBSERVATION_LOW, self._OBSERVATION_HIGH)
        self.action_space = Box(self._ACTION_LOW, self._ACTION_HIGH)
        # placeholder: ceil(60 s * 5 Hz) = 300 agent steps for the default configuration
        self._episode_steps = math.ceil(self._EPISODE_TIME_S * agent_interaction_freq)
        self._steps_left = 0
        self._seed = None
        self._started = False
        self._closed = False
        self._terminated = False
        self._altitude_ft = self._INITIAL_ALTITUDE_FT
        self._pitch_rad = 0.0
        self._roll_rad = 0.0
        self._heading_deg = self._INITIAL_HEADING_DEG
        self._u_fps = self._CRUISE_SPEED_FPS
        self._v_fps = 0.0
        self._w_fps = 0.0
        self._p_radps = 0.0
        self._q_radps = 0.0
        self._r_radps = 0.0

    def reset(self, seed=None, options=None):
        """Reset the stand-in; ``options`` are accepted and ignored as the upstream reset does."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._seed = int(seed)
        del options
        self._steps_left = self._episode_steps
        self._started = True
        self._terminated = False
        self._altitude_ft = self._INITIAL_ALTITUDE_FT
        self._pitch_rad = 0.0
        self._roll_rad = 0.0
        self._heading_deg = self._INITIAL_HEADING_DEG
        self._u_fps = self._CRUISE_SPEED_FPS
        self._v_fps = 0.0
        self._w_fps = 0.0
        self._p_radps = 0.0
        self._q_radps = 0.0
        self._r_radps = 0.0
        return list(self._observation()), {}

    def step(self, action):
        """Advance the stand-in by one agent interaction and return the upstream five-tuple."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if not self._started:
            raise RuntimeError("Call reset before using step method.")
        values = list(action)
        if len(values) != 3:
            raise ValueError("mismatch between action and action space size")
        controls = []
        for value in values:
            number = float(value)
            if not math.isfinite(number) or number < -1.0 or number > 1.0:
                raise ValueError(f"action value {value!r} is outside the action space")
            controls.append(number)
        aileron, elevator, rudder = controls
        dt_s = self.sim_steps_per_agent_step / self.JSBSIM_DT_HZ  # placeholder: 12 / 60 = 0.2 s
        previous_roll, previous_pitch = self._roll_rad, self._pitch_rad
        self._roll_rad += (self._AILERON_ROLL_RAD * aileron - self._roll_rad) * self._RESPONSE
        self._pitch_rad += (self._ELEVATOR_PITCH_RAD * elevator - self._pitch_rad) * self._RESPONSE
        self._p_radps = (self._roll_rad - previous_roll) / dt_s
        self._q_radps = (self._pitch_rad - previous_pitch) / dt_s
        self._r_radps = math.radians(self._YAW_RATE_DEG_S) * rudder
        self._heading_deg = (self._heading_deg + self._YAW_RATE_DEG_S * rudder * dt_s) % 360.0
        self._v_fps = self._SIDESLIP_FPS * rudder
        self._w_fps = self._VERTICAL_SPEED_FPS * math.sin(self._pitch_rad)
        self._altitude_ft += self._u_fps * math.sin(self._pitch_rad) * dt_s
        self._steps_left -= 1
        altitude_error_ft = self._altitude_ft - self._INITIAL_ALTITUDE_FT
        track_error_deg = self._reduce_angle(self._heading_deg - self._INITIAL_HEADING_DEG)
        self._terminated = (self._steps_left <= 0
                            or abs(altitude_error_ft) > self._MAX_ALTITUDE_DEVIATION_FT)
        # placeholder: a stand-in reward in 0..1, not the upstream assessor reward
        reward = max(0.0, 1.0 - abs(altitude_error_ft) / self._MAX_ALTITUDE_DEVIATION_FT
                     - abs(track_error_deg) / self._TRACK_SCALE_DEG)
        return list(self._observation()), reward, self._terminated, False, {"reward": reward}

    def close(self):
        """Close the stand-in and drop its state (the upstream close() drops the simulation)."""
        self._closed = True
        self._started = False

    def _observation(self):
        altitude_error_ft = self._altitude_ft - self._INITIAL_ALTITUDE_FT
        track_error_deg = self._reduce_angle(self._heading_deg - self._INITIAL_HEADING_DEG)
        return [
            self._altitude_ft,
            self._pitch_rad,
            self._roll_rad,
            self._u_fps,
            self._v_fps,
            self._w_fps,
            self._p_radps,
            self._q_radps,
            self._r_radps,
            altitude_error_ft,
            track_error_deg,
        ]

    @staticmethod
    def _reduce_angle(angle_deg):
        """``utils.reduce_reflex_angle_deg`` (jsbgym/utils.py:95-102) without importing the clone."""
        new_angle = angle_deg % 360.0
        if new_angle > 180.0:
            new_angle -= 360.0
        return new_angle
