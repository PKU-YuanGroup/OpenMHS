# Facts and tags for gh.neuracoreai/bigym

Every fact cites its source at commit `14beb30318ad14c5d6723175c2ee2281129792af`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DrawerTopOpen succeeds when the last normalized joint value of the base cabinet's drawer state is within TOLERANCE of 1 | upstream_code | bigym/envs/cupboards.py:34-38 |
| TOLERANCE is 0.1 | upstream_code | bigym/envs/cupboards.py:11 |
| The cupboard task base selects the counter_base_wall_3x1 preset and exposes its first BaseCabinet as cabinet_drawers | upstream_code | bigym/envs/cupboards.py:14-25 |
| The first BaseCabinet of that preset enables big drawer 1 and small drawers 3 and 4 | upstream_code | bigym/envs/presets/counter_base_wall_3x1.yaml:3-7 |
| BaseCabinet.get_state returns the normalized position of every joint of the cabinet body | upstream_code | bigym/envs/props/cabintets.py:21-28 |
| BiGymEnv is a Gymnasium environment whose default robot is H1 | upstream_code | bigym/bigym_env.py:34-48 |
| The control frequency is bounded to 20..500 Hz and the physics timestep is 0.002 s | upstream_code | bigym/bigym_env.py:25-28 |
| The control_frequency constructor parameter defaults to CONTROL_FREQUENCY_MAX | upstream_code | bigym/bigym_env.py:53-59 |
| The environment takes round(500/control_frequency) physics substeps per control call | upstream_code | bigym/bigym_env.py:95-98 |
| The action space is built by the configured action mode with action_scale equal to the substep count | upstream_code | bigym/bigym_env.py:106-108 |
| JointPositionActionMode builds a Box from the floating-base delta bounds, the limb control range and the gripper range | upstream_code | bigym/action_modes.py:208-232 |
| The H1 floating-base delta ranges are -0.01..0.01 for translation and -0.05..0.05 for rotation | upstream_code | bigym/robots/configs/h1.py:126-127 |
| The H1 limb delta action range is -0.1..0.1 | upstream_code | bigym/robots/configs/h1.py:145-147 |
| The Robotiq 2F85 gripper control range is 0..1 | upstream_code | bigym/robots/configs/robotiq.py:7-10 |
| The observation space is a Dict with proprioception and proprioception_grippers; a floating base adds floating-base position and accumulated-action arrays | upstream_code | bigym/bigym_env.py:252-288 |
| The default ObservationConfig has no cameras, proprioception on and privileged information off | upstream_code | bigym/utils/observation_config.py:49-55 |
| reset(seed, options) updates the seed, resets physics, action and robot, calls _on_reset and returns (observation, info) | upstream_code | bigym/bigym_env.py:392-406 |
| step rejects an action with a wrong shape or outside the action space before stepping | upstream_code | bigym/bigym_env.py:449-465 |
| step returns (observation, reward, terminated, truncated, info) | upstream_code | bigym/bigym_env.py:420-447 |
| terminate is success or fail and truncate is not is_healthy | upstream_code | bigym/bigym_env.py:163-171 |
| reward is success times SPARSE_REWARD_FACTOR | upstream_code | bigym/bigym_env.py:494-496 |
| fail is true when the pelvis position norm exceeds MAX_DISTANCE_FROM_ORIGIN | upstream_code | bigym/bigym_env.py:478-492 |
| MAX_DISTANCE_FROM_ORIGIN is 10 | upstream_code | bigym/bigym_env.py:30 |
| The cupboards reset robot position is [-0.2, 0, 0] | upstream_code | bigym/envs/cupboards.py:17 |
| The README says tasks are instantiated directly | vendor_doc | README.md:82 |

Limits: the driver declares none. The action-space bounds are derived by the Gymnasium bridge from the fake
backend's Box; because the fake is a stand-in and no single upstream line states all of its bounds, the driver does
not set `action_space_ref`, and the reference marks those limits with the fake's origin rather than a source. The
fake's 15 values are 3 floating-base deltas, 10 arm/wrist deltas and 2 Robotiq gripper values for the default
`JointPositionActionMode(floating_base=True, absolute=False)` configuration. The real space is built from the loaded
model and the constructor's action mode (`bigym/action_modes.py:208-232`), so its exact shape and bounds are a
deployment configuration, not a constant of the task class.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:bigym-DrawerTopOpen`, level F0 (analytic task
model; no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 2 ms (the default 500 Hz control
period and PHYSICS_DT 0.002 s at `bigym/bigym_env.py:25-28`), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore. The gaps say that the fake has no rigid-body dynamics, that its observation arrays are
shorter than upstream's, that the action space is a stand-in, that no upstream environment was run, and that
truncation and camera observations are not modelled.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and
the state stays readable.

Tags: bigym, cupboards, drawer, manipulation, mobile-manipulation, h1, mujoco, gymnasium, simulation
