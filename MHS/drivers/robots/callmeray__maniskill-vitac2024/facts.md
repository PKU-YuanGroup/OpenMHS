# Facts and tags for gh.callmeray/maniskill-vitac2024

Every fact cites its source at commit `114035d58c693dba00ff616fef6e67e1fe62a1f1`: `upstream_code` is code or a
comment of the clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated
from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ContinuousInsertionRandomizedMarkerEnv-v1 is registered with the entry point envs.peg_insertion:ContinuousInsertionSimGymRandomizedPointFLowEnv | upstream_code | envs/__init__.py:3-6 |
| The environment base class ContinuousInsertionSimEnv derives from gymnasium's gym.Env | upstream_code | envs/peg_insertion.py:67 |
| The action space is Box(low=-1, high=1, shape=(3,), dtype=np.float32), a three-element action | upstream_code | envs/peg_insertion.py:129 |
| The constructor requires step_penalty, final_reward and max_action; max_steps defaults to 15 | upstream_code | envs/peg_insertion.py:70-73 |
| step increments the episode counter, multiplies the action by max_action, and returns observation, reward, terminated, truncated and info | upstream_code | envs/peg_insertion.py:624-633 |
| The action is clipped to +-max_action; its in-plane components are rotated by the current offset angle and added to the x and y offset, and its third component is added to the theta offset | upstream_code | envs/peg_insertion.py:493-501 |
| The error-too-large thresholds are 12 on the x offset, 12 on the y offset and 15 on the theta offset, compared with a 1e-5 tolerance | upstream_code | envs/peg_insertion.py:506-509 |
| The reward is the decrease of the evaluated offset error minus step_penalty; an error-too-large step adds -2*step_penalty*(max_steps-steps)+step_penalty and a success adds final_reward | upstream_code | envs/peg_insertion.py:704-715 |
| The episode truncates when the elapsed steps reach max_steps and terminates on error_too_large or is_success | upstream_code | envs/peg_insertion.py:717-721 |
| The registered class's default observation holds gt_offset (three float32 values) and marker_flow of shape (2, 2, 128, 2) float32; render_rgb defaults to False | upstream_code | envs/peg_insertion.py:740-788 |
| reset accepts offset, seed and peg_idx and returns the observation with an empty info dictionary | upstream_code | envs/peg_insertion.py:467-490 |
| seed() sets numpy's global random generator with np.random.seed | upstream_code | envs/peg_insertion.py:192-195 |
| The registered subclass reads kwargs['params'].tac_sensor_meta_file before the superclass constructor, so a params object is mandatory | upstream_code | envs/peg_insertion.py:763 |
| The upstream training configuration sets step_penalty 1, final_reward 10, max_action [2.0, 2.0, 4.0] and max_steps 8 for this environment | upstream_code | configs/parameters/peg_insertion.yaml:3-6 |
| The training script creates the environment with gym.make(env_name, device=wp_device, **env_args), so the constructor arguments come from the caller | upstream_code | scripts/universal_training_script.py:42 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(low=-1, high=1, shape=(3,))`: `action.values` from -1 to 1 per element, `envs/peg_insertion.py:129`), and
`ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:vitac-peg-insertion-fake`, level F0 (the fake is
kinematic; no dynamics and no contact model), determinism `seeded` with `seed_control` `parameter` (the fake honors
`reset(seed)`, while the upstream reset does not call `seed()`), `timestep_ms` 0 (one tick is one environment step, not
a fixed physics interval), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps name
the upstream SAPIEN/IPC simulation that was not run, the zero marker flow, the placeholder constants and the
construction problem of `gymnasium.make(env_id)`.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the fake declares no native stop); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: gymnasium, sapien, tactile, peg-insertion, reinforcement-learning, simulation
