"""OpenMHS driver for gh.kagisokgwahla/capstone-molecule-environment: the molecule-v0 simulation.

The upstream is a small reinforcement-learning environment for inverse drug design.  It is not a Gymnasium
environment in the sense of the bridge: ``MoleculeEnvironment`` has no ``action_space`` and no
``observation_space``, its ``reset()`` returns ``None``, its ``step()`` returns an ``Observation`` object instead of
the Gymnasium five-tuple, and its ``seed(Smiles)`` takes a SMILES string, not an integer seed
(``gym_molecule/envs/molecule_env.py:38-85``).  A ``GymnasiumDriver`` derives the contract from the environment's
spaces, so that shape cannot express this interface.  This package is therefore a direct ``Driver`` over the
upstream class (see RESULT.json, "DEVIATION FROM THE CARD").

The two bound capabilities are ``cap.world.step.v1`` and ``cap.world.reset.v1``.  A step accepts the catalogue
class's ``ticks`` and an ``action`` object shaped like the upstream ``Action`` class (``action_c``, ``pos`` and
``mol``; ``molecule_env.py:87-96``); the driver builds a plain stand-in object with those three attributes and calls
``MoleculeEnvironment.step`` once per tick.  A reset calls ``MoleculeEnvironment.reset`` and then
``MoleculeEnvironment.seed("C")`` so that both the current molecule and ``molecule_list`` are the documented carbon
start state (``molecule_env.py:39-41`` and ``:77-79``); the upstream ``reset`` alone leaves ``molecule_list``
untouched.

``cap.world.seed.v1`` is deliberately not bound: the upstream ``seed`` is a SMILES start-molecule setter, not a
random-number-generator seed, so the class's integer ``seed`` input cannot be carried without inventing a mapping.
The environment exposes no state snapshot either, so the fidelity contract claims no determinism kind.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The fake backend (``fake.py``) is the package's own pure Python stand-in; it was not compared with the
upstream environment (RDKit and gym were not run where the gate ran).  This package is model-authored and
unreviewed, and is checked on the fake backend only.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from mhs import canonical
from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

MOLECULE_ENV = "gym_molecule/envs/molecule_env.py"
INIT = "gym_molecule/__init__.py"


@dataclass
class _Action:
    """The three fields ``MoleculeEnvironment.step`` reads from an action object (``molecule_env.py:45-55``)."""

    action_c: str
    pos: str
    mol: str


class MoleculeEnvironmentDriver(Driver):
    device_id = "molecule-v0"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R0"
    native = "gym_molecule.envs:MoleculeEnvironment"
    backends = {"fake": ".fake:FakeMoleculeEnvironment"}
    display_name = "molecule-v0 molecular editing environment"
    vendor, model = "kagisokgwahla", "capstone-molecule-environment"
    tags = ["molecule", "drug-design", "reinforcement-learning", "simulation", "smiles"]
    facts = [
        Fact("The environment is registered under the id molecule-v0 with entry point "
             "gym_molecule.envs:MoleculeEnvironment", source="upstream_code", ref=f"{INIT}:3-6"),
        Fact("MoleculeEnvironment is a gym.Env subclass", source="upstream_code", ref=f"{MOLECULE_ENV}:14"),
        Fact("The constructor starts the current molecule as carbon, Chem.MolFromSmiles('C')",
             source="upstream_code", ref=f"{MOLECULE_ENV}:39"),
        Fact("The constructor starts molecule_list as ['C']", source="upstream_code", ref=f"{MOLECULE_ENV}:41"),
        Fact("step adds action_ob.mol at the front or the back of molecule_list when action_c is Add",
             source="upstream_code", ref=f"{MOLECULE_ENV}:46-50"),
        Fact("step removes the first or the last molecule_list element when action_c is Remove",
             source="upstream_code", ref=f"{MOLECULE_ENV}:51-55"),
        Fact("step rebuilds current_molecule from listToSmiles, updates obs and returns only self.obs: no reward, "
             "terminated or truncated value", source="upstream_code", ref=f"{MOLECULE_ENV}:57-63"),
        Fact("reset sets current_molecule to carbon and returns nothing", source="upstream_code",
             ref=f"{MOLECULE_ENV}:65-66"),
        Fact("seed takes a SMILES string and sets current_molecule and molecule_list from it", source="upstream_code",
             ref=f"{MOLECULE_ENV}:77-79"),
        Fact("listToSmiles concatenates every molecule_list entry into one SMILES string", source="upstream_code",
             ref=f"{MOLECULE_ENV}:81-85"),
        Fact("render returns a grid image of mol_Steps drawn with Draw.MolsToGridImage", source="upstream_code",
             ref=f"{MOLECULE_ENV}:68-74"),
        Fact("Action.setAction stores action_c, mol (default 'C') and pos", source="upstream_code",
             ref=f"{MOLECULE_ENV}:93-96"),
        Fact("Observation.getObservation returns Chem.MolToSmiles of its molecule", source="upstream_code",
             ref=f"{MOLECULE_ENV}:114-116"),
        Fact("The README describes the project as a reinforcement learning environment for inverse drug design",
             source="vendor_doc", ref="README.md:16"),
        Fact("The README names step, reset, render, seed and close as the essential methods", source="vendor_doc",
             ref="README.md:41-42"),
        Fact("The test constructs MoleculeEnvironment and asserts that it is a gym.Env", source="upstream_code",
             ref="tests/environment_test.py:5-7"),
        Fact("environment.yml lists Python 3.7.7 with gym and rdkit", source="vendor_doc",
             ref="environment.yml:7-15"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the molecule and tick stay readable")
    #: The model as deployed.  The upstream environment is a discrete molecule-list editor: it has no time step, no
    #: seed control and no state snapshot, and its transitions are functional-group list operations.
    fidelity = {
        "engine": "custom:gym_molecule-molecule-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the list edits are deterministic, but the upstream exposes no integer seed (its seed() takes a "
                     "SMILES string) and no get_state/set_state, so this package makes no replay claim",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: each transition adds or removes a SMILES fragment in molecule_list; there is no physics, "
            "no time step and no continuous state",
            "the fake backend replaces RDKit's MolFromSmiles/MolToSmiles with plain SMILES string concatenation; it "
            "does not parse, validate or canonicalise a molecule, and it was not compared with the upstream "
            "environment",
            "the upstream defines no action_space or observation_space, returns an Observation object from step and "
            "None from reset, and has no reward, terminated, truncated or info values",
            "no seed control: the upstream seed(Smiles) selects a start molecule and is not an integer RNG seed, so "
            "cap.world.seed.v1 is not bound",
            "rendering is not served: render() returns a PIL image and cap.world.render.v1 needs an artifact store",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }

    # ------------------------------------------------------------------ state
    def _tick_value(self) -> int:
        return int(getattr(self, "_tick", 0))

    def _episode_value(self) -> int:
        return int(getattr(self, "_episode", 0))

    def _observation(self) -> dict:
        """The current molecule as the SMILES string the upstream listToSmiles builds (``molecule_env.py:81-85``)."""
        return {"smiles": str(self.native.listToSmiles())}

    @read("observation", type="object", description="Current molecule as the concatenated molecule_list SMILES string",
          properties={"smiles": Field("string", description="SMILES string of the current molecule_list")})
    def observation(self) -> dict:
        return self._observation()

    @read("tick", type="integer", unit="1", description="Transitions applied since the last reset")
    def tick(self) -> int:
        return self._tick_value()

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self) -> int:
        return self._episode_value()

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Apply one molecule edit per tick to the upstream MoleculeEnvironment list",
            input={
                "ticks": Field("integer", unit="1",
                               description="Transitions to advance; the edit is applied at every tick"),
                "action": Field("object", description="The upstream action object: action_c, pos and mol",
                                properties={
                                    "action_c": Field("string", description="Add or Remove, as the upstream step reads it"),
                                    "pos": Field("string", description="front or back, as the upstream step reads it"),
                                    "mol": Field("string", description="SMILES fragment added to molecule_list"),
                                }),
            })
    def step(self, ticks: int, action: dict) -> dict:
        edit = _Action(str(action["action_c"]), str(action["pos"]), str(action["mol"]))
        for _ in range(int(ticks)):
            self.native.step(edit)
        self._tick = self._tick_value() + int(ticks)
        observation = self._observation()
        return {
            "observation": observation,
            "tick": self._tick,
            "state_hash": canonical.digest({"observation": observation, "tick": self._tick}),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the current molecule and molecule_list to the carbon start state",
            input={"options": Field("object", description="Environment-specific reset options",
                                    properties={
                                        "smiles": Field("string",
                                                        description="Start SMILES passed to MoleculeEnvironment.seed"),
                                    })})
    def reset_world(self, options=None) -> dict:
        start = "C"
        if options is not None:
            if not isinstance(options, Mapping):
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "options must be an object")
            start = options.get("smiles", "C")
            if not isinstance(start, str) or not start:
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "options.smiles must be a non-empty string")
        self.native.reset()
        self.native.seed(start)
        self._tick = 0
        self._episode = self._episode_value() + 1
        return {"observation": self._observation(), "seed": 0}
