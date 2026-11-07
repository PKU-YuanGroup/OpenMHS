# Facts and tags for gh.qlan3/gym-games

Every fact cites its source at commit `0220815982456a20f02887b20a7d9a5fbeeedd55`: `upstream_code` is a code or
comment line of the clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| NChainEnv is a chain of n states and the agent always starts in state s2 | upstream_code | gym_exploration/envs/nchain.py:9-10 |
| In state s1 the reward is 0.001 and in state sN it is 1 | upstream_code | gym_exploration/envs/nchain.py:12 |
| The action space is Discrete(2): the integer actions 0 and 1 | upstream_code | gym_exploration/envs/nchain.py:17 |
| Action 1 moves right (the state is incremented) and any other action moves left (the state is decremented); the state stays at the ends of the chain | upstream_code | gym_exploration/envs/nchain.py:49-54 |
| The reward is computed from the state before the transition | upstream_code | gym_exploration/envs/nchain.py:48 |
| The reward is 1.0 when the state is n-1 and the action is 1, 0.001 when the state is 0 and the action is 0, and 0 otherwise | upstream_code | gym_exploration/envs/nchain.py:36-42 |
| The observation is the vector (v <= state), as uint8: 1 for the states up to and including the current state and 0 for the rest | upstream_code | gym_exploration/envs/nchain.py:25-26 |
| The observation is evaluated over v = arange(n) in reset and step | upstream_code | gym_exploration/envs/nchain.py:31 |
| The observation space is Box(low=0, high=1, shape=(n,), dtype=uint8) | upstream_code | gym_exploration/envs/nchain.py:22 |
| The step limit is max_steps = n + 8 | upstream_code | gym_exploration/envs/nchain.py:23 |
| The episode terminates when the step counter reaches max_steps | upstream_code | gym_exploration/envs/nchain.py:55-59 |
| A reset sets the state to 1 and the step counter to 0 and returns the initial observation | upstream_code | gym_exploration/envs/nchain.py:28-34 |
| reset calls super().reset(seed=seed) to seed np_random; NChainEnv draws no random numbers, so the seed changes nothing in the chain | upstream_code | gym_exploration/envs/nchain.py:29-30 |
| NChain-v1 is registered with entry_point gym_exploration.envs:NChainEnv | upstream_code | gym_exploration/__init__.py:9-12 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the
environment (`Discrete(2)`: `action.index` from 0 to 1, with the source `upstream_code` and the ref
`gym_exploration/envs/nchain.py:17`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated
(R0), so no limit is `operator_required`.

Fidelity contract (`driver.py` `fidelity_level = "F0"` and `fidelity = {"gaps": [...]}`): the bridge derives
engine `gymnasium:NChain-v1`, determinism `seeded` with `seed_control` `parameter`, timestep 0 (a tick is one
discrete transition; NChainEnv has no `dt`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled, that the fake was not compared with the upstream environment, and
that the bridge auto-resets after a terminal step (`autoreset = True`; the upstream class does not auto-reset).

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: nchain, exploration, reinforcement-learning, simulation, gymnasium
