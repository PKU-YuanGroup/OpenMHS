"""Fake backend of the molecule-v0 driver: a pure Python stand-in for ``MoleculeEnvironment``.

Why a fake: the upstream environment needs RDKit, gym and the clone's chemistry data, and package code never imports
the clone.  This module mirrors the *interface* of ``gym_molecule.envs:MoleculeEnvironment`` (the class the driver
names as ``native``): ``step(action_ob)`` reads ``action_c``, ``pos`` and ``mol``, ``reset()`` restores the carbon
current molecule, ``seed(Smiles)`` restores a SMILES start state, and ``listToSmiles()`` concatenates the list
(``gym_molecule/envs/molecule_env.py:38-85``).  The public members are the upstream class's members (gate G7).

What this is not: the upstream environment.  It does not use RDKit: a molecule is a plain SMILES string and
``MolFromSmiles``/``MolToSmiles`` parsing, validation and canonicalisation are not modelled.  The fake was not
compared with the upstream environment.  The start molecule ``C`` and the ``Add``/``Remove`` behaviour are copied
from the cited upstream lines, not measured.

Nothing here talks to a device.
"""

# gym_molecule/envs/molecule_env.py:39 and :41: the constructor starts with carbon and molecule_list ['C'].
START_SMILES = "C"


class _Observation:
    """The ``Observation`` object the upstream ``step`` returns (``molecule_env.py:98-119``) without RDKit."""

    def __init__(self, smiles):
        self.mol = smiles
        self.observation = smiles
        self.info = []

    def getInfo(self):
        """The upstream asks RDKit's feature factory; the fake has no features and returns an empty list."""
        self.info = []
        return self.info

    def getObservation(self):
        self.observation = self.mol
        return self.observation

    def update(self, mol):
        self.mol = mol


class FakeMoleculeEnvironment:
    """A stand-in for ``MoleculeEnvironment``: the same list edits, reset and seed methods."""

    def __init__(self):
        self.current_molecule = START_SMILES
        self.obs = _Observation(START_SMILES)
        self.molecule_list = [START_SMILES]
        self.mol_Steps = []
        self.smiles = []

    def step(self, action_ob):
        """``molecule_env.py:45-63``: edit the list, rebuild the current molecule and return the observation."""
        if action_ob.action_c == "Add":
            if action_ob.pos == "front":
                self.molecule_list.insert(0, action_ob.mol)
            elif action_ob.pos == "back":
                self.molecule_list.append(action_ob.mol)
        elif action_ob.action_c == "Remove":
            if action_ob.pos == "front":
                self.molecule_list.remove(self.molecule_list[0])
            elif action_ob.pos == "back":
                self.molecule_list.pop()
        self.current_molecule = self.listToSmiles()
        self.obs.update(self.current_molecule)
        self.mol_Steps.append(self.current_molecule)
        legend = str(len(self.mol_Steps)) + ". " + self.listToSmiles()
        self.smiles.append(legend)
        return self.obs

    def reset(self):
        """``molecule_env.py:65-66``: set the current molecule back to carbon and return nothing."""
        self.current_molecule = START_SMILES

    def seed(self, Smiles):
        """``molecule_env.py:77-79``: set the current molecule and molecule_list from a SMILES string."""
        self.current_molecule = Smiles
        self.molecule_list = [Smiles]

    def listToSmiles(self):
        """``molecule_env.py:81-85``: concatenate every molecule_list entry into one SMILES string."""
        smiles = ""
        for mol_str in self.molecule_list:
            smiles += mol_str
        return smiles
