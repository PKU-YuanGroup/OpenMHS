# Facts and tags for gh.chuanyune/maniskill-vitac2025

Every fact cites the upstream clone at commit `a3d7df54bca9a2e57f34b37be3a3df36dc218915`. The same facts are written
into `driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Track 1 registers PegInsertionRandomizedMarkerEnv-v1 with entry_point envs.peg_insertion:PegInsertionSimMarkerFLowEnv | upstream_code | Track_1/envs/__init__.py:3-6 |
| PegInsertionSimMarkerFLowEnv extends PegInsertionSimEnv | upstream_code | Track_1/envs/peg_insertion.py:1138 |
| The action space is Box(low=-1, high=1, shape=(3,), dtype=float32) | upstream_code | Track_1/envs/peg_insertion.py:294-296 |
| A step scales the action by max_action_mm_deg and applies it with _sim_step | upstream_code | Track_1/envs/peg_insertion.py:796-798 |
| step returns (observation, reward, terminated, truncated, info) | upstream_code | Track_1/envs/peg_insertion.py:809 |
| reset accepts offset_mm_deg, seed, peg_idx and options and returns (observation, info) | upstream_code | Track_1/envs/peg_insertion.py:335-337 |
| The separate seed(seed) method calls numpy.random.seed | upstream_code | Track_1/envs/peg_insertion.py:300-303 |
| The default observation holds relative_motion of four floats and gt_offset of three floats | upstream_code | Track_1/envs/peg_insertion.py:328-332 |
| The marker-flow subclass replaces surface_pts with marker_flow of shape (2, 2, 128, 2) and rebuilds observation_space from that default observation | upstream_code | Track_1/envs/peg_insertion.py:1181-1198 |
| get_obs drops surface_pts and adds marker_flow from the two tactile sensors | upstream_code | Track_1/envs/peg_insertion.py:1289-1297 |
| When render_rgb is true the observation also carries rgb_images shaped (2, 240, 320, 3) | upstream_code | Track_1/envs/peg_insertion.py:1189-1196 |
| The tactile movement flag is set when the mean surface difference exceeds 1.5e-3 m | upstream_code | Track_1/envs/peg_insertion.py:949-951 |
| The error flag is set when the x or y offset exceeds 12 mm or the theta offset exceeds 15 degrees | upstream_code | Track_1/envs/peg_insertion.py:957-966 |
| Success requires no error, no step limit, no tactile movement flag, steps times z_step_size_mm above 0.35, and every peg bottom point more than 0.3 mm below the hole surface | upstream_code | Track_1/envs/peg_insertion.py:970-978 |
| The episode truncates when too_many_steps, tactile_movement_too_large or error_too_large is set | upstream_code | Track_1/envs/peg_insertion.py:1083-1087 |
| The reward subtracts step_penalty, adds final_reward on success and adds a remaining-steps penalty when the episode is truncated by error or tactile movement | upstream_code | Track_1/envs/peg_insertion.py:1049-1063 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1, 1, (3,))`: `action.values` is bounded element by element, source `upstream_code`, ref
`Track_1/envs/peg_insertion.py:294-296`), and `ticks` (1 to `max_ticks`, 10000 by default). The fake's
action space copies the upstream `Box` at `Track_1/envs/peg_insertion.py:294-296`; no number from `fake.py` is used
as a fact or a limit. The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:PegInsertionRandomizedMarkerEnv-v1`, level F0
(kinematic: no dynamics, no contacts and no tactile sensor model), determinism `seeded` with `seed_control`
`parameter`, timestep 0 ms (one tick is one insertion step and no simulated time is advanced), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say the fake is not the upstream SAPIEN/IPC
simulator, that marker flow and optional RGB images are not modelled, that upstream reset ignores its seed, and that
nothing was compared with an upstream run or a physical device.

Episode policy (`driver.py`, `autoreset = True`): a step after a terminal or truncated state starts a new full
episode through the bridge. The upstream `gymnasium.Env` returns the terminal flags and leaves the next reset to the
caller; the package serves the world this way so a long-running client can keep stepping. This is a serving choice,
not an upstream fact, and the fidelity gaps repeat it.

Safety: simulated R0 device. The e-stop is the runtime's software latch; the upstream class has no native stop, so
nothing is claimed to be called. After an e-stop the runtime refuses step and reset until `mhs.safety.reset` clears
the latch, and the world state stays readable. No hardware backend exists and no hardware run was made.

Tags: manipulation, peg-insertion, tactile, vision, reinforcement-learning, simulation, gymnasium, sapien

Other entry symbols of the card are not served by this one package (one package serves one device class): Track 1
`LongOpenLockRandPointFlowEnv` at `Track_1/envs/long_open_lock.py:990`, Track 2 `PegInsertionSimMarkerFLowEnvV2` at
`Track_2/envs/peg_insertion_v2.py:1206`, and Track 3 `PegInsertionSimMarkerFLowEnv` at
`Track_3/envs/peg_insertion.py:1137`. This package serves the first confirmed symbol, Track 1
`PegInsertionSimMarkerFLowEnv` at `Track_1/envs/peg_insertion.py:1138`, registered as
`PegInsertionRandomizedMarkerEnv-v1`.
