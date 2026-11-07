"""Fake backend of the SustainDC Gymnasium driver (pure Python, no upstream import).

The driver names ``sustaindc_env:SustainDC`` as its native class.  This module re-implements the public Gymnasium
surface the bridge uses -- ``reset``, ``step``, ``seed``, ``close``, ``action_space`` and ``observation_space`` --
with the sizes and bounds the upstream environments state, and placeholder transitions.  It imports neither
gymnasium nor the clone.

Upstream SustainDC is a multi-agent environment: ``EnvConfig.DEFAULT_CONFIG`` runs ``agent_ls``, ``agent_dc`` and
``agent_bat`` (sustaindc_env.py:40), and each agent has a ``Discrete(3)`` action space (envs/carbon_ls.py:40,
utils/make_envs_pyenv.py:132, envs/bat_env_fwd_view.py:27).  The bridge derives a
``{"agent_ls": 0..2, "agent_dc": 0..2, "agent_bat": 0..2}`` Dict action from those spaces.  The observation sizes
and bounds are the upstream ones: a 26-element Box from -2 to 2 for the load-shifting agent
(envs/carbon_ls.py:45), a 14-element Box from -1 to 1 for the data-center agent
(utils/make_envs_pyenv.py:114-116) and a 13-element Box from -1 to 1 for the battery agent
(envs/bat_env_fwd_view.py:23-24).

Everything the upstream does not state (initial values, transition increments and rewards) is test data and is
marked ``# placeholder``.  Nothing here talks to a device, runs the data-center physics, or reproduces an upstream
trajectory; the fidelity ``gaps`` of the driver say what is not modelled.
"""

import random

# sustaindc_env.py:40: the default configuration runs these three agents.
AGENTS = ("agent_ls", "agent_dc", "agent_bat")
# envs/carbon_ls.py:45, utils/make_envs_pyenv.py:114-116 and envs/bat_env_fwd_view.py:23-24: observation sizes.
OBS_SIZES = {"agent_ls": 26, "agent_dc": 14, "agent_bat": 13}
# envs/carbon_ls.py:45, utils/make_envs_pyenv.py:114-116 and envs/bat_env_fwd_view.py:23-24: observation bounds.
OBS_BOUNDS = {"agent_ls": 2.0, "agent_dc": 1.0, "agent_bat": 1.0}
# envs/carbon_ls.py:40, utils/make_envs_pyenv.py:132 and envs/bat_env_fwd_view.py:27: Discrete(3) per agent.
ACTION_SIZE = 3
# placeholder: 7 days at 4 timesteps per hour (upstream default days_per_episode 7, sustaindc_env.py:55, and
# 4 timesteps per hour, utils/make_envs_pyenv.py:194).
EPISODE_TICKS = 672


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        return len(value) == len(self.low) and all(
            low <= item <= high for item, low, high in zip(value, self.low, self.high))


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` and maps each member."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = None
        self.dtype = None


def _box(size, bound):
    return Box([-float(bound)] * size, [float(bound)] * size)


class FakeSustainDC:
    """A small SustainDC stand-in with the upstream agent keys, spaces and observation sizes."""

    def __init__(self, **_options):
        # sustaindc_env.py:164-189: one space per configured agent.  The bridge maps the Dict members to JSON.
        self.observation_space = Dict({name: _box(OBS_SIZES[name], OBS_BOUNDS[name]) for name in AGENTS})
        self.action_space = Dict({name: Discrete(ACTION_SIZE) for name in AGENTS})
        self.agents = list(AGENTS)                 # sustaindc_env.py:40
        self._rng = random.Random(0)
        self._seed = None
        self._tick = 0
        self._observations = {name: [0.0] * OBS_SIZES[name] for name in AGENTS}  # placeholder: zero start state
        self._closed = False

    def _observation_dict(self):
        """A copy of the per-agent state dict, in the shape upstream reset() returns (sustaindc_env.py:502-531)."""
        return {name: list(self._observations[name]) for name in AGENTS}

    def reset(self, seed=None, options=None):
        """Reset the episode; the bridge also accepts a Gymnasium seed and an options object.

        Upstream reset() takes no arguments and returns only the state dict (sustaindc_env.py:436-531); the fake
        accepts the optional seed so the bridge can reproduce a run, and returns ``(state, info)`` as gymnasium
        expects.  ``options`` is accepted and ignored.
        """
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._tick = 0
        # placeholder: the initial agent states are not drawn by upstream reset() (they come from its managers).
        self._observations = {
            name: [round(self._rng.uniform(-0.5, 0.5), 6) for _ in range(OBS_SIZES[name])]  # placeholder
            for name in AGENTS
        }
        return self._observation_dict(), {"tick": 0, "seed": self._seed}  # placeholder info values

    def step(self, action):
        """Apply one action per agent, advance one quarter-hour tick and return the gymnasium five-tuple.

        Upstream step() takes an action dict but returns per-agent reward, terminated and truncated dicts
        (sustaindc_env.py:533-621).  The bridge serves a single scalar reward and a single terminated/truncated
        flag, so the fake sums the three placeholder rewards and truncates at EPISODE_TICKS.
        """
        if not isinstance(action, dict):
            raise ValueError("action must be a dict keyed by agent")
        for name in AGENTS:
            value = action.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < ACTION_SIZE:
                raise ValueError(f"action[{name!r}] must be an int in 0..{ACTION_SIZE - 1}")

        self._tick += 1
        rewards = {}
        for index, name in enumerate(AGENTS):
            # placeholder: the transition and the individual reward are test data, not upstream physics.
            delta = (action[name] - 1) * 0.01 * (index + 1)
            bound = OBS_BOUNDS[name]
            self._observations[name] = [
                round(max(-bound, min(bound, item + delta)), 6) for item in self._observations[name]
            ]
            rewards[name] = -0.01 * (index + 1) * action[name]  # placeholder
        reward = float(sum(rewards.values()))  # placeholder: the bridge carries one scalar reward
        truncated = self._tick >= EPISODE_TICKS  # placeholder: fixed episode length
        info = {"tick": self._tick, "actions": dict(action), "rewards": rewards}  # placeholder info values
        return self._observation_dict(), reward, False, truncated, info

    def seed(self, seed=None):
        """Set the generator of the next reset, as upstream seed() seeds its generators (sustaindc_env.py:241-249)."""
        self._seed = int(seed) if seed is not None else 1
        self._rng = random.Random(self._seed)
        return None

    def close(self):
        """Close the environment; upstream close() exists at sustaindc_env.py:739-743."""
        self._closed = True
