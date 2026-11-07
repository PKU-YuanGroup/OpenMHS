"""Fake backend of the MetaGym Bandits driver: a pure Python stand-in for ``Bandits``.

Why a fake: gym is not installed here, the fake needs only the Python standard library, and package
code never imports the clone.  This module re-implements the small, analytic
``metagym.bandits.bandits_env:Bandits`` interface (the class the driver names as ``native``) and
the ``bandits-v0`` registration values.  Every constant and rule below cites a line of the clone at
the pinned commit ``ca724c22fd0c2ade8ec905edc688a1befdf98a3c``.

The public members are the methods ``Bandits`` itself defines (``reset``, ``step``, ``sample_task``,
``set_task``, ``expected_upperbound``; gate G7), and the space class duck-types ``gym.spaces.Discrete``
(the bridge reads ``n``, ``start``, ``shape`` and ``dtype``).  Inherited ``gym.Env`` helpers such as
``close``, ``render`` and ``seed`` are omitted; this is a fidelity gap of the fake.

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the
driver:

* the upstream ``reset()`` raises until ``set_task`` has run; this fake installs a fixed placeholder
  gain table in ``__init__`` so the bridge can open and reset it like a registered environment;
* upstream draws from numpy's global random generator, this fake uses Python's ``random.Random``;
* the observations are ``None`` in both, as the upstream ``observation_space`` is ``None``.

Nothing here talks to a device.
"""

import math
import random

# metagym/bandits/__init__.py:18-23: bandits-v0 is registered with kwargs arms=50 and max_steps=1000
ARMS = 50
MAX_STEPS = 1000
# metagym/bandits/bandits_env.py:34-36: the default Classical task parameters
DEFAULT_MEAN = 0.50
DEFAULT_DEV = 0.05

# placeholder test data: the fake's fixed gain table seed.  The values it produces are not device
# facts; the upstream task draw uses numpy's global random generator (bandits_env.py:46).
FAKE_SEED = 0x4D455441


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class FakeBandits:
    """Bandits without numpy: ``reset()`` and ``step(action)`` return what the upstream class returns."""

    def __init__(self, arms=ARMS, max_steps=MAX_STEPS, **_options):
        self.max_steps = int(max_steps)                                   # bandits_env.py:18
        self.action_space = Discrete(arms)                                # bandits_env.py:21
        self.observation_space = None                                     # bandits_env.py:24
        self.exp_gains = None
        self.K = int(arms)                                                # bandits_env.py:28
        self.need_reset = True                                            # bandits_env.py:29
        self._rng = random.Random(FAKE_SEED)                              # test data, see FAKE_SEED
        # The upstream reset() raises until set_task has run (bandits_env.py:62-64).  The fake installs
        # a fixed placeholder task so the bridge can reset it; this is a fidelity gap, not upstream.
        self.set_task(self.sample_task())

    def sample_task(self, distribution_settings="Classical", mean=DEFAULT_MEAN, dev=DEFAULT_DEV):
        """The three distributions of ``bandits_env.py:33-55`` on Python's random generator."""
        if distribution_settings == "Classical":
            # bandits_env.py:43-48.  numpy's randint(0, K - 1) is high-exclusive, mirrored here.
            fac = math.sqrt(self.K - 1)
            exp_gains = [mean - dev / fac] * self.K
            sel_idx = self._rng.randrange(self.K - 1)
            exp_gains[sel_idx] = mean + fac * dev
            return [min(1.0, max(0.0, value)) for value in exp_gains]
        if distribution_settings == "Uniform":
            # bandits_env.py:49-50
            return [min(1.0, max(0.0, (self._rng.random() - 0.50) * 3.464 + mean)) for _ in range(self.K)]
        if distribution_settings == "Gaussian":
            # bandits_env.py:51-52 (upstream clips the scalar draw, not an array)
            return min(1.0, max(0.0, self._rng.gauss(mean, dev)))
        raise Exception("No such distribution_settings: %s", distribution_settings)

    def set_task(self, task_config):
        self.exp_gains = task_config                                  # bandits_env.py:58
        assert len(self.exp_gains) == self.K, "task_config must have K gains"   # bandits_env.py:59
        self.need_reset = True                                        # bandits_env.py:60

    def reset(self):
        if self.exp_gains is None:                                    # bandits_env.py:63-64
            raise Exception("Must call \"set_task\" before reset")
        self.steps = 0                                                # bandits_env.py:65
        self.need_reset = False                                       # bandits_env.py:66
        return None                                                   # bandits_env.py:67

    def step(self, action):
        if self.need_reset:                                           # bandits_env.py:70-71
            raise Exception("Must \"reset\" before doing any actions")
        exp_gain = self.exp_gains[action]                             # bandits_env.py:72
        reward = 1 if self._rng.random() < exp_gain else 0            # bandits_env.py:73
        info = {"steps": self.steps, "expected_gain": exp_gain}       # bandits_env.py:74
        self.steps += 1                                               # bandits_env.py:75
        done = self.steps >= self.max_steps                           # bandits_env.py:76
        if done:                                                      # bandits_env.py:77-78
            self.need_reset = True
        return None, reward, done, info                               # bandits_env.py:80

    def expected_upperbound(self):
        return self.max_steps * max(self.exp_gains)                   # bandits_env.py:82-83
