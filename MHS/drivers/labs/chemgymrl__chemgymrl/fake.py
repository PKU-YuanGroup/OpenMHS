"""Fake backend of the GenWurtzExtract-v2 driver: a pure Python stand-in for the chemistry bench.

Why a fake: the upstream package needs gymnasium, numpy, numba and the clone's data files, and package code never
imports the clone.  This module re-implements the *interface* of
``chemistrylab.benches.extract_bench:GeneralWurtzExtract_v2`` (the class the driver names as ``native``): the same
``reset(seed, options)`` and ``step(action)`` returns, a ``Discrete`` action space, a ``Box`` observation space and
the ``metadata`` mapping.  The public members are the ones the upstream class has (``reset``, ``step``; gate G7).

What this is not: the upstream environment.  It does not model vessels, materials, spectra, reactions or the
reward generator.  The vessel fills, layer vectors and reward below are placeholder data (``# placeholder``), and
the fidelity ``gaps`` of the driver say so.  The structural constants (three working vessels, 100 layer values per
vessel, seven targets, 41 flattened discrete actions, 50 steps) are copied from the cited upstream lines, not
measured from it.

The two space classes duck-type ``gymnasium.spaces.Discrete`` and ``Box``: the bridge reads ``n``, ``start``,
``low``, ``high`` and ``shape``.
"""

import random

# chemistrylab/benches/extract_bench.py:159-165: five initial vessels, of which three are working vessels
N_VESSELS = 3
# chemistrylab/benches/characterization_bench.py:68: layers=100 values per vessel
LAYER_VALUES = 100
# chemistrylab/benches/general_bench.py:68: GenBench's default max_steps
MAX_STEPS = 50
# chemistrylab/reactions/available_reactions/chloro_wurtz.json:9-16: the seven products of chloro_wurtz.json
TARGETS = (
    "dodecane",
    "5-methylundecane",
    "4-ethyldecane",
    "5,6-dimethyldecane",
    "4-ethyl-5-methylnonane",
    "4,5-diethyloctane",
    "NaCl",
)
# chemistrylab/benches/extract_bench.py:166-179: eight amounts arrays of five rows plus the last Action's one row
N_ACTIONS = 5 + 5 + 5 + 5 + 5 + 5 + 5 + 5 + 1


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"
        self.seed_value = None

    def seed(self, seed=None):
        self.seed_value = seed

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeGeneralWurtzExtract:
    """A minimal stand-in for ``GeneralWurtzExtract_v2``: ``reset``, ``step`` and the two spaces."""

    def __init__(self):
        # chemistrylab/benches/extract_bench.py:152-155
        self.metadata = {"render_modes": ["rgb_array"], "render_fps": 10}
        self.render_mode = "rgb_array"
        # chemistrylab/benches/general_bench.py:85 and :99: Discrete(n_actions)
        self.action_space = Discrete(N_ACTIONS)
        # chemistrylab/benches/general_bench.py:90: Box(0, 1, observation_shape, dtype=np.float32)
        size = N_VESSELS * (LAYER_VALUES + len(TARGETS))
        self.observation_space = Box([0.0] * size, [1.0] * size)
        # chemistrylab/benches/general_bench.py:68: GenBench's max_steps
        self.max_steps = MAX_STEPS
        # chemistrylab/benches/extract_bench.py:181: the products loaded as the target list
        self.targets = list(TARGETS)
        self.target_material = None
        self.steps = 0
        self._target_index = 0
        self._seed = None
        self._terminal = False
        # The upstream constructor calls reset() (general_bench.py:105); the bridge resets again with its seed.
        self.reset()

    def reset(self, *args, seed=None, options=None):
        """``general_bench.py:235-240``: seed the generator, choose a target, rebuild the working vessels."""
        self._seed = seed
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self.action_space.seed(seed)
        # options are accepted and ignored: upstream's reset never reads them
        self._target_index = self._rng.randrange(len(self.targets))
        self.target_material = self.targets[self._target_index]
        self.steps = 0
        self._terminal = False
        # placeholder: the three working vessels start with arbitrary fill fractions and mix counters
        self._vessels = [
            {"fill": 0.6, "mix": 0},   # placeholder
            {"fill": 0.25, "mix": 0},  # placeholder
            {"fill": 0.0, "mix": 0},   # placeholder
        ]
        return self._observation(), {}

    def step(self, action):
        """``general_bench.py:201-222``: apply one discrete action and return the five-tuple."""
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) is not in the action space")
        group, row, terminal = _flattened_action(action)
        self._apply(group, row)
        self.steps += 1
        # general_bench.py:213: done = terminal or steps >= max_steps
        done = bool(terminal or self.steps >= self.max_steps)
        self._terminal = done
        # placeholder: the fake never computes the upstream reward generator
        reward = 0.0
        # general_bench.py:222: (state, reward, done, False, {})
        return self._observation(), reward, done, False, {}

    def _apply(self, group, row):
        """Placeholder event effects for the nine upstream Action groups (extract_bench.py:169-178)."""
        vessels = self._vessels
        if group == 0:            # drain by pixel from vessel 0
            vessels[0]["fill"] = max(0.0, vessels[0]["fill"] - 0.02 * (row + 1))
        elif group == 1:          # mix vessel 0
            vessels[0]["mix"] += 1
        elif group == 2:          # pour vessel 1 into vessel 0
            moved = min(vessels[1]["fill"], 0.05)
            vessels[1]["fill"] -= moved
            vessels[0]["fill"] = min(1.0, vessels[0]["fill"] + moved)
        elif group == 3:          # pour vessel 2 into vessel 0
            moved = min(vessels[2]["fill"], 0.05)
            vessels[2]["fill"] -= moved
            vessels[0]["fill"] = min(1.0, vessels[0]["fill"] + moved)
        elif group == 4:          # pour vessel 0 into vessel 2
            moved = min(vessels[0]["fill"], 0.05)
            vessels[0]["fill"] -= moved
            vessels[2]["fill"] = min(1.0, vessels[2]["fill"] + moved)
        elif group in (5, 6):     # pour a solvent into vessel 0
            vessels[0]["fill"] = min(1.0, vessels[0]["fill"] + 0.02)
        elif group == 7:          # mix vessels 0, 1 and 2
            for vessel in vessels:
                vessel["mix"] += 1
        else:                     # the terminal mixing action
            for vessel in vessels:
                vessel["mix"] += 1

    def _observation(self):
        """Placeholder layer vectors plus the one-hot target, for every working vessel."""
        one_hot = [0.0] * len(self.targets)
        one_hot[self._target_index] = 1.0
        out = []
        for vessel in self._vessels:
            filled = int(round(vessel["fill"] * LAYER_VALUES))
            shift = vessel["mix"] % LAYER_VALUES
            for index in range(LAYER_VALUES):
                value = 1.0 if index < filled else 0.0
                if vessel["mix"] and (index - shift) % LAYER_VALUES < 5:
                    value = 0.5
                out.append(value)
            out.extend(one_hot)
        return out


def _flattened_action(action):
    """``general_bench.py:229``: one index per (Action, parameter row), in the order of the action list."""
    # extract_bench.py:169-178: the row count and terminal flag of each of the nine Action entries
    groups = (
        (5, False), (5, False), (5, False), (5, False), (5, False),
        (5, False), (5, False), (5, False), (1, True),
    )
    remaining = int(action)
    for group, (rows, terminal) in enumerate(groups):
        if remaining < rows:
            return group, remaining, terminal
        remaining -= rows
    raise AssertionError(f"{action!r} is not in the action space")
