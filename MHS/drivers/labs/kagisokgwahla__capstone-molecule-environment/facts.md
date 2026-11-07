# Facts and tags for gh.kagisokgwahla/capstone-molecule-environment

Every fact cites its source at commit `8c1bb00fcec88b366ba3947623fa3d52990be0d2`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is registered under the id molecule-v0 with entry point gym_molecule.envs:MoleculeEnvironment | upstream_code | gym_molecule/__init__.py:3-6 |
| MoleculeEnvironment is a gym.Env subclass | upstream_code | gym_molecule/envs/molecule_env.py:14 |
| The constructor starts the current molecule as carbon, Chem.MolFromSmiles('C') | upstream_code | gym_molecule/envs/molecule_env.py:39 |
| The constructor starts molecule_list as ['C'] | upstream_code | gym_molecule/envs/molecule_env.py:41 |
| step adds action_ob.mol at the front or the back of molecule_list when action_c is Add | upstream_code | gym_molecule/envs/molecule_env.py:46-50 |
| step removes the first or the last molecule_list element when action_c is Remove | upstream_code | gym_molecule/envs/molecule_env.py:51-55 |
| step rebuilds current_molecule from listToSmiles, updates obs and returns only self.obs: no reward, terminated or truncated value | upstream_code | gym_molecule/envs/molecule_env.py:57-63 |
| reset sets current_molecule to carbon and returns nothing | upstream_code | gym_molecule/envs/molecule_env.py:65-66 |
| seed takes a SMILES string and sets current_molecule and molecule_list from it | upstream_code | gym_molecule/envs/molecule_env.py:77-79 |
| listToSmiles concatenates every molecule_list entry into one SMILES string | upstream_code | gym_molecule/envs/molecule_env.py:81-85 |
| render returns a grid image of mol_Steps drawn with Draw.MolsToGridImage | upstream_code | gym_molecule/envs/molecule_env.py:68-74 |
| Action.setAction stores action_c, mol (default 'C') and pos | upstream_code | gym_molecule/envs/molecule_env.py:93-96 |
| Observation.getObservation returns Chem.MolToSmiles of its molecule | upstream_code | gym_molecule/envs/molecule_env.py:114-116 |
| The README describes the project as a reinforcement learning environment for inverse drug design | vendor_doc | README.md:16 |
| The README names step, reset, render, seed and close as the essential methods | vendor_doc | README.md:41-42 |
| The test constructs MoleculeEnvironment and asserts that it is a gym.Env | upstream_code | tests/environment_test.py:5-7 |
| environment.yml lists Python 3.7.7 with gym and rdkit | vendor_doc | environment.yml:7-15 |

Limits: the driver declares none. `cap.world.step.v1` bounds `ticks` to 1..10000 in the catalogue class; that class
bound is inherited by the binding (the driver does not restate or narrow it). The action object has no numeric bound
in the upstream: `action_c`, `pos` and `mol` are strings used as list operations and SMILES fragments. The device is
simulated (R0), so no limit is `operator_required`.

Capabilities: `cap.world.step.v1` and `cap.world.reset.v1` only. `cap.world.seed.v1` is not bound because the
upstream `seed(Smiles)` takes a SMILES start molecule, not an integer RNG seed; no faithful integer mapping exists.
The step contract's `action` object is documented as `{action_c, pos, mol}` because those are the three attributes
`MoleculeEnvironment.step` reads (`molecule_env.py:45-55`); this narrows the class's open action object without
changing its type. The reset contract takes the class's `options` object with an optional `smiles` member that is
passed to `MoleculeEnvironment.seed` (`molecule_env.py:77-79`), so a reset can start from a chosen SMILES; without it
the start is carbon.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `custom:gym_molecule-molecule-v0`, level F0 (a discrete
molecule-list editor with no dynamics or time step), determinism `none` with `seed_control` `none` (the environment
has no integer seed and no state snapshot), timestep 0 ms, `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled, including that the fake replaces RDKit with plain SMILES
string concatenation.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the molecule and tick stay readable.

Tags: molecule, drug-design, reinforcement-learning, simulation, smiles
