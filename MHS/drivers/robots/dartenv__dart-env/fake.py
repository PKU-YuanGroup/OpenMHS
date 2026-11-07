"""Fake backend of the dart-env driver: a pure Python stand-in for ``gym.envs.algorithmic.copy_:CopyEnv``.

Why a fake: the upstream clone is an old gym package (``pip install .``, numpy, six and the rest of its stack), and
the gate never imports or installs the clone.  This module re-implements the generic tape environment of
``gym/envs/algorithmic/algorithmic_env.py`` and the Copy task of ``gym/envs/algorithmic/copy_.py``, the class the
driver names as ``native``.  Every rule and constant below cites the line of the clone at the pinned commit
43e5f8c17b534e180e2340ec2ef405950ad7f542.  The public members are the ones ``CopyEnv`` and its bases have
(``reset``, ``step``, ``seed``, ``close``, ``generate_input_data``, ``target_from_input_data``, ``input_width`` and
``time_limit``; gate G7), and the space classes duck-type ``gym.spaces.Discrete`` and ``gym.spaces.Tuple`` (the
bridge reads ``n`` and ``spaces``).

What this is not: the upstream environment.  Differences, all in the driver's fidelity ``gaps``:

* the tape and the reset length come from Python's ``random.Random``; upstream draws both from numpy's RandomState
  (``gym/utils/seeding.py``), so a seed does not give the same tape on the two;
* there is no rendering, no numpy ``np_random`` semantics, no ``PassiveEnvChecker`` and no registered
  ``TimeLimit`` wrapper;
* observations are Python ints, as the class returns before any wrapper conversion.

Numbers in this file are either constants of the cited upstream code or test-only initial values.  Nothing here
talks to a device.
"""

import random

# gym/envs/algorithmic/algorithmic_env.py:49: starting_min_length default of AlgorithmicEnv, inherited by CopyEnv
STARTING_MIN_LENGTH = 2
# gym/envs/algorithmic/algorithmic_env.py:59: "last" episodes kept for the promotion decision
PROMOTION_WINDOW = 10
# gym/envs/algorithmic/algorithmic_env.py:47: MIN_REWARD_SHORTFALL_FOR_PROMOTION
PROMOTION_SHORTFALL = -1.0
# gym/envs/algorithmic/algorithmic_env.py:215: the smallest generated tape stops growing at 30
MAX_MIN_LENGTH = 30
# gym/envs/algorithmic/algorithmic_env.py:244-245: the one-dimensional movement set and the initial read head
MOVEMENTS = ("left", "right")
READ_HEAD_START = 0


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``0 .. n - 1`` (``gym/spaces/discrete.py``)."""

    def __init__(self, n):
        assert n >= 0
        self.n = int(n)
        self.start = 0
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < self.n


class Tuple:
    """Duck-typed ``gym.spaces.Tuple``: a product of simpler spaces, checked element by element."""

    def __init__(self, spaces):
        self.spaces = list(spaces)
        self.shape = None

    def contains(self, value):
        if isinstance(value, list):
            value = tuple(value)
        return (isinstance(value, tuple) and len(value) == len(self.spaces)
                and all(space.contains(item) for space, item in zip(self.spaces, value)))


class FakeCopyEnv:
    """CopyEnv without numpy: ``reset()`` and ``step(action)`` return what the upstream class returns.

    The class-level promotion state mirrors the upstream quirk that ``AlgorithmicEnv.min_length`` and
    ``reward_shortfalls`` are shared by every instance (``algorithmic_env.py:64`` and ``:73``); a new fake resets
    them exactly as the upstream constructor does.
    """

    MIN_REWARD_SHORTFALL_FOR_PROMOTION = PROMOTION_SHORTFALL
    MOVEMENTS = MOVEMENTS
    READ_HEAD_START = READ_HEAD_START
    reward_shortfalls = []
    min_length = STARTING_MIN_LENGTH

    def __init__(self, base=5, chars=True):
        # copy_.py:9: CopyEnv(base=5, chars=True) is the configuration Copy-v0 registers (no kwargs)
        self.base = base
        self.last = PROMOTION_WINDOW
        self.episode_total_reward = None
        FakeCopyEnv.reward_shortfalls = []
        if chars:
            self.charmap = [chr(ord("A") + index) for index in range(base)]   # algorithmic_env.py:65-66
        else:
            self.charmap = [str(index) for index in range(base)]              # algorithmic_env.py:67-68
        self.charmap.append(" ")                                              # algorithmic_env.py:69
        FakeCopyEnv.min_length = STARTING_MIN_LENGTH
        # algorithmic_env.py:78-80: movement, write flag, character
        self.action_space = Tuple([Discrete(len(self.MOVEMENTS)), Discrete(2), Discrete(self.base)])
        # algorithmic_env.py:83: one character or the blank index base
        self.observation_space = Discrete(self.base + 1)
        self.np_random = random.Random()
        self._closed = False
        self.seed()                                                           # algorithmic_env.py:84
        self.reset()                                                          # algorithmic_env.py:85

    def seed(self, seed=None):
        """Seed the tape generator; the upstream uses numpy's generator (algorithmic_env.py:91-93)."""
        self.np_random = random.Random(seed)
        return [seed]

    def reset(self):
        self._check_levelup()
        self.last_action = None                                               # algorithmic_env.py:221
        self.last_reward = 0                                                  # algorithmic_env.py:222
        self.read_head_position = self.READ_HEAD_START                        # algorithmic_env.py:223
        self.write_head_position = 0                                          # algorithmic_env.py:224
        self.episode_total_reward = 0.0                                       # algorithmic_env.py:225
        self.time = 0                                                         # algorithmic_env.py:226
        length = self.np_random.randrange(3) + FakeCopyEnv.min_length         # algorithmic_env.py:227
        self.input_data = self.generate_input_data(length)                    # algorithmic_env.py:228
        self.target = self.target_from_input_data(self.input_data)            # algorithmic_env.py:229
        return self._get_obs()                                                # algorithmic_env.py:230

    def step(self, action):
        assert self.action_space.contains(action)                             # algorithmic_env.py:163
        self.last_action = action                                             # algorithmic_env.py:164
        inp_act, out_act, pred = action                                       # algorithmic_env.py:165
        done = False                                                          # algorithmic_env.py:166
        reward = 0.0                                                          # algorithmic_env.py:167
        self.time += 1                                                        # algorithmic_env.py:168
        assert 0 <= self.write_head_position                                  # algorithmic_env.py:169
        if out_act == 1:                                                      # algorithmic_env.py:170
            try:
                correct = pred == self.target[self.write_head_position]      # algorithmic_env.py:172
            except IndexError:
                correct = False                                               # algorithmic_env.py:179
            if correct:
                reward = 1.0                                                  # algorithmic_env.py:181
            else:
                reward = -0.5                                                 # algorithmic_env.py:184
                done = True                                                   # algorithmic_env.py:185
            self.write_head_position += 1                                     # algorithmic_env.py:186
            if self.write_head_position >= len(self.target):                  # algorithmic_env.py:187
                done = True                                                   # algorithmic_env.py:188
        self._move(inp_act)                                                   # algorithmic_env.py:189
        if self.time > self.time_limit:                                       # algorithmic_env.py:190
            reward = -1.0                                                     # algorithmic_env.py:191
            done = True                                                       # algorithmic_env.py:192
        obs = self._get_obs()                                                 # algorithmic_env.py:193
        self.last_reward = reward                                             # algorithmic_env.py:194
        self.episode_total_reward += reward                                   # algorithmic_env.py:195
        return (obs, reward, done, {})                                        # algorithmic_env.py:196

    @property
    def input_width(self):
        return len(self.input_data)                                           # algorithmic_env.py:160

    @property
    def time_limit(self):
        # algorithmic_env.py:198-203: input_width + len(target) + 4
        return self.input_width + len(self.target) + 4

    def generate_input_data(self, size):
        # algorithmic_env.py:263-264: one random character in 0 .. base - 1 per position
        return [self.np_random.randrange(self.base) for _ in range(size)]

    def target_from_input_data(self, input_data):
        # copy_.py:12-13: the Copy task's target is the input tape itself
        return input_data

    def _check_levelup(self):
        # algorithmic_env.py:205-217
        if self.episode_total_reward is None:
            return
        FakeCopyEnv.reward_shortfalls.append(self.episode_total_reward - len(self.target))
        FakeCopyEnv.reward_shortfalls = FakeCopyEnv.reward_shortfalls[-self.last:]
        if (len(FakeCopyEnv.reward_shortfalls) == self.last
                and min(FakeCopyEnv.reward_shortfalls) >= self.MIN_REWARD_SHORTFALL_FOR_PROMOTION
                and FakeCopyEnv.min_length < MAX_MIN_LENGTH):
            FakeCopyEnv.min_length += 1
            FakeCopyEnv.reward_shortfalls = []

    def _move(self, movement):
        # algorithmic_env.py:247-249
        named = self.MOVEMENTS[movement]
        self.read_head_position += 1 if named == "right" else -1

    def _get_obs(self, pos=None):
        # algorithmic_env.py:251-261: the character under the read head, or base when out of bounds
        if pos is None:
            pos = self.read_head_position
        if pos < 0:
            return self.base
        try:
            return self.input_data[pos]
        except IndexError:
            return self.base

    def close(self):
        # gym/core.py:107: Env.close is a no-op by default; keep the callable for the bridge teardown
        self._closed = True
