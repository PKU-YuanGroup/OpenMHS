# Facts and tags for gh.farama-foundation/mo-gymnasium

Every fact cites its source at commit `8d280fdc3f517b18090619806843c03f51d775af`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

This package covers one of the card's five entry symbols, the FishWood environment. The other four are not covered:
`BreakableBottles` (`mo_gymnasium/envs/breakable_bottles/breakable_bottles.py:12`), `MOContinuousMountainCar`
(`mo_gymnasium/envs/continuous_mountain_car/continuous_mountain_car.py:12`), `DeepSeaTreasure`
(`mo_gymnasium/envs/deep_sea_treasure/deep_sea_treasure.py:89`) and `FourRoom`
(`mo_gymnasium/envs/four_room/four_room.py:34`).

| fact | source | ref |
|---|---|---|
| MO-Gymnasium follows the Gymnasium API but returns vectorized rewards as numpy arrays | vendor_doc | README.md:13 |
| fishwood-v0 is registered with the entry point mo_gymnasium.envs.fishwood.fishwood:FishWood and no max_episode_steps wrapper | upstream_code | mo_gymnasium/envs/fishwood/__init__.py:4-7 |
| The observation space is Box(low=0, high=1, shape=(1,), dtype=int32) and has two states: 0 fishing and 1 in the woods | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:15-18 |
| The action space is Discrete(2): 0 go fishing and 1 go collect wood | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:20-23 |
| The reward is 2-dimensional with one objective per resource | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:25-28 |
| The state constants are FISH 0, WOOD 1 and MAX_TS 200 | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:45-47 |
| The constructor defaults fishproba to 0.1 and woodproba to 0.9 | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:49 |
| The action space is spaces.Discrete(2) | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:56 |
| The observation space is spaces.Box(low=0, high=1, shape=(1,), dtype=int32) | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:58 |
| The reward space is spaces.Box(low=[0, 0], high=[1.0, 1.0], dtype=float32) and reward_dim is 2 | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:60-61 |
| The fisherman starts in the woods: _state is WOOD and reset restores that state with timestep 0 | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:63-69 |
| reset calls super().reset(seed=seed), so the seed arms the environment's np_random generator | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:65-66 |
| step draws a Bernoulli reward for the state the fisherman is leaving: woodproba pays the wood objective and fishproba pays the fish objective | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:84-89 |
| step sets the state to [action] and increments the timestep | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:91-93 |
| The episode returns terminated and truncated when the timestep equals MAX_TS | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:97 |
| The episode ends after MAX_TS = 200 steps | upstream_code | mo_gymnasium/envs/fishwood/fishwood.py:33-34 |
| mo_gymnasium.make disables the gymnasium env checker because it requires the reward to be a scalar | upstream_code | mo_gymnasium/utils.py:21-22 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(2)`: `action.index` from 0 to 1, with the source `upstream_code` and the ref
`mo_gymnasium/envs/fishwood/fishwood.py:56`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated
(R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:fishwood-v0`, level F0 (two states, a direct
transition and a Bernoulli reward per step, with no forces, contacts or continuous time), determinism `seeded` with
`seed_control` `parameter` (the reset arms the generator, so a seed repeats a reward sequence), `timestep_ms` 0
(turn-based: one tick is one action), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.
The gaps say what is not modelled, including that the 2-objective reward vector of MO-Gymnasium is not carried by
`cap.world.step.v1` (the fake returns the sum of the one-hot objectives as the scalar reward and keeps the full
`[fish, wood]` vector in `info.objectives`).

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: fishwood, multi-objective, two-state, reinforcement-learning, simulation, gymnasium
