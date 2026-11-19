# Facts and scope for gh.rgalljamov/learn2walk

Facts cite the read-only source at commit `09d3bbd64a6b2fdd538b1d4465001bb1914243de`. The table matches the Fact declarations in driver.py and the generated reference.json.

| Fact | Source | Ref |
|---|---|---|
| MimicWalker3dEnv is a concrete subclass of MimicEnv | upstream_code | `mujoco/gym_mimic_envs/mujoco/mimic_walker3d.py:31` |
| MimicEnv is a subclass of gym's MujocoEnv and EzPickle | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:27` |
| MimicWalker3dEnv implements the base class hooks: COM indices [0, 1, 2], trunk rotation indices [3, 4, 5], the not-actuated joints [0, 1, 2, 3, 4, 5], and maximum actuator velocities [5, 1, 10, 10, 5, 1, 10, 10] | upstream_code | `mujoco/gym_mimic_envs/mujoco/mimic_walker3d.py:59-84` |
| The constructor reads the model file name from config_light.WALKER_MJC_XML_FILE, builds the mocap reference trajectories, joins the name below assets/, and calls MimicEnv.__init__ with the XML path and the reference object | upstream_code | `mujoco/gym_mimic_envs/mujoco/mimic_walker3d.py:37-47` |
| The configured model file name is walker3d_flat_feet_lowmass.xml | upstream_code | `scripts/config_light.py:28` |
| The reference trajectories are loaded from a hard-coded absolute assets path: /home/rustam/code/remote/ on remote machines and /mnt/88E4BD3EE4BD2EF6/... elsewhere; data paths are built from that root | upstream_code | `scripts/mocap/ref_trajecs.py:26-35` |
| MimicWalker3d-v0 is registered with entry point gym_mimic_envs.mujoco:MimicWalker3dEnv | upstream_code | `mujoco/gym_mimic_envs/__init__.py:8-10` |
| The gym_mimic_envs.mujoco package initializer imports MimicWalker2dEnv from mimic_walker2d, so importing the package entry point executes that import first | upstream_code | `mujoco/gym_mimic_envs/mujoco/__init__.py:1` |
| MimicEnv builds the simulation with MujocoEnv.__init__(xml_path, frame_skip), then sets the model timestep to 1 / SIM_FREQ and control_freq = SIM_FREQ / frame_skip, syncs the reference trajectories to that control frequency and overwrites actuator_forcerange with the configured torque ranges | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:53-63` |
| The simulation runs at SIM_FREQ = 1000 Hz and the control loop at CTRL_FREQ = 200 Hz | upstream_code | `scripts/config_light.py:30-32` |
| The configured peak joint torques are [50, 50, 50, 5] for hip_sag, hip_front, knee and ankle | upstream_code | `scripts/config_light.py:35-36` |
| get_torque_ranges repeats its four peak arguments for both sides into an 8 by 2 range | upstream_code | `scripts/common/config.py:29-33` |
| frame_skip is SIM_FREQ / CTRL_FREQ and must be an integer | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:184-189` |
| The MJCF model uses the RK4 integrator with timestep 0.001 s and defines the default motor ctrlrange as -300 to 300 | upstream_code | `mujoco/gym_mimic_envs/mujoco/assets/walker3d_flat_feet.xml:8-11` |
| The actuator list has eight motors: hip sagittal, hip frontal, knee and ankle, right then left | upstream_code | `mujoco/gym_mimic_envs/mujoco/assets/walker3d_flat_feet.xml:71-80` |
| MimicEnv.step rescales the action, mirrors it in a mirroring mode, calls do_simulation(action, frame_skip), advances the reference trajectories, builds the observation, computes the imitation reward, evaluates the terminal condition and returns (observation, reward, done, {}) | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:66-131` |
| In torque mode rescale_actions clips every policy action to [-1, 1] and scales it by PEAK_JOINT_TORQUES * 2 | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:155-164` |
| The constant-speed mocap dataset contains 35 steps of walking at 1.5 m/s sampled at 400 Hz | vendor_doc | `assets/ref_trajecs/mocaps_readme.md:3` |
| The observation is [phase, desired walking speed] + qpos[1:] + qvel; the 3D layout runs from index 0 (phase) and 1 (desired velocity) through 28 (left ankle velocity) | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:351-388` |
| The imitation reward uses weights from config.rew_weights for a sum of pose, velocity, COM and power rewards, or sqrt(pose) * sqrt(COM) in MOD_REW_MULT, and multiplies by rew_scale | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:540-559` |
| The reward weights string is '8200' outside MOD_FLY and '7300' in MOD_FLY; rew_scale is 1 and the alive bonus is 0.2 * rew_scale | upstream_code | `scripts/common/config.py:128-146` |
| The episode ends when the COM height is below 0.5, the episode duration reaches cfg.ep_dur_max or the walked distance exceeds cfg.max_distance + 0.01; outside evaluation it also ends on early termination | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:109-124` |
| The configured maximum episode length is 3000 steps and the maximum walking distance is 10 | upstream_code | `scripts/config_light.py:8-10` |
| Early termination thresholds are COM height below 0.75, sagittal trunk angle above 0.3 or below -0.05, frontal deviation above 0.2, axial deviation above 0.5 and absolute lateral COM position above 0.2; MOD_FLY disables the COM-height condition | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:583-610` |
| reset_model calls get_init_state, applies qpos/qvel, subtracts the lowest foot-site z from COM z, checks reward > 0.95 * rew_scale outside MOD_FLY, advances the reference trajectories and returns the observation | upstream_code | `mujoco/gym_mimic_envs/mimic_env.py:440-473` |
| README.md names mimic_walker3d.py as the main environment used to train walking policies and walker3d_flat_feet.xml as the model that defines the morphology and inertial properties | vendor_doc | `README.md:36-40` |

## Served contract and limits

Only the fake MimicWalker3d environment is served, through GymnasiumDriver over the legacy Gym interface. The
card still names MujocoDriver; a family override is proposed in the model decision. The configured lowmass XML,
the imported mimic_walker2d module and the loader's project-relative data route are unavailable at the pin.
No upstream construction, simulator execution or hardware execution was performed.

The fake's eight-component [-300, 300] envelope is placeholder data borrowed from the available
walker3d_flat_feet.xml. That XML is not the configured lowmass model. There is no action_space_ref and the
generated limit has no upstream source: it identifies the fake backend. The torque-mode policy clip [-1, 1] is a
separate operation in mimic_env.py:155-164, not proof of the missing model's action space.

## Fidelity and safety

The fake is analytic F0, seeded and lockstep at a derived 5 ms control period (1000 Hz / 200 Hz). Its gait,
constant desired speed, state transitions and terminal rewards are placeholders; no reference trajectory was
compared. Legacy reset() takes no keyword arguments; the bridge's keyword call falls back to seed(seed), then
reset(). The upstream inherited Gym implementation is outside this clone. Rendering, contacts, dynamics and
snapshot/restore are not modelled. The software latch freezes this fake after in-flight work settles and refuses
step, reset and seed until a safety reset; the state remains readable. No native or physical stop is claimed.

The card records NOASSERTION and publish_review: required. Publication requires an owner licence decision.

Tags: biped, walking, humanoid, mujoco, gym, reinforcement-learning, simulation
