"""Fake backend of the ChemistryLab driver: a pure Python stand-in for ``ExtractWorldEnv``.

Why a fake: the upstream clone needs the legacy ``gym`` package, numpy, matplotlib and cmocean, and package code never
imports the clone; ``ExtractWorldEnv`` (the base class of the driver's ``native`` symbol) is what this module
re-implements.  The public members are the ones ``ExtractWorldEnv`` has (``reset`` and ``step``; gate G7), and
``action_space`` is the same two-element ``MultiDiscrete([n_actions, 5])`` shape (``water_oil_v1.py:56``).

What this is not: the upstream extraction.  It keeps four material amounts per vessel and applies a simple transfer
for the valve/transfer operations; the vessel event queue, phase separation, spectra and thermodynamics are not
modelled (the driver's fidelity ``gaps`` say so).  The state is a compact three-vessel document, not
``util.generate_state``'s full matrices.  All invented starting amounts, fractions and sizes below are test data
(``# placeholder``); the copied constants cite their upstream line.

Nothing here talks to a device.
"""

# Constants mirrored from the clone at f6536cbc30f06c8d326107a68725f46bb53cff15.
DT = 0.01                                    # chemistrylab/extractworldgym/extractworld_v1_engine.py:18
MAX_STEPS = 100                              # chemistrylab/extractworldgym/extractworld_v1_engine.py:17

# Test data of this stand-in, not facts of the upstream environment.
MATERIAL_ROWS = 4                            # placeholder: the fake's material subset
LAYER_VALUES = 5                             # placeholder: the fake's compact layer vector
INITIAL_AMOUNTS = (                          # placeholder: [H2O, Na, Cl, C6H14] per vessel
    (30.0, 10.0, 10.0, 0.0),                 # placeholder
    (0.0, 0.0, 0.0, 0.0),                    # placeholder
    (0.0, 0.0, 0.0, 0.0),                    # placeholder
)
TARGET_INDEX = 1                             # placeholder: Na in the fake's material row
TRANSFER_FRACTION = 0.25                     # placeholder: share moved per full multiplier
OIL_ADDED = 5.0                              # placeholder: amount added per full multiplier


class MultiDiscrete:
    """Duck-typed ``gym.spaces.MultiDiscrete``: the two-element action space the bridge reads."""

    def __init__(self, nvec):
        self.nvec = [int(value) for value in nvec]
        self.low = [0 for _ in self.nvec]
        self.high = [value - 1 for value in self.nvec]
        self.shape = (len(self.nvec),)
        self.dtype = "int64"


class FakeExtractWorld:
    """The subset of ``ExtractWorldEnv`` the bridge drives: ``reset()`` and ``step(action)``."""

    def __init__(self, **_options):
        self.dt = DT
        self.n_steps = MAX_STEPS
        self.action_space = MultiDiscrete([9, 5])
        self.vessels = None
        self.external_vessels = None
        self.state = None
        self.done = False
        self.reset()

    def reset(self):
        self.done = False
        self.n_steps = MAX_STEPS
        self._amounts = [list(row) for row in INITIAL_AMOUNTS]
        self.state = self._state()
        return self.state

    def step(self, action):
        if not isinstance(action, (list, tuple)) or len(action) != 2:
            raise ValueError("ExtractWorld expects a two-element MultiDiscrete action")
        selector, level = int(action[0]), int(action[1])
        if not 0 <= selector <= 8 or not 0 <= level <= 4:
            raise ValueError("action is outside the MultiDiscrete([9, 5]) space")
        multiplier = level / 4.0 if level != 0 else 0.0       # water_oil_v1.py:107
        reward = -1.0                                        # water_oil_v1.py:105
        done = False
        if selector == 0:
            self._transfer(0, 1, multiplier * TRANSFER_FRACTION)
        elif selector in (1, 2, 3):
            pass                                             # mixing changes no fake amount
        elif selector == 4:
            self._transfer(1, 0, multiplier * TRANSFER_FRACTION)
        elif selector == 5:
            self._transfer(1, 2, multiplier * TRANSFER_FRACTION)
        elif selector == 6:
            self._transfer(0, 2, multiplier * TRANSFER_FRACTION)
        elif selector == 7:
            self._amounts[0][3] += multiplier * OIL_ADDED
        else:                                                # selector 8: Done (water_oil_v1.py:189-192)
            done = True
            reward = self._done_reward()
        self.n_steps -= 1                                    # extractworld_v1_engine.py:63-66
        if self.n_steps == 0:
            done = True
            reward = self._done_reward()
        self.done = done
        self.state = self._state()                           # extractworld_v1_engine.py:62
        return self.state, reward, done, {}                  # extractworld_v1_engine.py:67

    def _transfer(self, source, destination, fraction):
        """Move ``fraction`` of every fake material amount between two vessels (test data, placeholder)."""

        for index, amount in enumerate(self._amounts[source]):
            moved = amount * min(max(fraction, 0.0), 1.0)
            self._amounts[source][index] = amount - moved
            self._amounts[destination][index] += moved

    def _done_reward(self):
        """``done_reward`` of ``water_oil_v1.py:195-205``: -100 when beaker 2 has no target material."""

        collected = self._amounts[2][TARGET_INDEX]
        initial = INITIAL_AMOUNTS[0][TARGET_INDEX]
        if abs(collected) < 1e-6:
            return -100.0
        return (collected / initial) * 100.0

    def _state(self):
        """A compact three-vessel state: [material matrix, solute matrix, layer vector] per vessel."""

        vessels = []
        for amounts in self._amounts:
            material_matrix = [[0.0] * 10 for _ in range(MATERIAL_ROWS)]
            for index, amount in enumerate(amounts):
                material_matrix[index][9] = amount
            solute_matrix = [[0.0] * MATERIAL_ROWS for _ in range(MATERIAL_ROWS)]
            layer_vector = [sum(amounts)] * LAYER_VALUES
            vessels.append([material_matrix, solute_matrix, layer_vector])
        return vessels
