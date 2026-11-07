# Facts and tags for gh.chemgymrl/chemgymrl

Every fact cites its source at commit `ab8227b6b33f13617b7e551bdf6b894df7eec68d`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| GenWurtzExtract-v2 is registered with entry point chemistrylab.benches.extract_bench:GeneralWurtzExtract_v2 | upstream_code | chemistrylab/__init__.py:15-18 |
| The registration passes only id and entry_point: there is no max_episode_steps wrapper, so the environment's own max_steps is the only step bound | upstream_code | chemistrylab/__init__.py:15-18 |
| GenBench defaults max_steps to 50 | upstream_code | chemistrylab/benches/general_bench.py:68 |
| The episode ends when the selected Action is terminal or the step counter reaches max_steps | upstream_code | chemistrylab/benches/general_bench.py:213 |
| GenBench counts n_actions as one action per parameter row of every Action | upstream_code | chemistrylab/benches/general_bench.py:85 |
| GenBench builds a discrete action space as gym.spaces.Discrete(self.n_actions) | upstream_code | chemistrylab/benches/general_bench.py:99 |
| GeneralWurtzExtract_v2 has nine Action entries and its amounts parameters hold five rows each; the last Action holds one row, so the flattened list has 41 discrete actions | upstream_code | chemistrylab/benches/extract_bench.py:166-179 |
| A discrete action is an index into the flattened (Action, parameter row) list, not into the nine Action entries | upstream_code | chemistrylab/benches/general_bench.py:229 |
| The last parameter row of GeneralWurtzExtract_v2 is terminal | upstream_code | chemistrylab/benches/extract_bench.py:178 |
| The extraction bench's shelf has three working vessels | upstream_code | chemistrylab/benches/extract_bench.py:165 |
| GeneralWurtzExtract_v2 observes layers and targets | upstream_code | chemistrylab/benches/extract_bench.py:186 |
| CharacterizationBench measures 100 layer values per vessel and a target vector whose length is the number of targets | upstream_code | chemistrylab/benches/characterization_bench.py:66-70 |
| encode_target returns a one-hot vector over the targets | upstream_code | chemistrylab/benches/characterization_bench.py:177-186 |
| The chloro-wurtz reaction file lists seven products | upstream_code | chemistrylab/reactions/available_reactions/chloro_wurtz.json:9-16 |
| GeneralWurtzExtract_v2 loads the chloro-wurtz PRODUCTS as its targets | upstream_code | chemistrylab/benches/extract_bench.py:181 |
| The observation space is gym.spaces.Box(0, 1, observation_shape, dtype=np.float32) | upstream_code | chemistrylab/benches/general_bench.py:90 |
| reset accepts seed and options, reseeds numpy's global generator and the action space, draws a target uniformly from targets, and returns (observation, {}) | upstream_code | chemistrylab/benches/general_bench.py:235-240 |
| step applies the selected action, advances every working vessel and returns (state, reward, done, False, {}) | upstream_code | chemistrylab/benches/general_bench.py:201-222 |
| Most actions advance a vessel by dt=0.01 s; the two solvent pours and the final mixing action use dt=0 and the final Action is terminal | upstream_code | chemistrylab/benches/extract_bench.py:169-178 |
| The bench metadata declares rgb_array rendering at 10 frames per second | upstream_code | chemistrylab/benches/extract_bench.py:152-155 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the fake
environment's `Discrete(41)` (`action.index` from 0 to 40, with no source and the ref
`action_space of the fake backend .fake:FakeGeneralWurtzExtract`) and `ticks` (1 to `max_ticks`, 10000 by default).
The device is simulated (R0), so no limit is `operator_required`.

Observation size: `CharacterizationBench` gives 100 layer values and a seven-element target one-hot per vessel for
three working vessels, so the flat observation has `3 * (100 + 7) = 321` values. The fake returns the full
321-value shape; its values are placeholder data, not chemistry.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:GenWurtzExtract-v2`, level F0 (a stand-in that
models state transitions directly, not the chemistry), determinism `seeded` with `seed_control` `parameter`,
`timestep_ms` 0 because the environment is event-driven (each Action carries its own dt), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and that the fake was not
compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: chemistry, extraction, reinforcement-learning, simulation, gymnasium
