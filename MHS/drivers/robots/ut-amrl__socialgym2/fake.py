"""Package fake for the SocialGym2 multi-agent simulator (``RosSocialEnv``).

The acceptance gate runs without ROS, ``ut_multirobot_sim``, PettingZoo or the upstream
``observer``/``rewarder`` objects, so this module is a pure-Python stand-in for the environment's
step contract.  It does not import or run the clone.

This fake preserves the native ParallelEnv surface: action_space(agent), observation_space(agent), and five
per-agent mappings from step. The package adapter.py wraps both this raw fake and an explicitly attached native;
it owns joint-space construction, reward/flag reduction and preservation of original info.

Every numeric value of the stand-in's motion and start state is test data marked
``# placeholder``; it is not a fact of the simulator.  The real observation width is
``len(observer)`` and therefore configuration dependent, so the fake uses a shorter placeholder
per agent and says so in the driver's fidelity gaps.  Nothing here talks to a device.
"""

import random
from collections.abc import Mapping

#: The fake models five agents, the maximum of the upstream constructor default num_agents=(3, 5)
#: (src/environment/ros_social_gym.py:80-81,144-157).  The real agent count is a deployment
#: configuration, not a device bound.
N_AGENTS = 5                                      # placeholder configuration
#: The real observation width is len(observer) (src/environment/ros_social_gym.py:169-171); the
#: observer's registered observation list is a runtime configuration.  The fake returns a shorter
#: placeholder vector, disclosed in the driver's fidelity gaps.
OBSERVATION_WIDTH = 4                             # placeholder, smaller than the real width
#: Placeholder observation value used by the fake's trivial dynamics.
OBSERVATION_START = 0.0                           # placeholder
OBSERVATION_STEP = 0.25                           # placeholder


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the bridge reads ``n``, ``start`` and ``dtype``."""

    def __init__(self, n):
        self.n = int(n)
        self.start = 0
        self.shape = ()
        self.dtype = "int64"


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakeSocialGym:
    """Pure-Python stand-in for ``environment.ros_social_gym:RosSocialEnv``.

    The fake exposes upstream reset/step/close and per-agent space methods; it performs no joint projection.
    """

    def __init__(self, **_options):
        self.possible_agents = [f"player_{index}" for index in range(N_AGENTS)]
        # ros_social_gym.py:168: every possible agent gets spaces.Discrete(2).
        self.action_spaces = dict({agent: Discrete(2) for agent in self.possible_agents})
        # ros_social_gym.py:169-171: Box(low=-9999, high=9999, shape=(len(observer),)).
        self.observation_spaces = dict(
            {
                agent: Box(
                    [-9999.0] * OBSERVATION_WIDTH,
                    [9999.0] * OBSERVATION_WIDTH,
                    (OBSERVATION_WIDTH,),
                )
                for agent in self.possible_agents
            }
        )
        self._rng = random.Random(0)              # placeholder
        self._pending_seed = None
        self.agents = list(self.possible_agents)
        self._tick = 0
        self._observations = {}
        self._reset(None)

    def action_space(self, agent):
        return self.action_spaces[agent]

    def observation_space(self, agent):
        return self.observation_spaces[agent]

    def _reset(self, seed):
        self.agents = list(self.possible_agents)
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._tick = 0
        self._observations = {
            agent: [OBSERVATION_START + 0.01 * index for index in range(OBSERVATION_WIDTH)]
            for agent in self.possible_agents
        }                                         # placeholder values

    def _observation(self):
        return {agent: list(values) for agent, values in self._observations.items()}

    def reset(self, seed=None, options=None):
        """Reset the episode and return ``(observations, infos)`` like ``RosSocialEnv.reset``.

        The upstream signature is ``reset(seed=None, return_info=True, options=None)``
        (src/environment/ros_social_gym.py:272) and it returns a dict of per-agent observations
        plus a dict of infos (src/environment/ros_social_gym.py:341-346).
        """
        if options is not None and not isinstance(options, dict):
            raise ValueError("options must be a mapping")
        self._reset(seed)
        return self._observation(), {agent: {} for agent in self.possible_agents}

    def step(self, action_dict):
        """Apply one joint action and return the native five per-agent mappings.

        ``action_dict`` maps an agent name to its ``Discrete(2)`` action, as
        ``RosSocialEnv.step`` receives (src/environment/ros_social_gym.py:348,361-367).  The
        upstream returns ``(observations, rewards, terminations, truncations, infos)`` with
        per-agent dicts (src/environment/ros_social_gym.py:447); the shared production adapter projects scalar reward and flags and preserves all maps.  The motion below is placeholder test data, not simulator dynamics.
        """
        if not isinstance(action_dict, dict):
            raise ValueError("action_dict must map agent names to discrete actions")
        rewards = {}
        terminations = {}
        truncations = {}
        agents_info = {}
        for index, agent in enumerate(self.possible_agents):
            action = int(action_dict.get(agent, 0))
            if action not in (0, 1):
                raise ValueError(f"{agent}: action must be 0 or 1")
            # Placeholder motion: the first value moves toward +1 or -1 depending on the action.
            self._observations[agent][0] = self._observations[agent][0] + OBSERVATION_STEP * (
                1 if action == 1 else -1
            )
            self._observations[agent][0] = max(-9999.0, min(9999.0, self._observations[agent][0]))
            rewards[agent] = 0.0               # placeholder
            terminations[agent] = False
            truncations[agent] = False
            agents_info[agent] = {"index": index, "action": action}
        self._tick += 1
        return self._observation(), rewards, terminations, truncations, agents_info

    def close(self):
        """``RosSocialEnv.close`` is a no-op (src/environment/ros_social_gym.py:220-221)."""
        return None
