"""Fake backend of the TabularMDP driver: a pure Python stand-in for ``maml_rl.envs.mdp:TabularMDPEnv``.

Why a fake: neither ``gym`` nor ``gymnasium`` is importable where the acceptance gate runs, and package code never
imports or runs the read-only clone (task rule 1).  This module re-implements the class the driver names as ``native``
from ``maml_rl/envs/mdp.py`` at commit 4ef92cebfa11760d9de55d54fc8e827271982a63.  Its public members are the ones
``TabularMDPEnv`` has (``reset``, ``step``, ``seed``, ``sample_tasks``, ``reset_task``; gate G7), and the two space
classes duck-type ``gym.spaces.Discrete`` and ``gym.spaces.Box`` (the bridge reads ``n``, ``start``, ``low``, ``high``,
``shape`` and ``dtype``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the random stream is Python's ``random.Random`` instead of ``gym.utils.seeding.np_random`` (numpy), so one seed
  does not give the same trajectory on the two;
* observations and rewards are Python floats and lists instead of numpy ``float32`` arrays and numpy scalars;
* the registered ``TabularMDP-v0`` adds gym's 10-step ``TimeLimit`` wrapper; this fake models the environment class
  itself, whose ``step`` always returns ``done=False`` (mdp.py:75), so it does not truncate at 10 steps;
* there is no rendering, no ``PassiveEnvChecker`` and no ``OrderEnforcing`` wrapper.

The defaults below are the ones the clone states: ``num_states=10`` and ``num_actions=5`` come from the registration
(maml_rl/envs/__init__.py:19), and the uniform transition tensor and zero mean rewards are the constructor defaults
(maml_rl/envs/mdp.py:31-35).  Any number that is not taken from the clone is a test value and is marked
``# placeholder``.
"""

import random

# maml_rl/envs/__init__.py:19: kwargs={'num_states': 10, 'num_actions': 5}
NUM_STATES = 10
NUM_ACTIONS = 5


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = [float(low)] * int(shape[0])
        self.high = [float(high)] * int(shape[0])
        self.shape = (int(shape[0]),)
        self.dtype = dtype

    def contains(self, value):
        try:
            values = list(value)
        except TypeError:
            return False
        return len(values) == self.shape[0] and all(
            low <= float(item) <= high for item, low, high in zip(values, self.low, self.high))


class FakeTabularMDPEnv:
    """``TabularMDPEnv`` without numpy: ``reset()`` and ``step(action)`` return what the clone's do."""

    def __init__(self, num_states=NUM_STATES, num_actions=NUM_ACTIONS, task=None):
        self.num_states = int(num_states)
        self.num_actions = int(num_actions)
        # maml_rl/envs/mdp.py:27-29
        self.action_space = Discrete(self.num_actions)
        self.observation_space = Box(0.0, 1.0, (self.num_states,))
        task = dict(task or {})
        self._task = task
        # maml_rl/envs/mdp.py:31-35: uniform transitions and zero mean rewards when the task supplies neither
        self._transitions = task.get("transitions")
        if self._transitions is None:
            uniform = 1.0 / self.num_states
            self._transitions = [
                [[uniform for _ in range(self.num_states)] for _ in range(self.num_actions)]
                for _ in range(self.num_states)
            ]
        self._rewards_mean = task.get("rewards_mean")
        if self._rewards_mean is None:
            self._rewards_mean = [[0.0 for _ in range(self.num_actions)] for _ in range(self.num_states)]
        self._state = 0
        self._rng = random.Random()
        self.seed()

    def seed(self, seed=None):
        # maml_rl/envs/mdp.py:39-41: self.np_random, seed = seeding.np_random(seed); return [seed]
        if seed is None:
            seed = random.SystemRandom().randrange(2 ** 31)   # placeholder: a fresh seed, not a device bound
        self._rng = random.Random(seed)
        return [seed]

    def sample_tasks(self, num_tasks):
        # maml_rl/envs/mdp.py:43-50: Dirichlet(1) transitions and Normal(1, 1) mean rewards
        tasks = []
        for _ in range(int(num_tasks)):
            transitions = [
                [self._dirichlet(1.0, self.num_states) for _ in range(self.num_actions)]
                for _ in range(self.num_states)
            ]
            rewards_mean = [
                [self._rng.gauss(1.0, 1.0) for _ in range(self.num_actions)]
                for _ in range(self.num_states)
            ]
            tasks.append({"transitions": transitions, "rewards_mean": rewards_mean})
        return tasks

    def reset_task(self, task):
        # maml_rl/envs/mdp.py:52-55
        self._task = task
        self._transitions = task["transitions"]
        self._rewards_mean = task["rewards_mean"]

    def reset(self):
        # maml_rl/envs/mdp.py:57-63: an episode always starts on the first state, observed one-hot
        self._state = 0
        return self._one_hot()

    def step(self, action):
        assert self.action_space.contains(action)
        # maml_rl/envs/mdp.py:65-75
        mean = self._rewards_mean[self._state][action]
        reward = self._rng.gauss(float(mean), 1.0)
        self._state = self._choose(self._transitions[self._state][action])
        return self._one_hot(), reward, False, dict(self._task)

    # -- helpers ---------------------------------------------------------------
    def _one_hot(self):
        observation = [0.0] * self.num_states
        observation[self._state] = 1.0
        return observation

    def _dirichlet(self, alpha, count):
        draws = [self._rng.gammavariate(alpha, 1.0) for _ in range(int(count))]
        total = sum(draws)
        return [draw / total for draw in draws]

    def _choose(self, probabilities):
        total = float(sum(probabilities))
        if total <= 0.0:
            return self._rng.randrange(self.num_states)
        threshold = self._rng.random() * total
        running = 0.0
        for index, probability in enumerate(probabilities):
            running += float(probability)
            if threshold < running:
                return index
        return len(probabilities) - 1
