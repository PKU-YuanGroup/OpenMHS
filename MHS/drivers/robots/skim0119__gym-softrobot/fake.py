"""Fake backend of the OctoMuscleCrawl-v0 driver: a pure-Python point-mass stand-in.

Why a fake: the acceptance gate runs without the upstream stack (gymnasium, numpy, PyElastica, COOMM; pyproject.toml
20-29), and package code never imports the upstream clone.  The public surface is the one the upstream
``gym_softrobot.envs.octopus:OctoMuscleCrawlEnv`` has (``reset``, ``step``, ``render``, ``close``; gate G7), and the
space class duck-types ``gymnasium.spaces.Box`` (the bridge reads ``low``, ``high``, ``shape`` and ``dtype``).

This is not the upstream environment.  It integrates a point-mass central body with a hand-written force map, so it
has no Cosserat rods, contacts, friction, suction or muscle dynamics.  The six-value observation keeps the upstream
layout (three displacement values followed by three velocity values), but its numbers come from the surrogate.  The
driver's fidelity ``gaps`` list every omission.

Every numeric value in this module is fake test data, marked ``# placeholder`` where it is a constant.  None of these
numbers is a Fact, a Limit or a citation of the upstream device.
"""

import math
import random

# placeholder: the upstream default in config.py:23 is 8 arms; this fake uses the same shape to exercise the bridge.
DEFAULT_N_ARMS = 8
# placeholder: the upstream OctopusMuscleConfig sets n_channels to 9 (config.py:163-164); this is only the fake shape.
DEFAULT_N_CHANNELS = 9
# placeholder: the upstream control interval is 1/60 s (config.py:95); used only to advance the fake.
DEFAULT_CONTROL_DT = 1.0 / 60.0
# placeholder: the upstream T_L is 2.4 s and the episode lasts five cycles (config.py:93-101).
DEFAULT_T_L = 2.4
DEFAULT_EPISODE_CYCLES = 5.0
# placeholder: the upstream base length and lateral penalty are 0.45 m and 0.5 (config.py:29 and :106).
DEFAULT_BASE_LENGTH = 0.45
DEFAULT_LATERAL_PENALTY = 0.5
# placeholder: the upstream failure penalty is -100 (config.py:110); used only if the fake state becomes non-finite.
DEFAULT_FAILURE_PENALTY = -100.0
# placeholder: the fake observation has six values (three displacement, three velocity); upstream says (6,).
OBSERVATION_SIZE = 6
# placeholder: the surrogate's thrust, lateral-coupling and drag gains are arbitrary test values.
FORWARD_GAIN = 0.6
LATERAL_GAIN = 0.05
DRAG = 0.8
SUCTION_RELIEF = 0.4
# placeholder: the surrogate reports a small positive strain energy so the info dict stays realistic.
STRAIN_SCALE = 0.001


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a flat lower/upper bound and a shape."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype

    def contains(self, value):
        raw = value.tolist() if hasattr(value, "tolist") else value
        values = [float(item) for item in raw]
        if len(values) != len(self.low):
            return False
        return all(low <= item <= high for low, item, high in zip(self.low, values, self.high))


class _FakeConfig:
    """The few configuration values the surrogate reads; every value is a placeholder."""

    n_arms = DEFAULT_N_ARMS                       # placeholder
    n_channels = DEFAULT_N_CHANNELS               # placeholder
    control_dt = DEFAULT_CONTROL_DT               # placeholder
    T_L = DEFAULT_T_L                             # placeholder
    episode_duration_cycles = DEFAULT_EPISODE_CYCLES  # placeholder
    base_length = DEFAULT_BASE_LENGTH             # placeholder
    lateral_penalty = DEFAULT_LATERAL_PENALTY     # placeholder
    failure_penalty = DEFAULT_FAILURE_PENALTY     # placeholder

    @property
    def episode_duration_s(self):
        return self.episode_duration_cycles * self.T_L

    @property
    def reward_scale(self):
        return 1.0 / (self.episode_duration_cycles * 0.8 * self.base_length)   # placeholder


class _FakeSimulation:
    """A point-mass body driven by a placeholder force map; not the upstream elastica simulation."""

    def __init__(self, *, n_arms, n_channels, control_dt, rng):
        self.n_arms = int(n_arms)
        self.n_channels = int(n_channels)
        self.control_dt = float(control_dt)
        self.time = 0.0
        self.initial_position = [0.0, 0.0, 0.0]   # placeholder
        self.position = list(self.initial_position)
        self.velocity = [0.0, 0.0, 0.0]
        # placeholder: a seeded per-arm thrust bias, so two seeds give different trajectories.
        self.bias = [rng.uniform(-0.05, 0.05) for _ in range(self.n_arms)]
        self.strain_energy = 0.0

    def _command_rows(self, action):
        raw = action.tolist() if hasattr(action, "tolist") else action
        values = list(raw)
        if values and isinstance(values[0], (list, tuple)):
            flat = [float(item) for row in values for item in row]
        else:
            flat = [float(item) for item in values]
        expected = self.n_arms * self.n_channels
        if len(flat) != expected:
            raise ValueError(f"action must carry {expected} values, got {len(flat)}")
        return [flat[index * self.n_channels:(index + 1) * self.n_channels]
                for index in range(self.n_arms)]

    def advance(self, duration, action):
        rows = self._command_rows(action)
        muscle = [index for index in (1, 2, 3, 4, 7, 8) if index < self.n_channels] or list(range(self.n_channels))
        suction = [index for index in (5, 6) if index < self.n_channels]
        activations = []
        suctions = []
        for arm, row in enumerate(rows):
            active = sum((row[index] + 1.0) * 0.5 for index in muscle) / len(muscle)
            activations.append(active + self.bias[arm])
            if suction:
                suctions.append(sum((row[index] + 1.0) * 0.5 for index in suction) / len(suction))
            else:
                suctions.append(0.0)
        half = len(activations) // 2
        mean_activation = sum(activations) / len(activations)
        mean_suction = sum(suctions) / len(suctions)
        asymmetry = (sum(activations[:half]) / half
                     - sum(activations[half:]) / (len(activations) - half))
        accel_x = LATERAL_GAIN * asymmetry
        accel_z = -FORWARD_GAIN * mean_activation * (1.0 - SUCTION_RELIEF * mean_suction)
        self.velocity[0] += accel_x * duration
        self.velocity[2] += accel_z * duration
        self.velocity[0] *= (1.0 - DRAG * duration)
        self.velocity[2] *= (1.0 - DRAG * duration)
        self.position[0] += self.velocity[0] * duration
        self.position[2] += self.velocity[2] * duration
        self.time += duration
        self.strain_energy = STRAIN_SCALE * sum(activations)

    def observation(self):
        return [
            self.position[0] - self.initial_position[0],
            self.position[1] - self.initial_position[1],
            self.position[2] - self.initial_position[2],
            self.velocity[0],
            self.velocity[1],
            self.velocity[2],
        ]

    def is_finite(self):
        return all(math.isfinite(value) for value in self.position + self.velocity)


class FakeOctoMuscleCrawlEnv:
    """``OctoMuscleCrawl-v0`` without gymnasium, numpy or elastica; only the upstream method names are public."""

    metadata = {"render_modes": ["rgb_array"], "render_fps": 60}

    def __init__(self, *, config=None, horizon=None, render_mode=None):
        if render_mode not in {None, *self.metadata["render_modes"]}:
            raise ValueError(f"Unsupported render mode: {render_mode}")
        self.render_mode = render_mode
        self.config = config if config is not None else _FakeConfig()
        self.horizon = horizon or max(
            1, math.ceil(self.config.episode_duration_s / self.config.control_dt))
        self.n_arms = int(self.config.n_arms)
        self.n_channels = int(self.config.n_channels)
        count = self.n_arms * self.n_channels
        self.action_space = Box([-1.0] * count, [1.0] * count, shape=(self.n_arms, self.n_channels))
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE,
                                     shape=(OBSERVATION_SIZE,))
        self.simulation = None
        self._step_count = 0
        self._previous_forward = 0.0
        self._rng = random.Random()

    def _require_simulation(self):
        if self.simulation is None:
            raise RuntimeError("reset() must be called before stepping the environment")
        return self.simulation

    def _observation(self):
        return self._require_simulation().observation()

    def reset(self, *, seed=None, options=None):
        del options
        if seed is not None:
            self._rng = random.Random(seed)
        self.simulation = _FakeSimulation(
            n_arms=self.n_arms,
            n_channels=self.n_channels,
            control_dt=float(self.config.control_dt),
            rng=self._rng,
        )
        self._step_count = 0
        self._previous_forward = 0.0
        return self._observation(), {"time": self.simulation.time}

    def step(self, action):
        simulation = self._require_simulation()
        previous_position = simulation.position[2]
        simulation.advance(float(self.config.control_dt), action)
        self._step_count += 1
        current_position = simulation.position[2]
        forward = previous_position - current_position
        lateral = abs(simulation.position[0])
        base_length = float(self.config.base_length)
        reward = forward / base_length - float(self.config.lateral_penalty) * lateral / base_length
        terminated = not simulation.is_finite()
        truncated = self._step_count >= self.horizon and not terminated
        if terminated:
            reward = float(self.config.failure_penalty * self.config.reward_scale)
        info = {
            "time": simulation.time,
            "forward_progress": forward,
            "lateral_deviation": lateral,
            "strain_energy": simulation.strain_energy,
        }
        return self._observation(), float(reward), terminated, truncated, info

    def render(self):
        return None

    def close(self):
        self.simulation = None
