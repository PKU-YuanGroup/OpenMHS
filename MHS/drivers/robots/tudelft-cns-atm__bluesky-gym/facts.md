# Facts and tags for gh.tudelft-cns-atm/bluesky-gym

Every fact cites its source at commit `8d7d79c63a3dab5de0e7bd8c2afb74737377f2e5`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DescentEnv-v0 is registered with entry point bluesky_gym.envs.descent_env:DescentEnv and max_episode_steps=300 | upstream_code | bluesky_gym/__init__.py:6-10 |
| DescentEnv is a gymnasium.Env subclass | upstream_code | bluesky_gym/envs/descent_env.py:31 |
| The action space is a Box from -1 to 1 with shape (1,) | upstream_code | bluesky_gym/envs/descent_env.py:61 |
| The observation space is a Dict of altitude, vz, target_altitude and runway_distance, each a Box from -inf to +inf | upstream_code | bluesky_gym/envs/descent_env.py:52-59 |
| ACTION_2_MS is 12.5 | upstream_code | bluesky_gym/envs/descent_env.py:17 |
| _get_action multiplies the action by ACTION_2_MS and its comment says the result is metres per second | upstream_code | bluesky_gym/envs/descent_env.py:145-147 |
| A non-negative action sets the target altitude to 1000000 (a climb command) and a negative action sets it to 0 (a descent command) before setting the selected vertical speed | upstream_code | bluesky_gym/envs/descent_env.py:154-159 |
| The environment sends BlueSky the stack command 'DT 1;FF' | upstream_code | bluesky_gym/envs/descent_env.py:71 |
| ACTION_FREQUENCY is 30 | upstream_code | bluesky_gym/envs/descent_env.py:29 |
| step calls bs.sim.step() ACTION_FREQUENCY times before it reads the observation | upstream_code | bluesky_gym/envs/descent_env.py:187-194 |
| A reset draws the initial altitude with np.random.randint(ALT_MIN, ALT_MAX) and the target altitude as that altitude plus np.random.randint(-TARGET_ALT_DIF, TARGET_ALT_DIF) | upstream_code | bluesky_gym/envs/descent_env.py:169-170 |
| ALT_MIN is 2000, ALT_MAX is 4000 and TARGET_ALT_DIF is 500 | upstream_code | bluesky_gym/envs/descent_env.py:23-25 |
| A reset creates KL001 as an A320 at the drawn altitude with speed AC_SPD and switches VNAV off | upstream_code | bluesky_gym/envs/descent_env.py:172-173 |
| AC_SPD is 150 | upstream_code | bluesky_gym/envs/descent_env.py:27 |
| The observation normalisation constants are ALT_MEAN 1500, ALT_STD 3000, VZ_MEAN 0, VZ_STD 5, RWY_DIS_MEAN 100 and RWY_DIS_STD 200 | upstream_code | bluesky_gym/envs/descent_env.py:10-15 |
| The observation divides (altitude - ALT_MEAN) by ALT_STD, (vz - VZ_MEAN) by VZ_STD, (target_altitude - ALT_MEAN) by ALT_STD and (runway_distance - RWY_DIS_MEAN) by RWY_DIS_STD | upstream_code | bluesky_gym/envs/descent_env.py:104-107 |
| runway_distance is DEFAULT_RWY_DIS (200) minus the great-circle distance from 52N 4E to the aircraft times NM2KM (1.852) | upstream_code | bluesky_gym/envs/descent_env.py:94-101 |
| The reward is abs(target_altitude - altitude) * ALT_DIF_REWARD_SCALE while the runway is ahead and the altitude is positive, CRASH_PENALTY when the altitude is zero or below, and altitude * RWY_ALT_DIF_REWARD_SCALE when the runway is reached | upstream_code | bluesky_gym/envs/descent_env.py:127-143 |
| ALT_DIF_REWARD_SCALE is -5/3000, CRASH_PENALTY is -100 and RWY_ALT_DIF_REWARD_SCALE is -50/3000 | upstream_code | bluesky_gym/envs/descent_env.py:19-21 |
| A terminated step deletes every aircraft from the BlueSky traffic | upstream_code | bluesky_gym/envs/descent_env.py:200-203 |
| close sends 'quit' to the BlueSky stack | upstream_code | bluesky_gym/envs/descent_env.py:276-277 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the fake
environment (`Box(-1, 1, (1,))`: `action.values` from -1 to 1, with no source and the ref
`action_space of the fake backend .fake:FakeDescentEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `bluesky:DescentEnv-v0`, level F0 (an analytic aircraft
motion with no force, contact, actuator, sensor or noise model), determinism `seeded` with `seed_control`
`parameter`, timestep 30000 ms per tick (`ACTION_FREQUENCY` 30 BlueSky steps at the `DT 1` setting,
`descent_env.py:29` and `:71`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps record the fake's placeholder runway geometry and the differences from BlueSky and from numpy's random stream.

Safety: simulated R0 device. An e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No hardware run was made and the model is unreviewed.

Tags: air-traffic-management, bluesky, descent, vertical-control, reinforcement-learning, simulation, gymnasium
