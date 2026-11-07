# Facts and tags for gh.sofadefrost/sofagym

Every fact cites its source at commit `f5ad4e44a0dc522d8018c184245b7aa630292118`: `upstream_code` is a line of the
clone and `vendor_doc` is a text file of the clone. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SofaGym registers 'trunk-v0' with entry point 'sofagym.envs:TrunkEnv' | upstream_code | sofagym/envs/__init__.py:64-67 |
| TrunkEnv.DEFAULT_CONFIG sets scene Trunk, deterministic True, goal True, the goalList positions [40, 40, 100] and [-10, 20, 80], scale_factor 5, timer_limit 250, discrete True, dt 0.01, nb_actions 16, dim_state 66 and randomize_states False | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:33-59 |
| TrunkEnv sets the wrapped environment's action_space to spaces.Discrete(nb_actions) | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:72 |
| TrunkEnv sets the wrapped environment's observation_space to a Box with low -1 and high 1 and dim_state elements | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:75-77 |
| TrunkEnv constructs an AbstractEnv (or a ServerEnv when use_server is set) and keeps it in self.env | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:65 |
| TrunkEnv defines __getattr__ and forwards any missing attribute to its wrapped environment | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:82-85 |
| TrunkEnv.reset calls initialize_states, init_goal and the wrapped environment's reset, then returns the state array | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:87-101 |
| AbstractEnv.step returns the legacy four-tuple obs, reward, done, info | upstream_code | sofagym/AbstractEnv.py:324-367 |
| AbstractEnv.step calls step_simulation once per environment step | upstream_code | sofagym/AbstractEnv.py:351 |
| step_simulation applies the action and then runs scale_factor simulation steps of dt seconds each | upstream_code | sofagym/AbstractEnv.py:544-548 |
| The default trunk configuration sets scale_factor 5 and dt 0.01 s, so one environment step advances 0.05 s of simulated time | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:40-53 |
| action_to_command maps actions 0-7 to cables 0-7 with displacement +1 and actions 8-15 to cables 0-7 with displacement -1, and raises NotImplementedError for any other action | upstream_code | sofagym/envs/Trunk/TrunkToolbox.py:331-378 |
| The trunk prefab is documented as actuated with 8 cables | upstream_code | sofagym/envs/Trunk/TrunkScene.py:42 |
| The trunk scene creates four large cables and four small cables in self.cables; each large cable has 21 positions (a pull point plus the 20 points of the loop) and each small one 11 (a pull point plus 10) | upstream_code | sofagym/envs/Trunk/TrunkScene.py:80-123 |
| getState reads the point count of the first cable, averages those points over the first four cables, rounds every coordinate to 3 decimals and divides it by 4, then appends the goal position | upstream_code | sofagym/envs/Trunk/TrunkToolbox.py:204-235 |
| The tip used by the reward is the mean of the last points of the first four cables | upstream_code | sofagym/envs/Trunk/TrunkToolbox.py:103-121 |
| The reward is min(sqrt(max((previous distance - current distance) / previous distance, 0)), 1.0) and the cost is the current tip-to-goal distance | upstream_code | sofagym/envs/Trunk/TrunkToolbox.py:77-82 |
| getReward returns done True when the tip-to-goal distance is at most 1.0 and False otherwise | upstream_code | sofagym/envs/Trunk/TrunkToolbox.py:238-257 |
| A reset draws a new goal from goalList with np_random.choice | upstream_code | sofagym/AbstractEnv.py:228-234 |
| seed() replaces np_random with seeding.np_random(seed) | upstream_code | sofagym/AbstractEnv.py:250 |
| AbstractEnv initializes np_random from config['seed'] in __init__ | upstream_code | sofagym/AbstractEnv.py:161-163 |
| AbstractEnv.step increments timer and sets a local truncated flag at timer_limit but returns the four-tuple without it, so the flag is discarded | upstream_code | sofagym/AbstractEnv.py:359-367 |
| The cable constraints set maxPositiveDisp 70 for the large cables and 40 for the small cables, with maxDispVariation 1 | upstream_code | sofagym/envs/Trunk/TrunkScene.py:98-121 |
| The trunk length is 195 and the four pull points sit at distance 10 from the axis | upstream_code | sofagym/envs/Trunk/TrunkScene.py:72-77 |
| TrunkEnv declares dim_state 66 | upstream_code | sofagym/envs/Trunk/TrunkEnv.py:32 |
| SofaGym needs a SOFA installation, currently supported version v23.06, with the mandatory SofaPython3 plugin and SoftRobots among the optional plugins | vendor_doc | README.md:12-20 |
| The README states SofaGym works with gym v0.21.0 | vendor_doc | README.md:29 |
| The documented loop is gym.make('trunk-v0'), env.seed(42), env.reset(), then env.step(action) returning observation, reward, done and info, and env.close() | vendor_doc | README.md:108-118 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(16)`: `action.index` from 0 to 15, with no source and the ref
`action_space of the fake backend .fake:FakeTrunkEnv`) plus `ticks` (1 to `max_ticks`, 10000 by default). The device is
simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `sofagym:trunk-v0`, level F1 (the scene's cable geometry
and the action/reward/observation rules, no finite-element deformation), determinism `seeded` with `seed_control`
`parameter`, timestep 50 ms (scale_factor 5 times dt 0.01 s, `TrunkEnv.py:40` and `:53`, applied in
`AbstractEnv.py:544-548`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say
what is not modelled, including that the fake's kinematic bend does not match SOFA's TetrahedronFEM solve and that the
clone discards its timer truncation.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No hardware backend exists and no hardware run is claimed.

Tags: soft-robotics, trunk, cable-actuated, reinforcement-learning, simulation, sofagym

License: the clone has no LICENSE file at its root and its README and setup.py state no license, so the card's
`NOASSERTION` / unknown class is recorded as it is; this package requires publish review and makes no license claim.
